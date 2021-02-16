import asyncio
import datetime as dt
import re
import typing as t

import discord
import wavelink
import logging
from assets import *
from discord.ext import commands, menus
import urllib.parse as urlparse


class QueueMenu(menus.ListPageSource):
    def __init__(self, ctx, data):
        self.ctx = ctx

        super().__init__(data, per_page=10)

    async def write_queue(self, menu, queue):
        offset = (menu.current_page * self.per_page) + 1
        len_data = len(self.entries)

        em = discord.Embed(
            title="Player Queue",
            colour=MAIN,
            timestamp=dt.utcnow())

        if not queue:
            em.description = 'There are no more tracks in the queue.'

        for i, track in enumerate(queue, offset):
            em.add_field(name=f"Position {i} | {track.author}",
                         value=f"[`{track.title} ({get_track_length(track)})`]({track.uri})", inline=False)
            em.set_footer(text=f"{offset:,} - {min(len_data, offset + self.per_page - 1):,} "
                               f"of {len_data:,} tracks")

        return em

    async def format_page(self, menu, entries):
        queue = []
        _queue = []

        for track in entries:
            queue.append(track)

        # noinspection PyTypeChecker

        return await self.write_queue(menu, queue)


log = logging.getLogger(__name__)


class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        # woo hoo music stuff that I'm too lazy to work on
        self.bot.loop.create_task(self.start_nodes())
        self.sp = SpotifyClient(
            self.bot.configuration['spotify_client_id'],
            self.bot.configuration['spotify_client_secret'])

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot and after.channel is None:
            if not [m for m in before.channel.members if not m.bot]:
                await self.get_player(member.guild).teardown()

    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node):
        print(f"Wavelink node [{node.identifier}] ready.")

    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_end")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def on_player_stop(self, node, payload):
        if payload.player.queue.repeat_mode == RepeatMode.ONE:
            await payload.player.repeat_track()

        else:
            await payload.player.advance()

    async def start_nodes(self):
        await self.bot.wait_until_ready()

        nodes = {
            "MAIN": {
                "host": "127.0.0.1",
                "port": 2333,
                "rest_uri": "http://127.0.0.1:2333",
                "password": "youshallnotpass",
                "identifier": "MAIN",
                "region": "us-east",
            }
        }

        for node in nodes.values():
            await self.wavelink.initiate_node(**node)

    # noinspection PyTypeChecker
    # Ugh pycharm messing things up again
    def get_player(self, obj):
        if isinstance(obj, commands.Context):
            return self.wavelink.get_player(obj.guild.id, cls=Player, context=obj)
        elif isinstance(obj, discord.Guild):
            return self.wavelink.get_player(obj.id, cls=Player)

    @commands.command(name="connect", aliases=["join", "c", 'conn'],
                      description='Connect to a voice channel.')
    @commands.guild_only()
    async def connect_command(self, ctx, *, channel: t.Optional[discord.VoiceChannel]):
        player = self.get_player(ctx)
        channel = await player.connect(ctx)
        em = discord.Embed(
            description=f"{SHARD} Connected to `{channel.name}`",
            color=MAIN)
        await ctx.send(embed=em)

    @commands.command(name="disconnect", aliases=["leave", 'd', 'dconn'],
                      description='Disconnect from a voice channel.')
    @commands.guild_only()
    async def disconnect_command(self, ctx):
        player = self.get_player(ctx)
        await player.teardown()
        em = discord.Embed(
            description=f"{SHARD} Disconnected.",
            color=MAIN)
        await ctx.send(embed=em)

    @commands.command(name="play", aliases=['pl'],
                      descrption='Play some music.')
    @commands.guild_only()
    async def play_command(self, ctx, *, query: t.Optional[str]):
        player = self.get_player(ctx)
        if not player.is_connected:
            await player.connect(ctx)

        if query is None:
            if player.queue.is_empty:
                raise QueueIsEmpty

            await player.set_pause(False)
            em = discord.Embed(
                description=f"{SHARD} Playing.",
                color=MAIN)
            await ctx.send(embed=em)

        else:
            if re.search(SPOTIFY_URL_REGEX, query):
                track = await self.sp.get_track(query)
                query = f"ytsearch:{track}"
                log.debug("Found tracks with a Spotify Link")

            elif not re.search(YOUTUBE_URL_REGEX, query):
                query = query.strip("<>")
                query = f"ytsearch:{query}"
                log.debug("Found tracks with a Youtube Link")

            await player.add_tracks(ctx, await self.wavelink.get_tracks(query, retry_on_failure=True))

    @commands.command(name="pause", aliases=['ps'],
                      description='Pause the currently playing music.')
    @commands.guild_only()
    async def pause_command(self, ctx):
        player = self.get_player(ctx)

        if player.is_paused:
            raise PlayerIsAlreadyPaused

        await player.set_pause(True)
        em = discord.Embed(
            description=f"{SHARD} Paused.",
            color=MAIN)
        await ctx.send(embed=em)

    @commands.command(name="stop", aliases=['stp'],
                      description='Stop the currently playing music. This is not equivalent '
                                  'to the `pause` command, this one clears the queue. If you '
                                  'want to only pause music, consider using the `pause` command'
                                  'instead of this one.')
    @commands.guild_only()
    async def stop_command(self, ctx):
        player = self.get_player(ctx)
        player.queue.empty()
        await player.stop()
        em = discord.Embed(
            description=f"{SHARD} Stopped playing music.",
            color=MAIN)
        await ctx.send(embed=em)

    @commands.command(name="next", aliases=["skip", 'n', 'nxt'],
                      description='Skip to the next song in the queue.')
    @commands.guild_only()
    async def next_command(self, ctx):
        player = self.get_player(ctx)

        if not player.queue.upcoming:
            raise NoMoreTracks

        await player.stop()
        em = discord.Embed(
            description=f"{SHARD} Skipped to next track.",
            color=MAIN)
        await ctx.send(embed=em)

    @commands.command(name="previous", aliases=['prev', 'prvs'],
                      description='Play the previous song in the queue.')
    @commands.guild_only()
    async def previous_command(self, ctx):
        player = self.get_player(ctx)

        if not player.queue.history:
            raise NoPreviousTracks

        player.queue.position -= 2
        await player.stop()
        em = discord.Embed(
            description=f"{SHARD} Playing previous track in the queue.",
            color=MAIN)
        await ctx.send(embed=em)

    @commands.command(name="shuffle", aliases=['shffl', 'sf'],
                      description='Shuffles the queue.')
    @commands.guild_only()
    async def shuffle_command(self, ctx):
        player = self.get_player(ctx)
        player.queue.shuffle()
        em = discord.Embed(
            description=f"{SHARD} Shuffled the queue.",
            color=MAIN)
        await ctx.send(embed=em)

    @commands.command(name="repeat", aliases=['r', 'rpt'],
                      description='Set a song\'s repeat mode.')
    @commands.guild_only()
    async def repeat(self, ctx, mode: t.Optional[str]):
        player = self.get_player(ctx)

        if mode:
            mode = mode.lower()
            if mode in ('1', 'once', 'track', 'song'):
                mode = 'one'

            elif mode in ('0', 'no'):
                mode = 'none'

            elif mode in ('queue', 'playlist', 'tracks'):
                mode = 'all'

            if mode not in ("none", "one", "all"):
                raise InvalidRepeatMode
            else:
                player.queue.set_repeat_mode(mode)
                em = discord.Embed(
                    description=f"{SHARD} Set repeat mode to `{mode}`",
                    color=MAIN)
                await ctx.send(embed=em)
                return

        em = discord.Embed(
            title='Choose a repeat mode',
            description='React to the emoji you want to set.',
            color=MAIN)
        msg = await ctx.send(embed=em)
        await msg.add_reaction(NO_REPEAT)
        await msg.add_reaction(REPEAT_ONE)
        await msg.add_reaction(REPEAT_ALL)

        def check(reaction, user):
            return user == ctx.message.author and str(reaction.emoji) in (NO_REPEAT, REPEAT_ONE, REPEAT_ALL)

        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

        except asyncio.TimeoutError:
            em = discord.Embed(
                description=f"{ERROR} User did not respond in time.",
                color=RED)
            await ctx.send(embed=em)
            return

        else:
            if str(reaction.emoji) == NO_REPEAT:
                player.queue.set_repeat_mode('none')
                mode = "none"

            elif str(reaction.emoji) == REPEAT_ONE:
                player.queue.set_repeat_mode("one")
                mode = "one"

            elif str(reaction.emoji) == REPEAT_ALL:
                player.queue.set_repeat_mode("all")
                mode = "all"

        em = discord.Embed(
            description=f"{SHARD} Set repeat mode to `{mode}`",
            color=MAIN)
        await ctx.send(embed=em)

    @commands.command(name="queue", aliases=['q'],
                      description='See your song queue.')
    @commands.guild_only()
    async def queue_command(self, ctx):
        player = self.get_player(ctx)

        if player.queue.is_empty:
            raise QueueIsEmpty

        queue = menus.MenuPages(source=QueueMenu(
            ctx, player.queue.upcoming), delete_message_after=True)
        await queue.start(ctx)

    @commands.command(
        name='search',
        aliases=['srch', 'sr'],
        description='Search for some music.')
    async def search(self, ctx, *, query):
        player = self.get_player(ctx)
        query = query.strip("<>")
        if not re.match(URL_REGEX, query):
            query = f"ytsearch:{query}"

        await player.search_tracks(ctx, await self.wavelink.get_tracks(query))

    @commands.command(
        name='remove',
        description='Removes a track from the queue.')
    @commands.guild_only()
    async def remove_tracks(self, ctx, track_id: int):
        player = self.get_player(ctx)
        await player.remove_track(track_id)

        em = discord.Embed(
            description=f"{SHARD} Removed track number `{track_id}`",
            color=GREEN)
        await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(Music(bot))
