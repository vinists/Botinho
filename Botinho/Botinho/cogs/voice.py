import os

from discord.ext import commands
import discord

from Helper import utils

import asyncio
import requests

from config import Settings, get_settings
settings: Settings = get_settings()

voicerssKey = settings.voice_token
ibmkey = settings.ibm_voice_token

voicesString = "Dinis\nMarcia\nLigia\nYara\nLeonor\nIsabela"


def getVoice(output, voz="Isabela"):
    if voz == "Isabela":
        from ibm_watson import TextToSpeechV1
        from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

        path = f"temp.mp3"
        voice = "pt-BR_IsabelaV3Voice"
        url = "https://api.us-south.text-to-speech.watson.cloud.ibm.com/"

        tts = TextToSpeechV1(authenticator=IAMAuthenticator(ibmkey))
        tts.set_service_url(url)
        r = tts.synthesize(output, accept="audio/mp3", voice=voice).get_result()
    else:

        lang = "pt-pt" if voz == "Leonor" else "pt-br"
        url = f"http://api.voicerss.org/?key={voicerssKey}&hl={lang}&v={voz}&c=MP3&src={output}&f=12khz_16bit_stereo"   
        r = requests.get(url, stream=True)
    
    path = utils.get_epoch_filename("mp3")

    if r.status_code == 200:
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
    else:
        return None
    return path

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vozSelected = "Isabela"

    @commands.command(name="voz", aliases=["voice"], description='Comando para selecionar a voz ou listar as vozes disponíveis.')
    async def voiceList(self, ctx: commands.Context, cmd=None, voz=None):
        if cmd == "list":
            await ctx.send(voicesString.replace(self.vozSelected, f"{self.vozSelected} - Selecionado"))
        elif cmd == "set":
            if voz:
                voz = voz.replace(voz[0], voz[0].upper())
                if voz in voicesString:
                    self.vozSelected = voz
                    await ctx.send("Voz alterada com sucesso para: " + self.vozSelected)
                else:
                    await ctx.send("Erro, verifique se inseriu a voz certa (!vozes set [voz desejada]), "
                                +"use !voz list para listar as vozes disponíveis.")
        else:
            await ctx.send("Que? Usa-se assim: !voz [list ou set]. O comando para falar é \"!falar [frase (entre aspas)]\"")
                

    @commands.command(name='falar', aliases=["say", "dizer"],description='Toca audio text-to-speech')
    async def voice(self, ctx: commands.Context, *content):
        try:

            if content[0] == "-a":
                anon = True
                content = tuple(x for x in content if x != "-a")
            else:
                anon = False

            channel = ctx.message.author.voice.channel
            path = getVoice(" ".join(content), voz=self.vozSelected)

            if path:
                if anon:
                    await ctx.message.delete()

                vc = await channel.connect()
                player = vc.play(discord.FFmpegPCMAudio(path), after=lambda e: print('done', e))

                while vc.is_playing():
                    await asyncio.sleep(1)

                vc.stop()
                await vc.disconnect()
                os.remove(path)
            else:
                await ctx.send("Um erro aconteceu ao processar o áudio, verifique os logs.")

        except AttributeError as e:
            await ctx.send("Você não está em um canal de voz.", e)


async def setup(bot):
    await bot.add_cog(Voice(bot))

if __name__ == "__main__":
    print(getVoice("Isto aqui e um teste."))