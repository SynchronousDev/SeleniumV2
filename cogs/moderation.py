import typing as t
from copy import deepcopy
from dateutil.relativedelta import relativedelta

from discord.ext import tasks
from assets import *
import pytimeparse as pytp
import asyncio
from datetime import datetime as dt, timedelta

log = logging.getLogger(__name__)


class Mod(commands.Cog, name='Moderation'):
    def __init__(self, bot):
        self.bot = bot
        self.mute_task = self.check_mutes.start()

    def cog_unload(self):
        self.mute_task.cancel()

    @tasks.loop(seconds=1)
    async def check_mutes(self):
        current_time = dt.utcnow()
        mutes = deepcopy(self.bot.muted_users)

        for key, value in mutes.items():
            if value['mute_duration'] is None:
                continue

            unmute_time = value['muted_at'] + relativedelta(seconds=value['mute_duration'])

            guild = self.bot.get_guild(value['guild_id'])
            member = guild.get_member(value['_id'])

            data = await self.bot.config.find_one({"_id": guild.id})
            mute_role = guild.get_role(data['mute_role_id'])

            if current_time >= unmute_time:
                try:
                    await self.bot.mutes.delete_one({"_id": member.id})

                except discord.MemberNotFound:
                    pass

                if mute_role in member.roles:
                    await member.remove_roles(mute_role, reason='Mute time expired', atomic=True)

                else:
                    pass

                try:
                    self.bot.muted_users.pop(member.id)

                except KeyError:
                    pass

    @check_mutes.before_loop
    async def before_check_mutes(self):
        await self.bot.wait_until_ready()

    @commands.command(
        name='kick',
        aliases=['k'],
        description='Kicks members from the server. 3 second cooldown, must have Kick Users permission.')
    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.guild_only()
    @commands.bot_has_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def kick_cmd(self, ctx, member: discord.Member, *, reason: t.Optional[str] = "no reason provided"):
        if ctx.guild.me.top_role > member.top_role:
            if ctx.author.top_role > member.top_role:
                if member is not ctx.guild.owner:
                    em = discord.Embed(
                        description=f"{CHECK} Kicked {member.mention} for `{reason}`.",
                        timestamp=dt.utcnow(),
                        colour=GREEN)
                    await ctx.send(embed=em)
                    await send_punishment(member, ctx.guild, 'kick', ctx.author, reason)
                    await member.kick(reason=reason)
                else:
                    raise RoleNotHighEnough

            else:
                raise RoleNotHighEnough

        else:
            raise BotRoleNotHighEnough

    @commands.command(
        name='ban',
        aliases=['b'],
        description='Bans members from the server. 5 second cooldown, must have Ban Members permission.')
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def ban_cmd(self, ctx, member: t.Union[discord.Member, discord.User],
                      delete_days: t.Optional[int], *, reason: t.Optional[str] = "no reason provided"):
        delete_days = int(delete_days) if delete_days else 7
        if delete_days > 7:
            em = discord.Embed(
                description=f"{ERROR} The `days_delete` parameter has to be either equal or less than 7.",
                colour=RED)
            await ctx.send(embed=em)
            return

        if isinstance(member, discord.Member):
            if ctx.guild.me.top_role > member.top_role:
                if ctx.author.top_role > member.top_role:
                    if member is not ctx.guild.owner:
                        em = discord.Embed(
                            description=f"{CHECK} Banned {member.mention} for `{reason}`.",
                            timestamp=dt.utcnow(),
                            colour=GREEN)
                        await ctx.send(embed=em)
                        await send_punishment(member, ctx.guild, 'ban', ctx.author, reason)
                        await member.ban(reason=reason, delete_message_days=delete_days)
                    else:
                        raise RoleNotHighEnough

                else:
                    raise RoleNotHighEnough

            else:
                raise BotRoleNotHighEnough

        elif isinstance(member, discord.User):
            em = discord.Embed(
                description=f"{CHECK} Banned {member.mention} for `{reason}`.",
                timestamp=dt.utcnow(),
                colour=GREEN)
            await ctx.send(embed=em)
            await ctx.guild.ban(member, reason=reason, delete_message_days=delete_days)

    @commands.command(
        name='softban',
        aliases=['sban', 'sb', 'softb'],
        description='Bans a member and deletes all of their messages within a 14 day span.')
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def softban_cmd(self, ctx, member: discord.Member, *, reason: t.Optional[str] = "no reason provided"):
        if ctx.guild.me.top_role > member.top_role:
            if ctx.author.top_role > member.top_role:
                if member is not ctx.guild.owner:
                    em = discord.Embed(
                        description=f"{CHECK} Softbanned {member.mention} for `{reason}`.",
                        timestamp=dt.utcnow(),
                        colour=GREEN)
                    await ctx.send(embed=em)
                    await send_punishment(member, ctx.guild, 'softban', ctx.author, reason)
                    await member.ban(reason=reason, delete_message_days=7)
                    await asyncio.sleep(1)
                    await member.unban(reason='Softban actioned by {0} (ID {1})'.format(ctx.author, ctx.author.id))

                else:
                    raise RoleNotHighEnough

            else:
                raise RoleNotHighEnough

        else:
            raise BotRoleNotHighEnough

    @commands.command(
        name='unban',
        aliases=['ub', 'unb'],
        description='Unbans members from a server.')
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def unban_cmd(self, ctx, member: t.Union[discord.User, int],
                        *, reason: t.Optional[str] = 'no reason provided'):
        if isinstance(member, discord.User):
            try:
                await ctx.guild.unban(member, reason=reason)

            except Exception:
                raise commands.MemberNotFound(member)

        elif isinstance(member, int):
            user = await self.bot.get_user(member)
            if not user:
                raise commands.MemberNotFound(member)

            try:
                await ctx.guild.unban(user, reason=reason)

            except Exception:
                raise commands.MemberNotFound(member)

        em = discord.Embed(
            description=f"{CHECK} Unbanned {member.mention} for `{reason}`.",
            timestamp=dt.utcnow(),
            colour=GREEN)
        await ctx.send(embed=em)

    @commands.command(
        name='warn',
        aliases=['w', 'wrn'],
        description='Warns members in the server. 5 second cooldown, must have Manage Messages permission.')
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def warn_cmd(self, ctx, member: discord.Member, *, reason: t.Optional[str] = "no reason provided"):
        if ctx.guild.me.top_role > member.top_role:
            if ctx.author.top_role > member.top_role:
                em = discord.Embed(
                    description=f"{CHECK} Warned {member.mention} for `{reason}`.",
                    timestamp=dt.utcnow(),
                    colour=GREEN)
                await ctx.send(embed=em)
                try:
                    await send_punishment(member, ctx.guild, 'warn', ctx.author, reason)

                except discord.Forbidden:
                    pass

            else:
                raise RoleNotHighEnough

        else:
            raise BotRoleNotHighEnough

    @commands.command(
        name='mute',
        aliases=['m', 'silence'],
        description='Mutes users in the server. '
                    '3 second cooldown, must have Manage Messages permission. Cannot be bypassed.')
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.has_permissions(manage_messages=True)
    async def mute_cmd(self, ctx, member: discord.Member, *args):
        time = pytp.parse(args[0]) or None
        if not time:
            reason = ' '.join(args)

        else:
            reason = ' '.join(args[1:])
            if not reason:
                reason = 'no reason provided'

        data = await self.bot.config.find_one({"_id": ctx.guild.id})
        try:
            mute_role = ctx.guild.get_role(data['mute_role_id'])
            if not mute_role:
                em = discord.Embed(
                    description=f"{SHARD} Couldn't find a mute role to assign to {member.mention}, making one now...",
                    colour=MAIN)
                msg = await ctx.send(embed=em)

                mute_role = await create_mute_role(self.bot, ctx)

                await msg.delete()

        except KeyError:
            em = discord.Embed(
                description=f"{SHARD} Couldn't find a mute role to assign to {member.mention}, making one now...",
                colour=MAIN)
            msg = await ctx.send(embed=em)

            mute_role = await create_mute_role(self.bot, ctx)

            await msg.delete()

        if ctx.guild.me.top_role > member.top_role:
            if ctx.author.top_role > member.top_role:
                if member is not ctx.guild.owner:
                    try:
                        if self.bot.muted_users[member.id]:
                            em = discord.Embed(
                                description=f"{ERROR} {member.mention} is already muted! "
                                            f"Talk about adding insult to injury.",
                                colour=RED)
                            await ctx.send(embed=em)
                            return

                    except KeyError:
                        pass

                    data = {
                        '_id': member.id,
                        'muted_at': dt.utcnow(),
                        'mute_duration': time or None,
                        'muted_by': ctx.author.id,
                        'guild_id': ctx.guild.id
                    }
                    await self.bot.mutes.update_one({"_id": member.id}, {'$set': data}, upsert=True)
                    self.bot.muted_users[member.id] = data
                    em = discord.Embed(
                        description=f"{CHECK} Muted {member.mention} lasting {str(convert_time(time))}"
                                    f", for `{reason}`.", timestamp=dt.utcnow(),
                        colour=GREEN)
                    await ctx.send(embed=em)
                    await member.add_roles(mute_role, reason=f'Muted by {ctx.author} lasting {str(convert_time(time))}'
                                                             f', for {reason}.', atomic=True)

                    try:
                        await send_punishment(member, ctx.guild, 'mute', ctx.author, reason, convert_time(time))

                    except discord.Forbidden:
                        pass

                else:
                    raise RoleNotHighEnough

            else:
                raise RoleNotHighEnough

        else:
            raise BotRoleNotHighEnough

    @commands.command(
        name='unmute',
        aliases=['um', 'umt', 'unm'],
        description='Unmutes members in the server. 3 second cooldown, must have Manage Messages permission.')
    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.has_permissions(manage_messages=True)
    async def unmute_cmd(self, ctx, member: discord.Member,
                         *, reason: t.Optional[str] = 'no reason provided'):
        data = await self.bot.config.find_one({"_id": ctx.guild.id})
        try:
            mute_role = ctx.guild.get_role(data['mute_role_id'])
            if not mute_role:
                em = discord.Embed(
                    description=f"{SHARD} Couldn't find a mute role to assign to {member.mention}, making one now...",
                    colour=MAIN)
                msg = await ctx.send(embed=em)

                mute_role = await create_mute_role(self.bot, ctx)

                await msg.delete()

        except KeyError:
            em = discord.Embed(
                description=f"{SHARD} Couldn't find a mute role to assign to {member.mention}, making one now...",
                colour=MAIN)
            msg = await ctx.send(embed=em)

            mute_role = await create_mute_role(self.bot, ctx)

            await msg.delete()

        if ctx.guild.me.top_role > member.top_role:
            if ctx.author.top_role > member.top_role:
                if mute_role in member.roles:
                    em = discord.Embed(
                        description=f"{CHECK} Unmuted {member.mention} for `{reason}`.",
                        timestamp=dt.utcnow(),
                        colour=GREEN)
                    await ctx.send(embed=em)

                    try:
                        await self.bot.mutes.delete_one({"_id": member.id})

                    except discord.MemberNotFound:
                        pass

                    try:
                        self.bot.muted_users.pop(member.id)

                    except KeyError:
                        pass

                    await member.remove_roles(mute_role, reason=reason)

                    try:
                        await send_punishment(member, ctx.guild, 'unmute', ctx.author, reason)

                    except discord.Forbidden:
                        pass

                else:
                    em = discord.Embed(
                        description=f"{ERROR} {member.mention} is not muted.",
                        colour=RED)
                    await ctx.send(embed=em)
                    return

            else:
                raise RoleNotHighEnough

        else:
            raise BotRoleNotHighEnough

    @commands.command(
        name='lock',
        aliases=['lck', 'lk', 'lockdown'],
        description='Locks a channel. Essentially mutes the channel and no one can talk in it. '
                    'Run the command again to unlock the channel.')
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_guild_permissions(manage_channels=True)
    async def lock_cmd(self, ctx, channel: t.Optional[discord.TextChannel]):
        channel = channel or ctx.channel

        if ctx.guild.default_role not in channel.overwrites:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False)
            }
            await channel.edit(overwrites=overwrites)
            em = discord.Embed(
                description=f"{LOCK} {channel.mention} is now locked.",
                colour=RED)
            await ctx.send(embed=em)

        elif (channel.overwrites[ctx.guild.default_role].send_messages
              or channel.overwrites[ctx.guild.default_role].send_messages is None):
            overwrites = channel.overwrites[ctx.guild.default_role]
            overwrites.send_messages = False
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrites)
            em = discord.Embed(
                description=f"{LOCK} {channel.mention} is now locked.",
                colour=RED)
            await ctx.send(embed=em)

        else:
            overwrites = channel.overwrites[ctx.guild.default_role]
            overwrites.send_messages = True
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrites)
            em = discord.Embed(
                description=f"{UNLOCK} {channel.mention} is now unlocked.",
                colour=GREEN)
            await ctx.send(embed=em)

    @commands.command(
        name='slowmode',
        aliases=['slm', 'sl'],
        description='Changes the slowmode delay on a given channel. '
                    'Must be equal or less than 6 hours. Requires Manage Channels permission.')
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_guild_permissions(manage_channels=True)
    async def slowmode_cmd(self, ctx, channel: t.Optional[discord.TextChannel], time: pytp.parse):
        channel = channel or ctx.channel
        if time > 21600 or time < 1:
            em = discord.Embed(
                description=f"{ERROR} Slowmode time should be equal or less than 6 hours.",
                colour=RED)
            await ctx.send(embed=em)
            return

        await channel.edit(slowmode_delay=time, reason='Slowmode delay edited by {ctx.author} via slowmode command')
        em = discord.Embed(
            description=f":clock1: Slowmode delay for {channel.mention} was set to {str(convert_time(time))}",
            colour=GREEN)
        await ctx.send(embed=em)

    @commands.command(
        name='purge',
        aliases=['p', 'prg', 'prune'])
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.has_permissions(manage_messages=True)
    async def purge_cmd(self, ctx, limit: int, members: commands.Greedy[discord.Member]):
        if 0 < limit < 1001:
            await ctx.message.delete()
            deleted = await ctx.channel.purge(
                limit=limit,
                after=dt.utcnow() - timedelta(days=14),
                check=lambda m: m.author in members or not len(members))

            if not len(deleted):
                em = discord.Embed(
                    description=f"{ERROR} Could not find any messages to delete.\n"
                                f"```Messages older than 2 weeks cannot be deleted```",
                    color=RED)
                await ctx.send(embed=em)

            em = discord.Embed(
                description=f"{CHECK} Deleted {len(deleted, )} messages in {ctx.channel.mention}",
                color=GREEN)
            await ctx.send(embed=em, delete_after=2)

        else:
            em = discord.Embed(
                description=f"{ERROR} The limit provided is not within acceptable boundaries.\n"
                            f"```Limit must be in between 1 and 1000 messages```",
                color=RED)
            await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(Mod(bot))
