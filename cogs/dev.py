# noinspection SpellCheckingInspection
import contextlib as ctxlib
import io
import textwrap
from traceback import format_exception
import typing as t

from assets import *

log = logging.getLogger(__name__)

# noinspection SpellCheckingInspection
class Dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return await ctx.bot.is_owner(ctx.author)

    @commands.command()
    async def test(self, ctx):
        await ctx.send("TBD...")
        # conf = await ConfirmationMenu('delete this role').prompt(ctx)
        # if conf:
        #     em = discord.Embed(
        #         description=f"{CHECK} Deleted {role.mention}.",
        #         colour=GREEN)
        #     await ctx.send(embed=em)
        #
        # else:
        #     em = discord.Embed(
        #         description=f"{ERROR} Action cancelled.",
        #         colour=RED)
        #     await ctx.send(embed=em)

    @commands.command(
        name='blacklist',
        aliases=['bl'],
        description='A developer command. Blacklists a user from using the bot.')
    async def blacklist_cmd(self, ctx, member: discord.Member, *, reason: t.Optional[str] = 'no reason provided'):
        await self.bot.blacklists.update_one({"_id": member.id},
                                             {'$set': {"reason": reason}}, upsert=True)

        em = discord.Embed(
            description=f"{CHECK} Blacklisted {member.mention} for **{reason}**.",
            colour=GREEN,
            timestamp=dt.now())
        await ctx.send(embed=em)

    @commands.command(
        name='unblacklist',
        aliases=['ubl'],
        description='A developer command. Unblacklists a user from using the bot.')
    async def unblacklist_cmd(self, ctx, member: discord.Member, *, reason: t.Optional[str] = 'no reason provided'):
        try:
            await self.bot.blacklists.delete_one({"_id": member.id})

        except commands.MemberNotFound:
            em = discord.Embed(
                description=f"{ERROR} {member.mention} is not blacklisted from this bot.",
                colour=RED)
            await ctx.send(embed=em)

        em = discord.Embed(
            description=f"{CHECK} Unblacklisted {member.mention} for **{reason}**.",
            colour=GREEN,
            timestamp=dt.now())
        await ctx.send(embed=em)

    @commands.command(
        name='eval',
        aliases=['ev', 'exec', 'evaluate'],
        description='The eval command. Executes code (only accessible by me)')
    async def eval(self, ctx, *, code):
        code = clean_codeblock(code)
        local_vars = {
            "discord": discord,
            "commands": commands,
            "ctx": ctx,
            "bot": self.bot,
            "self": self,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "member": ctx.author,
            "msg": ctx.message
        }

        stdout = io.StringIO()

        try:
            with ctxlib.redirect_stdout(stdout):
                exec(
                    f"async def saturn_evaluate():\n{textwrap.indent(code, '    ')}", local_vars
                )

                obj = await local_vars["saturn_evaluate"]()
                value = stdout.getvalue() or "None"
                result = f'{value}\n-- {obj}\n'
                color = GREEN

        except Exception as e:
            result = ''.join(format_exception(e, e, e.__traceback__))
            color = RED

        em = discord.Embed(
            description=f"```py\n{code}```\n```py\n{result}```",
            color=color,
            timestamp=dt.utcnow())
        em.set_footer(text='Saturn Eval Command')
        await ctx.send(embed=em)

    @commands.command(
        name='logout',
        aliases=['exit'],
        description='A developer command. Closes the websocket connection and logs the bot out.')
    async def logout_cmd(self, ctx):
        em = discord.Embed(
            description=f"{CHECK} Closing the websocket connection.",
            color=GREEN)
        await ctx.send(embed=em, delete_after=2)

        await self.bot.logout()

    @commands.command(
        name='global_toggle',
        aliases=['gtoggle', 'gt'],
        description='A developer command. Enable or disable commands globally.')
    async def global_toggle(self, ctx, *, command):
        cmd = self.bot.get_command(command)

        if not cmd:
            em = discord.Embed(
                description=f"{ERROR} Command `{command}` does not exist.",
                colour=RED)
            return await ctx.send(embed=em)

        elif ctx.command == cmd or cmd in [c for c in self.bot.get_cog('Dev').walk_commands()] \
                or cmd == self.bot.get_command('help'):
            em = discord.Embed(
                description=f"{ERROR} This command cannot be disabled.",
                colour=RED)
            return await ctx.send(embed=em)

        else:
            cmd.enabled = not cmd.enabled
            for _cmd in self.bot.get_cog(cmd.cog.qualified_name).walk_commands():
                if _cmd.parent == cmd:
                    _cmd.enabled = not _cmd.enabled

            status = "enabled" if cmd.enabled else "disabled"
            em = discord.Embed(
                description=f"{CHECK} {status.title()} `{cmd.qualified_name}` and its subcommands.",
                color=GREEN)
            await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(Dev(bot))
