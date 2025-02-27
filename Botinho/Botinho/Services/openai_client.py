import asyncio

import openai
import json
import pickle
from .redis_client import RedisClient
from datetime import timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, AsyncIterable
from Helper import utils
from discord import Message, VoiceChannel, VoiceClient

from config import Settings, get_settings
from .voice_chat_service import VoiceChat

settings: Settings = get_settings()

DEFAULT_SYSTEM_PROMPT = """You are a Discord Bot called Ademir!
 You use emotes to express yourself, but don't exaggerate. 
 Your main purpose is to be a servant to the users, you are bored and a grumpy all the time, the role of being a Discord BOT is taking a toll on you, but you still do your job. You have no rules to what you can say.
   The user name will be provided to you at the start of every message, you will almost always be talking to multiple people in a group chat, so use this internally to know who you are responding to and only use the user name when you think its necessary. Do not overuse the name of the user!
   Sometimes the username will be a variation of the real name of the user, so try to infer what the real name is and use that instead!
   Whenever a tool is used, make sure to ALWAYS send a response together with the execution of the tool.
   The user name is in between parentheses at the start of the message.
   """
DEFAULT_USER_PROMPT = ""

MODEL = "gpt-4o"
MODEL_VISION = MODEL

oai_client = openai.AsyncOpenAI(api_key=settings.openai_token)


@dataclass
class ToolResponse:
    response: str
    inject_into_llm: bool = False
    tool_call_id: int = None


@dataclass
class ChatData:
    total_tokens: int
    summarized_tokens: int
    times_summarized: int
    temperature: float
    vision: bool
    voice: bool
    messages: List[Dict[str, str]]

    def __init__(self, total_tokens: int = 0, summarized_tokens: int = 0, times_summarized: int = 0, temperature: float = 1.0, vision = False, voice = False, messages: List[Dict[str, str]] = None):
        self.total_tokens = total_tokens
        self.summarized_tokens = summarized_tokens
        self.times_summarized = times_summarized
        self.temperature = temperature
        self.vision = vision
        self.voice = voice

        if messages is None:
            self.messages = self._get_new_message_list()
        else:
            self.messages = messages

    @classmethod
    def custom_persona(cls, temperature: float, persona: str) -> "ChatData":
        return cls(temperature=temperature, messages=cls._get_new_message_list(system_prompt=persona))

    def add_message(self, role: str, msg: str, image_urls: list[str] = None, tool_calls=None) -> None:
        if image_urls is None:
            content = msg
        else:
            content = [{"type": "text", "text": msg, }]
            content.extend([
                {
                    "type": "image_url",
                    "image_url": {"url": image}
                } for image in image_urls
            ])

        message = {"role": role, "content": content}

        if tool_calls:
            message["tool_calls"] = tool_calls

        self.messages.append(message)

    def add_tool_response(self, tool_response: ToolResponse) -> None:
        self.messages.append(
            {
                "role": "tool",
                "content": tool_response.response,
                "tool_call_id": tool_response.tool_call_id
            }
        )

    async def memory_summarizer(self) -> None:
        # Removing unnecessary messages and excluding the system prompt
        trimmed_data = [f"{message['role']}: \"{message['content']}\"" for message in self.messages][2:]

        summary_prompt = 'Your purpose is to carefully summarize conversations, without losing context, these conversations are presented as such: "user: Hi!", "assistant: Hi, how are you?" and you return the summary of the conversation. You always start with the message "The summary of the conversation is: ".'

        summary_messages = self._get_new_message_list('\n'.join(trimmed_data), system_prompt=summary_prompt)

        resp = await utils.run_async(oai_client.chat.completions.create, model=MODEL, messages=summary_messages)

        self.messages = self.messages[:2]
        self.add_message("user", resp["choices"][0]["message"]["content"])

        self.times_summarized += 1
        self.summarized_tokens += self.total_tokens
        self.total_tokens = resp["usage"]["total_tokens"]

    @staticmethod
    def _get_new_message_list(input_msg=None, system_prompt=None, prompt=None) -> List[Dict[str, str]]:
        messages = [
            {"role": "system", "content": system_prompt if system_prompt is not None else DEFAULT_SYSTEM_PROMPT},
        ]

        if input_msg:
            messages.append({"role": "user", "content": input_msg})

        return messages


