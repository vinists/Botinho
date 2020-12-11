from discord.ext import commands
import random as rd
import discord
import logging
import os

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("token")
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.command()
async def add(ctx, left: int, right: int):
    await ctx.send(left + right)

@bot.command()
async def moeda(ctx):
    await ctx.send("cara" if rd.randint(0,1) == 1 else "coroa")


bot.run(TOKEN)
    
        


