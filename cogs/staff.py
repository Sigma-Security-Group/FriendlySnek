from secret import DEBUG
import re
from datetime import datetime

from discord import Embed, Color
from discord.ext import commands

from constants import *

from __main__ import log, cogsReady
if DEBUG:
    from constants.debug import *

class Staff(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Staff"), flush=True)
        cogsReady["staff"] = True

    def _getMember(self, searchTerm: str):
        """
            X.

            Parameters:
            searchTerm (str): X.

            Returns:
            X.
        """
        searchTerm = searchTerm.lower()
        member = None
        for member_ in self.bot.get_guild(GUILD_ID).members:
            if searchTerm.replace("<", "").replace("@", "").replace("!", "").replace(">", "").isdigit() and int(searchTerm.replace("<", "").replace("@", "").replace("!", "").replace(">", "")) == member_.id:
                """ Mentions, IDs """
                member = member_
                break
            elif (searchTerm == member_.display_name.lower()) or (searchTerm == member_.name.lower()) or (searchTerm == member_.mention.lower()) or (searchTerm == member_.name.lower() + "#" + member_.discriminator) or (searchTerm == member_.mention.lower().replace("<@", "<@!")) or (searchTerm == member_.mention.lower().replace("<@!", "<@")) or (searchTerm.isdigit() and int(searchTerm) == member_.discriminator):
                """ Display names, name, raw name """
                member = member_
                break
            elif (searchTerm in member_.display_name.lower()) or (searchTerm in member_.name.lower()) or (searchTerm in member_.mention.lower()) or (searchTerm in member_.mention.lower().replace("<@", "<@!")) or (searchTerm in member_.mention.lower().replace("<@!", "<@")):
                """ Parts of name """
                member = member_
        return member

    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def getMember(self, ctx, *, searchTerm) -> None:
        """
            Get a member.

            Parameters:
            interaction: X.
            searchTerm: X.

            Returns:
            X.
        """
        member = self._getMember(searchTerm)
        if member is None:
            await ctx.response.send_message(f"No member found for search term: {searchTerm}")
        else:
            await ctx.response.send_message(f"Member found: {member.display_name} ({member})")

    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def purgeMessagesFromMember(self, ctx, *, searchTerm) -> None:
        """
            Purge all messages from a member.

            Parameters:
            interaction: X.
            searchTerm: X.

            Returns:
            None.
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.warning(f"No member found for search term: {searchTerm}")
            await ctx.response.send_message(f"No member found for search term: {searchTerm}")
            return
        log.critical(f"\n---------\n{ctx.user.display_name} ({ctx.author}) is purging all messages from {searchTerm}: {member.display_name} ({member})\n---------")
        await ctx.response.send_message(f"Purging messages by {member.display_name} ({member}). This may take a while")
        guild = self.bot.get_guild(GUILD_ID)
        for channel in guild.text_channels:
            log.debug(f"Purging {channel}")
            try:
                await channel.purge(limit=None, check=lambda m: m.author.id == member.id)
            except Exception:
                log.warning(f"Could not purge messages from channel {channel}")
        log.debug("Done purging messages")
        await ctx.followup.send(f"Done purging messages by {member.display_name} ({member})")

    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def lastActivity(self, ctx, pingStaff="yes") -> None:
        """
            Get last activity for all members.

            Parameters:
            interaction: X.
            pingStaff: X.

            Returns:
            None.
        """
        log.debug(f"Analyzing members' last activity")
        await ctx.response.send_message(f"Analyzing members' last activity. This may take a while")
        guild = self.bot.get_guild(GUILD_ID)
        lastMessagePerMember = {member: None for member in guild.members}
        msg = await ctx.followup.send("Checking channel:")
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
        lastActivityPerMember = [(f"{member.display_name} ({member})", f"{member.mention}\n<t:{round(lastMessage.created_at.timestamp())}:F>\n{lastMessage.jump_url}" if lastMessage is not None else f"{member.mention}\nNOT FOUND")
        for member, lastMessage in sorted(lastMessagePerMember.items(), key=lambda x: x[1].created_at if x[1] is not None else datetime(1970, 1, 1))]
        for i in range(0, len(lastActivityPerMember), 25):
            embed = Embed(title=f"Last activity per member ({i + 1} - {min(i + 25, len(lastActivityPerMember))} / {len(lastActivityPerMember)})")
            for j in range(i, min(i + 25, len(lastActivityPerMember))):
                embed.add_field(name=lastActivityPerMember[j][0], value=lastActivityPerMember[j][1], inline=False)
            await ctx.followup.send(embed=embed)
        if pingStaff.lower() in ("y", "yes", "ping"):
            await ctx.followup.send(f"{guild.get_role(UNIT_STAFF).mention} Last activity analysis has finished")

    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def lastActivityForMember(self, ctx, *, searchTerm) -> None:
        """
            Get last activity for member.

            Parameters:
            interaction: X.
            searchTerm: X.

            Returns:
            None.
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.warning(f"No member found for search term: {searchTerm}")
            await ctx.response.send_message(f"No member found for search term: {searchTerm}")
            return
        await ctx.response.send_message(f"Searching messages by {member.display_name} ({member})")
        guild = self.bot.get_guild(GUILD_ID)
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
            await ctx.followup.send(f"Last activity by {member.display_name} ({member}): Not found")
        else:
            await ctx.followup.send(f"Last activity by {member.display_name} ({member}): <t:{round(lastMessage.created_at.timestamp())}:F>")

    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def promote(self, ctx, *, searchTerm:str) -> None:
        """
            Promote a member to the next rank.

            Parameters:
            ctx: The Discord context.
            searchTerm (str): Search query for discord user.

            Returns:
            None.
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.info(f"No member found for search term: {searchTerm}!")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{searchTerm}`", color=Color.red()))
            return
        guild = self.bot.get_guild(GUILD_ID)
        for role in member.roles:
            if role.id in PROMOTIONS:
                newRole = guild.get_role(PROMOTIONS[role.id])
                # Promote member to Technician if they are a SME
                if newRole.id == SPECIALIST:
                    isSME = False
                    for role_ in member.roles:
                        if role_.id in SME_ROLES:
                            isSME = True
                            break
                    if isSME:
                        newRole = guild.get_role(TECHNICIAN)
                log.info(f"Promoting {member.display_name} ({member}) from {role} to {newRole}!")
                await member.remove_roles(role)
                await member.add_roles(newRole)
                embed = Embed(title="✅ Member promoted", description=f"{member.mention} promoted from `{role}` to `{newRole}`!", color=Color.green())
                embed.set_footer(text=f"ID: {member.id}")
                embed.timestamp = datetime.now()
                await ctx.send(embed=embed)
                break
        else:
            log.warning(f"No promotion possible for {member.display_name} ({member})!")
            embed = Embed(title="❌ No possible promotion", description=f"Member: {member.mention}", color=Color.red())
            embed.set_footer(text=f"ID: {member.id}")
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)

    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def demote(self, interaction, *, searchTerm) -> None:
        """
            Demote a member to the previous rank.

            Parameters:
            interaction: X.
            searchTerm: X.

            Returns:
            None.
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.warning(f"No member found for search term: {searchTerm}")
            await interaction.response.send_message(f"No member found for search term: {searchTerm}")
            return
        guild = self.bot.get_guild(GUILD_ID)
        for role in member.roles:
            if role.id in DEMOTIONS:
                newRole = guild.get_role(DEMOTIONS[role.id])
                log.info(f"Demoting {member.display_name} from {role} to {newRole}")
                await member.remove_roles(role)
                await member.add_roles(newRole)
                break
        else:
            log.warning(f"No demotion possible for {member.display_name}")

    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def searchModLogs(self, interaction, *, searchTerm) -> None:
        """
            Search through the moderation logs.

            Parameters:
            interaction: X.
            searchTerm: X.

            Returns:
            None.
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
            log.debug(f"Searching Moderation Logs for {member.display_name} ({member})")
            await self.bot.get_channel(STAFF_CHAT).send(f"Searching Moderation Logs for {member.display_name} ({member})")
            messageLinksList = []
            numMessages = 0
            async for message in self.bot.get_channel(MODERATION_LOG).history(limit=None):
                numMessages += 1
                try:
                    if (member.display_name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.display_name.lower()) - 1]) and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.display_name.lower()) + len(member.display_name)])) or\
                       (member.name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.name.lower()) - 1]) and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.name.lower()) + len(member.name)])) or\
                       (member.mention in message.content and not re.match(r"\w", message.content[message.content.index(member.mention) - 1]) and not re.match(r"\w", message.content[message.content.index(member.mention) + len(member.mention)])) or\
                       (member.mention.replace("<@", "<@!") in message.content and not re.match(r"\w", message.content[message.content.index(member.mention.replace("<@", "<@!")) - 1]) and not re.match(r"\w", message.content[message.content.index(member.mention.replace("<@", "<@!")) + len(member.mention.replace("<@", "<@!"))])) or\
                       (member.mention.replace("<@!", "<@") in message.content and not re.match(r"\w", message.content[message.content.index(member.mention.replace("<@!", "<@")) - 1]) and not re.match(r"\w", message.content[message.content.index(member.mention.replace("<@!", "<@")) + len(member.mention.replace("<@!", "<@"))])) or\
                       str(member.id) in message.content:
                        messageLinksList.append(message.jump_url)
                except Exception:
                    try:
                        if (member.display_name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.display_name.lower()) - 1])) or\
                           (member.name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(member.name.lower()) - 1])) or\
                           (member.mention in message.content and not re.match(r"\w", message.content[message.content.index(member.mention) - 1])) or\
                           (member.mention.replace("<@", "<@!") in message.content and not re.match(r"\w", message.content[message.content.index(member.mention.replace("<@", "<@!")) - 1])) or\
                           (member.mention.replace("<@!", "<@") in message.content and not re.match(r"\w", message.content[message.content.index(member.mention.replace("<@!", "<@")) - 1])) or\
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

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Staff(bot))
