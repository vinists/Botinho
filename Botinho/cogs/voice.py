from discord.ext import commands
import discord
import asyncio

import requests
from decouple import config

import time
import os

def getVoice(output):

    url = f"http://api.voicerss.org/?key={config('voice')}&hl=pt-br&v=Dinis&c=MP3&src={output}"
    r = requests.get(url, stream=True)
    path = f"temp/{str(time.time()).split('.')[0]}.mp3"
    with open(path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk:
                f.write(chunk)
    return path

def cleanTemp(fname):
    os.remove(fname)

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='voice', description='Toca audio text-to-speech')
    async def voice(self, ctx: commands.Context, content: str):
        
        path = getVoice(content)
        user = ctx.author
        channel = ctx.message.author.voice.channel

        if channel != None:
            vc = await channel.connect()
            player = vc.play(discord.FFmpegPCMAudio(path), after=lambda e: print('done', e))
            
            while vc.is_playing():
                await asyncio.sleep(1)

            vc.stop()
            await vc.disconnect()

            cleanTemp(path)
        else:
            await ctx.say('User is not in a channel.')
        

def setup(bot):
    bot.add_cog(Voice(bot))

if __name__ == "__main__":
    print(getVoice("Isto aqui é um teste."))