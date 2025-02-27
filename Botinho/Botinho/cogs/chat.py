import asyncio

import discord.ext.commands
from discord.ext import commands

from Services import openai_client, redis_client
from Services.voice_chat_service import VoiceChat, get_voice_client, should_use_voice

import textwrap
import typing

from config import Settings, get_settings
settings: Settings = get_settings()


class Chat(commands.Cog):
    def __init__(self, bot: discord.ext.commands.AutoShardedBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author != self.bot.user and (self.bot.user.mentioned_in(message) or message.guild is None and message.content.startswith(settings.prefix) is not True):
            await message.channel.typing()

            message.content = message.content.replace(self.bot.user.mention, "")
            message.content = f"({message.author.display_name}) {message.content}"
            attachments_raw = message.attachments
            imgs = []
            for attachment in attachments_raw:
                imgs.append(str(attachment))

            vc = None
            voice_channel = None
            if message.guild:
                vc = get_voice_client(self.bot.voice_clients, message.guild.id)
                voice_channel = message.author.voice.channel if message.author.voice else None

            chat = openai_client.Chat(str(message.channel.id), voice_channel)
            response_generator = chat.send_message(message.content, imgs)

            async for response_raw in response_generator:
                if response_raw:
                    if len(response_raw) >= 2000:
                        response = textwrap.wrap(response_raw, 2000, replace_whitespace=False)
                    else:
                        response = [response_raw]

                    for chunk in response:
                        if message.guild:
                            await message.reply(chunk)
                        else:
                            await message.channel.send(chunk)

                    if should_use_voice(vc, voice_channel) and response_raw.startswith("[SYSTEM") is False:
                        audio_response = await openai_client.OpenAIGeneral.generate_text_to_speech(response_raw)
                        await redis_client.PubSub(str(message.channel.id)).publish(audio_response)

    @commands.hybrid_group(name="chat", fallback="tokens")
    async def chat(self, ctx):
        chat_data = await openai_client.Chat(ctx.channel.id).get_chat_data()

        if chat_data is not None:
            await ctx.send(f"Usando {chat_data.total_tokens} de 128000 tokens.\n"
                           f"Total absoluto de tokens resumidos: {chat_data.summarized_tokens}\n"
                           f"Quantidade de vezes que o chat foi resumido: {chat_data.times_summarized}")

    @chat.command(name="persona")
    async def custom_persona(self, ctx, temperature: typing.Optional[float] = 0.7, *, message: str = commands.clean_content):
        await openai_client.Chat(ctx.channel.id).set_custom_persona(temperature, message)
        await ctx.send("Personalidade setada!")

    @chat.command()
    async def clear(self, ctx):
        await openai_client.Chat(ctx.channel.id).clear_chat()
        await ctx.send("Chat limpo!")


async def setup(bot):
    await bot.add_cog(Chat(bot))
