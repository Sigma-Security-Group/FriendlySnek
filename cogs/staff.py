import re
import json
from datetime import datetime
from tqdm import tqdm
import discord
from discord import Embed
from discord.ext import commands

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *

class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        log.debug("Staff Cog is ready", flush=True)
        cogsReady["staff"] = True
    
    def _getMember(self, searchTerm):
        member = None
        for member_ in self.bot.get_guild(SERVER).members:
            if searchTerm.replace("<", "").replace("@", "").replace("!", "").replace(">", "").isdigit() and int(searchTerm.replace("<", "").replace("@", "").replace("!", "").replace(">", "")) == member_.id:
                member = member_
                break
            if searchTerm == member_.display_name or searchTerm == member_.name or searchTerm == member_.mention or searchTerm == member_.mention.replace("<@", "<@!") or searchTerm == member_.mention.replace("<@!", "<@") or (searchTerm.isdigit() and int(searchTerm) == member_.discriminator):
                member = member_
                break
            if searchTerm.lower() == member_.display_name.lower() or searchTerm.lower() == member_.name.lower() or searchTerm.lower() == member_.mention.lower() or searchTerm.lower() == member_.mention.lower().replace("<@", "<@!") or searchTerm.lower() == member_.mention.lower().replace("<@!", "<@") or (searchTerm.isdigit() and int(searchTerm) == member_.discriminator):
                member = member_
                break
            if searchTerm in member_.display_name or searchTerm in member_.name or searchTerm in member_.mention or searchTerm in member_.mention.replace("<@", "<@!") or searchTerm in member_.mention.replace("<@!", "<@"):
                member = member_
            if searchTerm.lower() in member_.display_name.lower() or searchTerm.lower() in member_.name.lower() or searchTerm.lower() in member_.mention.lower() or searchTerm.lower() in member_.mention.lower().replace("<@", "<@!") or searchTerm.lower() in member_.mention.lower().replace("<@!", "<@"):
                member = member_
        return member
    
    @commands.command(help="Get a member")
    @commands.has_any_role(UNIT_STAFF)
    async def getMember(self, ctx, *, searchTerm):
        """
        Get a member
        """
        member = self._getMember(searchTerm)
        if member is None:
            await ctx.send(f"No member found for search term: {searchTerm}")
        else:
            await ctx.send(f"Member found: {member.display_name} ({member.name}#{member.discriminator})")
    
    @commands.command(help="Purge all messages from a member")
    @commands.has_any_role(UNIT_STAFF)
    async def purgeMessagesFromMember(self, ctx, *, searchTerm):
        """
        Purge all messages from a member
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.warning(f"No member found for search term: {searchTerm}")
            await ctx.send(f"No member found for search term: {searchTerm}")
            return
        log.critical(f"\n---------\n{ctx.author.display_name} ({ctx.author.name}#{ctx.author.discriminator}) is purging all messages from {searchTerm}: {member.display_name} ({member.name}#{member.discriminator})\n---------")
        await ctx.send(f"Purging messages by {member.display_name} ({member.name}#{member.discriminator}). This may take a while")
        guild = self.bot.get_guild(SERVER)
        for channel in guild.text_channels:
            log.debug(f"Purging {channel}")
            try:
                await channel.purge(limit=None, check=lambda m: m.author.id == member.id)
            except Exception:
                log.warning(f"Could not purge messages from channel {channel}")
        log.debug("Done purging messages")
        await ctx.send(f"Done purging messages by {member.display_name} ({member.name}#{member.discriminator})")
    
    @commands.command(help="Get last activity for all members")
    @commands.has_any_role(UNIT_STAFF)
    async def lastActivity(self, ctx):
        """
        Get last activity for all members
        """
        log.debug(f"Analyzing members' last activity")
        await ctx.send(f"Analyzing members' last activity. This may take a while")
        guild = self.bot.get_guild(SERVER)
        lastMessagePerMember = {member: None for member in guild.members}
        msg = await ctx.send("Checking channel:")
        for i, channel in enumerate(guild.text_channels, 1):
            await msg.edit(content=f"Checking channel: {channel.name} ({i} / {len(guild.text_channels)})")
            membersNotChecked = set(channel.members)
            async for message in channel.history(limit=None):
                for member in set(membersNotChecked):
                    if member.bot:
                        membersNotChecked.discard(member)
                        continue
                    if lastMessagePerMember[member] is not None and lastMessagePerMember[member].created_at > message.created_at:
                        membersNotChecked.discard(member)
                if message.author in membersNotChecked:
                    membersNotChecked.discard(message.author)
                    if lastMessagePerMember[message.author] is None or message.created_at > lastMessagePerMember[message.author].created_at:
                        lastMessagePerMember[message.author] = message
                if len(membersNotChecked) == 0:
                    break
        log.debug("Done searching messages")
        await msg.edit(content=f"Done searching messages")
        # lastActivityPerMember = [(f"{member.display_name} ({member.name}#{member.discriminator})", f"<t:{round(lastMessage.created_at.timestamp())}:F>\n{lastMessage.jump_url}" if lastMessage is not None else "NOT FOUND")
        lastActivityPerMember = [(f"{member.display_name} ({member.name}#{member.discriminator})", f"{member.mention}\n<t:{round(lastMessage.created_at.timestamp())}:F>\n{lastMessage.jump_url}" if lastMessage is not None else f"{member.mention}\nNOT FOUND")
                                 for member, lastMessage in sorted(lastMessagePerMember.items(), key=lambda x: x[1].created_at if x[1] is not None else datetime(1970, 1, 1))]
        for i in range(0, len(lastActivityPerMember), 25):
            embed = Embed(title=f"Last activity per member ({i + 1} - {min(i + 25, len(lastActivityPerMember))} / {len(lastActivityPerMember)})")
            for j in range(i, min(i + 25, len(lastActivityPerMember))):
                embed.add_field(name=lastActivityPerMember[j][0], value=lastActivityPerMember[j][1], inline=False)
            await ctx.send(embed=embed)
        await ctx.send(f"{guild.get_role(UNIT_STAFF).mention} Last activity analysis has finished")
    
    @commands.command(help="Get last activity for member")
    @commands.has_any_role(UNIT_STAFF)
    async def lastActivityForMember(self, ctx, *, searchTerm):
        """
        Get last activity for member
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.warning(f"No member found for search term: {searchTerm}")
            await ctx.send(f"No member found for search term: {searchTerm}")
            return
        await ctx.send(f"Searching messages by {member.display_name} ({member.name}#{member.discriminator})")
        guild = self.bot.get_guild(SERVER)
        lastMessage = None
        for channel in guild.text_channels:
            try:
                lastMessageInChannel = await channel.history(limit=None).find(lambda m: m.author.id == member.id)
                if lastMessageInChannel is None:
                    continue
                if lastMessage is None or lastMessageInChannel.created_at > lastMessage.created_at:
                    lastMessage = lastMessageInChannel
            except Exception:
                log.warning(f"Could not search messages from channel {channel}")
        log.debug("Done searching messages")
        if lastMessage is None:
            await ctx.send(f"Last activity by {member.display_name} ({member.name}#{member.discriminator}): Not found")
        else:
            await ctx.send(f"Last activity by {member.display_name} ({member.name}#{member.discriminator}): <t:{round(lastMessage.created_at.timestamp())}:F>")
    
    @commands.command(help="Promote a member to the next rank")
    @commands.has_any_role(UNIT_STAFF)
    async def promote(self, ctx, *, searchTerm):
        """
        Promote a member to the next rank
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.warning(f"No member found for search term: {searchTerm}")
            await ctx.send(f"No member found for search term: {searchTerm}")
            return
        guild = self.bot.get_guild(SERVER)
        for role in member.roles:
            if role.id in PROMOTIONS:
                newRole = guild.get_role(PROMOTIONS[role.id])
                # Turn promotions to operator into promotions to technician if member is SME
                if newRole.id == OPERATOR:
                    isSME = False
                    for role_ in member.roles:
                        if role_.id in SME_ROLES:
                            isSME = True
                            break
                    if isSME:
                        newRole = guild.get_role(TECHNICIAN)
                log.info(f"Promoting {member.display_name} from {role} to {newRole}")
                await member.remove_roles(role)
                await member.add_roles(newRole)
                break
        else:
            log.warning(f"No promotion possible for {member.display_name}")

    @commands.command(help="Demote a member to the previous rank")
    @commands.has_any_role(UNIT_STAFF)
    async def demote(self, ctx, *, searchTerm):
        """
        Demote a member to the previous rank
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.warning(f"No member found for search term: {searchTerm}")
            await ctx.send(f"No member found for search term: {searchTerm}")
            return
        guild = self.bot.get_guild(SERVER)
        for role in member.roles:
            if role.id in DEMOTIONS:
                newRole = guild.get_role(DEMOTIONS[role.id])
                log.info(f"Demoting {member.display_name} from {role} to {newRole}")
                await member.remove_roles(role)
                await member.add_roles(newRole)
                break
        else:
            log.warning(f"No demotion possible for {member.display_name}")
    
    @commands.command(help="Search through the moderation logs")
    @commands.has_any_role(UNIT_STAFF)
    async def searchModLogs(self, ctx, *, searchTerm):
        """
        Demote a member to the previous rank
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.warning(f"No member found for search term: {searchTerm}")
            log.debug(f"Searching Moderation Logs for search term: {searchTerm}")
            await self.bot.get_channel(STAFF_CHAT).send(f"Searching Moderation Logs for search term: {searchTerm}")
            messageLinksList = []
            numMessages = 0
            async for message in self.bot.get_channel(MODERATION_LOG).history(limit=None):
                numMessages += 1
                if searchTerm.lower() in message.content.lower():
                    messageLinksList.append(message.jump_url)
            log.debug(f"Checked {numMessages} message{'s' * (numMessages != 1)}")
            if len(messageLinksList) > 0:
                messageLinks = "\n".join(messageLinksList[::-1])
                await self.bot.get_channel(STAFF_CHAT).send(f"Moderation Logs related to search term: {searchTerm}\n{messageLinks}")
            else:
                await self.bot.get_channel(STAFF_CHAT).send(f"No Moderation Logs related to search term: {searchTerm}")
        else:
            log.debug(f"Searching Moderation Logs for {member.display_name}({member.name}#{member.discriminator})")
            await self.bot.get_channel(STAFF_CHAT).send(f"Searching Moderation Logs for {member.display_name}({member.name}#{member.discriminator})")
            messageLinksList = []
            numMessages = 0
            async for message in self.bot.get_channel(MODERATION_LOG).history(limit=None):
                numMessages += 1
                try:
                    if (member.display_name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.display_name.lower()) - 1]) and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.display_name.lower()) + len(member.display_name)])) or\
                       (member.name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.name.lower()) - 1]) and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.name.lower()) + len(member.name)])) or\
                       (member.mention in message.content and not re.match(r"\w", message.content[message.content.index(member.mention) - 1]) and not re.match(r"\w", message.content[message.content.index(member.mention) + len(member.mention)])) or\
                       (member.mention.replace('<@', '<@!') in message.content and not re.match(r"\w", message.content[message.content.index(member.mention.replace('<@', '<@!')) - 1]) and not re.match(r"\w", message.content[message.content.index(member.mention.replace('<@', '<@!')) + len(member.mention.replace('<@', '<@!'))])) or\
                       (member.mention.replace('<@!', '<@') in message.content and not re.match(r"\w", message.content[message.content.index(member.mention.replace('<@!', '<@')) - 1]) and not re.match(r"\w", message.content[message.content.index(member.mention.replace('<@!', '<@')) + len(member.mention.replace('<@!', '<@'))])) or\
                       str(member.id) in message.content:
                        messageLinksList.append(message.jump_url)
                except Exception:
                    try:
                        if (member.display_name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.display_name.lower()) - 1])) or\
                           (member.name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.name.lower()) - 1])) or\
                           (member.mention in message.content and not re.match(r"\w", message.content[message.content.index(member.mention) - 1])) or\
                           (member.mention.replace('<@', '<@!') in message.content and not re.match(r"\w", message.content[message.content.index(member.mention.replace('<@', '<@!')) - 1])) or\
                           (member.mention.replace('<@!', '<@') in message.content and not re.match(r"\w", message.content[message.content.index(member.mention.replace('<@!', '<@')) - 1])) or\
                           str(member.id) in message.content:
                            messageLinksList.append(message.jump_url)
                    except Exception:
                        log.exception(f"Message:\n\n{message.content}\n")
            log.debug(f"Checked {numMessages} message{'s' * (numMessages != 1)}")
            if len(messageLinksList) > 0:
                messageLinks = "\n".join(messageLinksList[::-1])
                await self.bot.get_channel(STAFF_CHAT).send(f"Moderation Logs related to {member.display_name}({member.name}#{member.discriminator}):\n{messageLinks}")
            else:
                await self.bot.get_channel(STAFF_CHAT).send(f"No Moderation Logs related to {member.display_name}({member.name}#{member.discriminator})")

def setup(bot):
    bot.add_cog(Staff(bot))