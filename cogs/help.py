import typing as t
from assets import *
from discord.ext import commands, menus

class HelpMenu(menus.ListPageSource):
    def __init__(self, ctx, data, bot):
        self.ctx = ctx
        self.bot = bot

        super().__init__(data, per_page=1, )

    # noinspection SpellCheckingInspection
    async def write_help(self, menu, cog, prefix):
        offset = (menu.current_page * self.per_page) + 1
        len_data = len(self.entries)
        em = discord.Embed(
                title="Saturn's Commands",
                description=f'**General Information**\nServer - `{self.ctx.guild}`'
                            f'\nCommands in this server start with `{prefix}`\n\n'
                            f'**Quick Links**\n[Support Server](https://discord.gg/HANGYrUF2y)\n'
                            f'[Invite Saturn (Administrator)]('
                            f'https://discord.com/oauth2/authorize?client_id=799328036662935572&permissions=8'
                            f'&redirect_uri=https%3A%2F%2F127.0.0.1%3A5000%2Flogin&scope=bot)\n'
                            f'[Invite Saturn (Recommended)](https://discord.com/api/oauth2/authorize?client_id'
                            f'=799328036662935572&permissions=536145143&redirect_uri=https%3A%2F%2F127.0.0.1%3A5000'
                            f'%2Flogin&scope=bot)\n\n',
                colour=MAIN,
                timestamp=dt.utcnow())

        desc = self.bot.get_cog(cog).description

        text = f"{desc if desc else 'No description provided.'}```\n**Commands in the {cog} cog**```diff\n"

        for command in self.bot.get_cog(cog).walk_commands():
            if command.hidden or not command.enabled:
                if command.parent is not None:
                    text += f"-   {command.name}\n"

                else:
                    text += f"- {command.name}\n"

            elif command.parent is not None:
                text += f"    {command.name}\n"

            else:
                text += f"{command.name}\n"

        em.add_field(name="Description", value=f"```{text}```", inline=False)
        em.set_footer(text=f"{offset:,} of {len_data:,} cogs | "
                           f"{len([cmd for cmd in self.bot.get_cog(cog).walk_commands()])} commands in {cog} cog")

        return em

    # noinspection PyTypeChecker
    async def format_page(self, menu, entries):
        prefix = await retrieve_prefix(self.bot, self.ctx)
        return await self.write_help(menu, entries, prefix)


log = logging.getLogger(__name__) 


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command('help')

    @commands.command(
        name='help',
        aliases=['h', 'commands'],
        description='The help command')
    @commands.cooldown(1, 3, commands.BucketType.member)
    async def help(self, ctx, *, entity: t.Optional[str]):
        if not entity:
            cogs = [c for c in self.bot.cogs.keys()]
            cogs.remove('Events')
            cogs.remove('Help')
            cogs.remove('Dev')
            cogs.remove('Reaction Roles')
            cogs.remove('ErrorHandler')
            cogs.remove('Jishaku')

            help_menu = menus.MenuPages(source=HelpMenu(ctx, cogs, self.bot), delete_message_after=True)

            await help_menu.start(ctx)

        else:
            command = self.bot.get_command(entity)
            if command:
                cog_name = command.cog.qualified_name.title() + \
                           " 》 " if command.cog else ''
                parent_name = command.parent.name.title() + " 》 " if command.parent else ''
                command_name = command.name.title()
                em = discord.Embed(
                    title='{0}{1}{2}'.format(cog_name, parent_name, command_name),
                    colour=MAIN,
                    timestamp=dt.now())
                em.add_field(name='Description',
                             value=command.description if command.description else "No description for this "
                                                                                   "command.",
                             inline=False)
                em.add_field(name='Syntax', value=await syntax(command), inline=False)
                em.add_field(name='Aliases',
                             value=f"```{', '.join(command.aliases)}```" if command.aliases else "No aliases for "
                                                                                                 "this command.")
                if hasattr(command, "all_commands"):
                    _subcommands = []
                    subcommands = [cmd for cmd in command.cog.walk_commands()]
                    for cmd in subcommands:
                        if cmd.parent == command:
                            _subcommands.append(cmd.name)

                    if not len(_subcommands):
                        pass

                    else:
                        em.add_field(name='Subcommands', value='```\n' + '\n'.join(_subcommands) + '```', inline=False)

                em.set_footer(text='Invoked by ' + ctx.author.name,
                              icon_url=self.bot.user.avatar_url)
                await ctx.send(embed=em)

            else:
                em = discord.Embed(
                    description=f"{ERROR} Command `{entity}` does not exist.",
                    colour=RED)
                await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(Help(bot))
