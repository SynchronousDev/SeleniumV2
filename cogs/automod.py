import collections
import re

from better_profanity import profanity

from assets import *
from .moderation import mute_members

log = logging.getLogger(__name__)


# noinspection SpellCheckingInspection
class AutoMod(commands.Cog, name='Auto Moderation'):
    def __init__(self, bot):
        self.bot = bot
        self._cache = {}

    async def get_censor_words(self):
        with open(self.bot.path + '/assets/profanity.txt', 'r') as f:
            file = f.read()

        return file.split('\n')

    async def profanity_command_check(self, message: discord.Message):
        starts, prefix = False, None
        content = message.content
        for _prefix in await retrieve_raw_prefix(self.bot, message):
            if content.startswith(_prefix):
                starts = True
                prefix = _prefix

        if not starts:
            return False
        content = content.replace(prefix, '')
        if self.bot.get_command(content[:2]) or self.bot.get_command(content[:1]):
            return True

        else:
            return False

    async def cog_check(self, ctx: commands.Context) -> bool:
        if not ctx.guild or not ctx.author.guild_permissions.manage_guild:
            return False
        return True

    async def update_cache(self, message: discord.Message):
        """
        Update the bot's message cache.
        """
        try:
            if not self._cache[message.author.id]:
                self._cache[message.author.id] = []

        except KeyError:
            self._cache[message.author.id] = []

        self._cache[message.author.id].append(message)

    def get_cache(self, member) -> list or None:
        """
        Retrieve a member's message cache.
        """
        try:
            for message in self._cache[member.id]:
                # filter out all items in the self._cache that were created more than 5 seconds ago
                if message.created_at - timedelta(seconds=3) > dt.utcnow():
                    self._cache[member.id].remove(message)

                return self._cache[member.id]

        except KeyError:
            return []

    def is_spamming(self, member):
        cache = self.get_cache(member)

        if len(cache) > 5:
            return True

        return False

    async def delete_cache(self, member):
        """
        Delete a member's cache.
        """
        try:
            if not self._cache[member.id]:
                log.info("Request to clear cache on member without a previous cache.")
                return False

            self._cache.pop(member.id)

        except KeyError:
            return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return

        _data = await self.bot.config.find_one({"_id": message.guild.id})
        msg = message.content.lower()
        await self.update_cache(message)

        try:
            if _data['profanity_toggle']:  # check if profanity is enabled
                try:
                    if _data['words']:  #
                        profanity.load_censor_words(_data['words'])

                except KeyError:
                    profanity.load_censor_words_from_file(
                        self.bot.path + '/assets/profanity.txt')

                # anti-profanity
                if (
                        # message just has plain profanity
                        profanity.contains_profanity(msg) or
                        profanity.contains_profanity(
                            msg.replace(' ', '')) or  # message has spaces and remove the spaces
                        profanity.contains_profanity(
                            re.sub(r'[^\w\s]', '', msg)) or  # message has punctuation, remove punctuation
                        # message has invis unicode character
                        profanity.contains_profanity(msg.replace('­', '')) or
                        profanity.contains_profanity(
                            "".join(collections.OrderedDict.fromkeys(msg)))  # duplicate chars
                ):
                    if await self.profanity_command_check(message): return # make sure that they're not adding a word
                    # in that case then don't do stuff

                    await message.delete()
                    em = discord.Embed(
                        description=f"{WARNING} That word is not allowed in **{message.guild}**!",
                        colour=GOLD)
                    await message.channel.send(embed=em)

            if _data['spam_toggle'] and self.is_spamming(message.author):
                to_delete = len(self.get_cache(message.author))
                await self.delete_cache(message.author)
                data = await self.bot.config.find_one({"_id": message.guild.id})
                try:
                    whitelist = data['spam_whitelist']
                    if message.author.id in whitelist: return
                    # check that the author isn't in the spam whitelist

                except KeyError or TypeError: pass # if there is no whitelist

                try:
                    if not (mute_role := message.guild.get_role(_data['mute_role'])):
                        mute_role = await create_mute_role(self.bot, message)

                except TypeError or KeyError:
                    # create the mute role
                    mute_role = await create_mute_role(self.bot, message)

                try:
                    # purge the spam messages sent by the author
                    # I originally had the check to be lambda m: m in self.get_cache but it just didn't quite work
                    # because I was emptying the cache after the messages were purged
                    await message.channel.purge(
                        limit=to_delete,
                        check=lambda m: m.author == message.author)  # make sure that the message author is the spammer

                except discord.NotFound or discord.NoMoreItems or asyncio.QueueEmpty:
                    pass

                if not message.author.guild_permissions.manage_messages:
                    # mute the member, only if they can't mute other people so they have mute invincibility
                    await mute_members(self.bot, message, message.author,
                                       "sending messages too quickly", mute_role, 10)

                em = discord.Embed(
                    description=f"{WARNING} Spam is not allowed in **{message.guild}**!",
                    colour=GOLD)
                await message.channel.send(embed=em)

        except KeyError or TypeError:
            pass

    @commands.group(
        name='profanity',
        aliases=['prof', 'swears', 'sw', 'curses'],
        description='The command to change the settings for the anti-profanity system.',
        invoke_without_command=True
    )
    async def anti_profanity(self, ctx):
        await ctx.invoke(self.bot.get_command('help'), entity='profanity')

    @anti_profanity.command(
        name='toggle',
        aliases=['switch', 'tggle'],
        description='Toggles the anti-profanity system on or off.'
    )
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def toggle_profanity(self, ctx):
        data = await self.bot.config.find_one({"_id": ctx.guild.id})
        try:
            if not data['profanity_toggle']:
                toggle = False
            else:
                toggle = data['profanity_toggle']

        except KeyError or TypeError:
            toggle = False

        await self.bot.config.update_one({"_id": ctx.guild.id},
                                         {'$set': {"profanity_toggle": not toggle}}, upsert=True)
        status = "enabled" if not toggle else "disabled"
        em = discord.Embed(
            description=f"{CHECK} {status.title()} anti-profanity.",
            color=GREEN)
        await ctx.send(embed=em)

    @anti_profanity.command(
        name='add',
        aliases=['addword', 'addcurse', 'addswear', 'addprofanity'],
        description='Adds a curse word the anti-profanity system detects. '
                    'Use -default to include the default Saturn wordlist.'
    )
    @commands.cooldown(1, 3, commands.BucketType.member)
    async def add_curse(self, ctx, *, word: str):
        if word == "-default":
            words = await self.get_censor_words()

        else:
            words = []

        data = await self.bot.config.find_one({"_id": ctx.guild.id})
        if words and word in words:
            em = discord.Embed(
                description=f"{ERROR} That word is already recognized as a curse word.",
                colour=RED)
            return await ctx.send(embed=em)

        try:
            _ = data['words']
            if not data['words']:
                words.append(word)

            else:
                words = data['words']
                if word in words:
                    em = discord.Embed(
                        description=f"{ERROR} That word is already recognized as a curse word.",
                        colour=RED)
                    return await ctx.send(embed=em)

                words.append(word)

        except KeyError or TypeError:
            words.append(word)

        await self.bot.config.update_one({"_id": ctx.guild.id},
                                         {'$set': {"words": words}}, upsert=True)

        if word != '-default':
            await ctx.message.delete()

        em = discord.Embed(
            description=f"{CHECK} Added "
                        f"{f'|| {word} ||' if word != '-default' else 'the default wordlist'} "
                        f"as a recognized curse word.",
            color=GREEN)
        await ctx.send(embed=em)

    @anti_profanity.command(
        name='delete',
        aliases=['remove', 'delcurse', 'removeswear', 'delprofanity'],
        description='Removes a curse word the anti-profanity system detects.'
    )
    @commands.cooldown(1, 3, commands.BucketType.member)
    async def remove_curse(self, ctx, *, word: str):
        words = await self.get_censor_words()

        data = await self.bot.config.find_one({"_id": ctx.guild.id})
        try:
            if not data['words']:
                words.remove(word)

            else:
                words = data['words']
                if word not in words:
                    em = discord.Embed(
                        description=f"{ERROR} That word is not recognized as a curse word.",
                        colour=RED)
                    return await ctx.send(embed=em)

                words.remove(word)

        except KeyError or TypeError:
            words.remove(word)

        await self.bot.config.update_one({"_id": ctx.guild.id},
                                         {'$set': {"words": words}}, upsert=True)
        await ctx.message.delete()

        em = discord.Embed(
            description=f"{CHECK} Removed || {word} || as a registered curse word.",
            color=GREEN)
        await ctx.send(embed=em)

    @anti_profanity.command(
        name='clear',
        aliases=['clearsw', 'clearwords', 'clearcurses', 'clearswears'],
        description='Deletes all currently registered words. For deleting one word, use the `profanity delswears `'
    )
    @commands.cooldown(1, 3, commands.BucketType.member)
    async def clear_curses(self, ctx):
        await self.bot.config.update_one({"_id": ctx.guild.id},
                                         {'$unset': {"words": 1}})
        em = discord.Embed(
            description=f"{CHECK} Deleted all recognized curse words.",
            color=GREEN)
        await ctx.send(embed=em)

    @commands.group(
        name='spam',
        aliases=['antispam', 'sp', 'asp', 'anti-spam'],
        description='The command to change the settings for the anti-spam system.',
        invoke_without_command=True
    )
    async def anti_spam(self, ctx):
        await ctx.invoke(self.bot.get_command('help'), entity='spam')

    @anti_spam.command(
        name='toggle',
        aliases=['switch', 'tggle'],
        description='Toggles the anti-spam system on or off.'
    )
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def toggle_antispam(self, ctx):
        data = await self.bot.config.find_one({"_id": ctx.guild.id})
        try:
            if not data['spam_toggle']:
                toggle = False
            else:
                toggle = data['spam_toggle']

        except KeyError or TypeError:
            toggle = False

        await self.bot.config.update_one({"_id": ctx.guild.id},
                                         {'$set': {"spam_toggle": not toggle}}, upsert=True)
        status = "enabled" if not toggle else "disabled"
        em = discord.Embed(
            description=f"{CHECK} {status.title()} anti-spam.",
            color=GREEN)
        await ctx.send(embed=em)

    @anti_spam.command(
        name='whitelist',
        aliases=['disablefor', 'untrack'],
        description='Adds a member to the anti-spam whitelist. If they spam, the automod will ignore them.'
    )
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def whitelist_antispamspam(self, ctx, member: discord.Member):
        data = await self.bot.config.find_one({"_id": ctx.guild.id})
        try:
            if not data['spam_whitelist']:
                whitelist = []

            else:
                whitelist = data['spam_whitelist']

        except KeyError or TypeError:
            whitelist = []

        if member.id in whitelist:
            em = discord.Embed(
                description=f"{ERROR} {member.mention} is already whitelisted.",
                colour=RED)
            return await ctx.send(embed=em)

        whitelist.append(member.id)

        await self.bot.config.update_one({"_id": ctx.guild.id},
                                         {'$set': {"spam_whitelist": whitelist}}, upsert=True)
        em = discord.Embed(
            description=f"{CHECK} Added {member.mention} to the anti-spam whitelist.",
            color=GREEN)
        await ctx.send(embed=em)

    @anti_spam.command(
        name='unwhitelist',
        aliases=['enablefor', 'track', 'blacklist'],
        description='Adds a member to the anti-spam whitelist. If they spam, the automod will ignore them.'
    )
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def unwhitelist_antispamspam(self, ctx, member: discord.Member):
        data = await self.bot.config.find_one({"_id": ctx.guild.id})
        try:
            if not data['spam_whitelist']:
                em = discord.Embed(
                    description=f"{ERROR} There are no whitelists in this guild.",
                    colour=RED)
                return await ctx.send(embed=em)

            else:
                whitelist = data['spam_whitelist']

        except KeyError or TypeError:
            em = discord.Embed(
                description=f"{ERROR} There are no whitelists in this guild.",
                colour=RED)
            return await ctx.send(embed=em)

        if member.id not in whitelist:
            em = discord.Embed(
                description=f"{ERROR} {member.mention} is not whitelisted.",
                colour=RED)
            return await ctx.send(embed=em)

        whitelist.remove(member.id)

        await self.bot.config.update_one({"_id": ctx.guild.id},
                                         {'$set': {"spam_whitelist": whitelist}}, upsert=True)
        em = discord.Embed(
            description=f"{CHECK} Removed {member.mention} from the anti-spam whitelist.",
            color=GREEN)
        await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(AutoMod(bot))
