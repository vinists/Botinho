from discord.ext import commands
import random as rd
import discord
import logging
import asyncio


logging.basicConfig(level=logging.INFO)

TOKEN = "Nzg1ODY2MjkzMTAyMjQ3OTM2.X8-FBA.iOd-Wjt0IK0UwckyD6j0b46HOsc"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.command()
async def add(ctx, left: int, right: int):
    await ctx.send(left + right)

@bot.command()
async def moeda(ctx):
    await ctx.send("cara" if rd.randint(0,1) == 1 else "coroa")


bot.run(TOKEN)
    
        


