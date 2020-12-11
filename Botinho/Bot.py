from discord.ext import commands
import random as rd
import discord
import logging
import os

# To run locally you need to install "python-decouple" with pip and create a .env file with the token.
try:
    from decouple import config
    TOKEN = config("token")
except ImportError:
    TOKEN = os.environ["token"]


logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()

bot = commands.AutoShardedBot(command_prefix="!", intents=intents)
bot.load_extension('cogs.general')


bot.run(TOKEN)
    
        


