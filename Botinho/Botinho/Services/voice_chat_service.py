import asyncio
import io
import os

from discord import VoiceClient, VoiceChannel

from .redis_client import PubSub
from discord.ext import commands
import discord
import tempfile


def should_use_voice(vc, user_voice_channel):
    return vc and vc.channel == user_voice_channel and vc.is_connected() and not vc.is_playing()


def get_voice_client(voice_clients, guild_id):
    for voice_client in voice_clients:
        if voice_client.guild.id == guild_id:
            return voice_client


class VoiceChatManager:
    def __init__(self):
        self.voice_chats = {}

    def get_voice_chat(self, server_id, token, channel=None, client=None):
        if server_id not in self.voice_chats:
            self.voice_chats[server_id] = VoiceChat(token, channel, client)
        return self.voice_chats[server_id]

    async def remove_voice_chat(self, server_id):
        if server_id in self.voice_chats:
            await self.voice_chats[server_id].disconnect()
            del self.voice_chats[server_id]


class VoiceChat:
    token: str
    channel: VoiceChannel
    client: VoiceClient = None

    def __init__(self, token: str,  channel: VoiceChannel, client: VoiceClient = None):
        self.channel = channel
        self.client = client
        self.token = token
        self.queue = asyncio.Queue()
        self.pubsub = PubSub(token)
        self.temp_files = []

    def cleanup_temp_files(self):
        for path in self.temp_files:
            try:
                os.remove(path)
            except OSError:
                pass
        self.temp_files = []

    async def connect(self):
        if self.channel is not None and self.client is None:
            self.client = await self.channel.connect()
            return True

        return False

    async def disconnect(self):
        await self.pubsub.unsubscribe()

        if self.client:
            await self.client.disconnect(force=True)
            self.cleanup_temp_files()

    async def play_audio(self, audio: io.BytesIO):
        fd, path = tempfile.mkstemp()
        try:
            if self.client:
                with os.fdopen(fd, 'wb') as tmp:
                    tmp.write(audio.read())

                def after_playback(error):
                    if error:
                        print('An error occurred during playback:', error)

                    self.cleanup_temp_files()

                self.client.play(discord.FFmpegPCMAudio(path), after=after_playback)
            else:
                await self.disconnect()

        except Exception as e:
            print("An error occurred: ", e)
            await self.disconnect()

    async def enqueue_audio(self, audio_data: bytes):
        audio = io.BytesIO(audio_data)
        self.queue.put_nowait(audio)

    async def player(self):
        while True:
            audio_data = await self.queue.get()
            await self.play_audio(audio_data)
            await asyncio.sleep(1)

    async def subscribe(self, timeout: int):
        async for message in self.pubsub.subscribe(timeout):
            if type(message) is not str:
                await self.enqueue_audio(message["data"])

    async def start(self, timeout: int):
        if not self.client and await self.connect():
            player_task = asyncio.create_task(self.player())
            subscribe_task = asyncio.create_task(self.subscribe(timeout))

            try:
                await subscribe_task
            finally:
                player_task.cancel()
                await self.disconnect()
        else:
            return "[SYSTEM: User is not connected to a voice channel.]"

    async def stop(self):
        await self.pubsub.publish(self.pubsub.STOPWORD)

