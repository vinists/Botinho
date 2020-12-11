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
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.command()
async def add(ctx, left: int, right: int):
    await ctx.send(left + right)

@bot.command()
async def moeda(ctx):
    await ctx.send("cara" if rd.randint(0,1) == 1 else "coroa")


bot.run(TOKEN)
    
        


