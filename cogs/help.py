import typing as t
from assets import *
from discord.ext import commands, menus

class HelpMenu(menus.ListPageSource):
    def __init__(self, ctx, data, bot):
        self.ctx = ctx
        self.bot = bot

        super().__init__(data, per_page=1)

    async def write_help(self, menu, cogs, prefix):
        offset = (menu.current_page * self.per_page) + 1
        len_data = len(self.entries)
        em = discord.Embed(
                title="Selenium's Commands",
                description=f'Prefix for this server: `{prefix}` | '
                            f'[Join the support server](https://discord.gg/HANGYrUF2y) | '
                            f'[Invite Selenium (Administrator)](https://discord.com/oauth2/authorize?client_id=793572249059196959&permissions=8&scope=bot) | '
                            f'[Invite Selenium (Recommended)](https://discord.com/oauth2/authorize?client_id=793572249059196959&permissions=501083383&scope) | ',
                colour=MAIN,
                timestamp=dt.utcnow())
        em.set_footer(text=f"{offset:,} - {min(len_data, offset + self.per_page - 1):,} "
                           f"of {len_data:,} cogs")

        
        try:
            for cog in [c for c in cogs]:
                text = "\n"
                for command in self.bot.get_cog(cog).walk_commands():
                    if command.hidden:
                        continue

                    elif command.parent is not None:
                        text += f"   {command.name}\n"

                    else:
                        text += f"{command.name}\n"

                em.add_field(name=cog, value=f"```{text}```", inline=True)

        except AttributeError:
            text = "\n"

            for command in self.bot.get_cog(cogs).walk_commands():
                if command.hidden:
                    continue

                elif command.parent is not None:
                    text += f"   {command.name}\n"

                else:
                    text += f"{command.name}\n"

            em.add_field(name=cogs, value=f"```{text}```", inline=False)

        return em

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

            help_menu = menus.MenuPages(source=HelpMenu(ctx, cogs, self.bot))

            await help_menu.start(ctx)

        else:
            cog = self.bot.get_cog(entity.capitalize())
            if cog:
                pass

            else:
                command = self.bot.get_command(entity)
                if command:
                    em = discord.Embed(
                        title='{0}{1}{2}'.format(
                            str(command.cog.qualified_name).title() + ' ▸ '
                            if command.cog.qualified_name else '',
                            str(command.parent.name).title() + ' ▸ '
                            if command.parent else '',
                            str(command.name).title()),
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
                        subcmds = []
                        subcommands = [cmd for cmd in command.cog.walk_commands()]
                        for cmd in subcommands:
                            if cmd.parent == command:
                                subcmds.append(cmd.name)

                        if not len(subcmds):
                            pass

                        else:
                            em.add_field(name='Subcommands', value='```\n' + '\n'.join(subcmds) + '```', inline=False)

                    em.set_footer(text='Invoked by ' + ctx.author.name,
                                  icon_url=self.bot.user.avatar_url)
                    await ctx.send(embed=em)

                else:
                    em = discord.Embed(
                        description=f"{ERROR} Entity `{entity}` does not exist.",
                        colour=RED)
                    await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(Help(bot))
