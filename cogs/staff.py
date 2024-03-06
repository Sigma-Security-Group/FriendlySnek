import re
import json

from datetime import datetime, timezone
from discord import utils, Embed, Color
from discord.ext import commands  # type: ignore
from unidecode import unidecode

from secret import DEBUG
from constants import *
from __main__ import log, cogsReady
if DEBUG:
    from constants.debug import *

class Staff(commands.Cog):
    """Staff Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Staff"), flush=True)
        cogsReady["staff"] = True

    def _getMember(self, searchTerm: str) -> discord.Member | None:
        """Searches for a discord.Member - supports a lot of different serach terms.

        Parameters:
        searchTerm (str): Search query for a discord.Member.

        Returns:
        discord.Member | None: Returns a discord.Member if found, otherwise None.
        """
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff _getMember: guild is None")
            return None

        member = None
        for member_ in guild.members:
            if searchTerm.replace("<", "").replace("@", "").replace("!", "").replace(">", "").isdigit() and int(searchTerm.replace("<", "").replace("@", "").replace("!", "").replace(">", "")) == member_.id:
                """ Mentions, IDs """
                member = member_
                break
            elif (searchTerm == member_.display_name.lower()) or (isinstance(member_.global_name, str) and searchTerm == member_.global_name.lower()) or (searchTerm == member_.name.lower()) or (searchTerm == member_.mention.lower()) or (searchTerm == member_.name.lower() + "#" + member_.discriminator) or (searchTerm == member_.mention.lower().replace("<@", "<@!")) or (searchTerm == member_.mention.lower().replace("<@!", "<@")) or (searchTerm.isdigit() and int(searchTerm) == member_.discriminator):
                """ Display names, name, raw name """
                member = member_
                break
            elif (searchTerm in member_.display_name.lower()) or (searchTerm in member_.name.lower()) or (searchTerm in member_.mention.lower()) or (searchTerm in member_.mention.lower().replace("<@", "<@!")) or (searchTerm in member_.mention.lower().replace("<@!", "<@")):
                """ Parts of name """
                member = member_
        return member

    @commands.command(name="getmember")
    @commands.has_any_role(UNIT_STAFF, SNEK_LORD)
    async def getMember(self, ctx: commands.Context, *, member: str) -> None:
        """Get detailed information about a guild member."""
        targetMember = self._getMember(member)
        if targetMember is None:
            await ctx.send(f"No member found for search term: `{member}`")
            return

        embed = Embed(description=targetMember.mention, color=targetMember.color)
        avatar = targetMember.avatar if targetMember.avatar else targetMember.display_avatar
        embed.set_author(icon_url=targetMember.display_avatar, name=targetMember)
        embed.set_thumbnail(url=avatar)
        embed.add_field(name="Joined", value="`Unknown`" if targetMember.joined_at is None else utils.format_dt(targetMember.joined_at, style="f"), inline=True)
        embed.add_field(name="Registered", value=utils.format_dt(targetMember.created_at, style="f"), inline=True)

        roles = [role.mention for role in targetMember.roles]  # Fetch all member roles
        roles.pop(0)  # Remove @everyone role
        roles = roles[::-1]  # Reverse the list
        embed.add_field(name=f"Roles [{len(targetMember.roles) - 1}]", value=" ".join(roles) if len(roles) > 0 else "None", inline=False)

        KEY_PERMISSIONS = {
            "Administrator": targetMember.guild_permissions.administrator,
            "Manage Server": targetMember.guild_permissions.manage_guild,
            "Manage Roles": targetMember.guild_permissions.manage_roles,
            "Manage Channels": targetMember.guild_permissions.manage_channels,
            "Manage Messages": targetMember.guild_permissions.manage_messages,
            "Manage Webhooks": targetMember.guild_permissions.manage_webhooks,
            "Manage Nicknames": targetMember.guild_permissions.manage_nicknames,
            "Manage Emojis": targetMember.guild_permissions.manage_emojis,
            "Kick Members": targetMember.guild_permissions.kick_members,
            "Ban Members": targetMember.guild_permissions.ban_members,
            "Mention Everyone": targetMember.guild_permissions.mention_everyone
        }

        PERMISSIONS = [name for name, perm in KEY_PERMISSIONS.items() if perm]
        if len(PERMISSIONS) > 0:
            embed.add_field(name="Key Permissions", value=", ".join(PERMISSIONS), inline=False)

        if targetMember.id == targetMember.guild.owner_id:
            embed.add_field(name="Acknowledgements", value="Server Owner", inline=False)

        embed.set_footer(text=f"ID: {targetMember.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

    @commands.command(name="purge")
    @commands.has_any_role(UNIT_STAFF, SNEK_LORD)
    async def purgeMessagesFromMember(self, ctx: commands.Context, *, member: str) -> None:
        """Purges all messages from a specific member."""
        tagetMember = self._getMember(member)
        if tagetMember is None:
            log.info(f"No member found for search term: {member}")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff purgeMessagesFromMember: guild is None")
            return

        log.critical(f"\n---------\n{ctx.author.display_name} ({ctx.author}) is purging all messages from {member}: {tagetMember.display_name} ({tagetMember})\n---------")
        embed = Embed(title="Purging messages", description=f"Member: {tagetMember.mention}\nThis may take a while!", color=Color.orange())
        embed.set_footer(text=f"ID: {tagetMember.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

        for channel in guild.text_channels:
            log.debug(f"Purging {tagetMember.display_name} ({tagetMember}) messages in {channel.mention}.")
            try:
                await channel.purge(limit=None, check=lambda m: m.author.id == tagetMember.id)
            except (discord.Forbidden, discord.HTTPException):
                log.warning(f"Could not purge {tagetMember.display_name} ({tagetMember}) messages from {channel.mention}!")
        log.info(f"Done purging {tagetMember.display_name} ({tagetMember}) messages!")
        embed = Embed(title="✅ Messages purged", description=f"Member: {tagetMember.mention}", color=Color.green())
        embed.set_footer(text=f"ID: {tagetMember.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

    @commands.command(name="lastactivity")
    @commands.has_any_role(UNIT_STAFF, SNEK_LORD)
    async def lastActivity(self, ctx: commands.Context, pingStaff: str = "yes") -> None:
        """Get last activity (message) for all members."""
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff lastactivity: guild is None")
            return

        log.info(f"Analyzing members' last activity")
        embed = Embed(title="Analyzing members' last activity", color=Color.orange())
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

        lastMessagePerMember = {member: None for member in guild.members}
        embed = Embed(title="Channel checking", color=Color.orange())
        embed.add_field(name="Channel", value="Loading...", inline=True)
        embed.add_field(name="Progress", value="0 / 0", inline=True)
        embed.set_footer(text=f"Run by: {ctx.author}")
        msg = await ctx.send(embed=embed)
        textChannels = len(guild.text_channels)
        for i, channel in enumerate(guild.text_channels, 1):
            embed.set_field_at(0, name="Channel", value=f"{channel.mention}", inline=True)
            embed.set_field_at(1, name="Progress", value=f"{i} / {textChannels}", inline=True)
            await msg.edit(embed=embed)
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
        log.info("Message searching done!")
        embed = Embed(title="✅ Channel checking", color=Color.green())
        embed.set_footer(text=f"Run by: {ctx.author}")
        embed.timestamp = datetime.now()
        await msg.edit(embed=embed)
        lastActivityPerMember = [(f"{member.display_name} ({member})", f"{member.mention}\n{utils.format_dt(lastMessage.created_at, style='F')}\n[Last Message]({lastMessage.jump_url})" if lastMessage is not None else f"{member.mention}\nNot Found!")
        for member, lastMessage in sorted(lastMessagePerMember.items(), key=lambda x: x[1].created_at if x[1] is not None else datetime(1970, 1, 1).replace(tzinfo=timezone.utc))]
        for i in range(0, len(lastActivityPerMember), 25):
            embed = Embed(title=f"Last activity per member ({i + 1} - {min(i + 25, len(lastActivityPerMember))} / {len(lastActivityPerMember)})", color=Color.dark_green())
            for j in range(i, min(i + 25, len(lastActivityPerMember))):
                embed.add_field(name=lastActivityPerMember[j][0], value=lastActivityPerMember[j][1], inline=False)
            await ctx.send(embed=embed)
        if pingStaff.lower() in ("y", "ye", "yes", "ping"):
            roleUnitStaff = guild.get_role(UNIT_STAFF)
            await ctx.send(f"{'' if roleUnitStaff is None else roleUnitStaff.mention} Last activity analysis has finished!")

    @commands.command(name="lastactivitymember")
    @commands.has_any_role(UNIT_STAFF, SNEK_LORD)
    async def lastActivityForMember(self, ctx: commands.Context, *, member: str) -> None:
        """Get last activity (message) for a specific member."""
        targetMember = self._getMember(member)
        if targetMember is None:
            log.info(f"No member found for search term: {member}!")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff lastactivitymember: guild is None")
            return

        lastMessage = None
        for channel in guild.text_channels:
            try:
                lastMessageInChannel = await channel.history(limit=None).find(lambda m: m.author.id == targetMember.id)
                if lastMessageInChannel is None:
                    continue
                if lastMessage is None or lastMessageInChannel.created_at > lastMessage.created_at:
                    lastMessage = lastMessageInChannel
            except Exception:
                log.warning(f"Could not search messages from channel #{channel.name}!")
        log.debug("Done searching messages!")
        if lastMessage is None:
            embed = Embed(title="❌ Last activity", description=f"Activity not found!\nMember: {targetMember.mention}", color=Color.red())
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)
        else:
            embed = Embed(title="✅ Last activity", description=f"Activity found: {utils.format_dt(lastMessage.created_at.timestamp(), style='F')}!\nMember: {targetMember.mention}", color=Color.green())
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)

    @commands.command(name="promote")
    @commands.has_any_role(UNIT_STAFF, SNEK_LORD)
    async def promote(self, ctx: commands.Context, *, member: str) -> None:
        """Promote a member to the next rank."""
        targetMember = self._getMember(member)
        if targetMember is None:
            log.info(f"No member found for search term: {member}!")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff promote: guild is None")
            return

        for role in targetMember.roles:
            if role.id in PROMOTIONS:
                newRole = guild.get_role(PROMOTIONS[role.id])
                if newRole is None:
                    log.exception("Staff promote: newRole is None")
                    return

                # Promote member to Technician if they are a SME
                if newRole.id == OPERATOR:
                    isSME = False
                    for role_ in targetMember.roles:
                        if role_.id in SME_ROLES:
                            isSME = True
                            break
                    if isSME:
                        newRole = guild.get_role(TECHNICIAN)
                log.info(f"Promoting {targetMember.display_name} ({targetMember}) from {role} to {newRole}!")
                await targetMember.remove_roles(role)
                await targetMember.add_roles(newRole)
                embed = Embed(title="✅ Member promoted", description=f"{targetMember.mention} promoted from {role.mention} to {newRole.mention}!", color=Color.green())
                embed.set_footer(text=f"ID: {targetMember.id}")
                embed.timestamp = datetime.now()
                await ctx.send(embed=embed)
                break

        else:
            log.info(f"No promotion possible for {targetMember.display_name} ({targetMember})!")
            embed = Embed(title="❌ No possible promotion", description=f"Member: {targetMember.mention}", color=Color.red())
            embed.set_footer(text=f"ID: {targetMember.id}")
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)

    @commands.command(name="demote")
    @commands.has_any_role(UNIT_STAFF, SNEK_LORD)
    async def demote(self, ctx: commands.Context, *, member: str) -> None:
        """Demote a member to the previous rank."""
        targetMember = self._getMember(member)
        if targetMember is None:
            log.info(f"No member found for search term: {member}")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff promote: guild is None")
            return

        for role in targetMember.roles:
            if role.id in DEMOTIONS:
                newRole = guild.get_role(DEMOTIONS[role.id])
                if newRole is None:
                    log.exception("Staff promote: newRole is None")
                    return

                log.info(f"Demoting {targetMember.display_name} ({targetMember}) from {role} to {newRole}!")
                await targetMember.remove_roles(role)
                await targetMember.add_roles(newRole)
                embed = Embed(title="✅ Member demoted", description=f"{targetMember.mention} demoted from {role.mention} to {newRole.mention}!", color=Color.green())
                embed.set_footer(text=f"ID: {targetMember.id}")
                embed.timestamp = datetime.now()
                await ctx.send(embed=embed)
                break

        else:
            log.info(f"No demotion possible for {targetMember.display_name} ({targetMember})!")
            embed = Embed(title="❌ No possible demotion", description=f"Member: {targetMember.mention}", color=Color.red())
            embed.set_footer(text=f"ID: {targetMember.id}")
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)

    @commands.command(name="searchmodlogs")
    @commands.has_any_role(UNIT_STAFF, SNEK_LORD)
    async def searchModLogs(self, ctx: commands.Context, *, member: str) -> None:
        """ Fetch all occurrences ances in the moderation log related to a member. """
        channelStaffChat = self.bot.get_channel(STAFF_CHAT)
        channelModerationLog = self.bot.get_channel(MODERATION_LOG)
        if not isinstance(channelStaffChat, discord.TextChannel) or not isinstance(channelModerationLog, discord.TextChannel):
            log.exception("Staff searchmodlogs: channelStaffChat or channelModerationLog not discord.TextChannel")
            return

        targetMember = self._getMember(member)
        if targetMember is None:
            log.info(f"No member found for search term: {member}")
            log.debug(f"Searching Moderation Logs for search term: {member}")
            await channelStaffChat.send(f"Searching Moderation Logs for search term: {member}")
            messageLinksList = []
            numMessages = 0
            async for message in channelModerationLog.history(limit=None):
                numMessages += 1
                if member in message.content.lower():
                    messageLinksList.append(message.jump_url)
            log.debug(f"Checked {numMessages} message{'s' * (numMessages != 1)}")
            if len(messageLinksList) > 0:
                messageLinks = "\n".join(messageLinksList[::-1])
                await channelStaffChat.send(f"Moderation Logs related to search term: {member}\n{messageLinks}")
            else:
                await channelStaffChat.send(f"No Moderation Logs related to search term: {member}")
            return


        log.debug(f"Searching Moderation Logs for {targetMember.display_name} ({targetMember})")
        await channelStaffChat.send(f"Searching Moderation Logs for {targetMember.display_name} ({targetMember})")
        messageLinksList = []
        numMessages = 0
        async for message in channelModerationLog.history(limit=None):
            numMessages += 1
            try:
                if (targetMember.display_name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(targetMember.display_name.lower()) - 1]) and not re.match(r"\w", message.content.lower()[message.content.lower().index(targetMember.display_name.lower()) + len(targetMember.display_name)])) or\
                    (targetMember.name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(targetMember.name.lower()) - 1]) and not re.match(r"\w", message.content.lower()[message.content.lower().index(targetMember.name.lower()) + len(targetMember.name)])) or\
                    (targetMember.mention in message.content and not re.match(r"\w", message.content[message.content.index(targetMember.mention) - 1]) and not re.match(r"\w", message.content[message.content.index(targetMember.mention) + len(targetMember.mention)])) or\
                    (targetMember.mention.replace("<@", "<@!") in message.content and not re.match(r"\w", message.content[message.content.index(targetMember.mention.replace("<@", "<@!")) - 1]) and not re.match(r"\w", message.content[message.content.index(targetMember.mention.replace("<@", "<@!")) + len(targetMember.mention.replace("<@", "<@!"))])) or\
                    (targetMember.mention.replace("<@!", "<@") in message.content and not re.match(r"\w", message.content[message.content.index(targetMember.mention.replace("<@!", "<@")) - 1]) and not re.match(r"\w", message.content[message.content.index(targetMember.mention.replace("<@!", "<@")) + len(targetMember.mention.replace("<@!", "<@"))])) or\
                    str(targetMember.id) in message.content:
                    messageLinksList.append(message.jump_url)
            except Exception:
                try:
                    if (targetMember.display_name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(targetMember.display_name.lower()) - 1])) or\
                        (targetMember.name.lower() in message.content.lower() and not re.match(r"\w", message.content.lower()[message.content.lower().index(targetMember.name.lower()) - 1])) or\
                        (targetMember.mention in message.content and not re.match(r"\w", message.content[message.content.index(targetMember.mention) - 1])) or\
                        (targetMember.mention.replace("<@", "<@!") in message.content and not re.match(r"\w", message.content[message.content.index(targetMember.mention.replace("<@", "<@!")) - 1])) or\
                        (targetMember.mention.replace("<@!", "<@") in message.content and not re.match(r"\w", message.content[message.content.index(targetMember.mention.replace("<@!", "<@")) - 1])) or\
                        str(targetMember.id) in message.content:
                        messageLinksList.append(message.jump_url)
                except Exception:
                    log.exception(f"Message:\n\n{message.content}\n")
        log.debug(f"Checked {numMessages} message{'s' * (numMessages != 1)}")
        if len(messageLinksList) > 0:
            messageLinks = "\n".join(messageLinksList[::-1])
            await channelStaffChat.send(f"Moderation Logs related to {targetMember.display_name} ({targetMember}):\n{messageLinks}")
        else:
            await channelStaffChat.send(f"No Moderation Logs related to {targetMember.display_name} ({targetMember})")

    @commands.command(name="disablerolereservation")
    @commands.has_any_role(UNIT_STAFF, SNEK_LORD)
    async def disableRoleReservation(self, ctx: commands.Context, *, member: str) -> None:
        """Add member to role reservation blacklist."""
        targetMember = self._getMember(member)
        if targetMember is None:
            log.info(f"No member found for search term: {member}")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff disableRoleReservation: guild is None")
            return

        log.info(f"{targetMember.display_name} (id: {targetMember.id}) was added to role reservation blacklist by {ctx.author.display_name} (id: {ctx.author.id})")

        with open(ROLE_RESERVATION_BLACKLIST_FILE) as f:
            blacklist = json.load(f)
        if all(member["id"] != targetMember.id for member in blacklist):
            blacklist.append({"id": targetMember.id, "name": targetMember.display_name, "timestamp": datetime.now().timestamp(), "staffId": ctx.author.id, "staffName": ctx.author.display_name})
            with open(ROLE_RESERVATION_BLACKLIST_FILE, "w") as f:
                json.dump(blacklist, f, indent=4)
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            for event in events:
                for reservableRole in event["reservableRoles"]:
                    if event["reservableRoles"][reservableRole] == targetMember.id:
                        event["reservableRoles"][reservableRole] = None
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
            await self.bot.get_cog("Schedule").updateSchedule()

        embed = Embed(title="✅ Member blacklisted", description=f"{targetMember.mention} is no longer allowed to reserve roles!", color=Color.green())
        embed.set_footer(text=f"ID: {targetMember.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

    @commands.command(name="enablerolereservation")
    @commands.has_any_role(UNIT_STAFF, SNEK_LORD)
    async def enableRoleReservation(self, ctx: commands.Context, *, member: str) -> None:
        """Remove member from role reservation blacklist."""
        targetMember = self._getMember(member)
        if targetMember is None:
            log.info(f"No member found for search term: {member}")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff enableRoleReservation: guild is None")
            return

        log.info(f"{targetMember.display_name} (id: {targetMember.id}) was removed from role reservation blacklist by {ctx.author.display_name} (id: {ctx.author.id})")

        with open(ROLE_RESERVATION_BLACKLIST_FILE) as f:
            blacklist = json.load(f)
        removedMembers = [member for member in blacklist if member["id"] == targetMember.id]
        for member in removedMembers:
            blacklist.remove(member)
        if removedMembers:
            with open(ROLE_RESERVATION_BLACKLIST_FILE, "w") as f:
                json.dump(blacklist, f, indent=4)

        embed = Embed(title="✅ Member removed from blacklist", description=f"{targetMember.mention} is now allowed to reserve roles!", color=Color.green())
        embed.set_footer(text=f"ID: {targetMember.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)



    # Advisor command
    @commands.command(name="verify")
    @commands.has_any_role(UNIT_STAFF, SERVER_HAMSTER, ADVISOR, RECRUITER, SNEK_LORD)
    async def verify(self, ctx: commands.Context, *, member: str) -> None:
        """Verifies a Prospect (passed interview)."""
        targetMember = self._getMember(member)
        if targetMember is None:
            log.info(f"No member found for search term: {member}")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff verify: guild is None")
            return

        roleProspect = guild.get_role(PROSPECT)
        roleVerified = guild.get_role(VERIFIED)
        roleMember = guild.get_role(MEMBER)
        if roleProspect is None or roleVerified is None or roleMember is None:
            log.exception("Staff verify: roleProspect, roleVerified, roleMember is None")
            return

        if roleProspect not in targetMember.roles:
            await ctx.send(embed=Embed(title="❌ Failed to verify", description=f"{targetMember.mention} not a {roleProspect.mention}", color=Color.red()))
            return

        reason = "User verified"
        await targetMember.remove_roles(roleProspect, reason=reason)
        await targetMember.add_roles(roleVerified, reason=reason)
        await targetMember.add_roles(roleMember, reason=reason)
        embed = Embed(title="✅ Member verified", description=f"{targetMember.mention} verified!", color=Color.green())
        embed.set_footer(text=f"ID: {targetMember.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)



    # Hampter command
    @commands.command(name="gibcmdline")
    @commands.has_any_role(UNIT_STAFF, SERVER_HAMSTER, GUINEA_PIG, SNEK_LORD)
    async def gibcmdline(self, ctx: commands.Context) -> None:
        """Generates commandline from attached HTML modpack file."""

        # No modpack / no HTML
        if len(ctx.message.attachments) == 0 or ctx.message.attachments[0].content_type is None or not ctx.message.attachments[0].content_type.startswith("text/html"):
            await ctx.send(":moyai: I need a modpack file to generate the cmdline :moyai:")
            return

        # Modpack provided
        msg = await ctx.send("https://tenor.com/view/rat-rodent-vermintide-vermintide2-skaven-gif-20147931")
        attachmentInBytes = await ctx.message.attachments[0].read()  # Returns bytes
        html = attachmentInBytes.decode("utf-8")  # Convert to str

        mods = re.findall(r'(?<=<td data-type="DisplayName">).+(?=<\/td>)', html)

        alphanumerics = re.compile(r"[\W_]+", re.UNICODE)
        cmdline = ";".join(sorted(["@" + re.sub(alphanumerics, "", mod) for mod in mods], key=str.casefold))  # Casefold = caseinsensitive
        cmdline = unidecode(cmdline)

        await msg.edit(content=f"```{cmdline}```")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Staff(bot))
