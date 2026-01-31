import re, json, os, discord, logging

from datetime import datetime, timezone
from discord.ext import commands  # type: ignore
from unidecode import unidecode
from textwrap import wrap

from utils import Utils
from secret import DEBUG
from constants import *
if DEBUG:
    from constants.debug import *
from cogs.snekcoin import Snekcoin
from random import randint

log = logging.getLogger("FriendlySnek")

class Staff(commands.Cog):
    """Staff Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Staff"))
        self.bot.cogsReady["staff"] = True

    @staticmethod
    def _getMember(searchTerm: str, guild: discord.Guild) -> discord.Member | None:
        """Searches for a discord.Member - supports a lot of different serach terms.

        Parameters:
        searchTerm (str): Search query for a discord.Member.

        Returns:
        discord.Member | None: Returns a discord.Member if found, otherwise None.
        """
        member = None
        searchTerm = searchTerm.strip()
        searchTermLower = searchTerm.lower()
        searchTermId = searchTerm.replace("<", "").replace("@", "").replace("!", "").replace(">", "")
        for member_ in guild.members:
            # Mentions, IDs
            if searchTermId.isdigit() and int(searchTermId) == member_.id:
                member = member_
                break

            # Display name, global name, username, raw mention forms, and discriminator checks
            elif (
                # Match server-specific display name (nickname)
                searchTermLower == member_.display_name.lower()
                # Match Discord global display name (if it exists)
                or (isinstance(member_.global_name, str)
                    and searchTermLower == member_.global_name.lower())
                # Match account username
                or searchTermLower == member_.name.lower()
                # Match direct mention string (<@id>)
                or searchTermLower == member_.mention.lower()
                # Match legacy username#discriminator format
                or searchTermLower == member_.name.lower() + "#" + member_.discriminator
                # Handle mention variant with/without "!" (<@id> vs <@!id>)
                or searchTermLower == member_.mention.lower().replace("<@", "<@!")
                or searchTermLower == member_.mention.lower().replace("<@!", "<@")
            ):
                member = member_
                break


            # Parts of name
            elif (
                # Partial match inside server nickname (display name)
                searchTermLower in member_.display_name.lower()
                # Partial match inside account username
                or searchTermLower in member_.name.lower()
                # Partial match inside mention string (<@id>)
                or searchTermLower in member_.mention.lower()
                # Handle mention variant with "!" (<@!id>)
                or searchTermLower in member_.mention.lower().replace("<@", "<@!")
                # Handle mention variant without "!" (<@id>)
                or searchTermLower in member_.mention.lower().replace("<@!", "<@")
            ):
                member = member_

        return member

    @commands.command(name="getmember")
    async def getMember(self, ctx: commands.Context, *, member: str = commands.parameter(description="Target member")) -> None:
        """Get detailed information about a guild member."""
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Staff getmember: ctx.guild not discord.Guild")
            return
        targetMember = Staff._getMember(member, ctx.guild)
        if targetMember is None:
            await ctx.send(f"No member found for search term: `{member}`")
            return

        embed = discord.Embed(description=targetMember.mention, color=targetMember.color)
        avatar = targetMember.avatar if targetMember.avatar else targetMember.display_avatar
        embed.set_author(icon_url=targetMember.display_avatar, name=targetMember)
        embed.set_thumbnail(url=avatar)
        embed.add_field(name="Joined", value="`Unknown`" if targetMember.joined_at is None else discord.utils.format_dt(targetMember.joined_at, style="f"), inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(targetMember.created_at, style="f"), inline=True)

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
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def purgeMessagesFromMember(self, ctx: commands.Context, *, member: str = commands.parameter(description="Target member")) -> None:
        """Purges all messages from a specific member."""
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Staff purgeMessagesFromMember: ctx.guild not discord.Guild")
            return
        tagetMember = Staff._getMember(member, ctx.guild)
        if tagetMember is None:
            log.warning(f"{ctx.author.id} [{ctx.author.display_name}] No member found for search term '{member}'")
            await ctx.send(embed=discord.Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=discord.Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff purgeMessagesFromMember: guild is None")
            return

        log.info(f"\n---------\n{ctx.author.id} [{ctx.author.display_name}] Is purging all messages from '{member}' {tagetMember.display_name} [{tagetMember}]\n---------")
        embed = discord.Embed(title="Purging messages", description=f"Member: {tagetMember.mention}\nThis may take a while!", color=discord.Color.orange())
        embed.set_footer(text=f"ID: {tagetMember.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

        for channel in guild.text_channels:
            log.debug(f"Purging {tagetMember.id} [{tagetMember.display_name}] messages in {channel.mention}")
            try:
                await channel.purge(limit=None, check=lambda m: m.author.id == tagetMember.id)
            except (discord.Forbidden, discord.HTTPException):
                log.warning(f"Failed to purge {tagetMember.id} [{tagetMember.display_name}] messages from {channel.mention}")
        log.info(f"Done purging messages from {tagetMember.id} [{tagetMember.display_name}]")
        embed = discord.Embed(title="✅ Messages purged", description=f"Member: {tagetMember.mention}", color=discord.Color.green())
        embed.set_footer(text=f"ID: {tagetMember.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

    @commands.command(name="lastactivity")
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def lastActivity(self, ctx: commands.Context, pingStaff: str = commands.parameter(default="yes", description="If staff is pinged when finished")) -> None:
        """Get last activity (message) for all members."""
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff lastactivity: guild is None")
            return

        log.info(f"{ctx.author.id} [{ctx.author.display_name}] Fetches last activity for all members")
        embed = discord.Embed(title="Analyzing members' last activity", color=discord.Color.orange())
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

        lastMessagePerMember = {member: None for member in guild.members}
        embed = discord.Embed(title="Channel checking", color=discord.Color.orange())
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

        embed = discord.Embed(title="✅ Channel checking", color=discord.Color.green())
        embed.set_footer(text=f"Run by: {ctx.author}")
        embed.timestamp = datetime.now()
        await msg.edit(embed=embed)
        lastActivityPerMember = [(f"{member.display_name} ({member})", f"{member.mention}\n{discord.utils.format_dt(lastMessage.created_at, style='F')}\n[Last Message]({lastMessage.jump_url})" if lastMessage is not None else f"{member.mention}\nNot Found!")
        for member, lastMessage in sorted(lastMessagePerMember.items(), key=lambda x: x[1].created_at if x[1] is not None else datetime(1970, 1, 1, tzinfo=timezone.utc))]
        for i in range(0, len(lastActivityPerMember), 25):
            embed = discord.Embed(title=f"Last activity per member ({i + 1} - {min(i + 25, len(lastActivityPerMember))} / {len(lastActivityPerMember)})", color=discord.Color.dark_green())
            for j in range(i, min(i + 25, len(lastActivityPerMember))):
                embed.add_field(name=lastActivityPerMember[j][0], value=lastActivityPerMember[j][1], inline=False)
            await ctx.send(embed=embed)
        if pingStaff.lower() in ("y", "ye", "yes", "ping"):
            roleUnitStaff = guild.get_role(UNIT_STAFF)
            await ctx.send(f"{'' if roleUnitStaff is None else roleUnitStaff.mention} Last activity analysis has finished!")

    @commands.command(name="lastactivitymember")
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def lastActivityForMember(self, ctx: commands.Context, *, member: str = commands.parameter(description="Target member")) -> None:
        """Get last activity (message) for a specific member."""
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Staff lastactivitymember: ctx.guild not discord.Guild")
            return
        targetMember = Staff._getMember(member, ctx.guild)
        if targetMember is None:
            log.warning(f"{ctx.author.id} [{ctx.author.display_name}] No member found for search term '{member}'")
            await ctx.send(embed=discord.Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=discord.Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff lastactivitymember: guild is None")
            return

        log.info(f"{ctx.author.id} [{ctx.author.display_name}] Fetches last activity for {targetMember.id} [{targetMember.display_name}]")
        lastMessage = None
        for channel in guild.text_channels:
            try:
                lastMessageInChannel = await channel.history(limit=None).find(lambda m: m.author.id == targetMember.id)
                if lastMessageInChannel is None:
                    continue
                if lastMessage is None or lastMessageInChannel.created_at > lastMessage.created_at:
                    lastMessage = lastMessageInChannel
            except Exception:
                log.warning(f"Staff lastactivitymember: Failed to search messages from channel #{channel.name}")

        if lastMessage is None:
            embed = discord.Embed(title="❌ Last activity", description=f"Activity not found!\nMember: {targetMember.mention}", color=discord.Color.red())
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="✅ Last activity", description=f"Activity found: {discord.utils.format_dt(lastMessage.created_at, style='F')}!\nMember: {targetMember.mention}", color=discord.Color.green())
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)

    @commands.command(name="promote")
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def promote(self, ctx: commands.Context, *, member: str = commands.parameter(description="Target member")) -> None:
        """Promote a member to the next rank."""
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Staff promote: ctx.guild not discord.Guild")
            return
        targetMember = Staff._getMember(member, ctx.guild)
        if targetMember is None:
            log.warning(f"Staff promote: No member found for search term '{member}'")
            await ctx.send(embed=discord.Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=discord.Color.red()))
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

                log.info(f"{ctx.author.id} [{ctx.author.display_name}] Promotes {targetMember.id} [{targetMember.display_name}] from '{role}' to '{newRole}'")
                await targetMember.remove_roles(role)
                await targetMember.add_roles(newRole)
                embed = discord.Embed(title="✅ Member promoted", description=f"{targetMember.mention} promoted from {role.mention} to {newRole.mention}!", color=discord.Color.green())
                embed.set_footer(text=f"ID: {targetMember.id}")
                embed.timestamp = datetime.now()
                await ctx.send(embed=embed)
                break

        else:
            log.warning(f"{ctx.author.id} [{ctx.author.display_name}] No promotion possible for {targetMember.id} [{targetMember.display_name}]")
            embed = discord.Embed(title="❌ No possible promotion", description=f"Member: {targetMember.mention}", color=discord.Color.red())
            embed.set_footer(text=f"ID: {targetMember.id}")
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)

    @commands.command(name="demote")
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def demote(self, ctx: commands.Context, *, member: str = commands.parameter(description="Target member")) -> None:
        """Demote a member to the previous rank."""
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Staff demote: ctx.guild not discord.Guild")
            return
        targetMember = Staff._getMember(member, ctx.guild)
        if targetMember is None:
            log.warning(f"{ctx.author.id} [{ctx.author.display_name}] No member found for search term '{member}'")
            await ctx.send(embed=discord.Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=discord.Color.red()))
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

                log.info(f"{ctx.author.id} [{ctx.author.display_name}] Demoting {targetMember.id} [{targetMember.display_name}] from '{role}' to '{newRole}'")
                await targetMember.remove_roles(role)
                await targetMember.add_roles(newRole)
                embed = discord.Embed(title="✅ Member demoted", description=f"{targetMember.mention} demoted from {role.mention} to {newRole.mention}!", color=discord.Color.green())
                embed.set_footer(text=f"ID: {targetMember.id}")
                embed.timestamp = datetime.now()
                await ctx.send(embed=embed)
                break

        else:
            log.warning(f"{ctx.author.id} [{ctx.author.display_name}] No demotion possible for {targetMember.id} [{targetMember.display_name}]")
            embed = discord.Embed(title="❌ No possible demotion", description=f"Member: {targetMember.mention}", color=discord.Color.red())
            embed.set_footer(text=f"ID: {targetMember.id}")
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)

    @staticmethod
    def _match_member_reference(message_content: str, targetMember: discord.Member) -> str | None:
        """
        Returns a string if the message_content contains a reference to targetMember.
        The string is the search term that matched.
        Returns None if no match.

        The following types of references are checked:
        display_name (case-insensitive, word-boundary)
        exact name (case-insensitive, word-boundary)
        mention (<@id>, boundary-checked)
        mention variant (<@!id>, boundary-checked)
        alternate mention variant (<@id> from <@!id>), boundary-checked
        raw id anywhere in content
        """
        s = message_content
        s_lower = s.lower()
        display = targetMember.display_name.lower()
        name = targetMember.name.lower()
        mention = targetMember.mention
        mention_alt1 = mention.replace("<@", "<@!")
        mention_alt2 = mention.replace("<@!", "<@")
        id_str = str(targetMember.id)

        def boundary_ok(text: str, start: int, end: int) -> bool:
            # ensure char before/after are not word chars (if present)
            if start > 0 and re.match(r"\w", text[start - 1]):
                return False
            if end < len(text) and re.match(r"\w", text[end]):
                return False
            return True

        # display_name (case-insensitive)
        idx = s_lower.find(display)
        if idx != -1 and boundary_ok(s_lower, idx, idx + len(display)):
            return display

        # exact name (case-insensitive)
        idx = s_lower.find(name)
        if idx != -1 and boundary_ok(s_lower, idx, idx + len(name)):
            return name

        # mentions / variants (check raw message, not lowered)
        idx = s.find(mention)
        if idx != -1 and boundary_ok(s, idx, idx + len(mention)):
            return mention

        idx = s.find(mention_alt1)
        if idx != -1 and boundary_ok(s, idx, idx + len(mention_alt1)):
            return mention_alt1

        idx = s.find(mention_alt2)
        if idx != -1 and boundary_ok(s, idx, idx + len(mention_alt2)):
            return mention_alt2

        # raw id anywhere
        if id_str in s:
            return id_str

        return None

    @staticmethod
    def _getModLogContext(message: discord.Message, search_term: str) -> str:
        """Gets the context of a moderation log message for a specific search term.

        Parameters:
        message (discord.Message): The moderation log message.
        search_term (str): The search term that matched the message.

        Returns:
        str: The context of the moderation log message ("Reporter", "Subject", "Handler", or "Mentioned").
        """
        preSearch = message.content[:message.content.lower().index(search_term)-2].split("\n")[-1].lstrip("*").strip()
        if preSearch.startswith("Reporter"):
            return "`Reporter`"
        if preSearch.startswith("Subject"):
            return "**`Subject`**"
        if preSearch.startswith("Handler"):
            return "`Handler`"
        return "`Mention`"

    @commands.command(name="searchmodlogs")
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def searchModLogs(self, ctx: commands.Context, *, search_term: str = commands.parameter(description="Search term for a user/member. Surround in quotes for raw search")) -> None:
        """Fetch all occurrencesances in the moderation log related to a member."""
        # TODO
        # Implement filtering by context. E.g. only show logs where user was Reporter
        channelModerationLog = self.bot.get_channel(MODERATION_LOG)
        if not isinstance(channelModerationLog, discord.TextChannel):
            log.exception("Staff searchmodlogs: channelModerationLog not discord.TextChannel")
            return

        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Staff searchmodlogs: ctx.guild not discord.Guild")
            return


        log.info(f"{ctx.author.id} [{ctx.author.display_name}] Searching moderation logs for '{search_term}'")

        # Force no member search if surrounded by quotes
        forceRawSearch = False
        if (search_term.startswith('"') and search_term.endswith('"')) or (search_term.startswith("'") and search_term.endswith("'")):
            forceRawSearch = True
            search_term = search_term[1:-1]

        # Check if search term matches a member
        resultsMember = []
        targetMember = Staff._getMember(search_term, ctx.guild)
        if targetMember and not forceRawSearch:
            log.debug(f"Serach mod logs, found member '{targetMember.id} [{targetMember.display_name}]'")
            await ctx.send(f"Searching moderation logs for `{targetMember.display_name}` (`{targetMember}`)...")

            async for message in channelModerationLog.history(limit=None, oldest_first=False):
                memberReference = Staff._match_member_reference(message.content, targetMember)
                if not memberReference:
                    continue

                context = Staff._getModLogContext(message, memberReference)
                resultsMember.append({
                    "id": message.id,
                    "url": message.jump_url,
                    "context": context
                })

        # Raw string serach: serach_term
        resultsRawString = []
        if not targetMember:
            await ctx.send(f"Searching moderation logs for `{search_term}`...")

        async for message in channelModerationLog.history(limit=None, oldest_first=False):
            if search_term not in message.content.lower():
                continue

            context = Staff._getModLogContext(message, search_term)
            resultsRawString.append({
                "id": message.id,
                "url": message.jump_url,
                "context": context
            })

        # Filter out raw string results that are already in member results
        if resultsMember:
            memberResultIds = {msg["id"] for msg in resultsMember}
            resultsRawString = [msg for msg in resultsRawString if msg["id"] not in memberResultIds]


        # Nothing found
        if not resultsMember and not resultsRawString:
            embed = discord.Embed(
                title="❌ No moderation logs found",
                description=f"No moderation logs related to search term: `{search_term}`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        # Generate result messages
        genEnumList = lambda msgLinksList: [
            f"{i+1}. {msg['url']}: {msg['context']}"
            for i, msg in enumerate(msgLinksList[::-1])
        ]
        results = ""
        if resultsMember:
            results += f"**Member {targetMember.mention}**\n"
            results += "\n".join(genEnumList(resultsMember))

        if resultsMember and resultsRawString:
            results += "\n\n"

        if resultsRawString:
            results += f"**Raw string `{search_term}`**\n"
            results += "\n".join(genEnumList(resultsRawString))

        # Check Discord limits and make multiple embeds if needed
        resultParts = []
        currentPart = ""
        resultList = results.split("\n") if len(results) > DISCORD_LIMITS["message_embed"]["embed_description"] else [results]
        for line in resultList:
            if len(currentPart) + len(line) + 1 > DISCORD_LIMITS["message_embed"]["embed_description"]:
                resultParts.append(currentPart)
                currentPart = line
            else:
                if currentPart:
                    currentPart += "\n"
                currentPart += line
        if currentPart:
            resultParts.append(currentPart)

        for i, resultPart in enumerate(resultParts, 1):
            embed = discord.Embed(
                title=f"Moderation Log Search " +  (f"(Part {i}/{len(resultParts)})" if len(resultParts) > 1 else ""),
                description=resultPart,
                color=discord.Color.green()
            )
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)
        return

    @commands.command(name="disablerolereservation")
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def disableRoleReservation(self, ctx: commands.Context, *, member: str = commands.parameter(description="Target member")) -> None:
        """Disable role reservation for specified member."""
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Staff disablerolereservation: ctx.guild not discord.Guild")
            return
        targetMember = Staff._getMember(member, ctx.guild)
        if targetMember is None:
            log.info(f"{ctx.author.id} [{ctx.author.display_name}] No member found for search term '{member}'")
            await ctx.send(embed=discord.Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=discord.Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff disableRoleReservation: guild is None")
            return

        log.info(f"{ctx.author.id} [{ctx.author.display_name}] Added {targetMember.id} [{targetMember.display_name}] to role reservation blacklist")

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
            await self.bot.get_cog("Schedule").updateSchedule(guild)

        embed = discord.Embed(title="✅ Member blacklisted", description=f"{targetMember.mention} is no longer allowed to reserve roles!", color=discord.Color.green())
        embed.set_footer(text=f"ID: {targetMember.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

    @commands.command(name="enablerolereservation")
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def enableRoleReservation(self, ctx: commands.Context, *, member: str = commands.parameter(description="Target member")) -> None:
        """Enable role reservation for specified member."""
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Staff enablerolereservation: ctx.guild not discord.Guild")
            return
        targetMember = Staff._getMember(member, ctx.guild)
        if targetMember is None:
            log.info(f"{ctx.author.id} [{ctx.author.display_name}] No member found for search term '{member}'")
            await ctx.send(embed=discord.Embed(title="❌ No member found", description=f"Searched for: `{member}`", color=discord.Color.red()))
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff enableRoleReservation: guild is None")
            return

        log.info(f"{ctx.author.id} [{ctx.author.display_name}] Removed {targetMember.id} [{targetMember.display_name}] from role reservation blacklist")

        with open(ROLE_RESERVATION_BLACKLIST_FILE) as f:
            blacklist = json.load(f)
        removedMembers = [member for member in blacklist if member["id"] == targetMember.id]
        for member in removedMembers:
            blacklist.remove(member)
        if removedMembers:
            with open(ROLE_RESERVATION_BLACKLIST_FILE, "w") as f:
                json.dump(blacklist, f, indent=4)

        embed = discord.Embed(title="✅ Member removed from blacklist", description=f"{targetMember.mention} is now allowed to reserve roles!", color=discord.Color.green())
        embed.set_footer(text=f"ID: {targetMember.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

    @commands.command(name="smebigbrother")
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def smeBigBrother(self, ctx: commands.Context) -> None:
        """Summarize each SMEs activity last 6 months for Unit Staff."""
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff smeBigBrother: guild is None")
            return

        from cogs.botTasks import BotTasks
        await BotTasks.smeBigBrother(guild, True)

    @discord.app_commands.command(name="ban")
    @discord.app_commands.describe(
        user="Target user to be banned (by mention, ID, or username).",
        reason="Reason for banning the user.",
        delete_message_days="Number of days of messages to delete from the user."
    )
    @discord.app_commands.choices(delete_message_days=[
        discord.app_commands.Choice(name="0 days", value=0),
        discord.app_commands.Choice(name="1 day", value=86400),
        discord.app_commands.Choice(name="7 days", value=604800)
    ])
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_STAFF)
    async def ban(self, interaction: discord.Interaction, user: discord.User, reason: str, delete_message_days: int) -> None:
        """Ban a user from the Discord server."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Attempting to ban {user.id} [{user.display_name}] from the server")

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff ban: guild is None")
            return

        # Prevent banning yourself or the bot
        if user.id == interaction.user.id:
            embed = discord.Embed(title="❌ Ban failed", description="You cannot ban yourself!", color=discord.Color.red())
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if self.bot.user and user.id == self.bot.user.id:
            embed = discord.Embed(title="❌ Ban failed", description="You cannot ban me!", color=discord.Color.red())
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Check if user is already banned
        banEntry = None
        try:
            banEntry = await guild.fetch_ban(user)
        except Exception as e:
            banEntry = e

        # Already banned
        if isinstance(banEntry, discord.BanEntry):
            log.info(f"{interaction.user.id} [{interaction.user.display_name}] Tried to ban already banned user {user.id} [{user.display_name}]")
            embed = discord.Embed(title="❌ Ban failed", description=f"{user.mention} is already banned!", color=discord.Color.red())
            embed.add_field(name="Moderator", value=banEntry.user.mention if banEntry.user else "Unknown")
            if banEntry.reason:
                embed.add_field(name="Reason", value=banEntry.reason)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Error fetching ban status
        if isinstance(banEntry, Exception) and not isinstance(banEntry, discord.NotFound):
            log.exception(f"Staff ban: Failed to fetch ban for user {user.id} [{user.display_name}] - {banEntry}")
            embed = discord.Embed(title="❌ Ban failed", description="An error occurred while checking ban status!", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return


        # Check Permissions.ban_members
        if self.bot.user is None:
            log.exception("Staff ban: bot user is None")
            return
        botMember = guild.get_member(self.bot.user.id)
        if botMember is None or not botMember.guild_permissions.ban_members:
            log.exception(f"{interaction.user.id} [{interaction.user.display_name}] Failed to ban {user.id} [{user.display_name}] - insufficient permissions")
            embed = discord.Embed(
                title="❌ Ban failed",
                description="Failed to ban user! Insufficient permissions.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # DM banned user with appeal information
        roleUnitStaff = guild.get_role(UNIT_STAFF)
        if roleUnitStaff is None:
            log.exception("Staff ban: roleUnitStaff is None")
            return

        staffMembers = "\n".join(f"- {staff.display_name} ({staff})" for staff in roleUnitStaff.members)
        dm = f"You have been banned from {guild.name} for the following reason:\n> {reason}\n\nYou may appeal your ban by contacting a member of the Unit Staff:\n{staffMembers}\n\nAll appeals are subject to Unit Staff review."
        try:
            await user.send(dm)
        except Exception as e:
            log.warning(f"Failed to send ban DM to {user.id} [{user.display_name}] - {e}")


        # Ban user
        if isinstance(banEntry, discord.NotFound):
            try:
                await guild.ban(
                    user,
                    reason=f"Banned by {interaction.user} via /ban command.\nReason: {reason}",
                    delete_message_seconds=delete_message_days
                )
            except:
                # Failed to ban
                log.warning(f"{interaction.user.id} [{interaction.user.display_name}] Failed to ban {user.id} [{user.display_name}]")
                embed = discord.Embed(
                    title="❌ Ban failed",
                    description=f"Failed to ban {user.mention}!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # Successfully banned
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Banned {user.id} [{user.display_name}] from the server")
        embed = discord.Embed(
            title="✅ User banned",
            description=f"{user.mention} has been banned from the server!",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"User ID: {user.id}")
        embed.timestamp = datetime.now()

        await interaction.followup.send(embed=embed, ephemeral=True)


    @discord.app_commands.command(name="unban")
    @discord.app_commands.describe(user_id="Target user ID to be unbanned.")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_STAFF)
    async def unban(self, interaction: discord.Interaction, user_id: str) -> None:
        """Unban a user from the Discord server."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Attempting to unban user ID {user_id} from the server")

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff unban: guild is None")
            return

        errMsg = ""
        try:
            user = self.bot.get_user(int(user_id))
            if user is None:
                errMsg = f"No user found with ID: `{user_id}`"
                raise Exception("User not found")

            await guild.unban(user, reason=f"Unbanned by {interaction.user} via /unban command")
        except ValueError:
            errMsg = f"Invalid user ID: `{user_id}`"
        except discord.NotFound:
            errMsg = f"User `{user_id}` is not banned!"
        except discord.Forbidden:
            log.exception(f"{interaction.user.id} [{interaction.user.display_name}] Failed to unban {user_id} - insufficient permissions")
            errMsg = f"Insufficient permissions to unban user `{user_id}`!"
        except Exception:
            pass

        # Handle all error cases
        if errMsg:
            embed = discord.Embed(title="❌ Unban failed", description=errMsg, color=discord.Color.red())
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Successfully unbanned
        embed = discord.Embed(
            title="✅ User unbanned",
            description=f"{user.mention} ({user}) has been unbanned from the server!",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"User ID: {user_id}")
        embed.timestamp = datetime.now()
        await interaction.followup.send(embed=embed, ephemeral=True)


    # Kick Command
    @discord.app_commands.command(name="kick")
    @discord.app_commands.describe(user="Target user to be kicked (by mention, ID, or username).", reason="Reason for kicking the user.")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_STAFF)
    async def kick(self, interaction: discord.Interaction, user: discord.User, reason: str | None = None) -> None:
        """Kick a user from the Discord server."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Attempting to kick {user.id} [{user.display_name}] from the server")

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff kick: guild is None")
            return

        # Prevent kicking yourself or the bot
        if user.id == interaction.user.id:
            embed = discord.Embed(title="❌ Kick failed", description="You cannot kick yourself!", color=discord.Color.red())
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if self.bot.user and user.id == self.bot.user.id:
            embed = discord.Embed(title="❌ Kick failed", description="You cannot kick me!", color=discord.Color.red())
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Check if user is a member of the guild
        try:
            member = await guild.fetch_member(user.id)
        except discord.NotFound:
            embed = discord.Embed(title="❌ Kick failed", description=f"{user.mention} is not a member of this server!", color=discord.Color.red())
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        except Exception as e:
            log.exception(f"Staff kick: Failed to fetch member {user.id} [{user.display_name}] - {e}")
            embed = discord.Embed(title="❌ Kick failed", description="An error occurred while checking member status!", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Check Permissions.kick_members
        if self.bot.user is None:
            log.exception("Staff kick: bot user is None")
            return
        botMember = guild.get_member(self.bot.user.id)
        if botMember is None or not botMember.guild_permissions.kick_members:
            log.exception(f"{interaction.user.id} [{interaction.user.display_name}] Failed to kick {user.id} [{user.display_name}] - insufficient permissions")
            embed = discord.Embed(
                title="❌ Kick failed",
                description="Failed to kick user! Insufficient permissions.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Set default reason
        if reason is None:
            reason = "No reason provided."

        # DM kicked user
        dm = f"You have been kicked from {guild.name} for the following reason:\n> {reason}"
        try:
            await user.send(dm)
        except Exception as e:
            log.warning(f"Failed to send kick DM to {user.id} [{user.display_name}] - {e}")

        # Kick user
        try:
            await guild.kick(user, reason=f"Kicked by {interaction.user} via /kick command.\nReason: {reason}")
        except Exception:
            # Failed to kick
            log.warning(f"{interaction.user.id} [{interaction.user.display_name}] Failed to kick {user.id} [{user.display_name}]")
            embed = discord.Embed(
                title="❌ Kick failed",
                description=f"Failed to kick {user.mention}!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Successfully kicked
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Kicked {user.id} [{user.display_name}] from the server")
        embed = discord.Embed(
            title="✅ User kicked",
            description=f"{user.mention} has been kicked from the server!",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"User ID: {user.id}")
        embed.timestamp = datetime.now()

        # Log in audit log
        auditLogs = guild.get_channel(AUDIT_LOGS)
        if isinstance(auditLogs, discord.TextChannel):
            auditEmbed = discord.Embed(
                title="User Kicked",
                description=f"**User:** {user.mention} (`{user}`)\n**Moderator:** {interaction.user.mention} (`{interaction.user}`)\n**Reason:** {reason}",
                color=discord.Color.orange(),
            )
            auditEmbed.set_footer(text=f"User ID: {user.id}")
            auditEmbed.set_thumbnail(url=user.display_avatar.url)
            auditEmbed.timestamp = datetime.now()
            await auditLogs.send(embed=auditEmbed)

        await interaction.followup.send(embed=embed, ephemeral=True)



    # Hampter command
    @commands.command(name="gibcmdline")
    @commands.has_any_role(*CMD_LIMIT_DATACENTER)
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
        cmdline = wrap(unidecode(cmdline), DISCORD_LIMITS["message_embed"]["message_chars"]-10)

        for index, chunk in enumerate(cmdline):
            if index == 0:
                await msg.edit(content=f"```{chunk}```")
                continue
            await ctx.send(f"```{chunk}```")

    @discord.app_commands.command(name="updatemodpack")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_DATACENTER)
    @discord.app_commands.describe(modpack = "Updated modpack.", sendtoserverinfo = "Optional boolean if sending modpack to #server-info.")
    async def updatemodpack(self, interaction: discord.Interaction, modpack: discord.Attachment, sendtoserverinfo: bool = False) -> None:
        """Update snek mod list, for which mods to check on updates."""

        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Updating modpack id listing")
        # Parse modpack
        html = (await modpack.read()).decode("utf-8")
        modpackIds = [int(id) for id in re.findall(r"(?<=\"https:\/\/steamcommunity\.com\/sharedfiles\/filedetails\/\?id=)\d+", html)]

        # Save output
        with open(GENERIC_DATA_FILE) as f:
            genericData = json.load(f)
        genericData["modpackIds"] = modpackIds
        with open(GENERIC_DATA_FILE, "w") as f:
            json.dump(genericData, f, indent=4)

        # Optionally send
        if sendtoserverinfo:
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("Staff updatemodpack: guild is None")
                return
            channelServerInfo = guild.get_channel(SERVER_INFO)
            if not isinstance(channelServerInfo, discord.TextChannel):
                log.exception("Staff updatemodpack: channelServerInfo not discord.TextChannel")
                return

            await channelServerInfo.send(os.path.splitext(modpack.filename)[0], file=await modpack.to_file())


        mapsDefault = "\n".join(genericData["modpackMaps"]) if "modpackMaps" in genericData else None

        modal = StaffModal(self, f"Modpack updated! Now optionally change maps", f"staff_modal_maps")
        modal.add_item(discord.ui.TextInput(label="Maps (Click \"Cancel\" to not change anything!)", style=discord.TextStyle.long, placeholder="Training Map\nAltis\nVirolahti", default=mapsDefault, required=True))
        await interaction.response.send_modal(modal)
        await interaction.followup.send("Modpack updated!", ephemeral=True)

    # ZIT Feedback command
    @discord.app_commands.command(name="zit-feedback", description="Send feedback for Zeus in Training.")
    @discord.app_commands.describe(zeus="Zeus in Training to submit feedback to")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_ZEUS)
    async def zitfeedback(self, interaction: discord.Interaction, zeus: discord.Member) -> None:
        """Submit feedback for a Zeus in Training (ZiT).

        Creates embed with buttons to open modals for feedback submission.

        Parameters:
        zeus (discord.Member): Target ZiT to receive feedback.
        """
        if zeus.bot:
            embed = discord.Embed(title="❌ Feedback failed", description="You cannot submit feedback for the bot!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if zeus.id == interaction.user.id:
            embed = discord.Embed(title="❌ Feedback failed", description="You cannot submit feedback for yourself!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if all(role.id != ZEUS_IN_TRAINING for role in zeus.roles):
            embed = discord.Embed(title="❌ Feedback failed", description=f"{zeus.mention} is not a Zeus in Training!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="📝 ZiT Feedback",
            description=f"Please fill out the following fields to submit feedback for {zeus.mention}.\n[Red = Mandatory]\n[Blue = Optional]",
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"Submitted by {interaction.user.display_name}")
        for _ in range(5):
            embed.add_field(name="", value="", inline=False)

        viewCFG = {
            "opName": {"label": "Operation Name & Date", "id": "opname", "row": 0, "placeholder": "Operation Honda Civic - YYYY-MM-DD"},
            "wentWell": {"label": "Things Done Well", "id": "wentwell" , "row": 0, "placeholder": "Refer to #zeus-guidelines and Zeus Promotion Criteria Document.\n(Max 1024 characters)"},
            "couldImprove": {"label": "Points for Improvement", "id": "couldimprove", "row": 0, "placeholder": "Refer to #zeus-guidelines and Zeus Promotion Criteria Document.\n(Max 1024 characters)"},
            "additionalComments": {"label": "Additional Comments", "id": "additionalcomments", "row": 0, "placeholder": "Enter any additional comments.\n(Max 1024 characters)"},
            "recommend_yes": {"label": "[Recommend for Full Zeus Tags]", "id": "recommend_yes", "row": 1},
            "recommend_no": {"label": "[Don't Recommended for Full Zeus Tags]", "id": "recommend_no", "row": 1},
            "submit": {"label": "Submit", "id": "submit", "row": 2}
        }

        view = discord.ui.View(timeout=None)

        for id, customId in viewCFG.items():
            view.add_item(StaffButton(
                style = discord.ButtonStyle.danger if id in ["opName", "wentWell", "couldImprove", "recommend_yes", "recommend_no"] else discord.ButtonStyle.primary if id == "additionalComments" else discord.ButtonStyle.success,
                label = customId["label"],
                custom_id = f"staff_button_zitfeedback_{customId['id']}",
                row = customId.get("row", 0),
                disabled = False if id != "submit" else True
            ))

        # Store zeusId in view for later use and initialize required fields
        view.zeusId = zeus.id
        view.requiredFieldsFilled = {
            "opName": None,
            "wentWell": None,
            "couldImprove": None,
            "recommend": None
        }
        view.CFG = viewCFG
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    # Snek Lord command
    @commands.command(name="sneklord")
    @commands.has_any_role(SNEK_LORD)
    async def sneklord(self, ctx: commands.Context) -> None:
        """Snek lord prod test command."""
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Staff sneklord: guild is None")
            return
        for role in guild.roles:
            log.debug(f"ROLE: {role.name} - {hex(role.color.value)}")


@discord.app_commands.guilds(GUILD)
class Recruitment(commands.GroupCog, name="recruitment"):
    """Recruitment related commands."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @discord.app_commands.command(name="interview")
    @discord.app_commands.describe(member = "Target prospect member.")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_INTERVIEW)
    async def interview(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """Helps HR interview a prospect member and decide to verify or deny."""

        await interaction.response.defer(ephemeral=True, thinking=True)  # Ensure message history doesnt expire interaction deadline

        channelRecruitmentAndHR = interaction.guild.get_channel(RECRUITMENT_AND_HR)
        if not isinstance(channelRecruitmentAndHR, discord.TextChannel):
            log.exception("Staff interview: channelRecruitmentAndHR not discord.TextChannel")
            return

        if not isinstance(interaction.user, discord.Member):
            log.exception("Staff interview: interaction.user not discord.Member")
            return

        isAuthorStaff = [True for role in interaction.user.roles if role.id == UNIT_STAFF]
        async for message in channelRecruitmentAndHR.history(limit=1000):
            if message.embeds and message.embeds[0].title == "❌ Prospect denied" and message.embeds[0].footer.text and message.embeds[0].footer.text == f"Prospect ID: {member.id}":
                if isAuthorStaff:
                    embed = discord.Embed(title="⚠️ Prospect denied", description=f"Prospect ({member.mention}) has been denied before. Since you're Unit Staff, you may still continue and override the decision!", color=discord.Color.yellow())
                    embed.set_footer(text=f"Prospect ID: {member.id}")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    break

                # Not staff, cannot interview denied prospect
                embed = discord.Embed(title="❌ Prospect denied", description=f"Prospect ({member.mention}) has already been denied. Only Unit Staff may interview denied prospects!", color=discord.Color.red())
                embed.set_footer(text=f"Prospect ID: {member.id}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # Is staff or not denied before, continue with interview
        view = discord.ui.View(timeout=None)
        view.add_item(StaffButton(style=discord.ButtonStyle.green, label="Verify", custom_id=f"staff_button_interview_verify_{member.id}"))
        view.add_item(StaffButton(style=discord.ButtonStyle.red, label="Deny", custom_id=f"staff_button_interview_deny_{member.id}"))

        interviewQuestions = f"""- Be enthusiastic about sigma and the interview, your energy will set the stage for how our unit operates, if it sounds like you dont care or are disinterested it will affect the quality of the unit in the eyes of the interviewee.
- Be informative to the point and honest, don't sugar-coat things, be straight forward.

1. What year were you born in? (min. ~{datetime.now(timezone.utc).year - 17})
2. Do you have any previous experience with Arma 3 or any milsim game?
 a. Have you been in any other units? What kind of units were they?
3. Have you used Arma 3 mods before?
 b. Please ensure they know how to use the HTML download, and have mods downloaded before newcomer
4. Have you used Teamspeak before?
 c. Help install teamspeak client, and have connected/bookmarked SSG teamspeak server
5. How did you find out about us?
6. Is there a specific role or playstyle you are looking to do with us?
7. Any questions?"""

        embed = discord.Embed(title="Interview Structure", description=interviewQuestions, color=discord.Color.gold())
        embed.set_footer(text=f"Prospect member id: {member.id}")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


    @discord.app_commands.command(name="newcomers")
    @discord.app_commands.describe(member="Target verified member.", rename="New name for the member.")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_INTERVIEW)
    async def newcomers(self, interaction: discord.Interaction, member: discord.Member, rename: str | None = None) -> None:
        """Helps HR onboard a verified member as a newcomer. Grants candidate roles and optionally rename them."""

        await interaction.response.defer(ephemeral=True, thinking=True)

        if not isinstance(interaction.guild, discord.Guild):
            await interaction.followup.send(f"❌ Failed to onboard newcomer: Guild not found.\nPlease contact Unit Staff.", ephemeral=True)
            log.exception("Staff newcomers: interaction.guild not discord.Guild")
            return

        channelRecruitmentAndHR = interaction.guild.get_channel(RECRUITMENT_AND_HR)
        roleCandidate = interaction.guild.get_role(CANDIDATE)
        roleVerified = interaction.guild.get_role(VERIFIED)
        auditLogs = interaction.guild.get_channel(AUDIT_LOGS)

        try:
            if roleCandidate is None:
                raise Exception("roleCandidate is None")
            if roleVerified is None:
                raise Exception("roleVerified is None")
            if not isinstance(channelRecruitmentAndHR, discord.TextChannel):
                raise Exception("channelRecruitmentAndHR not discord.TextChannel")
            if not isinstance(auditLogs, discord.TextChannel):
                raise Exception("auditLogs not discord.TextChannel")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to onboard newcomer: {e}\nPlease contact Unit Staff.", ephemeral=True)
            log.exception(f"Staff newcomers: {e}")
            return

        memberHasRoles = len([True for role in member.roles if role.id == MEMBER or role.id == VERIFIED]) == 2
        if not memberHasRoles:
            unitStaff = interaction.guild.get_role(UNIT_STAFF)
            if not isinstance(unitStaff, discord.Role):
                log.exception("Staff newcomers: unitStaff not discord.Role")
                await interaction.followup.send("❌ Failed to onboard newcomer: Unit Staff role not found.\nPlease contact a server administrator.", ephemeral=True)
                return
            embed = discord.Embed(title="❌ Onboarding failed", description=f"{member.mention} is not a verified member!\n\nPlease contact {unitStaff.mention} to resolve this issue.", color=discord.Color.red())
            embed.set_footer(text=f"User ID: {member.id}")
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        bonus = randint(100, 150)
        auditEmbed = discord.Embed(
            title="Newcomer Onboarded",
            description=f"{member.mention} `({member.name})`\n\n**Onboarded by:** {interaction.user.mention} (`{interaction.user}`)\n**Recruitment Bonus:** 🪙 `{bonus}` SnekCoins",
            color=discord.Color.green(),
        )
        # Rename member
        if rename:
            oldName = member.display_name
            reason = f"Renamed by {interaction.user} via recruitment newcomers command."
            log.info(f"{interaction.user.id} [{interaction.user.display_name}] Renamed {member.id} [{oldName}] to [{rename}] during newcomers process")
            await member.edit(nick=rename, reason=reason)
            auditEmbed.add_field(name="Renamed", value=f"`{oldName}` ➔ `{rename}`", inline=False)
        await member.add_roles(roleCandidate, reason=f"Added by {interaction.user} via recruitment newcomers command.")
        await member.remove_roles(roleVerified, reason=f"Removed by {interaction.user} via recruitment newcomers command.")

        await Snekcoin.updateWallet(interaction.user.id, "money", bonus)

        # Log in audit log
        auditEmbed.set_footer(text=f"User ID: {member.id}")
        auditEmbed.set_thumbnail(url=member.display_avatar.url)
        auditEmbed.timestamp = datetime.now()
        await auditLogs.send(embed=auditEmbed)

        # Confirmation message
        embed = discord.Embed(
            title="✅ Newcomer onboarded",
            description=f"{member.mention} has completed their newcomer workshop!",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Bonus Payout 💰", value=f"{interaction.user.mention} has been awarded a recruitment bonus of 🪙 `{bonus}` SnekCoins for running the newcomers workshop.")
        embed.set_footer(text=f"User ID: {member.id}")
        embed.timestamp = datetime.now()
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Onboarded {member.id} [{member.display_name}] as newcomer")
        await channelRecruitmentAndHR.send(embed=embed)
        await interaction.followup.send(f"Successfully onboarded {member.mention} as a newcomer.\nYou have been awarded a recruitment bonus of 🪙 `{bonus}` SnekCoins.", ephemeral=True)


class StaffButton(discord.ui.Button):
    """Handling all staff buttons."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        customId = interaction.data["custom_id"]

        # Verify prospect from interview
        if customId.startswith("staff_button_interview_verify_"):
            memberId = int(customId.split("_")[-1])

            if not isinstance(interaction.guild, discord.Guild):
                log.exception("StaffButton callback: interaction.guild is not discord.Guild")
                return

            member = interaction.guild.get_member(memberId)
            if not isinstance(member, discord.Member):
                log.exception(f"StaffButton callback: member not discord.Member, id '{memberId}'")
                return

            verifyBonus = randint(20, 50)
            await Snekcoin.updateWallet(interaction.user.id, "money", verifyBonus)

            embed = discord.Embed(title="✅ Member verified", description=f"{member.mention} verified!", color=discord.Color.green())
            embed.add_field(name="Snekcoin Reward", value=f"You have been awarded 🪙 `{verifyBonus}` for interviewing a new member!\nKeep up the good work!", inline=False)
            embed.set_footer(text=f"Verified member id: {member.id}")
            embed.timestamp = datetime.now()
            await interaction.response.send_message(embed=embed, ephemeral=True)

            roleProspect = interaction.guild.get_role(PROSPECT)
            roleVerified = interaction.guild.get_role(VERIFIED)
            roleMember = interaction.guild.get_role(MEMBER)
            if roleProspect is None or roleVerified is None or roleMember is None:
                log.exception("StaffButton callback: roleProspect, roleVerified, roleMember is None")
                return

            reason = "User verified"
            if roleProspect in member.roles:
                await member.remove_roles(roleProspect, reason=reason)
                await member.add_roles(roleVerified, reason=reason)

            await member.add_roles(roleMember, reason=reason)


            # Logging
            channelAuditLogs = interaction.guild.get_channel(AUDIT_LOGS)
            if not isinstance(channelAuditLogs, discord.TextChannel):
                log.exception("StaffButton callback: channelAuditLogs not discord.TextChannel")
                return
            embed = discord.Embed(title="Member verified", description=f"Verified: {member.mention}\nInterviewer: {interaction.user.mention}", color=discord.Color.blue())
            embed.set_footer(text=f"Verified ID: {member.id} | Interviewer ID: {interaction.user.id}")
            embed.timestamp = datetime.now()
            await channelAuditLogs.send(embed=embed)

        # Deny prospect from interview
        if customId.startswith("staff_button_interview_deny_"):
            memberId = int(customId.split("_")[-1])

            member = interaction.guild.get_member(memberId)
            if not isinstance(member, discord.Member):
                log.exception(f"StaffButton callback: member not discord.Member, id '{memberId}'")
                return

            verifyBonus = randint(20, 50)
            await Snekcoin.updateWallet(interaction.user.id, "money", verifyBonus)

            embed = discord.Embed(title="❌ Prospect denied", description=f"{member.mention} denied", color=discord.Color.red())
            embed.add_field(name="Snekcoin Reward", value=f"You have been awarded 🪙 `{verifyBonus}` for interviewing a new member!\nKeep up the good work!", inline=False)
            embed.set_footer(text=f"Member id: {member.id}")
            embed.timestamp = datetime.now()
            await interaction.response.send_message(embed=embed, ephemeral=True)

            # Notify Recruitment-Coordinator
            if not isinstance(interaction.guild, discord.Guild):
                log.exception("StaffButton callback: interaction.guild is not discord.Guild")
                return

            channelRecruitmentAndHR = interaction.guild.get_channel(RECRUITMENT_AND_HR)
            if not isinstance(channelRecruitmentAndHR, discord.TextChannel):
                log.exception("StaffButton callback: channelRecruitmentAndHR not discord.TextChannel")
                return

            roleRecruitmentCoordinator = interaction.guild.get_role(RECRUITMENT_COORDINATOR)
            if roleRecruitmentCoordinator is None:
                log.exception("StaffButton callback: roleRecruitmentCoordinator is None")
                return

            embed = discord.Embed(title="❌ Prospect denied", description=f"{member.mention} has been denied in interview.\nInterviewer: {interaction.user.mention}", color=discord.Color.red())
            embed.set_footer(text=f"Prospect ID: {member.id} | Interviewer ID: {interaction.user.id}")
            embed.timestamp = datetime.now()

            await channelRecruitmentAndHR.send(roleRecruitmentCoordinator.mention, embed=embed)
            return

        # ZiT Feedback buttons
        if customId.startswith("staff_button_zitfeedback_"):
            view: discord.ui.View = self.view  # type: ignore
            zeusId = view.zeusId  # type: ignore
            zeusMember = interaction.guild.get_member(zeusId)
            embed = interaction.message.embeds[0]
            if customId == "staff_button_zitfeedback_submit":
                if not isinstance(zeusMember, discord.Member):
                    log.exception(f"StaffButton callback: zeusMember not discord.Member, id '{zeusId}'")
                    return

                recommend = view.requiredFieldsFilled["recommend"]  # type: ignore
                zeusRole = interaction.guild.get_role(ZEUS)
                curatorRole = interaction.guild.get_role(CURATOR)
                embed.title = f"✅ ZiT Feedback Submitted" if recommend else f"❌ ZiT Feedback Submitted"
                embed.set_field_at(4, name="Recommendation", value = f"✅ Recommending for {zeusRole.mention}" if recommend else f"❌ Not recommended for {zeusRole.mention}", inline=False)
                embed.color = discord.Color.green() if recommend else discord.Color.purple()
                embed.timestamp = datetime.now()
                embed.description = ""
                zFeedback = interaction.guild.get_channel(ZEUS_FEEDBACK)

                log.info(f"{interaction.user.id} [{interaction.user.display_name}] Submitted ZiT feedback for {zeusMember.id} [{zeusMember.display_name}]")

                await interaction.response.edit_message(content = "Thank you for submitting ZiT feedback!", embed = None, view = None)
                await zFeedback.send(content = f"{curatorRole.mention} Feedback is now ready for review.\n\nFeedback submitted for {zeusMember.mention} by {interaction.user.mention}.", embed=embed)
                return

            if customId in ("staff_button_zitfeedback_recommend_yes", "staff_button_zitfeedback_recommend_no"):
                if not isinstance(zeusMember, discord.Member):
                    log.exception(f"StaffButton callback: zeusMember not discord.Member, id '{zeusId}'")
                    return
                recommend = customId.split("_")[-1]
                if recommend == "yes":
                    btn = view.children[4]  # type: ignore
                    btnNotRecommend = view.children[5]  # type: ignore

                    btn.style = discord.ButtonStyle.green
                    btn.disabled = True
                    btnNotRecommend.style = discord.ButtonStyle.gray
                    btnNotRecommend.disabled = False
                    view.requiredFieldsFilled["recommend"] = True
                    embed.set_field_at(4, name="Recommendation", value="✅ Recommending for Full Zeus Tags", inline=False)
                else:
                    btn = view.children[5]  # type: ignore
                    btnRecommend = view.children[4]  # type: ignore

                    btn.style = discord.ButtonStyle.red
                    btn.disabled = True
                    btnRecommend.style = discord.ButtonStyle.gray
                    btnRecommend.disabled = False
                    view.requiredFieldsFilled["recommend"] = False
                    embed.set_field_at(4, name="Recommendation", value="❌ Not Recommending for Full Zeus Tags", inline=False)
                try:
                    allComplete = all(value is not None for key, value in view.requiredFieldsFilled.items())
                    view.children[6].disabled = not allComplete  # type: ignore
                    await interaction.response.edit_message(embed=embed, view=view)
                    return
                except Exception:
                    await interaction.response.edit_message(embed=embed, view=view)

            fieldId = customId.split("_")[3]
            cfg = next((c for c in view.CFG.values() if c.get("id") == fieldId), {})  # searhces view.CFG for matching fieldId
            default = None
            if customId == "staff_button_zitfeedback_opname":
                default = embed.fields[0].value if embed.fields[0].value != "" else None
            elif customId == "staff_button_zitfeedback_wentwell":
                default = embed.fields[1].value if embed.fields[1].value != "" else None
            elif customId == "staff_button_zitfeedback_couldimprove":
                default = embed.fields[2].value if embed.fields[2].value != "" else None
            elif customId == "staff_button_zitfeedback_additionalcomments":
                default = embed.fields[3].value if embed.fields[3].value != "" else None

            modal = StaffModal(self.view, f"ZiT Feedback", f"staff_modal_zitfeedback_{fieldId}")
            modal.add_item(discord.ui.TextInput(
                label = cfg.get("label", ""),
                placeholder = str(cfg.get("placeholder", ""))[:100],
                default = default,
                style = discord.TextStyle.short if (cfg.get("id") == "opname") else discord.TextStyle.paragraph,
                required = (cfg.get("id") != "additionalcomments"),
                max_length = 1024
            ))
            modal.embed = interaction.message.embeds[0]  # store embed in modal for later use
            await interaction.response.send_modal(modal)
            return

class StaffModal(discord.ui.Modal):
    """Handling all staff modals."""
    def __init__(self, instance, title: str, customId: str) -> None:
        super().__init__(title=title, custom_id=customId)
        self.instance = instance

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            log.exception("StaffModal on_submit: interaction.user not discord.Member")
            return
        if interaction.guild is None:
            log.exception("StaffModal on_submit: interaction.guild is None")
            return

        if interaction.data["custom_id"].startswith("staff_modal_zitfeedback"):
            embed = self.embed  # type: ignore
            fieldId = interaction.data["custom_id"].split("_")[-1]
            view: discord.ui.View = self.instance  # type: ignore
            userInput = self.children[0].value.strip()

            cfgKey, _ = next(((k, v) for k, v in view.CFG.items() if v.get("id") == fieldId), (None, {}))  # searches view.CFG for matching fieldId

            # Find the button that corresponds to this field
            btn = next((c for c in view.children if isinstance(c, discord.ui.Button) and c.custom_id == f"staff_button_zitfeedback_{fieldId}"), None)

            if cfgKey == "opName":
                btn.style = discord.ButtonStyle.green
                embed.set_field_at(0, name="Operation Name & Date", value=f"{userInput}", inline=False)
                view.requiredFieldsFilled["opName"] = True
            elif cfgKey == "wentWell":
                btn.style = discord.ButtonStyle.green
                embed.set_field_at(1, name="Things Done Well", value=f"{userInput}", inline=False)
                view.requiredFieldsFilled["wentWell"] = True
            elif cfgKey == "couldImprove":
                btn.style = discord.ButtonStyle.green
                embed.set_field_at(2, name="Points for Improvement", value=f"{userInput}", inline=False)
                view.requiredFieldsFilled["couldImprove"] = True
            elif cfgKey == "additionalComments":
                btn.style = discord.ButtonStyle.green
                embed.set_field_at(3, name="Additional Comments", value=f"{userInput}", inline=False)

            # Enable submit button only when required fields are filled
            try:
                allComplete = all(value is not None for key, value in view.requiredFieldsFilled.items())
                view.children[6].disabled = not allComplete  # type: ignore
            except Exception:
                pass

            await interaction.response.edit_message(embed=embed, view=view)
            return

        if interaction.data["custom_id"] != "staff_modal_maps":
            log.exception("StaffModal on_submit: modal custom_id != staff_modal_maps")
            return

        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Updating modpack maps listing")
        value: str = self.children[0].value.strip().split("\n")

        with open(GENERIC_DATA_FILE) as f:
            genericData = json.load(f)
        genericData["modpackMaps"] = value
        with open(GENERIC_DATA_FILE, "w") as f:
            json.dump(genericData, f, indent=4)

        await interaction.response.send_message(f"Maps updated!", ephemeral=True, delete_after=30.0)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.exception(error)


async def setup(bot: commands.Bot) -> None:
    Recruitment.interview.error(Utils.onSlashError)
    Recruitment.newcomers.error(Utils.onSlashError)
    Staff.updatemodpack.error(Utils.onSlashError)
    Staff.zitfeedback.error(Utils.onSlashError)
    Staff.ban.error(Utils.onSlashError)
    Staff.unban.error(Utils.onSlashError)
    Staff.kick.error(Utils.onSlashError)
    await bot.add_cog(Staff(bot))
    await bot.add_cog(Recruitment(bot))