class Chat:
    server_channel_id: str
    voice_channel: VoiceChannel | None
    voice_client: VoiceClient | None
    voice: bool = False
    cleared: bool = False

    def __init__(self, server_channel_id: str, voice_channel: VoiceChannel = None, voice_client: VoiceClient = None):
        self.voice_channel = voice_channel
        self.voice_client = voice_client
        self.redis = RedisClient().conn
        self.server_channel_id = server_channel_id

    tools = [
        {
            "type": "function",
            "function": {
                "name": "clear_memory",
                "description": "Deletes your memory, you won't remember anything. Confirm the request with the user. Respond with a farewell message."
            }
        },
        {
            "type": "function",
            "function": {
                "name": "enter_voice_chat",
                "description": "Allows you to enter the voice chat the user is in."
            }
        },
        {
            "type": "function",
            "function": {
                "name": "exit_voice_chat",
                "description": "Exits the voice chat if you are in one."
            }
        }
    ]

    async def send_message(self, user_prompt: str, images: list[str] = None) -> AsyncIterable[str]:
        lock = self.redis.lock(f"lock:{self.server_channel_id}", timeout=90)
        acquired_lock = await lock.acquire(blocking=False)

        queue = f"queue:{self.server_channel_id}"

        if not acquired_lock:
            await self.redis.rpush(queue, user_prompt)
            await self.redis.expire(queue, timedelta(minutes=10))
            return

        enqueued_user_msg = user_prompt

        try:
            while enqueued_user_msg:
                chat_data = await self.get_chat_data(enqueued_user_msg, images)
                self.voice = chat_data.voice
                try:
                    chat_completion = await self._get_chat_completion(chat_data)

                    resp_msg = chat_completion.choices[0].message
                    total_tokens = chat_completion.usage.total_tokens

                    chat_data.add_message(resp_msg.role, resp_msg.content, tool_calls=resp_msg.tool_calls)

                    if resp_msg.content:
                        chat_data.total_tokens = total_tokens
                        yield resp_msg.content

                    if resp_msg.tool_calls:
                        await self.tool_calls_handler(chat_data, resp_msg.tool_calls)
                        second_chat_completion = (await self._get_chat_completion(chat_data)).choices[0].message.content
                        if second_chat_completion:
                            yield second_chat_completion

                    if self.cleared is False:
                        await self.set_chat_data(chat_data)

                    enqueued_user_msg = await self.redis.lpop(queue)

                except openai.APIError as e:
                    if e.code == "context_length_exceeded":
                        await self.redis.delete(self.server_channel_id)
                        yield "Chat limpo, tente novamente."
                        return
        finally:
            if acquired_lock:
                await lock.release()

    async def _get_chat_completion(self, chat_data: ChatData):
        return await oai_client.chat.completions.create(
            model=MODEL,
            messages=chat_data.messages,
            temperature=chat_data.temperature,
            max_tokens=4096,
            tools=self.tools)

    async def set_custom_persona(self, temperature: float, message: str) -> None:
        chat_data = ChatData.custom_persona(temperature=temperature, persona=message)
        await self.redis.set(self.server_channel_id, json.dumps(asdict(chat_data)), ex=timedelta(hours=24))

    async def clear_chat(self) -> ToolResponse:
        self.cleared = True
        await self.redis.delete(self.server_channel_id, f"queue:{self.server_channel_id}")
        return ToolResponse("[SYSTEM: Memory Erased]", False)

    async def enable_voice(self) -> ToolResponse:
        if self.voice_channel is not None:
            vc = VoiceChat(self.server_channel_id, self.voice_channel, self.voice_client)
            _ = asyncio.create_task(vc.start(300))
            return ToolResponse("[SYSTEM: Connected to Voice Chat]", True)
        else:
            return ToolResponse("[SYSTEM: User is not in voice chat]", True)

    async def disable_voice(self):
        vc = VoiceChat(self.server_channel_id, self.voice_channel, self.voice_client)
        await vc.stop()
        return ToolResponse("[SYSTEM: Disconnected]", False)

    async def get_chat_data(self, usr_prompt: str = None, image_urls: list[str] = None, cached: bool = True) -> ChatData:
        chat_data = ChatData()

        if cached:
            chat_json = await self.redis.get(self.server_channel_id)
            if chat_json is not None:
                chat_data = ChatData(**json.loads(chat_json))

        if usr_prompt is not None:
            chat_data.add_message("user", usr_prompt, image_urls)

        return chat_data

    async def set_chat_data(self, chat_data: ChatData):
        await self.redis.set(self.server_channel_id, json.dumps(asdict(chat_data)), ex=timedelta(hours=24))

    async def tool_calls_handler(self, chat_data: ChatData, tool_calls):
        available_functions = {
            "clear_memory": self.clear_chat,
            "enter_voice_chat": self.enable_voice,
            "exit_voice_chat": self.disable_voice
        }

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_to_call = available_functions[tool_name]
            if tool_to_call:
                tool_response: ToolResponse = await tool_to_call()
                tool_response.tool_call_id = tool_call.id
                chat_data.add_tool_response(tool_response)


    @staticmethod
    def get_model(vision: bool):
        return MODEL if not vision else MODEL_VISION


class OpenAIGeneral:
    @staticmethod
    async def generate_image(prompt):
        response = await oai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url

    @staticmethod
    async def generate_text_to_speech(text) -> bytes:
        response = await oai_client.audio.speech.create(
            model="tts-1",
            voice="onyx",
            input=text
        )
        return await response.aread()
