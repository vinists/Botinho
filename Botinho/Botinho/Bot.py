from discord.ext import commands
import discord
import logging
import asyncio

from config import Settings, get_settings
settings: Settings = get_settings()

TOKEN = settings.discord_token


logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.AutoShardedBot(command_prefix=settings.prefix, intents=intents)

extensions_list = [
    'cogs.general',
    'cogs.voice',
    'cogs.music',
    'cogs.image',
    'cogs.chat'
]


async def main():
    async with bot:
        for extension in extensions_list:
            await bot.load_extension(extension)

        await bot.start(TOKEN)

asyncio.run(main())


    
        


