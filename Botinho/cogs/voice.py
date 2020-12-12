from discord.ext import commands
import discord
import asyncio

import time
import os

import requests
try:
    from decouple import config
    voicerssKey = config('voice')
except ImportError:
    voicerssKey = os.environ['voice']


vozesShow = "Dinis\nMarcia\nLigia\nYara\nLeonor"

def getVoice(output, voz="Dinis"):

    lang = "pt-pt" if voz == "Leonor" else "pt-br"
    url = f"http://api.voicerss.org/?key={voicerssKey}&hl={lang}&v={voz}&c=MP3&src={output}"   
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
        self.vozSelected = "Dinis"

    @commands.command(name="voz", aliases=["voice"], description='Comando para selecionar a voz ou listar as vozes disponíveis.')
    async def voiceList(self, ctx: commands.Context, cmd=None, voz=None):
        if cmd == "list":
            await ctx.send(vozesShow.replace(self.vozSelected, f"{self.vozSelected} - Selecionado"))
        elif cmd == "set":
            if voz and voz in vozesShow:
                self.vozSelected = voz
                await ctx.send("Voz alterada com sucesso para: " + self.vozSelected)
            else:
                await ctx.send("Erro, verifique se inseriu a voz certa (!vozes set [voz desejada]), "
                               +"use !voz list para listar as vozes disponíveis.")
        else:
            await ctx.send("Que? Usa-se assim: !voz [list ou set]. O comando para falar é \"!falar [frase (entre aspas)]\"")
                

    @commands.command(name='falar', aliases=["say", "dizer"],description='Toca audio text-to-speech')
    async def voice(self, ctx: commands.Context, *content):
        
        path = getVoice(" ".join(content), voz=self.vozSelected)
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