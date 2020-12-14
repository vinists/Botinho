from discord.ext import commands
import random as rd
import discord


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="moeda", aliases=["coin", "coinflip"])
    async def moeda(self, ctx):
        await ctx.send("cara" if rd.randint(0,1) == 1 else "coroa")

    @commands.command(name="add")
    async def add(self, ctx, left: int, right: int):
        await ctx.send(left + right)

    @commands.command(name="escolha", aliases=['choice'], description='Faça o bot escolher por você: !escolha [escolha A] [escolha B] [etc]')
    async def escolha(self, ctx, *args):
        await ctx.send(rd.choice(list(args)))

        
        


def setup(bot):
    bot.add_cog(General(bot))