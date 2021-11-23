from discord.ext import commands
import discord
import youtube_dl
import random

from discord.ext import commands
import random
import itertools
import sys
import traceback
from async_timeout import timeout

from functools import partial
import os
import asyncio

ytdl_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'temp/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'no_warnings': True,
    'default_search': 'auto',
    'verbose':True,
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_options)


class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""

class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume')

    def __init__(self, ctx: commands.Context):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(300):  # 5 minutes...
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f'Ocorreu um erro ao processar sua música.\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            embed = discord.Embed(title="Tocando agora", description=f"[{source.title}]({source.web_url}) [{source.requester.mention}]", color=discord.Color.green())
            
            if self.np == None:
                self.np = await self._channel.send(embed=embed)
            else:
                await self.np.edit(embed=embed)
            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))

class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester

        self.title = data.get('title')
        self.web_url = data.get('webpage_url')
        self.duration = data.get('duration')

    def __getitem__(self, item: str):
        return self.__getattribute__(item)

    @classmethod
    async def create_sources(cls, ctx, search: str, *, loop):
        loop = loop or asyncio.get_event_loop()
        
        to_run = partial(ytdl.extract_info, url=search, download=False)
        data = await loop.run_in_executor(None, to_run)

        sources = []
        
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries']
            first_video = data[0]
            for video in data:
                sources.append({'webpage_url': video['webpage_url'], 'requester': ctx.author, 'title': video['title']})
        
            embed = discord.Embed(title="", description=f"Queued [{first_video['title']}]({first_video['webpage_url']}) [{ctx.author.mention}]", color=discord.Color.green())        
            await ctx.send(embed=embed)
        else:
            await ctx.send("Falha ao carregar vídeo/playlist")
        
        return sources

    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming links expire."""
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(discord.FFmpegPCMAudio(data['url']), data=data, requester=requester)



#class Music(commands.Cog):
class Music(commands.Cog):
    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
            try:
                await guild.voice_client.disconnect()
            except AttributeError:
                pass

            try:
                del self.players[guild.id]
            except KeyError:
                pass
    
    def _embed_creator(self, description, title="", color=discord.Color.green()):
        return discord.Embed(title=title, description=description, color=color)

    async def _is_connected(self, ctx):
        vc = ctx.voice_client
        
        if not vc or not vc.is_connected():
            await ctx.send(embed=self._embed_creator("Eu não estou conectado a um canal de voz"))
            return False
        else:
            return True
    
    async def __local_check(self, ctx):
        """A local check which applies to all commands in this cog."""
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('Esse comando não pode ser usado em mensagens privadas.')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await ctx.send('Erro ao conectar ao canal de voz. '
                           'Esteja em um canal de voz ou me atribua a um.')

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player
    
    def set_player(self, ctx, player: MusicPlayer):
        self.players[ctx.guild.id] = player

    @commands.command(name='join', aliases=['connect', 'j'], description="Conecta a um canal de voz.")
    async def connect_(self, ctx, *, channel: discord.VoiceChannel=None):
        """Conecta a um canal de voz.
        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.
        This command also handles moving the bot to different channels.
        """
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                await ctx.send(embed=self._embed_creator("Nenhum canal para se juntar. Use `join` de um canal de voz."))
                raise InvalidVoiceChannel('No channel to join. Please either specify a valid channel or join one.')

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Connecting to channel: <{channel}> timed out.')
        if (random.randint(0, 1) == 0):
            await ctx.message.add_reaction('👍')
        await ctx.send(f'**Joined `{channel}`**')

    @commands.command(name='play', aliases=['sing','p'], description="toca música")
    async def play_(self, ctx, *, search: str):
        """Request a song and add it to the queue.
        This command attempts to join a valid voice channel if the bot is not already in one.
        Uses YTDL to automatically search and retrieve a song.
        Parameters
        ------------
        search: str [Required]
            The song to search and retrieve using YTDL. This could be a simple search, an ID or URL.
        """
        await ctx.trigger_typing()

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.connect_)
        player = self.get_player(ctx)

        sources = await YTDLSource.create_sources(ctx, search, loop=self.bot.loop)
        
        for source in sources:
            await player.queue.put(source)

    @commands.command(name='pause', aliases=["#"], description="pausa a música")
    async def pause_(self, ctx):
        """Pausa a música atual."""
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            return await ctx.send(embed=self._embed_creator("Não estou tocando nada"))
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send("Pausado ⏸️")

    @commands.command(name='resume', aliases=["/"], description="despausa a musica")
    async def resume_(self, ctx):
        """Resume a música atual."""
        vc = ctx.voice_client

        if not await self._is_connected(ctx):
            return
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.send("Resumindo ⏯️")

    @commands.command(name='skip', aliases=["s", "next"],description="pula para a próxima música")
    async def skip_(self, ctx):
        """Pula a música."""
        vc = ctx.voice_client

        if not await self._is_connected(ctx):
            return

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()
    
    @commands.command(name='remove', aliases=['rm', 'rem'], description="remove uma música espeficica da fila")
    async def remove_(self, ctx, pos : int=None):
        """Remove uma música específica da lista."""

        if not await self._is_connected(ctx):
            return

        player = self.get_player(ctx)
        if pos == None:
            player.queue._queue.pop()
        else:
            try:
                s = player.queue._queue[pos-1]
                del player.queue._queue[pos-1]
                await ctx.send(embed=self._embed_creator(f"Removido [{s['title']}]({s['webpage_url']}) [{s['requester'].mention}]"))
            except:
                await ctx.send(embed=self._embed_creator(f'Não foi possível encontrar música na posição "{pos}"'))
    
    @commands.command(name='clear', aliases=['clr', 'cl', 'cr'], description="limpa a fila inteira")
    async def clear_(self, ctx):
        """Limpa a fila inteira."""

        if not await self._is_connected(ctx):
            return

        player = self.get_player(ctx)
        player.queue._queue.clear()
        await ctx.send('**Cleared**')

    @commands.command(name='queue', aliases=['fila','lista','q', 'playlist', 'que'], description="mostra a fila")
    async def queue_info(self, ctx):
        """Mostra a lista atual."""
        vc = ctx.voice_client

        if not await self._is_connected(ctx):
            return

        player = self.get_player(ctx)
        if player.queue.empty():
            return await ctx.send(embed=self._embed_creator("Fila está vazia."))

        seconds = vc.source.duration % (24 * 3600) 
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        if hour > 0:
            duration = "%dh %02dm %02ds" % (hour, minutes, seconds)
        else:
            duration = "%02dm %02ds" % (minutes, seconds)

        # Grabs the songs in the queue...
        queueSize = int(len(player.queue._queue))
        
        upcoming = list(itertools.islice(player.queue._queue, 0, 20 if queueSize >= 20 else queueSize))
        fmt = '\n'.join(f"`{(upcoming.index(_)) + 1}.` [{_['title']}]({_['webpage_url']}) | ` {duration} Requested by: {_['requester']}`\n" for _ in upcoming)
        fmt = f"\n__Now Playing__:\n[{vc.source.title}]({vc.source.web_url}) | ` {duration} Requested by: {vc.source.requester}`\n\n__Up Next:__\n" + fmt + f"\n**{queueSize} songs in queue**"
        embed = discord.Embed(title=f'Queue for {ctx.guild.name}', description=fmt, color=discord.Color.green())
        embed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar_url)

        await ctx.send(embed=embed)

    @commands.command(name='np', aliases=['song', 'current', 'currentsong', 'playing'], description="mostra a música atual")
    async def now_playing_(self, ctx):
        """Mostra a música atual."""
        vc = ctx.voice_client

        if not await self._is_connected(ctx):
            return

        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send(embed=self._embed_creator("Eu não estou tocando nada."))
        
        seconds = vc.source.duration % (24 * 3600) 
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        if hour > 0:
            duration = "%dh %02dm %02ds" % (hour, minutes, seconds)
        else:
            duration = "%02dm %02ds" % (minutes, seconds)

        embed = self._embed_creator("[{vc.source.title}]({vc.source.web_url}) [{vc.source.requester.mention}] | `{duration}`")
        embed.set_author(icon_url=self.bot.user.avatar_url, name=f"Tocando agora 🎶")
        await ctx.send(embed=embed)

    @commands.command(name='volume', aliases=['vol', 'v'], description="altera o volume")
    async def change_volume(self, ctx, *, vol: float=None):
        """Change the player volume.
        Parameters
        ------------
        volume: float or int [Required]
            The volume to set the player to in percentage. This must be between 1 and 100.
        """
        vc = ctx.voice_client

        if not await self._is_connected(ctx):
            return
        
        if not vol:
            return await ctx.send(embed=self._embed_creator("🔊 **{(vc.source.volume)*100}%**"))

        if not 0 < vol < 101:
            return await ctx.send(embed=self._embed_creator("Por favor insira um valor de 1 a 100."))

        player = self.get_player(ctx)

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        await ctx.send(embed=self._embed_creator(f'**`{ctx.author}`** mudou o volume para **{vol}%**'))

    @commands.command(name='leave', aliases=["stop", "dc", "disconnect", "bye"], description="para a música e desconecta o player.")
    async def leave_(self, ctx):
        """Stop the currently playing song and destroy the player.
        !Warning!
            This will destroy the player assigned to your guild, also deleting any queued songs and settings.
        """

        if not await self._is_connected(ctx):
            return

        if (random.randint(0, 1) == 0):
            await ctx.message.add_reaction('👋')
        await ctx.send('**Desconectado com Sucesso**')

        await self.cleanup(ctx.guild)

    @commands.command(name='shuffle', aliases=["rand", "mix"], description="Randomiza a ordem das músicas na fila.")
    async def shuffle_(self, ctx):
        """Randomiza a ordem das músicas na fila."""
        
        if not await self._is_connected(ctx):
            return
        
        player = self.get_player(ctx)
        
        random.shuffle(player.queue._queue)
        
        return await ctx.send("Randomizado 🔀")

def setup(bot):
    bot.add_cog(Music(bot))