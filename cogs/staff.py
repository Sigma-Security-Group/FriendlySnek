from secret import DEBUG
import re
from datetime import datetime
from typing import Optional

from discord import utils, Embed, Color
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

    def _getMember(self, searchTerm: str) -> Optional[discord.Member]:
        """ Serach for a discord.Member with a wide support query.

        Parameters:
        searchTerm (str): Search query for a discord.Member.

        Returns:
        None | discord.Member: If the provided serach term found a member, it will return one discord.Member otherwise returns None.
        """
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

    @commands.command(name="getmember")
    @commands.has_any_role(UNIT_STAFF)
    async def getMember(self, ctx: commands.context, *, searchTerm: str) -> None:
        """ Get a member.

        Parameters:
        ctx (commands.context): The Discord context.
        searchTerm (str): Search query for a discord.Member.

        Returns:
        None.
        """
        member = self._getMember(searchTerm)
        if member is None:
            await ctx.send(f"No member found for search term: `{searchTerm}`")
        else:
            embed = Embed(description=member.mention, color=member.color)
            avatar = member.avatar if member.avatar else member.display_avatar
            embed.set_author(icon_url=member.display_avatar, name=member)
            embed.set_thumbnail(url=avatar)
            embed.add_field(name="Joined", value=utils.format_dt(member.joined_at, style="f"), inline=True)
            embed.add_field(name="Registered", value=utils.format_dt(member.created_at, style="f"), inline=True)

            roles = [role.mention for role in member.roles]  # Fetch all member roles
            roles.pop(0)  # Remove @everyone role
            roles = roles[::-1]  # Reverse the list
            embed.add_field(name=f"Roles [{len(member.roles) - 1}]", value=" ".join(roles) if len(roles) > 0 else "None", inline=False)

            KEY_PERMISSIONS = {
                "Administrator": member.guild_permissions.administrator,
                "Manage Server": member.guild_permissions.manage_guild,
                "Manage Roles": member.guild_permissions.manage_roles,
                "Manage Channels": member.guild_permissions.manage_channels,
                "Manage Messages": member.guild_permissions.manage_messages,
                "Manage Webhooks": member.guild_permissions.manage_webhooks,
                "Manage Nicknames": member.guild_permissions.manage_nicknames,
                "Manage Emojis": member.guild_permissions.manage_emojis,
                "Kick Members": member.guild_permissions.kick_members,
                "Ban Members": member.guild_permissions.ban_members,
                "Mention Everyone": member.guild_permissions.mention_everyone
            }

            PERMISSIONS = [name for name, perm in KEY_PERMISSIONS.items() if perm]
            if len(PERMISSIONS) > 0:
                embed.add_field(name="Key Permissions", value=", ".join(PERMISSIONS), inline=False)

            if member.id == member.guild.owner_id:
                embed.add_field(name="Acknowledgements", value="Server Owner", inline=False)

            embed.set_footer(text=f"ID: {member.id}")
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)

    @commands.command(name="purge")
    @commands.has_any_role(UNIT_STAFF)
    async def purgeMessagesFromMember(self, ctx: commands.context, *, searchTerm: str) -> None:
        """ Purges all messages from a member.

        Parameters:
        ctx (commands.context): The Discord context.
        searchTerm (str): Search query for a discord.Member.

        Returns:
        None.
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.info(f"No member found for search term: {searchTerm}")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{searchTerm}`", color=Color.red()))
            return

        log.critical(f"\n---------\n{ctx.author.display_name} ({ctx.author}) is purging all messages from {searchTerm}: {member.display_name} ({member})\n---------")
        embed = Embed(title="Purging messages", description=f"Member: {member.mention}\nThis may take a while!", color=Color.orange())
        embed.set_footer(text=f"ID: {member.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

        guild = self.bot.get_guild(GUILD_ID)
        for channel in guild.text_channels:
            log.debug(f"Purging {member.display_name} ({member.name}#{member.discriminator}) messages in {channel.mention}.")
            try:
                await channel.purge(limit=None, check=lambda m: m.author.id == member.id)
            except Exception:
                log.warning(f"Could not purge {member.display_name} ({member.name}#{member.discriminator}) messages from {channel.mention}!")
        log.info(f"Done purging {member.display_name} ({member.name}#{member.discriminator}) messages!")
        embed = Embed(title="✅ Messages purged", description=f"Member: {member.mention}", color=Color.green())
        embed.set_footer(text=f"ID: {member.id}")
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

    @commands.command(name="lastactivity")
    @commands.has_any_role(UNIT_STAFF)
    async def lastActivity(self, ctx: commands.context, pingStaff: str = "yes") -> None:
        """ Get last activity for all members.

        Parameters:
        ctx (commands.context): The Discord context.
        pingStaff (str): A string boolean to decide if to ping staff on command completion.

        Returns:
        None.
        """
        log.debug(f"Analyzing members' last activity")
        embed = Embed(title="Analyzing members' last activity", description="This may take a while!", color=Color.orange())
        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)

        guild = self.bot.get_guild(GUILD_ID)
        lastMessagePerMember = {member: None for member in guild.members}
        embed = Embed(title="Channel checking", color=Color.orange())
        embed.add_field(name="Channel", value="#Loading...", inline=True)
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
        log.debug("Message searching done!")
        embed = Embed(title="✅ Channel checking", description="Message searching done!", color=Color.green())
        embed.set_footer(text=f"Run by: {ctx.author}")
        embed.timestamp = datetime.now()
        await msg.edit(embed=embed)
        # Somewhere after this comment raises the error. I can't figure it out cuz I have no idea what this does
        # > Command raised an exception: TypeError: can't compare offset-naive and offset-aware datetimes
        lastActivityPerMember = [(f"{member.display_name} ({member.name}#{member.discriminator})", f"{member.mention}\n{utils.format_dt(lastMessage.created_at.timestamp(), style='F')}\n{lastMessage.jump_url}" if lastMessage is not None else f"{member.mention}\nNOT FOUND")
        for member, lastMessage in sorted(lastMessagePerMember.items(), key=lambda x: x[1].created_at if x[1] is not None else datetime(1970, 1, 1))]
        for i in range(0, len(lastActivityPerMember), 25):
            embed = Embed(title=f"Last activity per member ({i + 1} - {min(i + 25, len(lastActivityPerMember))} / {len(lastActivityPerMember)})")
            for j in range(i, min(i + 25, len(lastActivityPerMember))):
                embed.add_field(name=lastActivityPerMember[j][0], value=lastActivityPerMember[j][1], inline=False)
            await ctx.send(embed=embed)
        if pingStaff in ("y", "yes", "ping"):
            await ctx.send(f"{guild.get_role(UNIT_STAFF).mention} Last activity analysis has finished")

    @commands.command(name="lastactivitymember")
    @commands.has_any_role(UNIT_STAFF)
    async def lastActivityForMember(self, ctx: commands.context, *, searchTerm: str) -> None:
        """ Get last activity for member.

        Parameters:
        ctx (commands.context): The Discord context.
        searchTerm (str): Search query for a discord.Member.

        Returns:
        None.
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.info(f"No member found for search term: {searchTerm}!")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{searchTerm}`", color=Color.red()))
            return
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
                log.warning(f"Could not search messages from channel #{channel.name}!")
        log.debug("Done searching messages!")
        if lastMessage is None:
            embed = Embed(title="❌ Last activity", description=f"Activity not found!\nMember: {member.mention}", color=Color.red())
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)
        else:
            embed = Embed(title="✅ Last activity", description=f"Activity found: {utils.format_dt(lastMessage.created_at.timestamp(), style='F')}!\nMember: {member.mention}", color=Color.green())
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)

    @commands.command()
    @commands.has_any_role(UNIT_STAFF)
    async def promote(self, ctx: commands.context, *, searchTerm: str) -> None:
        """ Promote a member to the next rank.

        Parameters:
        ctx (commands.context): The Discord context.
        searchTerm (str): Search query for a discord.Member.

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
                if newRole.id == OPERATOR:
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
    async def demote(self, ctx: commands.context, *, searchTerm: str) -> None:
        """ Demote a member to the previous rank.

        Parameters:
        ctx (commands.context): The Discord context.
        searchTerm (str): Search query for a discord.Member.

        Returns:
        None.
        """
        member = self._getMember(searchTerm)
        if member is None:
            log.info(f"No member found for search term: {searchTerm}")
            await ctx.send(embed=Embed(title="❌ No member found", description=f"Searched for: `{searchTerm}`", color=Color.red()))
            return
        guild = self.bot.get_guild(GUILD_ID)
        for role in member.roles:
            if role.id in DEMOTIONS:
                newRole = guild.get_role(DEMOTIONS[role.id])
                log.info(f"Demoting {member.display_name} ({member}) from {role} to {newRole}!")
                await member.remove_roles(role)
                await member.add_roles(newRole)
                embed = Embed(title="✅ Member demoted", description=f"{member.mention} demoted from `{role}` to `{newRole}`!", color=Color.green())
                embed.set_footer(text=f"ID: {member.id}")
                embed.timestamp = datetime.now()
                await ctx.send(embed=embed)
                break
        else:
            log.warning(f"No demotion possible for {member.display_name} ({member})!")
            embed = Embed(title="❌ No possible demotion", description=f"Member: {member.mention}", color=Color.red())
            embed.set_footer(text=f"ID: {member.id}")
            embed.timestamp = datetime.now()
            await ctx.send(embed=embed)

    @commands.command(name="searchmodlogs")
    @commands.has_any_role(UNIT_STAFF)
    async def searchModLogs(self, ctx: commands.context, *, searchTerm: str) -> None:
        """ Search through the moderation logs.

        Parameters:
        ctx (commands.context): The Discord context.
        searchTerm (str): Search query for a discord.Member.

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
                if searchTerm in message.content.lower():
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
                await self.bot.get_channel(STAFF_CHAT).send(f"Moderation Logs related to {member.display_name} ({member.name}#{member.discriminator}):\n{messageLinks}")
            else:
                await self.bot.get_channel(STAFF_CHAT).send(f"No Moderation Logs related to {member.display_name} ({member.name}#{member.discriminator})")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Staff(bot))
