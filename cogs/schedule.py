import os, re, json, asyncio, discord, logging
import pytz  # type: ignore

from math import ceil
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse as datetimeParse  # type: ignore

from discord.ext import commands, tasks  # type: ignore

from .workshopInterest import WorkshopInterest  # type: ignore
import secret
from constants import *
if secret.DEBUG:
    from constants.debug import *


EMBED_INVALID = discord.Embed(title="❌ Invalid input", color=discord.Color.red())
MAX_SERVER_ATTENDANCE = 50


UTC = pytz.utc
TIME_ZONES = {
    "UTC": "UTC",
    "British Time (London)": "Europe/London",
    "Central European Time (Brussels)": "Europe/Brussels",
    "Eastern European Time (Sofia)": "Europe/Sofia",
    "Pacific American Time (LA)": "America/Los_Angeles",
    "Eastern American Time (NY)": "America/New_York",
    "Japanese Time (Tokyo)": "Asia/Tokyo",
    "Australian Western Time (Perth)": "Australia/Perth",
    "Australian Central Western Time (Eucla)": "Australia/Eucla",
    "Australian Central Time (Adelaide)": "Australia/Adelaide",
    "Australian Eastern Time (Sydney)": "Australia/Sydney"
}

TIMESTAMP_STYLES = {
    "t": "Short Time",
    "T": "Long Time",
    "d": "Short Date",
    "D": "Long Date",
    "f": "Short Date Time",
    "F": "Long Date Time",
    "R": "Relative Time"
}

EVENT_TYPE_COLORS = {
    "Operation": discord.Color.green(),
    "Workshop": discord.Color.blue(),
    "Event": discord.Color.gold()
}

SCHEDULE_EVENT_VIEW: dict[str, dict[str, discord.ButtonStyle | bool | int | None]] = {
    "Type": {
        "required": True,
        "row": 0,
        "startDisabled": False,
        "customStyle": None
    },
    "Title": {
        "required": True,
        "row": 0,
        "startDisabled": False,
        "customStyle": None
    },
    "Description": {
        "required": True,
        "row": 0,
        "startDisabled": False,
        "customStyle": None
    },
    "Duration": {
        "required": True,
        "row": 0,
        "startDisabled": False,
        "customStyle": None
    },
    "Time": {
        "required": True,
        "row": 0,
        "startDisabled": False,
        "customStyle": None
    },

    "External URL": {
        "required": False,
        "row": 1,
        "startDisabled": False,
        "customStyle": None
    },
    "Reservable Roles": {
        "required": False,
        "row": 1,
        "startDisabled": False,
        "customStyle": None
    },
    "Map": {
        "required": False,
        "row": 1,
        "startDisabled": False,
        "customStyle": None
    },
    "Max Players": {
        "required": True,
        "row": 1,
        "startDisabled": False,
        "customStyle": None
    },

    "Linking": {
        "required": True,
        "row": 2,
        "startDisabled": True,
        "customStyle": None
    },
    "Select Template: None": {
        "required": False,
        "row": 2,
        "startDisabled": True,
        "customStyle": None
    },
    "Save As Template": {
        "required": False,
        "row": 2,
        "startDisabled": True,
        "customStyle": None
    },
    "Update Template": {
        "required": False,
        "row": 2,
        "startDisabled": True,
        "customStyle": None
    },
    "Files": {
        "required": False,
        "row": 2,
        "startDisabled": False,
        "customStyle": None
    },

    "Submit": {
        "required": True,
        "row": 3,
        "startDisabled": False,
        "customStyle": discord.ButtonStyle.primary
    },
    "Cancel": {
        "required": False,
        "row": 3,
        "startDisabled": False,
        "customStyle": discord.ButtonStyle.primary
    }
}

SCHEDULE_EVENT_PREVIEW_EMBED = {
    "title": "Create an event!",
    "description": "[Red buttons = Mandatory]\n[Gray = Optional]\n[Green = Done]\n\n[Markdown Syntax (Formatting)](https://support.discord.com/hc/en-us/articles/210298617-Markdown-Text-101-Chat-Formatting-Bold-Italic-Underline)"
}

FILE_UPLOAD_EXTENSION_BLACKLIST = ["exe", "pif", "application", "gadget", "msi", "msp", "com", "scr", "hta", "cpl", "msc", "jar", "bat", "cmd", "vb", "vbs", "vbe", "js", "jse", "ws", "wsf", "wsc", "wsh", "ps1", "ps1xml", "ps2", "ps2xml", "psc1", "psc2", "msh", "msh1", "msh2", "mshxml", "msh1xml", "msh2xml", "scf", "lnk", "inf", "reg", "doc", "xls", "ppt", "docm", "dotm", "xlsm", "xltm", "xlam", "pptm", "potm", "ppam", "ppsm", "sldm", "sh", "bash", "zsh"]


log = logging.getLogger("FriendlySnek")

class Schedule(commands.Cog):
    """Schedule Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Schedule"))
        self.bot.cogsReady["schedule"] = True

        await self.updateSchedule()
        if not self.tenMinTask.is_running():
            self.tenMinTask.start()

    @staticmethod
    async def cancelCommand(channel: discord.DMChannel, abortText: str) -> None:
        """Sends an abort response to the user.

        Parameters:
        channel (discord.DMChannel): The users DM channel where the message is sent.
        abortText (str): The embed title - what is aborted.

        Returns:
        None.
        """
        await channel.send(embed=discord.Embed(title=f"❌ {abortText} canceled!", color=discord.Color.red()))

    @staticmethod
    async def checkDMChannel(user: discord.User | discord.Member) -> discord.DMChannel:
        """  """
        return await user.create_dm() if user.dm_channel is None else user.dm_channel

    async def saveEventToHistory(self, event, autoDeleted=False) -> None:
        """Saves a specific event to history.

        Parameters:
        event: The specified event.
        autoDeleted (bool): If the event was automatically deleted.

        Returns:
        None.
        """
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Schedule saveEventToHistory: guild is None")
            return

        if event.get("type", "Operation") == "Workshop" and (workshopInterestName := event.get("workshopInterest")) is not None:
            with open(WORKSHOP_INTEREST_FILE) as f:
                workshopInterestFile = json.load(f)
            if (workshop := workshopInterestFile.get(workshopInterestName)) is not None:
                updateWorkshopInterest = False
                for memberId in event["accepted"]:
                    if memberId in workshop["members"]:
                        updateWorkshopInterest = True
                        workshop["members"].remove(memberId)
                if updateWorkshopInterest:
                    with open(WORKSHOP_INTEREST_FILE, "w") as f:
                        json.dump(workshopInterestFile, f, indent=4)
                    channelWorkshopInterest = self.bot.get_channel(WORKSHOP_INTEREST)
                    if not isinstance(channelWorkshopInterest, discord.TextChannel):
                        log.exception("Schedule saveEventToHistory: channelWorkshopInterest not discord.TextChannel")
                        return
                    embed = WorkshopInterest.getWorkshopEmbed(guild, workshopInterestName)
                    workshopMessage = await channelWorkshopInterest.fetch_message(workshop["messageId"])
                    await workshopMessage.edit(embed=embed)

        with open(EVENTS_HISTORY_FILE) as f:
            eventsHistory = json.load(f)
        eventCopy = deepcopy(event)
        eventCopy["autoDeleted"] = autoDeleted
        eventCopy["authorName"] = member.display_name if (member := guild.get_member(eventCopy["authorId"])) is not None else "UNKNOWN"
        eventCopy["acceptedNames"] = [member.display_name if (member := guild.get_member(memberId)) is not None else "UNKNOWN" for memberId in eventCopy["accepted"]]
        eventCopy["declinedNames"] = [member.display_name if (member := guild.get_member(memberId)) is not None else "UNKNOWN" for memberId in eventCopy["declined"]]
        eventCopy["tentativeNames"] = [member.display_name if (member := guild.get_member(memberId)) is not None else "UNKNOWN" for memberId in eventCopy["tentative"]]
        eventCopy["standbyNames"] = [member.display_name if (member := guild.get_member(memberId)) is not None else "UNKNOWN" for memberId in eventCopy["standby"]]
        eventCopy["reservableRolesNames"] = {role: ((member.display_name if (member := guild.get_member(memberId)) is not None else "UNKNOWN") if memberId is not None else "VACANT") for role, memberId in eventCopy["reservableRoles"].items()} if eventCopy["reservableRoles"] is not None else {}
        eventsHistory.append(eventCopy)
        with open(EVENTS_HISTORY_FILE, "w") as f:
            json.dump(eventsHistory, f, indent=4)


# ===== <Tasks> =====

    @tasks.loop(minutes=10)
    async def tenMinTask(self) -> None:
        """10 minute interval tasks.

        Parameters:
        None.

        Returns:
        None.
        """
        while not all(self.bot.cogsReady.values()):
            await asyncio.sleep(1)

        # === Check for old events and deletes them. ===
        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            utcNow = datetime.now(timezone.utc)
            deletedEvents = []
            for event in events:
                endTime = UTC.localize(datetime.strptime(event["endTime"], TIME_FORMAT))
                if utcNow > endTime + timedelta(minutes=69):
                    if event["maxPlayers"] != "hidden":  # Save events that does not have hidden attendance
                        await self.saveEventToHistory(event, autoDeleted=True)
                    log.debug(f"Schedule tenMinTask: Auto deleting event '{event['title']}'")
                    deletedEvents.append(event)
                    eventMessage = await self.bot.get_channel(SCHEDULE).fetch_message(event["messageId"])
                    await eventMessage.delete()
                    author = self.bot.get_guild(GUILD_ID).get_member(event["authorId"])
                    embed = discord.Embed(title="Event auto deleted", description=f"Your {event['type'].lower()} has ended: `{event['title']}`\nIt has been automatically removed from the schedule. {PEEPO_POP}", color=discord.Color.orange())
                    await author.send(embed=embed)
            for event in deletedEvents:
                events.remove(event)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            log.exception(e)


        # === Checks if players have accepted the event and joined the voice channel. ===
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Schedule tenMinTask: guild is None")
            return

        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            utcNow = datetime.now(timezone.utc)

            channelArmaDiscussion = self.bot.get_channel(ARMA_DISCUSSION)
            if not isinstance(channelArmaDiscussion, discord.TextChannel):
                log.exception("Schedule tenMinTask: channelArmaDiscussion not discord.TextChannel")
                return

            for event in events:
                if event.get("checkedAcceptedReminders", False):
                    continue
                if event.get("type", "Operation") != "Operation":
                    continue
                startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
                if utcNow > startTime + timedelta(minutes=30):
                    membersAccepted = [member for memberId in event["accepted"] + event["standby"] if (member := guild.get_member(memberId)) is not None]
                    membersInVC = self.bot.get_channel(COMMAND).members + self.bot.get_channel(DEPLOYED).members

                    membersUnscheduled = [member for member in membersAccepted if member not in membersInVC] + [member for member in membersInVC if member not in membersAccepted and member.id != event["authorId"]]

                    event["checkedAcceptedReminders"] = True
                    with open(EVENTS_FILE, "w") as f:
                        json.dump(events, f, indent=4)
                    if len(membersUnscheduled) > 0:
                        log.debug(f"Schedule tenMinTask: Pinging unscheduled members: {', '.join([member.display_name for member in membersUnscheduled])}")
                        await channelArmaDiscussion.send(" ".join(member.mention for member in membersUnscheduled) + f"\nIf you are in-game, please:\n* Get in <#{COMMAND}> or <#{DEPLOYED}>\n* Hit accept ✅ on the <#{SCHEDULE}>\nIf you are not making it to this {event['type'].lower()}, please hit decline ❌ on the <#{SCHEDULE}>")
        except Exception as e:
            log.exception(e)

# ===== </Tasks> =====


# ===== <Refresh Schedule> =====

    @discord.app_commands.command(name="refreshschedule")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_REFRESHSCHEDULE)
    async def refreshSchedule(self, interaction: discord.Interaction) -> None:
        """Refreshes the schedule - Use if an event was deleted without using the reaction.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        await interaction.response.send_message(f"Refreshing <#{SCHEDULE}>...")
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Is refreshing the schedule")
        await self.updateSchedule()

    @refreshSchedule.error
    async def onRefreshScheduleError(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        """refreshSchedule errors - dedicated for the discord.app_commands.errors.MissingAnyRole error.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        error (discord.app_commands.AppCommandError): The end user error.

        Returns:
        None.
        """
        if type(error) == discord.app_commands.errors.MissingAnyRole:
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("Schedule onRefreshScheduleError: guild is None")
                return

            embed = discord.Embed(title="❌ Missing permissions", description=f"You do not have the permissions to refresh the schedule!\nThe permitted roles are: {', '.join([guild.get_role(role).name for role in CMD_LIMIT_REFRESHSCHEDULE])}.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        log.exception(error)

# ===== </Refresh Schedule> =====


# ===== <AAR> ====

    @discord.app_commands.command(name="aar")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_ZEUS)
    async def aar(self, interaction: discord.Interaction) -> None:
        """Move all users in Deployed to Command voice channel."""
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] is starting AAR")

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Schedule aar: guild is None")
            return

        channelDeployed = guild.get_channel(DEPLOYED)
        if not isinstance(channelDeployed, discord.VoiceChannel):
            log.exception("Schedule aar: channelDeployed is None")
            return

        channelCommand = guild.get_channel(COMMAND)
        if not isinstance(channelCommand, discord.VoiceChannel):
            log.exception("Schedule aar: channelDeployed is None")
            return

        await interaction.response.send_message("AAR has started, Thanks for running a bop!", ephemeral=True)

        deployed_members = channelDeployed.members
        for member in deployed_members:
            try:
                await member.move_to(channelCommand)
            except Exception:
                log.warning(f"Schedule aar: failed to move {member.id} [{member.display_name}]")


    @aar.error
    async def onaAarError(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        """aar errors - dedicated for the discord.app_commands.errors.MissingAnyRole error.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        error (discord.app_commands.AppCommandError): The end user error.

        Returns:
        None.
        """
        if type(error) == discord.app_commands.errors.MissingAnyRole:
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("Schedule onAarError: guild is None")
                return

            embed = discord.Embed(title="❌ Missing permissions", description=f"You do not have the permissions to move all users to command!\nThe permitted roles are: {', '.join([guild.get_role(role).name for role in CMD_LIMIT_ZEUS])}.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        log.exception(error)

# ===== </AAR> ====


# ===== <Schedule Functions> =====

    async def updateSchedule(self) -> None:
        """Updates the schedule channel with all messages."""
        channelSchedule = self.bot.get_channel(SCHEDULE)
        if not isinstance(channelSchedule, discord.TextChannel):
            log.exception("Schedule updateSchedule: channelSchedule not discord.TextChannel")
            return

        scheduleIntroMessage = f"__Welcome to the schedule channel!__\n🟩 Schedule operations: `/operation` (`/bop`)\n🟦 Workshops: `/workshop` (`/ws`)\n🟨 Generic events: `/event`\n\nThe datetime you see in here are based on __your local time zone__.\nChange timezone when scheduling events with `/changetimezone`.\n\nSuggestions/bugs contact: {', '.join([f'**{developerName.display_name}**' for name in DEVELOPERS if (developerName := channelSchedule.guild.get_member(name)) is not None])} -- <https://github.com/Sigma-Security-Group/FriendlySnek>"

        # Do not purge intro message if unchanged
        sendIntroMessage = True
        await channelSchedule.purge(limit=None,
                            check=lambda m: (
                                m.author.id in FRIENDLY_SNEKS and m.content != scheduleIntroMessage
                            ) or (m.content == scheduleIntroMessage and (isFoundIntroMessage := False))
        )

        if not sendIntroMessage:
            await channelSchedule.send(scheduleIntroMessage)

        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            if len(events) == 0:
                await channelSchedule.send("...\nNo bop?\n...\nSnek is sad")
                await channelSchedule.send(":cry:")
                return

            newEvents: list[dict] = []
            for event in sorted(events, key=lambda e: datetime.strptime(e["time"], TIME_FORMAT), reverse=True):
                Schedule.applyMissingEventKeys(event)
                msg = await channelSchedule.send(embed=self.getEventEmbed(event), view=self.getEventView(event), files=self.getEventFiles(event))
                event["messageId"] = msg.id
                newEvents.append(event)

            with open(EVENTS_FILE, "w") as f:
                json.dump(newEvents, f, indent=4)
        except Exception as e:
            log.exception(e)

    @staticmethod
    def applyMissingEventKeys(event: dict) -> None:
        """Applies missing keys to the event.

        Parameters:
        event (dict): The event.

        Returns:
        None.
        """
        event.setdefault("authorId", None)
        event.setdefault("type", None)
        event.setdefault("title", None)
        event.setdefault("description", None)
        event.setdefault("externalURL", None)
        event.setdefault("reservableRoles", None)
        event.setdefault("maxPlayers", None)
        event.setdefault("map", None)
        event.setdefault("time", None)
        event.setdefault("endTime", None)
        event.setdefault("duration", None)
        event.setdefault("messageId", None)
        event.setdefault("accepted", [])
        event.setdefault("declined", [])
        event.setdefault("tentative", [])
        event.setdefault("standby", [])
        event.setdefault("files", [])

    def getEventEmbed(self, event: dict) -> discord.Embed:
        """Generates an embed from the given event.

        Parameters:
        event (dict): The event.

        Returns:
        discord.Embed: The generated embed.
        """
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Schedule getEventEmbed: guild is None")
            return discord.Embed()

        embed = discord.Embed(title=event["title"], description=event["description"], color=EVENT_TYPE_COLORS[event.get("type", "Operation")])

        if event["reservableRoles"] is not None:
            embed.add_field(name="\u200B", value="\u200B", inline=False)
            embed.add_field(name=f"Reservable Roles ({len([role for role, memberId in event['reservableRoles'].items() if memberId is not None])}/{len(event['reservableRoles'])}) 👤", value="\n".join(f"{roleName} - {('*' + member.display_name + '*' if (member := guild.get_member(memberId)) is not None else '**VACANT**') if memberId is not None else '**VACANT**'}" for roleName, memberId in event["reservableRoles"].items()), inline=False)

        durationHours = int(event["duration"].split("h")[0].strip()) if "h" in event["duration"] else 0
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        embed.add_field(name="Time", value=f"{discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')} - {discord.utils.format_dt(UTC.localize(datetime.strptime(event['endTime'], TIME_FORMAT)), style='t' if durationHours < 24 else 'F')}", inline=(durationHours < 24))
        embed.add_field(name="Duration", value=event["duration"], inline=True)

        if event["map"] is not None:
            embed.add_field(name="Map", value=event["map"], inline=False)

        if event["externalURL"] is not None:
            embed.add_field(name="\u200B", value="\u200B", inline=False)
            embed.add_field(name="External URL", value=event["externalURL"], inline=False)
        embed.add_field(name="\u200B", value="\u200B", inline=False)

        isAcceptAndReserve = event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"]
        if not isAcceptAndReserve and len(event["standby"]) > 0 and (event["maxPlayers"] is None or (isinstance(event["maxPlayers"], int) and len(event["accepted"]) < event["maxPlayers"])):
            if event["maxPlayers"] is None:
                membersPromoted = len(event["standby"])
            else:
                membersPromoted = event["maxPlayers"] - len(event["accepted"])
            event["accepted"].extend(event["standby"][:membersPromoted])
            event["standby"] = event["standby"][membersPromoted:]

        accepted = [member.display_name for memberId in event["accepted"] if (member := guild.get_member(memberId)) is not None]
        declined = [member.display_name for memberId in event["declined"] if (member := guild.get_member(memberId)) is not None]
        tentative = [member.display_name for memberId in event["tentative"] if (member := guild.get_member(memberId)) is not None]
        standby = [member.display_name for memberId in event["standby"] if (member := guild.get_member(memberId)) is not None]

        # No limit || limit
        if event["maxPlayers"] is None or isinstance(event["maxPlayers"], int):
            embed.add_field(name=f"Accepted ({len(accepted)}) ✅" if event["maxPlayers"] is None else f"Accepted ({len(accepted)}/{event['maxPlayers']}) ✅", value="\n".join(name for name in accepted) if len(accepted) > 0 else "-", inline=True)
            embed.add_field(name=f"Declined ({len(declined)}) ❌", value=("\n".join("❌ " + name for name in declined)) if len(declined) > 0 else "-", inline=True)
            embed.add_field(name=f"Tentative ({len(tentative)}) ❓", value="\n".join(name for name in tentative) if len(tentative) > 0 else "-", inline=True)
            if len(standby) > 0:
                embed.add_field(name=f"Standby ({len(standby)}) :clock3:", value="\n".join(name for name in standby), inline=False)

        # Anonymous
        elif event["maxPlayers"] == "anonymous":
            embed.add_field(name=f"Accepted ({len(accepted) + len(standby)}) ✅", value="\u200B", inline=True)
            embed.add_field(name=f"Declined ({len(declined)}) ❌", value="\u200B", inline=True)
            embed.add_field(name=f"Tentative ({len(tentative)}) ❓", value="\u200B", inline=True)

        author = guild.get_member(event["authorId"])
        embed.set_footer(text="Created by Unknown User" if author is None else f"Created by {author.display_name}")
        embed.timestamp = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))

        return embed

    def getEventView(self, event: dict) -> discord.ui.View:
        view = ScheduleView()
        items = []

        # Add attendance buttons if maxPlayers is not hidden
        if event["maxPlayers"] != "hidden":
            isAcceptAndReserve = event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"]

            if isAcceptAndReserve:
                items.append(ScheduleButton(self, None, row=0, label="Accept & Reserve", style=discord.ButtonStyle.success, custom_id="reserve"))
            else:
                items.append(ScheduleButton(self, None, row=0, label="Accept", style=discord.ButtonStyle.success, custom_id="accepted"))

            items.extend([
                ScheduleButton(self, None, row=0, label="Decline", style=discord.ButtonStyle.danger, custom_id="declined"),
                ScheduleButton(self, None, row=0, label="Tentative", style=discord.ButtonStyle.secondary, custom_id="tentative")
            ])
            if event["reservableRoles"] is not None and not isAcceptAndReserve:
                items.append(ScheduleButton(self, None, row=0, label="Reserve", style=discord.ButtonStyle.secondary, custom_id="reserve"))

        items.append(ScheduleButton(self, None, row=0, emoji="⚙️", style=discord.ButtonStyle.secondary, custom_id="config"))
        for item in items:
            view.add_item(item)

        return view

    def getEventFiles(self, event: dict) -> list[discord.File]:
        """Generates a list of files from the given event.

        Parameters:
        event (dict): The event.

        Returns:
        list[discord.File]: The list of files.
        """
        if "files" not in event or not event["files"]:
            return None

        discordFiles = []
        for eventFile in event["files"]:
            try:
                with open(f"tmp/fileUpload/{eventFile}", "rb") as f:
                    discordFiles.append(discord.File(f, filename=eventFile.split("_", 2)[2]))
            except Exception as e:
                pass

        return discordFiles


    @staticmethod
    def getUserFileUploads(userId: str, isDiscordFormat = False, fullFilename = False) -> list[discord.File] | list[str]:
        """Filters uploaded files to specified user id.

        Parameters:
        userId (str): User id for filter.
        isDiscordFormat (bool): Return as list[discord.File]
        fullFilename (bool): Filename is "DATETIME_AUTHORID_FILENAME", or "FILENAME"

        Returns:
        List[discord.File] | List[str]: A list of discord files or filenames.
        """
        files = []
        for osFile in os.listdir("tmp/fileUpload"):
            outName = osFile if fullFilename else osFile.split("_", 2)[2]
            if userId in osFile:
                if isDiscordFormat:
                    with open(osFile) as f:
                        files.append(discord.File(f, filename=outName))
                else:
                    files.append(outName)
        return files

    def fromPreviewEmbedToDict(self, embed: discord.Embed) -> dict:
        """Generates event dict from preview embed."""
        # Finds a field's position if found (int), if none found (None)
        findFieldPos = lambda fieldName : None if embed.fields is None else (
            indexes[0] if len(
                indexes := [idx for idx, field in enumerate(embed.fields) if field.name is not None and field.name.startswith(fieldName)]
            ) > 0 else None
        )

        outputDict = {
            "authorId": None,
            "title": embed.title,
            "description": embed.description,
            "externalURL": None if (findFieldPosURL := findFieldPos("External URL")) is None else embed.fields[findFieldPosURL].value,
            "reservableRoles": None,
            "maxPlayers": None,
            "map": None if (findFieldPosMap := findFieldPos("Map")) is None else embed.fields[findFieldPosMap].value,
            "time": None,
            "endTime": None,
            "duration": None if (findFieldPosDuration := findFieldPos("Duration")) is None else embed.fields[findFieldPosDuration].value,
            "messageId": None,
            "accepted": [],
            "declined": [],
            "tentative": [],
            "standby": [],
            "type": [eventType for eventType in EVENT_TYPE_COLORS if EVENT_TYPE_COLORS[eventType] == embed.color][0] if embed.color in EVENT_TYPE_COLORS.values() else None,
            "files": []
        }

        # Reservable Roles
        fieldPos = findFieldPos("Reservable Roles")
        if fieldPos is not None:
            fieldResRolesValue = embed.fields[fieldPos].value
            if fieldResRolesValue is not None:
                outputDict["reservableRoles"] = {line[:-len(" - **VACANT**")]: None for line in fieldResRolesValue.split("\n")}

        # Attendance / Max Players
        fieldPos = findFieldPos("Accepted")
        if fieldPos is None:
            outputDict["maxPlayers"] = "hidden"
        else:
            fieldAcceptedName = embed.fields[fieldPos].name
            fieldAcceptedValue = embed.fields[fieldPos].value
            if fieldAcceptedName is not None and ("/" in fieldAcceptedName):  # Accepted (0/XX) ✅
                limitFirstPart = fieldAcceptedName[fieldAcceptedName.index("/") + 1:]  # XX) ✅
                outputDict["maxPlayers"] = int(limitFirstPart[:limitFirstPart.index(")")]) ## XX
            elif fieldAcceptedValue is not None and fieldAcceptedValue == "\u200B":
                outputDict["maxPlayers"] = "anonymous"

        # Time
        fieldPos = findFieldPos("Time")
        if fieldPos is not None:
            timeFieldValue = embed.fields[fieldPos].value
            if timeFieldValue is not None:
                matches = re.findall(r"(?<=<t:)\d+(?=:\w>)", timeFieldValue)
                outputDict["time"] = datetime.fromtimestamp(float(matches[0])).astimezone(pytz.utc).strftime(TIME_FORMAT)
                if len(matches) > 1:
                    outputDict["endTime"] = datetime.fromtimestamp(float(matches[1])).astimezone(pytz.utc).strftime(TIME_FORMAT)

        # Workshop Interest
        if outputDict["type"] == "Workshop":
            outputDict["workshopInterest"] = None
            if embed.author.name is not None:
                workshop = embed.author.name[len("Linking: "):]
                outputDict["workshopInterest"] = None if workshop == "None" else workshop

        fieldPos = findFieldPos("Files")
        if fieldPos is not None:
            filesFieldValue = embed.fields[fieldPos].value
            outputDict["files"] = filesFieldValue.split("\n")

        return outputDict

    def fromDictToPreviewEmbed(self, previewDict: dict) -> discord.Embed:
        """Generates event dict from preview embed."""
        # Title, Description, Color
        embed = discord.Embed(title=previewDict["title"], description=previewDict["description"], color=None if previewDict["type"] is None else EVENT_TYPE_COLORS[previewDict["type"]])

        # Reservable Roles
        if previewDict["reservableRoles"] is not None:
            embed.add_field(name="\u200B", value="\u200B", inline=False)
            embed.add_field(name=f"Reservable Roles (0/{len(previewDict['reservableRoles'])}) 👤", value="\n".join(f"{roleName} - **VACANT**" for roleName in previewDict["reservableRoles"]), inline=False)

        # Padding: Time/Duration | ResRoles
        if previewDict["time"] is not None or previewDict["duration"] is not None:
            embed.add_field(name="\u200B", value="\u200B", inline=False)

        # Time
        if previewDict["time"] is not None:
            hours = 0
            endTime = "<Set Duration>"
            if previewDict["duration"] is not None:
                hours, minutes, delta = self.getDetailsFromDuration(previewDict["duration"])
                endTime = discord.utils.format_dt(datetimeParse(previewDict["time"]).replace(tzinfo=pytz.utc) + delta, "t" if hours < 24 else "F")
            embed.add_field(name="Time", value=f"{discord.utils.format_dt(datetimeParse(previewDict['time']).replace(tzinfo=pytz.utc), 'F')} - {endTime}", inline=(hours < 24))

        # Duration
        if previewDict["duration"] is not None:
            embed.add_field(name="Duration", value=previewDict["duration"], inline=True)

        # Map
        if previewDict["map"] is not None:
            embed.add_field(name="Map", value=previewDict["map"], inline=False)

        # External URL
        if previewDict["externalURL"] is not None:
            embed.add_field(name="\u200B", value="\u200B", inline=False)
            embed.add_field(name="External URL", value=previewDict["externalURL"], inline=False)
        embed.add_field(name="\u200B", value="\u200B", inline=False)

        # Files
        if previewDict["files"] == []:
            for index, field in enumerate(embed.fields):
                if field.name == "Files":
                    embed.remove_field(index)
                    break

        elif previewDict["files"] is not None:
            embed.add_field(name="Files", value="\n".join(previewDict["files"]), inline=False)

        # Author, Footer, Timestamp
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Schedule fromDictToPreviewEmbed: guild is None")
            return discord.Embed(title="Error")
        if previewDict["type"] == "Workshop" and "workshopInterest" in previewDict:
            embed.set_author(name=f"Linking: {previewDict['workshopInterest']}")
        embed.set_footer(text="Created by Unknown User" if (author := guild.get_member(previewDict["authorId"])) is None else f"Created by {author.display_name}")
        if previewDict["time"] is not None:
            embed.timestamp = UTC.localize(datetime.strptime(previewDict["time"], TIME_FORMAT))

        # Attendance / Max Players
        if previewDict["maxPlayers"] == "hidden":
            return embed

        fieldNameNumberSuffix = ""
        if isinstance(previewDict["maxPlayers"], int):
            fieldNameNumberSuffix = f"/{previewDict['maxPlayers']}"

        fieldValue = "\u200B" if previewDict["maxPlayers"] == "anonymous" else "-"
        embed.add_field(name=f"Accepted (0{fieldNameNumberSuffix}) ✅", value=fieldValue, inline=True)
        embed.add_field(name="Declined (0) ❌", value=fieldValue, inline=True)
        embed.add_field(name="Tentative (0) ❓", value=fieldValue, inline=True)

        return embed

    def fromDictToPreviewView(self, previewDict: dict, selectedTemplate: str) -> discord.ui.View:
        """Generates preview view from event dict."""
        view = ScheduleView(authorId=previewDict["authorId"])
        for label, data in SCHEDULE_EVENT_VIEW.items():
            permittedEventTypesForTemplates = ("Workshop", "Event")

            style = discord.ButtonStyle.secondary
            previewDictKey = label.lower().replace("url", "URL").replace("linking", "workshopInterest").replace(" ", "")
            if label == "Type" or (previewDictKey in previewDict and previewDict[previewDictKey] is not None):
                style = discord.ButtonStyle.success
            elif isinstance(data["customStyle"], discord.ButtonStyle):
                style = data["customStyle"]
            elif data["required"]:
                style = discord.ButtonStyle.danger


            button = ScheduleButton(
                self,
                None,
                style=style,
                label=label,
                custom_id=f"event_schedule_{label.lower().replace(' ', '_')}",
                row=data["row"],
                disabled=data["startDisabled"]
            )

            # (Un)lock buttons depending on current event type
            if label == "Linking":
                button.disabled = (previewDict["type"] != "Workshop")  # Only workshop

            elif label == "Select Template: None":
                button.label = f"Select Template: {selectedTemplate}"
                # Quick disable if not permitted event type
                if previewDict["type"] is None or previewDict["type"] not in permittedEventTypesForTemplates:
                    button.disabled = True
                else:
                    # Disable if no templates exist
                    filename = f"data/{previewDict['type'].lower()}Templates.json"
                    with open(filename) as f:
                        templates = json.load(f)
                    button.disabled = len(templates) == 0

            elif label == "Save As Template":
                button.disabled = (previewDict["type"] not in permittedEventTypesForTemplates)

            # Allow if correct type and template selected
            elif label == "Update Template":
                button.disabled = (selectedTemplate == "None") or (previewDict["type"] not in permittedEventTypesForTemplates)

            view.add_item(button)

        return view


    @staticmethod
    def isAllowedToEdit(user: discord.Member, eventAuthorId: int) -> bool:
        """Is user allowed to edit event on schedule."""
        return (user.id == eventAuthorId) or (user.id in DEVELOPERS) or any(role.id == UNIT_STAFF or role.id == SERVER_HAMSTER for role in user.roles)

    @staticmethod
    def eventCollisionCheck(startTime: datetime, endTime: datetime) -> str | None:
        """Checks if inputted event (start- & endtime) collides with scheduled event with padding."""
        with open(EVENTS_FILE) as f:
            events = json.load(f)

        for event in events:
            if event.get("type", "Operation") == "Event":
                continue
            eventStartTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
            eventEndTime = UTC.localize(datetime.strptime(event["endTime"], TIME_FORMAT))
            if (eventStartTime <= startTime < eventEndTime) or (eventStartTime <= endTime < eventEndTime) or (startTime <= eventStartTime < endTime):
                return f"This time collides with the event `{event['title']}`.\nScheduled {discord.utils.format_dt(eventStartTime, style='F')} - {discord.utils.format_dt(eventEndTime, style='F')}"
            elif eventEndTime < startTime and eventEndTime + timedelta(hours=1) > startTime:
                return f"Your event would start less than an hour after the previous event (`{event['title']}`) ends!\nScheduled event: {discord.utils.format_dt(eventStartTime, style='F')} - {discord.utils.format_dt(eventEndTime, style='F')}"
            elif endTime < eventStartTime and endTime + timedelta(hours=1) > eventStartTime:
                return f"There is another event (`{event['title']}`) starting less than an hour after your event ends!\nScheduled event: {discord.utils.format_dt(eventStartTime, style='F')} - {discord.utils.format_dt(eventEndTime, style='F')}"

    @staticmethod
    async def hasCandidatePinged(candidateId: int, operationTitle: str, channelRecruitmentHr: discord.TextChannel) -> discord.Message | None:
        """Checks recent messages for candidate accept embed notifications

        Parameters:
        candidateId (int): ID of the target candidate member.
        operationTitle (str): Title of the target operation.
        channelRecruitmentHr (discord.TextChannel): Instance of the Recruitment & HR channel to search through.

        Returns:
        bool: Whether the notification embed has been found.
        """
        async for message in channelRecruitmentHr.history(limit=50):
            if message.author.id not in FRIENDLY_SNEKS:
                continue
            if not message.embeds:
                continue
            if message.embeds[0].description and str(candidateId) in message.embeds[0].description and f"`{operationTitle}`" in message.embeds[0].description:
                return message
        return None

    @staticmethod
    async def blockVerifiedRoleRSVP(interaction: discord.Interaction, event: dict) -> bool:
        """Checks if user has Verified role, and feedbacks blocking

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        event (dict): Target event.

        Returns:
        bool: True on block/quit. False on continue.
        """
        isUserRoleVerified = [True for userRole in interaction.user.roles if userRole.id == VERIFIED]
        if isUserRoleVerified and event["type"].lower() == "operation":
            if not isinstance(interaction.guild, discord.Guild):
                log.exception("Schedule blockVerifiedRoleRSVP: interaction.guild not discord.Guild")
                return True
            roleRecruitmentTeam = interaction.guild.get_role(RECRUITMENT_TEAM)
            if not isinstance(roleRecruitmentTeam, discord.Role):
                log.exception("Schedule blockVerifiedRoleRSVP: roleRecruitmentTeam not discord.Role")
                return True
            await interaction.response.send_message(f"{interaction.user.mention} Complete the newcomer workshop first in order to RSVP!\nPing {roleRecruitmentTeam.mention} for more information.", ephemeral=True)
            return True
        return False

    async def buttonHandling(self, message: discord.Message | None, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """Handling all schedule button interactions.

        Parameters:
        message (discord.Message | None): If the message is provided, it's used along with some specific button action.
        button (discord.ui.Button): The Discord button.
        interaction (discord.Interaction): The Discord interaction.
        authorId (int | None): ID of user who executed the command.

        Returns:
        None.
        """
        if not isinstance(interaction.user, discord.Member):
            log.exception("Schedule buttonHandling: interaction.user not discord.Member")
            return

        if interaction.message is None:
            log.exception("Schedule buttonHandling: interaction.message is None")
            return

        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)

            scheduleNeedsUpdate = True
            fetchMsg = False
            eventList: list[dict] = [event for event in events if event["messageId"] == interaction.message.id]

            rsvpOptions = ("accepted", "declined", "tentative", "standby")
            if button.custom_id in rsvpOptions:
                event = eventList[0]

                if await Schedule.blockVerifiedRoleRSVP(interaction, event):
                    return

                isAcceptAndReserve = event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"]

                # Promote standby to accepted if not AcceptAndReserve
                if interaction.user.id in event["accepted"] and not isAcceptAndReserve and len(event["standby"]) > 0:
                    standbyMember = event["standby"].pop(0)
                    event["accepted"].append(standbyMember)

                # User click on button twice - remove
                if interaction.user.id in event[button.custom_id]:
                    event[button.custom_id].remove(interaction.user.id)
                elif button.custom_id == "accepted" and interaction.user.id in event["standby"]:
                    event["standby"].remove(interaction.user.id)

                # "New" button
                else:
                    for option in rsvpOptions:
                        if interaction.user.id in event[option]:
                            event[option].remove(interaction.user.id)

                    # Place in standby if player cap is reached
                    if button.custom_id == "accepted" and isinstance(event["maxPlayers"], int) and len(event["accepted"]) >= event["maxPlayers"]:
                        event["standby"].append(interaction.user.id)
                    else:
                        event[button.custom_id].append(interaction.user.id)

                # Remove player from reservable role
                hadReservedARole = False
                if event["reservableRoles"] is not None:
                    for btnRoleName in event["reservableRoles"]:
                        if event["reservableRoles"][btnRoleName] == interaction.user.id:
                            event["reservableRoles"][btnRoleName] = None
                            hadReservedARole = True

                # User removes self from reserved role - Notify people on standby
                if isAcceptAndReserve and hadReservedARole and len(event["standby"]) > 0:
                    if not isinstance(interaction.guild, discord.Guild):
                        log.exception("Schedule buttonHandling: interaction.guild not discord.Guild")
                        return

                    vacantRoles = "\n".join([f"`{role}`" for role, reservedUser in event["reservableRoles"].items() if not reservedUser])
                    embed = discord.Embed(
                        title="Role(s) vacant",
                        description=f"The following role(s) are now vacant for event `{event['title']}`:\n{vacantRoles}",
                        color=discord.Color.green()
                    )

                    for standbyMemberId in event["standby"]:
                        standbyMember = interaction.guild.get_member(standbyMemberId)
                        if standbyMember is None:
                            log.warning(f"Schedule buttonhandling: Failed to get member with id '{standbyMemberId}'")
                            continue

                        try:
                            await standbyMember.send(embed=embed)
                        except Exception:
                            log.warning(f"Schedule buttonhandling: Failed to DM {standbyMember.id} [{standbyMember.display_name}] about vacant roles")


            # Ping Recruitment Team if candidate accepts
            if button.custom_id == "accepted" and eventList[0]["type"].lower() == "operation" and interaction.user.id in eventList[0]["accepted"] and any([True for role in interaction.user.roles if role.id == CANDIDATE]):
                if not isinstance(interaction.guild, discord.Guild):
                    log.exception("Schedule buttonHandling: interaction.guild not discord.Guild")
                    return
                channelRecruitmentHr = interaction.guild.get_channel(RECRUITMENT_AND_HR)
                if not isinstance(channelRecruitmentHr, discord.TextChannel):
                    log.exception("Schedule buttonHandling: channelRecruitmentHr not discord.TextChannel")
                    return
                if await Schedule.hasCandidatePinged(interaction.user.id, eventList[0]["title"], channelRecruitmentHr) is not None:
                    roleRecruitmentTeam = interaction.guild.get_role(RECRUITMENT_TEAM)
                    if not isinstance(roleRecruitmentTeam, discord.Role):
                        log.exception("Schedule buttonHandling: roleRecruitmentTeam is not discord.Role")
                        return

                    embed = discord.Embed(title="Candidate Accept", description=f"{interaction.user.mention} accepted operation `{eventList[0]['title']}`", color=discord.Color.blue())
                    embed.set_footer(text=f"Candidate ID: {interaction.user.id}")
                    await channelRecruitmentHr.send(roleRecruitmentTeam.mention, embed=embed)

            elif button.custom_id == "reserve":
                # Check if blacklisted
                with open(ROLE_RESERVATION_BLACKLIST_FILE) as f:
                    blacklist = json.load(f)
                if any(interaction.user.id == member["id"] for member in blacklist):
                    await interaction.response.send_message(embed=discord.Embed(title="❌ Sorry, seems like you are not allowed to reserve any roles!", description="If you have any questions about this situation, please contact Unit Staff.", color=discord.Color.red()), ephemeral=True, delete_after=60.0)
                    return

                event = eventList[0]
                scheduleNeedsUpdate = False

                if await Schedule.blockVerifiedRoleRSVP(interaction, event):
                    return

                isAcceptAndReserve = event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"]
                playerCapReached = isinstance(event["maxPlayers"], int) and len(event["accepted"]) >= event["maxPlayers"]

                # Normal reservation, but no space left
                if not isAcceptAndReserve and playerCapReached:
                    await interaction.response.send_message(embed=discord.Embed(title="❌ Sorry, seems like there's no space left in the :b:op!", color=discord.Color.red()), ephemeral=True, delete_after=60.0)
                    return

                # Remove from standby if no vacant roles
                if isAcceptAndReserve and interaction.user.id in event["standby"] and all(event["reservableRoles"].values()):
                    event["standby"].remove(interaction.user.id)
                    embed = self.getEventEmbed(event)
                    await interaction.response.edit_message(embed=embed)

                    with open(EVENTS_FILE, "w") as f:
                        json.dump(events, f, indent=4)
                    return

                # Add to standby
                if isAcceptAndReserve and playerCapReached and interaction.user.id not in event["accepted"] and interaction.user.id not in event["standby"]:
                    for option in rsvpOptions:
                        if interaction.user.id in event[option]:
                            event[option].remove(interaction.user.id)
                    event["standby"].append(interaction.user.id)

                    await interaction.response.send_message(embed=discord.Embed(title="✅ On standby list", description="The event player limit is reached!\nYou have been placed on the standby list. If an accepted member leaves, you will be notified about the vacant roles!", color=discord.Color.green()), ephemeral=True, delete_after=60.0)

                    if interaction.channel is None or isinstance(interaction.channel, discord.ForumChannel) or isinstance(interaction.channel, discord.CategoryChannel):
                        log.exception("Schedule buttonHandling: interaction.channel is invalid type")
                        return
                    embed = self.getEventEmbed(event)
                    originalMsgId = interaction.message.id
                    msg = await interaction.channel.fetch_message(originalMsgId)
                    await msg.edit(embed=embed)

                    with open(EVENTS_FILE, "w") as f:
                        json.dump(events, f, indent=4)
                    return



                # Select role to (un)reserve
                if not isinstance(interaction.user, discord.Member):
                    log.exception("Schedule buttonHandling: interaction.user not discord.Member")
                    return

                vacantRoles = [btnRoleName for btnRoleName, memberId in event["reservableRoles"].items() if memberId is None or interaction.user.guild.get_member(memberId) is None]

                view = ScheduleView()
                options = []

                if len(vacantRoles) > 0:
                    for role in vacantRoles:
                        options.append(discord.SelectOption(label=role))
                    view.add_item(ScheduleSelect(instance=self, eventMsg=interaction.message, placeholder="Select a role.", minValues=1, maxValues=1, customId="reserve_role_select", row=0, options=options))


                # Disable button if user hasn't reserved
                for roleName in event["reservableRoles"]:
                    if event["reservableRoles"][roleName] == interaction.user.id:
                        view.add_item(ScheduleButton(self, interaction.message, row=1, label="Unreserve Current Role", style=discord.ButtonStyle.danger, custom_id="reserve_role_unreserve"))
                        break

                if len(view.children) == 0:
                    await interaction.response.send_message(content=f"{interaction.user.mention} All roles are reserved!", ephemeral=True, delete_after=60.0)
                    return

                await interaction.response.send_message(content=interaction.user.mention, view=view, ephemeral=True, delete_after=60.0)
                return

            elif button.custom_id == "reserve_role_unreserve":
                scheduleNeedsUpdate = False
                if message is None:
                    log.exception("Schedule buttonHandling reserve_role_unreserve: message is None")
                    return
                event = [event for event in events if event["messageId"] == message.id][0]

                # Disable all discord.ui.Item
                if button.view is None:
                    log.exception("Schedule buttonHandling reserve_role_unreserve: button.view is None")
                    return

                for child in button.view.children:
                    child.disabled = True
                await interaction.response.edit_message(view=button.view)

                # Unreserve role
                for roleName in event["reservableRoles"]:
                    if event["reservableRoles"][roleName] != interaction.user.id:
                        continue

                    event["reservableRoles"][roleName] = None
                    await interaction.followup.send(embed=discord.Embed(title=f"✅ Role unreserved: `{roleName}`", color=discord.Color.green()), ephemeral=True)

                    # Event view has button "Accept & Reserve"
                    if event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"] and interaction.user.id in event["accepted"]:
                        event["accepted"].remove(interaction.user.id)
                        await message.edit(embed=self.getEventEmbed(event))

                    # Notify people on standby that reservable role(s) are vacant
                    if len(event["standby"]) > 0 and isinstance(event["maxPlayers"], int) and len(event["accepted"]) < event["maxPlayers"] and event["reservableRoles"] and not all(event["reservableRoles"].values()):
                        if not isinstance(interaction.guild, discord.Guild):
                            log.exception("Schedule buttonHandling: interaction.guild not discord.Guild")
                            return

                        vacantRoles = "\n".join([f"`{role}`" for role, reservedUser in event["reservableRoles"].items() if not reservedUser])
                        embed = discord.Embed(
                            title="Role(s) vacant",
                            description=f"The following role(s) are now vacant for event `{event['title']}`:\n{vacantRoles}",
                            color=discord.Color.green()
                        )

                        for standbyMemberId in event["standby"]:
                            standbyMember = interaction.guild.get_member(standbyMemberId)
                            if standbyMember is None:
                                log.warning(f"Schedule buttonhandling: Failed to get member with id '{standbyMemberId}'")
                                continue

                            try:
                                await standbyMember.send(embed=embed)
                            except Exception:
                                log.warning(f"Schedule buttonhandling: Failed to DM {standbyMember.id} [{standbyMember.display_name}] about vacant roles")
                        break

            elif button.custom_id == "config":
                event = eventList[0]
                scheduleNeedsUpdate = False

                if self.isAllowedToEdit(interaction.user, event["authorId"]) is False:
                    await interaction.response.send_message("Only the host, Unit Staff and Server Hampters can configure the event!", ephemeral=True, delete_after=60.0)
                    return

                view = ScheduleView()
                items = [
                    ScheduleButton(self, interaction.message, row=0, label="Edit", style=discord.ButtonStyle.primary, custom_id="edit"),
                    ScheduleButton(self, interaction.message, row=0, label="Delete", style=discord.ButtonStyle.danger, custom_id="delete")
                ]
                for item in items:
                    view.add_item(item)
                await interaction.response.send_message(content=f"{interaction.user.mention} What would you like to configure?", view=view, ephemeral=True, delete_after=30.0)

            elif button.custom_id == "edit":
                scheduleNeedsUpdate = False
                if message is None:
                    log.exception("Schedule buttonHandling edit: message is None")
                    return

                event = [event for event in events if event["messageId"] == message.id][0]
                if self.isAllowedToEdit(interaction.user, event["authorId"]) is False:
                    await interaction.response.send_message("Restart the editing process.\nThe button points to an event you aren't allowed to edit.", ephemeral=True, delete_after=5.0)
                    return
                await self.editEvent(interaction, event, message)

            elif button.custom_id == "delete":
                if message is None:
                    log.exception("Schedule buttonHandling delete: message is None")
                    return

                event = [event for event in events if event["messageId"] == message.id][0]
                scheduleNeedsUpdate = False

                embed = discord.Embed(title=f"Are you sure you want to delete this {event['type'].lower()}: `{event['title']}`?", color=discord.Color.orange())
                view = ScheduleView()
                items = [
                    ScheduleButton(self, message, row=0, label="Delete", style=discord.ButtonStyle.success, custom_id="delete_event_confirm"),
                    ScheduleButton(self, message, row=0, label="Cancel", style=discord.ButtonStyle.danger, custom_id="delete_event_cancel"),
                ]
                for item in items:
                    view.add_item(item)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=60.0)

            elif button.custom_id == "delete_event_confirm":
                scheduleNeedsUpdate = False

                if button.view is None:
                    log.exception("Schedule buttonHandling delete_event_confirm: button.view is None")
                    return

                if message is None:
                    log.exception("Schedule buttonHandling delete_event_confirm: message is None")
                    return

                # Disable buttons
                for button in button.view.children:
                    button.disabled = True
                await interaction.response.edit_message(view=button.view)

                # Delete event
                event = [event for event in events if event["messageId"] == message.id][0]
                await message.delete()
                try:
                    log.info(f"{interaction.user.id} [{interaction.user.display_name}] deleted the event '{event['title']}'")
                    await interaction.followup.send(embed=discord.Embed(title=f"✅ {event['type']} deleted!", color=discord.Color.green()), ephemeral=True)

                    # Notify attendees
                    utcNow = datetime.now(timezone.utc)
                    startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
                    if event["maxPlayers"] != "hidden" and utcNow > startTime + timedelta(minutes=30):
                        await self.saveEventToHistory(event)
                    else:
                        guild = self.bot.get_guild(GUILD_ID)
                        if guild is None:
                            log.exception("Schedule buttonHandling delete_event_confirm: guild is None")
                            return

                        for memberId in event["accepted"] + event["declined"] + event["tentative"] + event["standby"]:
                            member = guild.get_member(memberId)
                            if member is not None:
                                embed = discord.Embed(title=f"🗑 {event.get('type', 'Operation')} deleted: {event['title']}!", description=f"The {event.get('type', 'Operation').lower()} was scheduled to run:\n{discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}", color=discord.Color.red())
                                embed.set_footer(text=f"By: {interaction.user}")
                                try:
                                    await member.send(embed=embed)
                                except Exception as e:
                                    log.warning(f"{member.id} [{member.display_name}]")
                except Exception as e:
                    log.exception(f"{interaction.user.id} [{interaction.user.display_name}]")
                events.remove(event)

            elif button.custom_id == "delete_event_cancel":
                if button.view is None:
                    log.exception("Schedule buttonHandling delete_event_cancel: button.view is None")
                    return

                for item in button.view.children:
                    item.disabled = True
                await interaction.response.edit_message(view=button.view)
                await interaction.followup.send(embed=discord.Embed(title=f"❌ Event deletion canceled!", color=discord.Color.red()), ephemeral=True)
                return

            elif button.custom_id is not None and button.custom_id.startswith("event_schedule_"):
                if button.view is None:
                    log.exception("Schedule buttonHandling event_schedule_: button.view is None")
                    return

                if interaction.user.id != button.view.authorId:
                    await interaction.response.send_message(f"{interaction.user.mention} Only the one who executed the command may interact with the buttons!", ephemeral=True, delete_after=10.0)
                    return

                buttonLabel = button.custom_id[len("event_schedule_"):]

                generateModal = lambda style, placeholder, default, required, minLength, maxLength: ScheduleModal(
                        self, title="Create event", customId=f"modal_create_{buttonLabel}", eventMsg=interaction.message, view=button.view
                    ).add_item(
                        discord.ui.TextInput(
                            label=buttonLabel.replace("_", " ").capitalize(), style=style, placeholder=placeholder, default=default, required=required, min_length=minLength, max_length=maxLength
                        )
                    )

                previewEmbedDict = self.fromPreviewEmbedToDict(interaction.message.embeds[0])

                isAllRequiredInfoFilled = lambda : len([child.label for child in button.view.children if isinstance(child, discord.ui.Button) and child.label != "Submit" and child.style == discord.ButtonStyle.danger and child.disabled == False]) == 0

                match buttonLabel:
                    # INFO FIELDS
                    case "type":
                        typeOptions = []
                        if [True for role in interaction.user.roles if role.id in CMD_LIMIT_ZEUS]:
                            typeOptions.append(discord.SelectOption(emoji="🟩", label="Operation"))

                        typeOptions.extend(
                            [discord.SelectOption(emoji="🟦", label="Workshop"),
                            discord.SelectOption(emoji="🟨", label="Event")]
                        )
                        await interaction.response.send_message(interaction.user.mention, view=self.generateSelectView(
                            typeOptions,
                            False,
                            previewEmbedDict["type"] or "",
                            interaction.message,
                            "Select event type.",
                            "select_create_type",
                            button.view
                        ),
                            ephemeral=True,
                            delete_after=60.0
                        )

                    case "title":
                        placeholder = "Operation Honda Civic" if previewEmbedDict["title"] == SCHEDULE_EVENT_PREVIEW_EMBED["title"] else previewEmbedDict["title"]
                        default = None if previewEmbedDict["title"] == SCHEDULE_EVENT_PREVIEW_EMBED["title"] else previewEmbedDict["title"]
                        await interaction.response.send_modal(generateModal(discord.TextStyle.short, placeholder, default, True, 1, 256))

                    case "description":
                        placeholder = "Wazzup beijing" if previewEmbedDict["description"] == SCHEDULE_EVENT_PREVIEW_EMBED["description"] else previewEmbedDict["description"][:100]
                        default = None if previewEmbedDict["description"] == SCHEDULE_EVENT_PREVIEW_EMBED["description"] else previewEmbedDict["description"]
                        await interaction.response.send_modal(generateModal(discord.TextStyle.long, placeholder, default, True, 1, 4000))

                    case "duration":
                        placeholder = "2h30m" if previewEmbedDict["duration"] is None else previewEmbedDict["duration"]
                        default = "" if previewEmbedDict["duration"] is None else previewEmbedDict["duration"]
                        await interaction.response.send_modal(generateModal(discord.TextStyle.short, placeholder, default, True, 1, 16))

                    case "time":
                        # Set user time zone
                        with open(MEMBER_TIME_ZONES_FILE) as f:
                            memberTimeZones = json.load(f)
                        if str(interaction.user.id) not in memberTimeZones:
                            await interaction.response.send_message(f"{interaction.user.mention} Please retry after you've set a time zone in DMs!", ephemeral=True, delete_after=10.0)
                            timeZoneOutput = await self.changeTimeZone(interaction.user)
                            if timeZoneOutput is False:
                                await interaction.followup.send(embed=discord.Embed(title="❌ Timezone configuration canceled", description="You must provide a time zone in your DMs!", color=discord.Color.red()))
                            return

                        timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
                        nextHalfHour = datetime.now(timezone.utc) + (datetime.min.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)) % timedelta(minutes=30)

                        placeholder = nextHalfHour.astimezone(timeZone).strftime(TIME_FORMAT)
                        default = ""

                        if previewEmbedDict["time"] is not None:
                            default = placeholder = datetimeParse(previewEmbedDict["time"]).replace(tzinfo=pytz.utc).astimezone(timeZone).strftime(TIME_FORMAT)

                        await interaction.response.send_modal(generateModal(
                            style=discord.TextStyle.short,
                            placeholder=placeholder,
                            default=default,
                            required=True,
                            minLength=1,
                            maxLength=32
                        ))

                    case "external_url":
                        placeholder = "https://www.gnu.org" if previewEmbedDict["externalURL"] is None else previewEmbedDict["externalURL"][:100]
                        default = "" if previewEmbedDict["externalURL"] is None else previewEmbedDict["externalURL"]
                        await interaction.response.send_modal(generateModal(discord.TextStyle.short, placeholder, default, False, None, 1024))

                    case "reservable_roles":
                        placeholder = "Actual\n2IC\nA-10C Pilot"
                        default = ""
                        if previewEmbedDict["reservableRoles"] is not None:
                            default = placeholder = "\n".join(previewEmbedDict["reservableRoles"])[:100]

                        await interaction.response.send_modal(generateModal(discord.TextStyle.long, placeholder, default, False, 1, 512))

                    case "map":
                        with open(GENERIC_DATA_FILE) as f:
                            genericData = json.load(f)
                            if "modpackMaps" not in genericData:
                                log.warning("Schedule buttonHandling map: modpackMaps not in genericData")
                                return

                        options = [discord.SelectOption(label=mapName) for mapName in genericData["modpackMaps"]]
                        await interaction.response.send_message(interaction.user.mention, view=self.generateSelectView(
                            options,
                            True,
                            previewEmbedDict["map"],
                            interaction.message,
                            "Select a map.",
                            "select_create_map",
                            button.view
                        ),
                            ephemeral=True,
                            delete_after=60.0
                        )

                    case "max_players":
                        default = str(previewEmbedDict["maxPlayers"])

                        # Correct no input to default=""
                        if previewEmbedDict["maxPlayers"] == "hidden" and button.style == discord.ButtonStyle.danger:
                            default = ""

                        await interaction.response.send_modal(generateModal(
                            style=discord.TextStyle.short,
                            placeholder="None / <Number> / Anonymous / Hidden",  # Always this so ppl know what to type
                            default=default,
                            required=True,
                            minLength=1,
                            maxLength=9
                        ))

                    case "linking":
                        with open(WORKSHOP_INTEREST_FILE) as f:
                            workshops = json.load(f)
                        options = [discord.SelectOption(label=wsName) for wsName in workshops]
                        await interaction.response.send_message(interaction.user.mention, view=self.generateSelectView(
                            options,
                            True,
                            previewEmbedDict["workshopInterest"] if "workshopInterest" in previewEmbedDict else "",
                            interaction.message,
                            "Link event to a workshop.",
                            "select_create_linking",
                            button.view
                        ),
                            ephemeral=True,
                            delete_after=60.0
                        )


                    # FILES
                    case "files":
                        view = ScheduleView(authorId=interaction.user.id, previousMessageView=button.view)
                        items = [
                            ScheduleButton(self, interaction.message, row=0, label="Add", style=discord.ButtonStyle.success, custom_id="event_schedule_files_add", disabled=(len(previewEmbedDict["files"]) == 10)),
                            ScheduleButton(self, interaction.message, row=0, label="Remove", style=discord.ButtonStyle.danger, custom_id="event_schedule_files_remove", disabled=(len(previewEmbedDict["files"]) == 0)),
                        ]
                        for item in items:
                            view.add_item(item)

                        embed = discord.Embed(title="Attaching files", description="You may attach up to 10 files to your event.\nUpload them first using the command `/fileupload`.", color=discord.Color.gold())
                        await interaction.response.send_message(interaction.user.mention, embed=embed, view=view, ephemeral=True, delete_after=300.0)

                    case "files_add":
                        messageNew = await interaction.channel.fetch_message(message.id)
                        if not isinstance(messageNew, discord.Message):
                            log.exception("Schedule ButtonHandling files_add: messageNew not discord.Message")
                            return
                        previewEmbedDict = self.fromPreviewEmbedToDict(messageNew.embeds[0])
                        options = [discord.SelectOption(label=fileUpload) for fileUpload in Schedule.getUserFileUploads(str(interaction.user.id)) if fileUpload not in previewEmbedDict["files"]]

                        if len(options) == 0:
                            embed = discord.Embed(title="Attaching files [Add]", description="You have not uploaded any files yet.\nTo upload new files; run the command `/fileupload`.", color=discord.Color.red())
                            view = None
                        else:
                            embed = discord.Embed(title="Attaching files [Add]", description="Select a file to upload from the select menus below.\nTo upload new files; run the command `/fileupload`.", color=discord.Color.gold())
                            view = self.generateSelectView(options, False, None, messageNew, "Select a file.", "select_create_files_add", button.view.previousMessageView)

                        await interaction.response.edit_message(embed=embed, view=view)

                    case "files_remove":
                        messageNew = await interaction.channel.fetch_message(message.id)
                        if not isinstance(messageNew, discord.Message):
                            log.exception("Schedule ButtonHandling files_remove: messageNew not discord.Message")
                            return
                        previewEmbedDict = self.fromPreviewEmbedToDict(messageNew.embeds[0])
                        options = [discord.SelectOption(label=previewFile) for previewFile in previewEmbedDict["files"]]

                        if len(options) == 0:
                            embed = discord.Embed(title="Attaching files [Remove]", description="You have not selected any file to be attached.\nTo select a file, press the `Add` button.", color=discord.Color.red())
                            view = None
                        else:
                            embed = discord.Embed(title="Attaching files [Remove]", description="Select a file to remove from the select menus below.", color=discord.Color.gold())
                            view = self.generateSelectView(options, False, None, messageNew, "Select a file.", "select_create_files_remove", button.view.previousMessageView)

                        await interaction.response.edit_message(embed=embed, view=view)


                    # TEMPLATES
                    case "save_as_template":
                        if isAllRequiredInfoFilled() is False:
                            await interaction.response.send_message(f"{interaction.user.mention} Before saving the event as a template, you need to fill out the mandatory (red buttons) information!", ephemeral=True, delete_after=10.0)
                            return

                        await interaction.response.send_modal(generateModal(
                            style=discord.TextStyle.short,
                            placeholder="Fixed Wing Workshop + Cert",
                            default=None,
                            required=True,
                            minLength=1,
                            maxLength=63  # (BUTTON_LABEL_MAX_LEN := 80) - len("Select Template: ")
                        ))

                    case "update_template":
                        if isAllRequiredInfoFilled() is False:
                            await interaction.response.send_message(f"{interaction.user.mention} Before updating the template, you need to fill out the mandatory (red buttons) information!", ephemeral=True, delete_after=10.0)
                            return

                        # Fetch template name from button label
                        templateName = ""
                        for child in button.view.children:
                            if isinstance(child, discord.ui.Button) and child.label is not None and child.label.startswith("Select Template"):
                                templateName = "".join(child.label.split(":")[1:]).strip()
                                break
                        if templateName == "":
                            log.exception("Schedule buttonHandling: templateName is empty")
                            return
                        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Updated template '{templateName}'")
                        # Write to file
                        filename = f"data/{previewEmbedDict['type'].lower()}Templates.json"
                        with open(filename) as f:
                            templates = json.load(f)

                        templateIndex = None
                        for idx, template in enumerate(templates):
                            if template["templateName"] == templateName:
                                templateIndex = idx
                                break
                        else:
                            log.exception("Schedule buttonHandling: templateIndex not found")
                            return

                        previewEmbedDict["templateName"] = templateName
                        for shit in SCHEDULE_TEMPLATE_REMOVE_FROM_EVENT:
                            previewEmbedDict.pop(shit, None)
                        templates[templateIndex] = previewEmbedDict
                        with open(filename, "w") as f:
                            json.dump(templates, f, indent=4)

                        # Reply
                        await interaction.response.send_message(f"✅ Updated template: `{templateName}`", ephemeral=True, delete_after=10.0)


                    # EVENT FINISHING
                    case "submit":
                        log.debug(f"{interaction.user.id} [{interaction.user.display_name}] Submitted with event type '{previewEmbedDict['type']}'")
                        # Check if all mandatory fields are filled
                        if isAllRequiredInfoFilled() is False:
                            await interaction.response.send_message(f"{interaction.user.mention} Before creating the event, you need to fill out the mandatory (red buttons) information!", ephemeral=True, delete_after=10.0)
                            return

                        # Final fixup
                        previewEmbedDict["authorId"] = interaction.user.id
                        filesRealName = []
                        for filenameShort in previewEmbedDict["files"]:
                            for osFile in os.listdir("tmp/fileUpload"):
                                if str(interaction.user.id) in osFile and filenameShort in osFile:
                                    filesRealName.append(osFile)
                        previewEmbedDict["files"] = filesRealName


                        # Append event to JSON
                        with open(EVENTS_FILE) as f:
                            events = json.load(f)
                        events.append(previewEmbedDict)
                        with open(EVENTS_FILE, "w") as f:
                            json.dump(events, f, indent=4)

                        # Reply
                        await interaction.response.edit_message(content=f"`{previewEmbedDict['title']}` is now on <#{SCHEDULE}>!", embed=None, view=None)

                        # Update schedule
                        await self.updateSchedule()
                        log.debug(f"{interaction.user.id} [{interaction.user.display_name}] Submitted with event type, after updateschedule '{previewEmbedDict['type']}'")


                        guild = interaction.guild
                        if not isinstance(guild, discord.Guild):
                            log.exception("Schedule buttonHandling: guild not discord.Guild")
                            return

                        # Workshop interest ping
                        workshopInterestValue = previewEmbedDict.get("workshopInterest", None)
                        if workshopInterestValue:
                            with open(WORKSHOP_INTEREST_FILE) as f:
                                fileWSINT = json.load(f)
                            targetWorkshopMembers = [wsDetails.get("members", []) for wsName, wsDetails in fileWSINT.items() if workshopInterestValue == wsName][0]
                            if targetWorkshopMembers:
                                channelArmaDiscussion = guild.get_channel(ARMA_DISCUSSION)
                                if not isinstance(channelArmaDiscussion, discord.TextChannel):
                                    log.exception("Schedule buttonHandling: channelArmaDiscussion not discord.TextChannel")
                                    return

                                message = ""
                                for memberId in targetWorkshopMembers:
                                    message += workshopMember.mention + " " if (workshopMember := guild.get_member(memberId)) else ""
                                await channelArmaDiscussion.send(f"{message}\n**{previewEmbedDict['title']}** is up on <#{SCHEDULE}> - which you are interested in.\nNo longer interested? Unlist yourself in <#{WORKSHOP_INTEREST}>")


                        # Operation Pings
                        if previewEmbedDict["type"].lower() == "operation":
                            roleOperationPings = guild.get_role(OPERATION_PINGS)
                            if not isinstance(roleOperationPings, discord.Role):
                                log.exception("Schedule buttonHandling: roleOperationPings not discord.Role")
                                return

                            channelOperationAnnouncements = guild.get_channel(OPERATION_ANNOUNCEMENTS)
                            if not isinstance(channelOperationAnnouncements, discord.TextChannel):
                                log.exception("Schedule buttonHandling: channelOperationAnnouncements not discord.TextChannel")
                                return

                            with open(EVENTS_FILE) as f:
                                events = json.load(f)
                            event = [event for event in events if event["authorId"] == interaction.user.id and event["title"] == previewEmbedDict["title"] and event["description"] == previewEmbedDict["description"]][0]

                            embed = discord.Embed(title="Operation scheduled", url=f"https://discord.com/channels/{GUILD_ID}/{SCHEDULE}/{event['messageId']}", description=f"Title: **{previewEmbedDict['title']}**\nTime: {discord.utils.format_dt(UTC.localize(datetime.strptime(previewEmbedDict['time'], TIME_FORMAT)), style='F')}\nDuration: {previewEmbedDict['duration']}", color=EVENT_TYPE_COLORS["Operation"])
                            embed.set_footer(text=f"Created by {interaction.user.display_name}")
                            await channelOperationAnnouncements.send(content=roleOperationPings.mention, embed=embed)

                    case "cancel":
                        embed = discord.Embed(title="Are you sure you want to cancel this event scheduling?", color=discord.Color.orange())
                        view = ScheduleView(authorId=interaction.user.id)
                        items = [
                            ScheduleButton(self, interaction.message, row=0, label="Cancel", style=discord.ButtonStyle.success, custom_id="event_schedule_cancel_confirm"),
                            ScheduleButton(self, interaction.message, row=0, label="No, I changed my mind", style=discord.ButtonStyle.danger, custom_id="event_schedule_cancel_decline"),
                        ]
                        for item in items:
                            view.add_item(item)
                        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=60.0)

                    case "cancel_confirm":
                        if message is None:
                            log.exception("Schedule buttonHandling cancel_confirm: message is None")
                            return
                        for child in button.view.children:
                            if isinstance(child, discord.ui.Button):
                                child.disabled = True
                        await interaction.response.edit_message(view=button.view)
                        await message.edit(content="Nvm guys, didn't wanna bop.", embed=None, view=None)

                    case "cancel_decline":
                        if message is None:
                            log.exception("Schedule buttonHandling cancel_decline: message is None")
                            return
                        for child in button.view.children:
                            if isinstance(child, discord.ui.Button):
                                child.disabled = True
                        await interaction.response.edit_message(view=button.view)
                        await interaction.followup.send(content="Alright, I won't cancel the scheduling.", ephemeral=True)

                if buttonLabel.startswith("select_template"):
                    filename = f"data/{previewEmbedDict['type'].lower()}Templates.json"
                    with open(filename) as f:
                        templates: list[dict] = json.load(f)
                    templates.sort(key=lambda template : template["templateName"])

                    options = [discord.SelectOption(label=template["templateName"], description=template["description"][:100]) for template in templates]
                    setOptionLabel = ""
                    for child in button.view.children:
                        if isinstance(child, discord.ui.Button) and child.label is not None and child.label.startswith("Select Template"):
                            setOptionLabel = "".join(child.label.split(":")[1:]).strip()

                    await interaction.response.send_message(interaction.user.mention, view=self.generateSelectView(
                        options,
                        True,
                        setOptionLabel,
                        interaction.message,
                        "Select a template.",
                        "select_create_select_template",
                        button.view
                    ),
                        ephemeral=True,
                        delete_after=60.0
                    )


                return

            elif button.custom_id == "event_edit_files_add":
                messageNew = await interaction.channel.fetch_message(message.id)
                if not isinstance(messageNew, discord.Message):
                    log.exception("Schedule buttonHandling event_edit_files_add: messageNew not discord.Message")
                    return

                attachmentFilenames = [attachment.filename for attachment in messageNew.attachments]

                # Load all files uploaded by user, that isn't already attached to message
                options = [discord.SelectOption(label=fileUpload) for fileUpload in Schedule.getUserFileUploads(str(interaction.user.id)) if fileUpload not in attachmentFilenames]

                if len(options) == 0:
                    embed = discord.Embed(title="Attaching files [Add]", description="You do not have any new files to attach.\nTo upload new files; run the command `/fileupload`.", color=discord.Color.red())
                    view = None
                else:
                    embed = discord.Embed(title="Attaching files [Add]", description="Select a file to upload from the select menus below.\nTo upload new files; run the command `/fileupload`.", color=discord.Color.gold())
                    view = self.generateSelectView(options, False, None, messageNew, "Select a file.", "edit_select_files_add", button.view.previousMessageView)

                await interaction.response.edit_message(embed=embed, view=view)
                return

            elif button.custom_id == "event_edit_files_remove":
                messageNew = await interaction.channel.fetch_message(message.id)
                if not isinstance(messageNew, discord.Message):
                    log.exception("Schedule buttonHandling event_edit_files_remove: messageNew not discord.Message")
                    return

                attachmentFilenames = [attachment.filename for attachment in messageNew.attachments]
                options = [discord.SelectOption(label=fileUpload) for fileUpload in Schedule.getUserFileUploads(str(interaction.user.id)) if fileUpload in attachmentFilenames]

                if len(options) == 0:
                    embed = discord.Embed(title="Attaching files [Remove]", description="You have not selected any file to be attached.\nTo select a file, press the `Add` button.", color=discord.Color.red())
                    view = None
                else:
                    embed = discord.Embed(title="Attaching files [Remove]", description="Select a file to remove from the select menus below.", color=discord.Color.gold())
                    view = self.generateSelectView(options, False, None, messageNew, "Select a file.", "edit_select_files_remove", button.view.previousMessageView)

                await interaction.response.edit_message(embed=embed, view=view)
                return


            if scheduleNeedsUpdate:
                try:
                    embed = self.getEventEmbed(event)
                    if fetchMsg:  # Could be better - could be worse...
                        if interaction.channel is None or isinstance(interaction.channel, discord.ForumChannel) or isinstance(interaction.channel, discord.CategoryChannel):
                            log.exception("Schedule buttonHandling: interaction.channel is invalid type")
                            return

                        originalMsgId = interaction.message.id
                        msg = await interaction.channel.fetch_message(originalMsgId)
                        await msg.edit(embed=embed)
                    else:
                        await interaction.response.edit_message(embed=embed)
                except Exception as e:
                    log.exception(f"{interaction.user.id} | [{interaction.user.display_name}]")

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            log.exception(f"{interaction.user.id} | [{interaction.user.display_name}]")

    def generateSelectView(self, options: list[discord.SelectOption], noneOption: bool, setOptionLabel: str | None, eventMsg: discord.Message, placeholder: str, customId: str, eventMsgView: discord.ui.View | None = None):
        """Generates good select menu view - ceil(len(options)/25) dropdowns.

        Parameters:
        options (list[discord.SelectOption]): All select menu options
        noneOption (bool): Adds an option for None.
        setOptionLabel (str): Removes this (selected) option from the options.
        eventMsg (discord.Message): The event message.
        placeholder (str): Menu placeholder.
        customId (str): Custom ID of select menu.
        eventMsgView (discord.ui.View | None = None): Optional view of eventMsg

        Returns:
        None.
        """

        # Remove setOptionLabel from options
        if setOptionLabel is not None:
            for idx, option in enumerate(options):
                if option.label == setOptionLabel:
                    options.pop(idx)
                    break

        if noneOption:
            options.insert(0, discord.SelectOption(label="None", emoji="🚫"))

        # Generate view
        view = ScheduleView(previousMessageView=(eventMsgView.previousMessageView if hasattr(eventMsgView, "previousMessageView") else None))
        for i in range(ceil(len(options) / 25)):
            view.add_item(ScheduleSelect(instance=self, eventMsg=eventMsg, placeholder=placeholder, minValues=1, maxValues=1, customId=f"{customId}_REMOVE{i}", row=i, options=options[:25], eventMsgView=eventMsgView))
            options = options[25:]

        return view

    async def selectHandling(self, select: discord.ui.Select, interaction: discord.Interaction, eventMsg: discord.Message, eventMsgView: discord.ui.View | None) -> None:
        """Handling all schedule select menu interactions.

        Parameters:
        select (discord.ui.Select): The Discord select menu
        interaction (discord.Interaction): The Discord interaction.
        eventMsg (discord.Message): The event message.
        eventMsgView (discord.ui.View | None): The event message view.

        Returns:
        None.
        """
        if not isinstance(interaction.user, discord.Member):
            log.exception("Schedule selectHandling: interaction.user not discord.Member")
            return

        selectedValue = select.values[0]

        if select.custom_id.startswith("select_create_"):
            if eventMsgView is None:
                log.exception("Schedule selectHandling: eventMsgView is None")
                return

            infoLabel = select.custom_id[len("select_create_"):].split("_REMOVE")[0]  # e.g. "type"

            # Disable all discord.ui.Item if not in blacklist
            CASES_WHEN_SELECT_MENU_EDITS_AWAY = ("files_add", "files_remove")
            if infoLabel not in CASES_WHEN_SELECT_MENU_EDITS_AWAY:
                if select.view is None:
                    log.exception("Schedule selectHandling: select.view is None")
                    return
                for child in select.view.children:
                    child.disabled = True
                await interaction.response.edit_message(view=select.view)

            eventMsgNew = await interaction.channel.fetch_message(eventMsg.id)
            if not isinstance(eventMsgNew, discord.Message):
                log.exception("Schedule selectHandling: eventMsgNew not discord.Message")
                return

            previewEmbedDict = self.fromPreviewEmbedToDict(eventMsgNew.embeds[0])
            previewEmbedDict["authorId"] = interaction.user.id


            # Do preview embed edits
            match infoLabel:
                case "type":
                    log.debug(f"{interaction.user.id} [{interaction.user.display_name}] selected event type '{selectedValue}'")
                    previewEmbedDict["type"] = selectedValue

                    templateName = "None"
                    # Fetch templateName
                    for child in eventMsgView.children:
                        if isinstance(child, discord.ui.Button) and child.label is not None and child.label.startswith("Select Template: "):
                            templateName = ":".join(child.label.split(":")[1:]).strip()
                            break

                    # Update view
                    previewView = self.fromDictToPreviewView(previewEmbedDict, templateName)
                    eventMsgView.clear_items()
                    for item in previewView.children:
                        eventMsgView.add_item(item)

                case "map":
                    previewEmbedDict["map"] = None if previewEmbedDict["map"] == "None" else selectedValue

                case "linking":
                    previewEmbedDict["workshopInterest"] = None if selectedValue == "None" else selectedValue

                case "select_template":
                    # Update template buttons label & disabled
                    for child in eventMsgView.children:
                        if not isinstance(child, discord.ui.Button) or child.label is None:
                            continue
                        if child.label.startswith("Select Template"):
                            child.label = f"Select Template: {selectedValue}"
                        elif child.label == "Update Template":
                            child.disabled = (selectedValue == "None")

                    # Insert template info into preview embed and view
                    filename = f"data/{previewEmbedDict['type'].lower()}Templates.json"
                    with open(filename) as f:
                        templates = json.load(f)
                    for template in templates:
                        if template["templateName"] == selectedValue:
                            template["authorId"] = interaction.user.id
                            template["time"] = template["endTime"] = None
                            template["type"] = previewEmbedDict["type"]
                            embed = self.fromDictToPreviewEmbed(template)
                            for child in eventMsgView.children:
                                if not isinstance(child, discord.ui.Button) or child.label is None:
                                    continue

                                # Time is required but will not be saved in templates
                                if child.label == "Time":
                                    child.style = discord.ButtonStyle.danger
                                    continue

                                # All required fields are already filled
                                if child.style == discord.ButtonStyle.danger or child.label == "Type":
                                    child.style = discord.ButtonStyle.success
                                    continue

                                # Linking
                                if child.label == "Linking" and embed.footer.icon_url is not None:
                                    child.style = discord.ButtonStyle.success
                                    continue

                                # Ignore template buttons
                                if "Template" in child.label or child.style == discord.ButtonStyle.primary:
                                    continue

                                # Optional fields
                                jsonKey = (child.label[0].lower() + child.label[1:]).replace(" ", "")
                                if jsonKey == "linking":
                                    jsonKey = "workshopInterest"
                                child.style = discord.ButtonStyle.secondary if template[jsonKey] is None else discord.ButtonStyle.success

                            await eventMsgNew.edit(embed=embed, view=eventMsgView)
                            return


            if infoLabel == "files_add":
                if len(previewEmbedDict["files"]) < 10:
                    previewEmbedDict["files"].append(selectedValue)
            elif infoLabel == "files_remove":
                if selectedValue in previewEmbedDict["files"]:
                    previewEmbedDict["files"].remove(selectedValue)


            if infoLabel.startswith("files"):
                view = ScheduleView(authorId=interaction.user.id, previousMessageView=eventMsgView)
                items = [
                    ScheduleButton(self, eventMsgNew, row=0, label="Add", style=discord.ButtonStyle.success, custom_id="event_schedule_files_add", disabled=(len(previewEmbedDict["files"]) == 10)),
                    ScheduleButton(self, eventMsgNew, row=0, label="Remove", style=discord.ButtonStyle.danger, custom_id="event_schedule_files_remove", disabled=(len(previewEmbedDict["files"]) == 0))
                ]
                for item in items:
                    view.add_item(item)

                embed = discord.Embed(title="Attaching files", description="You may attach up to 10 files to your event.\nUpload them first using the command `/fileupload`.", color=discord.Color.gold())
                await interaction.response.edit_message(embed=embed, view=view)

            # Update eventMsg button style
            for child in eventMsgView.children:
                if isinstance(child, discord.ui.Button) and child.label is not None and child.label.lower().replace(" ", "_") == infoLabel:
                    child.style = discord.ButtonStyle.success
                    break

            # Edit preview embed & view
            await eventMsgNew.edit(embed=self.fromDictToPreviewEmbed(previewEmbedDict), view=eventMsgView)


        elif select.custom_id == "reserve_role_select":
            # Disable all discord.ui.Item
            if select.view is None:
                log.exception("Schedule selectHandling reserve_role_select: select.view is None")
                return

            await interaction.response.edit_message(view=None)

            with open(EVENTS_FILE) as f:
                events = json.load(f)
            event = [event for event in events if event["messageId"] == eventMsg.id][0]

            # Fail if role got reserved
            if event["reservableRoles"][selectedValue] is not None:
                await interaction.followup.send(embed=discord.Embed(title=f"❌ Role is already reserved!", color=discord.Color.red()), ephemeral=True)
                return

            # Remove user from any reserved roles
            for roleName in event["reservableRoles"]:
                if event["reservableRoles"][roleName] == interaction.user.id:
                    event["reservableRoles"][roleName] = None
                    break

            # Reserve desired role
            event["reservableRoles"][selectedValue] = interaction.user.id
            await interaction.followup.send(embed=discord.Embed(title=f"✅ Role reserved: `{selectedValue}`", color=discord.Color.green()), ephemeral=True)

            # Put the user in accepted
            if interaction.user.id in event["declined"]:
                event["declined"].remove(interaction.user.id)
            if interaction.user.id in event["tentative"]:
                event["tentative"].remove(interaction.user.id)
            if interaction.user.id in event["standby"]:
                event["standby"].remove(interaction.user.id)
            if interaction.user.id not in event["accepted"]:
                event["accepted"].append(interaction.user.id)

            # Write changes
            await eventMsg.edit(embed=self.getEventEmbed(event))
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)

            # Ping Recruitment Team if candidate reserves
            if event["type"].lower() == "operation" and any([True for role in interaction.user.roles if role.id == CANDIDATE]):
                if not isinstance(interaction.guild, discord.Guild):
                    log.exception("Schedule selectHandling: interaction.guild not discord.Guild")
                    return
                channelRecruitmentHr = interaction.guild.get_channel(RECRUITMENT_AND_HR)
                if not isinstance(channelRecruitmentHr, discord.TextChannel):
                    log.exception("Schedule selectHandling: channelRecruitmentHr not discord.TextChannel")
                    return
                if (message := await Schedule.hasCandidatePinged(interaction.user.id, event["title"], channelRecruitmentHr)) is not None:
                    roleRecruitmentTeam = interaction.guild.get_role(RECRUITMENT_TEAM)
                    if not isinstance(roleRecruitmentTeam, discord.Role):
                        log.exception("Schedule selectHandling: roleRecruitmentTeam not discord.Role")
                        return
                    if message.embeds:
                        embed = message.embeds[0]
                        embed.description = f"{interaction.user.mention} accepted operation `{event['title']}`\nReserved role `{selectedValue}`"
                        return await message.edit(embed=embed)
                    else:
                        embed = discord.Embed(title="Candidate Accept", description=f"{interaction.user.mention} accepted operation `{event['title']}`\nReserved role `{selectedValue}`", color=discord.Color.blue())
                        embed.set_footer(text=f"Candidate ID: {interaction.user.id}")
                        await channelRecruitmentHr.send(roleRecruitmentTeam.mention, embed=embed)


        elif select.custom_id == "edit_select":
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            event = [event for event in events if event["messageId"] == eventMsg.id][0]

            if self.isAllowedToEdit(interaction.user, event["authorId"]) is False:
                await interaction.response.send_message("Please restart the editing process.", ephemeral=True, delete_after=60.0)
                return

            eventType = event.get("type", "Operation")

            # Editing Type
            match selectedValue:
                case "Type":
                    options = [
                        discord.SelectOption(emoji="🟩", label="Operation"),
                        discord.SelectOption(emoji="🟦", label="Workshop"),
                        discord.SelectOption(emoji="🟨", label="Event")
                    ]
                    view = self.generateSelectView(options, False, eventType, eventMsg, "Select event type.", "edit_select_type")

                    await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

                # Editing Title
                case "Title":
                    modal = ScheduleModal(self, "Title", "modal_title", eventMsg)
                    modal.add_item(discord.ui.TextInput(label="Title", default=event["title"], placeholder="Operation Honda Civic", min_length=1, max_length=256))
                    await interaction.response.send_modal(modal)

                # Editing Linking
                case "Linking":
                    with open(WORKSHOP_INTEREST_FILE) as f:
                        wsIntOptions = json.load(f).keys()

                    options = [discord.SelectOption(label=wsName) for wsName in wsIntOptions]
                    view = self.generateSelectView(options, True, event["map"], eventMsg, "Link event to a workshop.", "edit_select_linking")
                    await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

                # Editing Description
                case "Description":
                    modal = ScheduleModal(self, "Description", "modal_description", eventMsg)
                    modal.add_item(discord.ui.TextInput(style=discord.TextStyle.long, label="Description", default=event["description"], placeholder="Bomb oogaboogas", min_length=1, max_length=4000))
                    await interaction.response.send_modal(modal)

                # Editing URL
                case "External URL":
                    modal = ScheduleModal(self, "External URL", "modal_externalURL", eventMsg)
                    modal.add_item(discord.ui.TextInput(style=discord.TextStyle.long, label="URL", default=event["externalURL"], placeholder="OPORD: https://www.gnu.org/", max_length=1024, required=False))
                    await interaction.response.send_modal(modal)

                # Editing Reservable Roles
                case "Reservable Roles":
                    modal = ScheduleModal(self, "Reservable Roles", "modal_reservableRoles", eventMsg)
                    modal.add_item(discord.ui.TextInput(style=discord.TextStyle.long, label="Reservable Roles", default=(None if event["reservableRoles"] is None else "\n".join(event["reservableRoles"].keys())), placeholder="Co-Zeus\nActual\nJTAC\nF-35A Pilot", max_length=512, required=False))
                    await interaction.response.send_modal(modal)

                # Editing Map
                case "Map":
                    with open(GENERIC_DATA_FILE) as f:
                        genericData = json.load(f)
                        if "modpackMaps" not in genericData:
                            log.exception("Schedule buttonHandling: modpackMaps not in genericData")
                            return
                    options = [discord.SelectOption(label=mapName) for mapName in genericData["modpackMaps"]]
                    view = self.generateSelectView(options, True, event["map"], eventMsg, "Select a map.", "edit_select_map")
                    await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

                # Editing Attendence
                case "Max Players":
                    modal = ScheduleModal(self, "Attendees", "modal_maxPlayers", eventMsg)
                    modal.add_item(discord.ui.TextInput(label="Attendees", default=event["maxPlayers"], placeholder="Number / None / Anonymous / Hidden", min_length=1, max_length=9))
                    await interaction.response.send_modal(modal)

                # Editing Duration
                case "Duration":
                    modal = ScheduleModal(self, "Duration", "modal_duration", eventMsg)
                    modal.add_item(discord.ui.TextInput(label="Duration", default=event["duration"], placeholder="2h30m", min_length=1, max_length=16))
                    await interaction.response.send_modal(modal)

                # Editing Time
                case "Time":
                    # Set user time zone
                    with open(MEMBER_TIME_ZONES_FILE) as f:
                        memberTimeZones = json.load(f)
                    if str(interaction.user.id) not in memberTimeZones:
                        await interaction.response.send_message("Please retry after you've set a time zone in DMs!", ephemeral=True, delete_after=60.0)
                        timeZoneOutput = await self.changeTimeZone(interaction.user)
                        if timeZoneOutput is False:
                            await interaction.followup.send(embed=discord.Embed(title="❌ Event Editing canceled", description="You must provide a time zone in your DMs!", color=discord.Color.red()))
                        return

                    # Send modal
                    timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
                    modal = ScheduleModal(self, "Time", "modal_time", eventMsg)
                    modal.add_item(discord.ui.TextInput(label="Time", default=datetimeParse(event["time"]).replace(tzinfo=UTC).astimezone(timeZone).strftime(TIME_FORMAT), placeholder="2069-04-20 04:20 PM", min_length=1, max_length=32))
                    await interaction.response.send_modal(modal)

                # Editing Files
                case "Files":
                    view = ScheduleView(authorId=interaction.user.id)
                    items = [
                        ScheduleButton(self, eventMsg, row=0, label="Add", style=discord.ButtonStyle.success, custom_id="event_edit_files_add", disabled=(len(eventMsg.attachments) == 10)),
                        ScheduleButton(self, eventMsg, row=0, label="Remove", style=discord.ButtonStyle.danger, custom_id="event_edit_files_remove", disabled=(not eventMsg.attachments)),
                    ]
                    for item in items:
                        view.add_item(item)

                    embed = discord.Embed(title="Attaching files", description="You may attach up to 10 files to your event.\nUpload them first using the command `/fileupload`.", color=discord.Color.gold())
                    await interaction.response.send_message(interaction.user.mention, embed=embed, view=view, ephemeral=True, delete_after=300.0)

            log.info(f"{interaction.user.id} [{interaction.user.display_name}] Edited the event '{event['title'] if 'title' in event else event['templateName']}'")

        # All select menu options in edit_select
        elif select.custom_id.startswith("edit_select_"):
            eventKey = select.custom_id[len("edit_select_"):].split("_REMOVE")[0]  # e.g. "files_add"

            with open(EVENTS_FILE) as f:
                events = json.load(f)
            event = [event for event in events if event["messageId"] == eventMsg.id][0]

            match eventKey:
                case "files_add":
                    allUserFiles = Schedule.getUserFileUploads(str(interaction.user.id), fullFilename=True)
                    specifiedFileList = [file for file in allUserFiles if file.split("_", 2)[2] == selectedValue]
                    if not specifiedFileList:
                        log.exception(f"Schedule selectHandling files_add: Could not find '{selectedValue}' in specifiedFileList")
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Interaction failed", description="Could not find file in fileuploads!", color=discord.Color.red()), ephemeral=True, delete_after=5.0)
                        return

                    filenameFull = specifiedFileList[0]
                    if filenameFull in event["files"]:
                        await interaction.response.send_message(embed=discord.Embed(title="❌ File already added", color=discord.Color.red()), ephemeral=True, delete_after=5.0)
                        return

                    filenameShort = filenameFull.split("_", 2)[2]
                    event["files"].append(filenameFull)
                    eventMsgNew = await interaction.channel.fetch_message(eventMsg.id)
                    with open(f"tmp/fileUpload/{filenameFull}", "rb") as f:
                        await eventMsgNew.add_files(discord.File(f, filename=filenameShort))

                case "files_remove":
                    eventMsgNew = await interaction.channel.fetch_message(eventMsg.id)
                    eventAttachmentDict = {eventAttachment.filename: eventAttachment for eventAttachment in eventMsgNew.attachments}
                    if selectedValue not in eventAttachmentDict:
                        log.exception(f"Schedule selectHandling files_remove: Could not find '{selectedValue}' in eventMsg.attachments")
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Interaction failed", description="Could not find attachment in message!", color=discord.Color.red()), ephemeral=True, delete_after=5.0)
                        return

                    allUserFiles = Schedule.getUserFileUploads(str(interaction.user.id), fullFilename=True)
                    filenameFull = [file for file in allUserFiles if file.split("_", 2)[2] == selectedValue][0]
                    if filenameFull not in event["files"]:
                        log.exception(f"Schedule selectHandling files_remove: filenameFull '{filenameFull}' not in event['files']")
                        await interaction.response.send_message(embed=discord.Embed(title="❌ File already removed", color=discord.Color.red()), ephemeral=True, delete_after=5.0)
                        return

                    event["files"].remove(filenameFull)
                    await eventMsgNew.remove_attachments(eventAttachmentDict[selectedValue])

                case _:
                    event[eventKey] = None if selectedValue == "None" else selectedValue

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)

            await eventMsg.edit(embed=self.getEventEmbed(event))
            await interaction.response.send_message(embed=discord.Embed(title="✅ Event edited", color=discord.Color.green()), ephemeral=True, delete_after=5.0)

    async def modalHandling(self, modal: discord.ui.Modal, interaction: discord.Interaction, eventMsg: discord.Message, view: discord.ui.View | None) -> None:
        if not isinstance(interaction.user, discord.Member):
            log.exception("Schedule modalHandling: interaction.user not discord.Member")
            return
        value: str = modal.children[0].value.strip()

        # == Creating Event ==

        if modal.custom_id.startswith("modal_create_") and view is not None:
            infoLabel = modal.custom_id[len("modal_create_"):]
            followupMsg = {}

            # Update embed
            previewEmbedDict = self.fromPreviewEmbedToDict(eventMsg.embeds[0])
            previewEmbedDict["authorId"] = interaction.user.id

            match infoLabel:
                case "title":
                    previewEmbedDict["title"] = SCHEDULE_EVENT_PREVIEW_EMBED["title"] if value == "" else value

                case "description":
                    previewEmbedDict["description"] = SCHEDULE_EVENT_PREVIEW_EMBED["description"] if value == "" else value

                case "duration":
                    if not re.match(r"^\s*((([1-9]\d*)?\d\s*h(\s*([0-5])?\d\s*m?)?)|(([0-5])?\d\s*m))\s*$", value):
                        await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                        return

                    hours, minutes, delta = self.getDetailsFromDuration(value)
                    previewEmbedDict["duration"] = f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}"

                case "time":
                    # Basic premise
                    with open(MEMBER_TIME_ZONES_FILE) as f:
                        memberTimeZones = json.load(f)
                    timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
                    try:
                        startTime = datetimeParse(value, tzinfos=None)
                    except Exception:
                        await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                        return

                    startTime = timeZone.localize(startTime).astimezone(pytz.utc)
                    if startTime < (datetime.now(timezone.utc) - timedelta(weeks=52/2)):
                        await interaction.response.send_message(interaction.user.mention, embed=discord.Embed(title="❌ Operation set too far in the past!", description="You've entered a time that is too far in the past!", color=discord.Color.red()), ephemeral=True, delete_after=10.0)
                        return

                    # Set time
                    previewEmbedDict["time"] = startTime.strftime(TIME_FORMAT)
                    previewEmbedDict["endTime"] = None
                    # Set endTime if duration available
                    if previewEmbedDict["duration"] is not None:
                        hours, minutes, delta = self.getDetailsFromDuration(previewEmbedDict["duration"])
                        previewEmbedDict["endTime"] = (startTime + delta).strftime(TIME_FORMAT)

                    collision = Schedule.eventCollisionCheck(startTime, (startTime + delta) if previewEmbedDict["endTime"] else startTime+timedelta(minutes=30))
                    if collision:
                        followupMsg["embed"] = discord.Embed(title="❌ There is a collision with another event!", description=collision, color=discord.Color.red())
                        followupMsg["embed"].set_footer(text="You may still continue with the provided time - but not recommended.")

                    if startTime < datetime.now(timezone.utc):
                        followupMsg["content"] = interaction.user.mention
                        followupMsg["embed"] = discord.Embed(title="⚠️ Operation set in the past!", description="You've entered a time that is in the past!", color=discord.Color.orange())

                case "external_url":
                    previewEmbedDict["externalURL"] = value or None

                case "reservable_roles":
                    previewEmbedDict["reservableRoles"] = None if value == "" else {role.strip(): None for role in value.split("\n") if role.strip() != ""}
                    if len(previewEmbedDict["reservableRoles"]) > 20:
                        previewEmbedDict["reservableRoles"] = None
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Too many roles", description=f"Due to Discord character limitation, we've set the cap to 20 roles.\nLink your order, e.g. OPORD, under URL if you require more flexibility.\n\nYour roles:\n{value}"[:4096], color=discord.Color.red()), ephemeral=True, delete_after=10.0)
                        return

                case "max_players":
                    valueLower = value.lower()
                    if valueLower not in ("none", "hidden", "anonymous") and not value.isdigit():
                        await interaction.response.send_message(embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                        return

                    if valueLower == "none":
                        previewEmbedDict["maxPlayers"] = None
                    elif value.isdigit():
                        previewEmbedDict["maxPlayers"] = 50 if int(value) > MAX_SERVER_ATTENDANCE else int(value)
                    else:
                        previewEmbedDict["maxPlayers"] = valueLower

                case "save_as_template":
                    previewEmbedDict["templateName"] = value

                    # Write to file
                    filename = f"data/{previewEmbedDict['type'].lower()}Templates.json"
                    with open(filename) as f:
                        templates: list[dict] = json.load(f)
                    templateOverwritten = (False, 0)
                    for idx, template in enumerate(templates):
                        if template["templateName"] == previewEmbedDict["templateName"]:
                            templateOverwritten = (True, idx)
                            break
                    log.info(f"{interaction.user.id} [{interaction.user.display_name}] Saved {('[Overwritten] ') * templateOverwritten[0]}a template as '{previewEmbedDict['templateName']}'")
                    if templateOverwritten[0]:
                        templates.pop(templateOverwritten[1])
                    for shit in SCHEDULE_TEMPLATE_REMOVE_FROM_EVENT:
                        previewEmbedDict.pop(shit, None)

                    templates.append(previewEmbedDict)
                    templates.sort(key=lambda template : template["templateName"])
                    with open(filename, "w") as f:
                        json.dump(templates, f, indent=4)

                    # Update label
                    for child in view.children:
                        if not isinstance(child, discord.ui.Button) or child.label is None:
                            continue
                        if child.label.startswith("Select Template"):
                            child.label = f"Select Template: {value}"
                            child.disabled = False
                        elif child.label == "Update Template":
                            child.disabled = False

                    # Reply & edit msg
                    await interaction.response.send_message(f"✅ Saved {('[Overwritten] ') * templateOverwritten[0]}template as: `{value}`", ephemeral=True, delete_after=10.0)
                    await eventMsg.edit(view=view)
                    return

            # Update button style
            for child in view.children:
                if isinstance(child, discord.ui.Button) and child.label is not None and child.label.lower().replace(" ", "_") == infoLabel:
                    if value == "":
                        child.style = discord.ButtonStyle.danger if SCHEDULE_EVENT_VIEW[infoLabel.replace("_", " ").title().replace("Url", "URL")]["required"] else discord.ButtonStyle.secondary
                    else:
                        child.style = discord.ButtonStyle.success
                    break

            await interaction.response.edit_message(embed=self.fromDictToPreviewEmbed(previewEmbedDict), view=view)
            if followupMsg:
                await interaction.followup.send(followupMsg["content"] if "content" in followupMsg else None, embed=(followupMsg["embed"] if "embed" in followupMsg else None), ephemeral=True)
            return

        # == Editing Event ==

        with open(EVENTS_FILE) as f:
            events = json.load(f)
        event = [event for event in events if event["messageId"] == eventMsg.id][0]

        if value == "":
            event[modal.custom_id[len("modal_"):]] = None

        elif modal.custom_id == "modal_reservableRoles":
            reservableRoles = value.split("\n")
            if len(reservableRoles) > 20:
                await interaction.response.send_message(embed=discord.Embed(title="❌ Too many roles", description=f"Due to Discord character limitation, we've set the cap to 20 roles.\nLink your order, e.g. OPORD, under URL if you require more flexibility.\n\nYour roles:\n{value}"[:4096], color=discord.Color.red()), ephemeral=True, delete_after=10.0)
                return

            # No res roles or all roles are unoccupied
            if event["reservableRoles"] is None or all([id is None for id in event["reservableRoles"].values()]):
                event["reservableRoles"] = {role.strip(): None for role in reservableRoles}

            # Res roles are set and some occupied
            else:
                event["reservableRoles"] = {role.strip(): event["reservableRoles"][role.strip()] if role in event["reservableRoles"] else None for role in reservableRoles}

        elif modal.custom_id == "modal_maxPlayers":
            if value.lower() == "none" or (value.isdigit() and int(value) > MAX_SERVER_ATTENDANCE):
                event["maxPlayers"] = None
            elif value.lower() in ("anonymous", "hidden"):
                event["maxPlayers"] = value.lower()
            elif value.isdigit() and 1 < int(value) < MAX_SERVER_ATTENDANCE:
                event["maxPlayers"] = int(value)
            else:
                await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                return

        elif modal.custom_id == "modal_duration":
            hours, minutes, delta = self.getDetailsFromDuration(value)

            event["duration"] = f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}"

            # Update event endTime if no template
            if "endTime" in event:
                startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
                endTime = startTime + delta
                event["endTime"] = endTime.strftime(TIME_FORMAT)

        elif modal.custom_id == "modal_time":
            startTimeOld = event["time"]
            hours, minutes, delta = self.getDetailsFromDuration(event["duration"])
            try:
                startTime = datetimeParse(value)
            except ValueError:
                await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                return

            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)
            timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
            startTime = timeZone.localize(startTime).astimezone(UTC)

            endTime = startTime + delta
            event["time"] = startTime.strftime(TIME_FORMAT)
            event["endTime"] = endTime.strftime(TIME_FORMAT)

            # Notify attendees of time change
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("Schedule modalHandling: guild is None")
                return None

            # Send before time-hogging processes - fix interaction failed
            await interaction.response.send_message(interaction.user.mention, embed=discord.Embed(title="✅ Event edited", color=discord.Color.green()), ephemeral=True, delete_after=15.0)

            previewEmbed = discord.Embed(title=f":clock3: The starting time has changed for: {event['title']}!", description=f"From: {discord.utils.format_dt(UTC.localize(datetime.strptime(startTimeOld, TIME_FORMAT)), style='F')}\n\u2000\u2000To: {discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}", color=discord.Color.orange())
            previewEmbed.add_field(name="\u200B", value=eventMsg.jump_url, inline=False)
            previewEmbed.set_footer(text=f"By: {interaction.user}")
            for memberId in event["accepted"] + event["declined"] + event["tentative"] + event["standby"]:
                member = guild.get_member(memberId)
                if member is not None:
                    try:
                        await member.send(embed=previewEmbed)
                    except Exception as e:
                        log.exception(f"{member.id} [{member.display_name}]")

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)

            # === Reorder events ===
            # Save message ID order
            msgIds = []
            for eve in events:
                msgIds.append(eve["messageId"])

            # Sort events
            sortedEvents = sorted(events, key=lambda e: datetime.strptime(e["time"], TIME_FORMAT), reverse=True)

            channelSchedule = await guild.fetch_channel(SCHEDULE)
            if not isinstance(channelSchedule, discord.TextChannel):
                log.exception("Schedule modalHandling: channelSchedule not discord.TextChannel")
                return

            anyEventChange = False
            for idx, eve in enumerate(sortedEvents):
                # If msg is in a different position
                if eve["messageId"] != msgIds[idx]:
                    anyEventChange = True
                    eve["messageId"] = msgIds[idx]

                    # Edit msg to match position
                    msg = await channelSchedule.fetch_message(msgIds[idx])
                    await msg.edit(embed=self.getEventEmbed(sortedEvents[idx]), view=self.getEventView(sortedEvents[idx]))

            if anyEventChange is False:
                msg = await channelSchedule.fetch_message(event["messageId"])
                await msg.edit(embed=self.getEventEmbed(event), view=self.getEventView(event))


            with open(EVENTS_FILE, "w") as f:
                json.dump(sortedEvents, f, indent=4)

            # If events are reordered and user have elevated privileges and may edit other events than self-made - warn them
            if anyEventChange and ((interaction.user.id in DEVELOPERS) or any(role.id == UNIT_STAFF or role.id == SERVER_HAMSTER for role in interaction.user.roles)):
                embed = discord.Embed(title="⚠️ Restart the editing process ⚠️", description="Delete all ephemeral messages, or you may risk editing some other event!", color=discord.Color.yellow())
                embed.set_footer(text=f"Only {guild.get_role(UNIT_STAFF).name}, {guild.get_role(SERVER_HAMSTER).name} & {guild.get_role(SNEK_LORD).name} have risk of causing this.")
                await interaction.followup.send(embed=embed, ephemeral=True)
            return


        else:
            event[modal.custom_id[len("modal_"):]] = value

        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)

        await eventMsg.edit(embed=self.getEventEmbed(event), view=self.getEventView(event))
        await interaction.response.send_message(interaction.user.mention, embed=discord.Embed(title="✅ Event edited", color=discord.Color.green()), ephemeral=True, delete_after=5.0)

    @staticmethod
    def getDetailsFromDuration(duration: str) -> tuple:
        """Extracts hours, minutes and delta time from user duration.

        Parameters:
        duration (str): A duration.

        Returns:
        tuple: tuple with hours, minutes, delta zipped.
        """
        duration = duration.lower()
        hours = int(duration.split("h")[0].strip()) if "h" in duration else 0
        minutes = int(duration.split("h")[-1].replace("m", "").strip()) if duration.strip()[-1] != "h" else 0
        delta = timedelta(hours=hours, minutes=minutes)
        return hours, minutes, delta

    async def editEvent(self, interaction: discord.Interaction, event: dict, eventMsg: discord.Message) -> None:
        """Edits a preexisting event.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        event (dict): The event.
        eventMsg (discord.Message): The preexisting event to edit.

        Returns:
        None.
        """
        editOptions = (
            "Type",
            "Title",
            "Description",
            "External URL",
            "Reservable Roles",
            "Map",
            "Max Players",
            "Duration",
            "Time",
            "Files"
        )
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Is editing the event '{event['title']}'")
        options = []
        for editOption in editOptions:
            options.append(discord.SelectOption(label=editOption))

        view = ScheduleView()
        view.add_item(ScheduleSelect(instance=self, eventMsg=eventMsg, placeholder="Select what to edit.", minValues=1, maxValues=1, customId="edit_select", row=0, options=options))

        await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)


# ===== </Schedule Functions> =====


# ===== <Event> =====

    @discord.app_commands.command(name="bop")
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_ZEUS)
    @discord.app_commands.guilds(GUILD)
    async def scheduleOperation(self, interaction: discord.Interaction) -> None:
        """Create an operation to add to the schedule."""
        await self.scheduleEventInteraction(interaction, "Operation")

    @scheduleOperation.error
    async def onBopError(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        """Bop errors - dedicated for the discord.app_commands.errors.MissingAnyRole error.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        error (discord.app_commands.AppCommandError): The end user error.

        Returns:
        None.
        """
        if isinstance(error, discord.app_commands.errors.MissingAnyRole):
            if interaction.guild is None:
                log.exception("Schedule onBopError: interaction.guild is None")
                return

            channelZeusGuidelines = interaction.guild.get_channel(ZEUS_GUIDELINES)
            if not isinstance(channelZeusGuidelines, discord.TextChannel):
                log.exception("Schedule onBopError: channelZeusGuidelines not discord.TextChannel")
                return

            embed = discord.Embed(title="❌ Missing permissions", description=f"You do not have the permissions to schedule an operation!\nPlease reference the {channelZeusGuidelines.mention} for more information!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        log.exception(error)

    @discord.app_commands.command(name="ws")
    @discord.app_commands.guilds(GUILD)
    async def scheduleWorkshop(self, interaction: discord.Interaction) -> None:
        """Create a workshop to add to the schedule."""
        await self.scheduleEventInteraction(interaction, "Workshop")

    @discord.app_commands.command(name="event")
    @discord.app_commands.guilds(GUILD)
    async def scheduleEvent(self, interaction: discord.Interaction) -> None:
        """Create an event to add to the schedule."""
        await self.scheduleEventInteraction(interaction, "Event")


    async def scheduleEventInteraction(self, interaction: discord.Interaction, preselectedType: str) -> None:
        """Create an event to add to the schedule."""
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Is creating an {preselectedType.lower()}")

        previewDict = {
            "authorId": interaction.user.id,
            "type": preselectedType
        }
        view = self.fromDictToPreviewView(previewDict, "None")

        embed=discord.Embed(title=SCHEDULE_EVENT_PREVIEW_EMBED["title"], description=SCHEDULE_EVENT_PREVIEW_EMBED["description"], color=EVENT_TYPE_COLORS[preselectedType])
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        embed.set_footer(text=f"Created by {interaction.user.display_name}")
        await interaction.response.send_message("Schedule an event using the buttons, and get a live preview!", embed=embed, view=view)


# ===== </Event> =====


# ===== <Fileupload> =====

    @staticmethod
    def convertBytes(size: int):
        for unit in ["bytes", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f'{size:.1f} {unit}'
            size /= 1024.0

    @discord.app_commands.command(name="fileupload")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.describe(file="File to upload")
    async def fileupload(self, interaction: discord.Interaction, file: discord.Attachment) -> None:
        """Upload file for later attachment when scheduling.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        file (discord.File): The file.

        Returns:
        None.
        """
        # Cap file size to ~25 MB
        if file.size > 26_250_000:
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid filesize", description="Max allowed filesize is 25 MB!", color=discord.Color.red()), ephemeral=True)
            return

        channelAuditLogs = self.bot.get_channel(AUDIT_LOGS)
        if not isinstance(channelAuditLogs, discord.TextChannel):
            log.exception("Schedule fileupload: channelAuditLogs not discord.TextChannel")
            return

        # Block files with file extension in blacklist
        fileExtension = os.path.splitext(file.filename)[1][1:] # Get extension without dot
        if not fileExtension or fileExtension.lower() in FILE_UPLOAD_EXTENSION_BLACKLIST:
            log.exception(f"{interaction.user.id} [{interaction.user.display_name}] Uploaded a blacklisted file extension '{file.filename}'")

            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("Schedule fileupload: guild is None")
                return
            roleSnekLord = guild.get_role(SNEK_LORD)
            if roleSnekLord is None:
                log.exception("Schedule fileupload: roleSnekLord is None")
                return

            embed = discord.Embed(title="❌ File upload blocked", description=f"User {interaction.user.mention} ({interaction.user.id}) uploaded the file '{file.filename}'.\nThis action has been blocked since the file extension is blacklisted.", color=discord.Color.red())
            await channelAuditLogs.send(roleSnekLord.mention, embed=embed)

            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid file extension", description="This file extension is blacklisted for security purposes.", color=discord.Color.red()), ephemeral=True)
            return


        # Block files with same name per user
        filenameCap = file.filename[:200]
        filenameExists = any([re.match(fr"\d+_{interaction.user.id}_{filenameCap}", file) for file in os.listdir("tmp/fileUpload/")])
        if filenameExists:
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid filename", description="You have already uploaded a file with this name before!", color=discord.Color.red()), ephemeral=True)
            return


        # Everything OK, save file

        # Naming scheme: 'DATETIME_AUTHORID_NAME'
        filenameNew = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{interaction.user.id}_{filenameCap}"
        with open(f"tmp/fileUpload/{filenameNew}", "wb") as f:
            await file.save(f)

        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Uploaded the file '{file.filename}' as '{filenameNew}'")
        embed = discord.Embed(title="✅ File uploaded", description=f"Uploaded file as `{filenameCap}`", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

        # Log
        if secret.DISCORD_LOGGING.get("upload_file", False):
            embed = discord.Embed(title="Uploaded file" + (" (Debug)" if secret.DEBUG else ""), color=discord.Color.blue())
            embed.add_field(name="Filename", value=f"`{file.filename}`")
            embed.add_field(name="Size", value=f"`{Schedule.convertBytes(file.size)}`")
            embed.add_field(name="Time", value=discord.utils.format_dt(datetime.now(timezone.utc), style="F"))
            embed.add_field(name="Member", value=interaction.user.mention)
            embed.set_footer(text=f"Member ID: {interaction.user.id}")

            await channelAuditLogs.send(embed=embed)

        # Cleanup files older than 20 weeks
        # Other cleanup methods are to have 1) a global file cap 2) an individual file cap
        fileUploadFiles = os.listdir("tmp/fileUpload")
        for fileUploadFile in fileUploadFiles:
            fileUploadFileTime = UTC.localize(datetime.strptime(fileUploadFile.split("_")[0], "%Y%m%d%H%M%S"))
            if fileUploadFileTime < (datetime.now(timezone.utc) - timedelta(weeks=20)):
                try:
                    os.remove(f"tmp/fileUpload/{fileUploadFile}")
                except Exception as e:
                    log.warning(f"Schedule fileupload: Failed to remove file '{fileUploadFile}' | {e}")


# ===== </Fileupload> =====


# ===== <Timestamp> =====

    @discord.app_commands.command(name="timestamp")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.describe(time = "Your local time, e.g. 9:00 PM", message = "Add a message before the timestamp", timezone = "Convert the time from a different time zone other than your personal, e.g. EST & Europe/London", informative = "Displays all formats, raw text, etc.")
    @discord.app_commands.choices(informative = [discord.app_commands.Choice(name="Yes plz", value="Yes")])
    async def timestamp(self, interaction: discord.Interaction, time: str, message: str = "", timezone: str = "", informative: discord.app_commands.Choice[str] | None = None) -> None:
        """Convert your local time to a dynamic Discord timestamp.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        time (str): Inputted time to be converted.
        message (str): Optionally adding a message before the timestamp.
        timezone (str): Optional custom time zone, which is separate from the user set preferred time zone.
        informative (discord.app_commands.Choice[str]): If the user want's the informative embed - displaying all timestamps with desc, etc.

        Returns:
        None.
        """
        # Get the inputted time
        try:
            timeParsed = datetimeParse(time)
        except ValueError:
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid time", description="Provide a valid time!", color=discord.Color.red()), ephemeral=True)
            return

        await interaction.response.defer()

        if not timezone:  # User's time zone
            # Get user time zone
            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)

            if str(interaction.user.id) not in memberTimeZones:
                timeZoneOutput = await self.changeTimeZone(interaction.user, isCommand=False)
                if not timeZoneOutput:
                    await self.cancelCommand(await self.checkDMChannel(interaction.user), "Timestamp creation")
                    await interaction.edit_original_response(embed=discord.Embed(title="❌ Timestamp creation canceled", description="You must provide a time zone in your DMs!", color=discord.Color.red()))
                    return
                with open(MEMBER_TIME_ZONES_FILE) as f:
                    memberTimeZones = json.load(f)
            timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])

        else:  # Custom time zone
            try:
                timeZone = pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                await interaction.edit_original_response(embed=discord.Embed(title="❌ Invalid time zone", description="Provide a valid time zone!", color=discord.Color.red()))
                return

        # Output timestamp
        timeParsed = timeZone.localize(timeParsed.replace(tzinfo=None))
        await interaction.edit_original_response(content = f"{message} {discord.utils.format_dt(timeParsed, 'F')}")
        if informative is not None:
            embed = discord.Embed(color=discord.Color.green())
            embed.set_footer(text=f"Local time: {timeParsed.strftime(TIME_FORMAT)}\nTime zone: {memberTimeZones[str(interaction.user.id)] if not timezone else timeZone}")
            timestamps = [discord.utils.format_dt(timeParsed, style=timestampStyle[0]) for timestampStyle in TIMESTAMP_STYLES.items()]
            embed.add_field(name="Timestamp", value="\n".join(timestamps), inline=True)
            embed.add_field(name="Copy this", value="\n".join([f"`{stamp}`" for stamp in timestamps]), inline=True)
            embed.add_field(name="Description", value="\n".join([f"`{timestampStyle[1]}`" for timestampStyle in TIMESTAMP_STYLES.items()]), inline=True)
            await interaction.user.send(embed=embed)

# ===== </Timestamp> =====


# ===== <Change Time Zone> =====

    @discord.app_commands.command(name="changetimezone")
    @discord.app_commands.guilds(GUILD)
    async def timeZoneCmd(self, interaction: discord.Interaction) -> None:
        """Change your time zone preferences for your next scheduled event."""
        await interaction.response.send_message("Changing time zone preferences...")
        timeZoneOutput = await self.changeTimeZone(interaction.user, isCommand=True)
        if not timeZoneOutput:
            await self.cancelCommand(await self.checkDMChannel(interaction.user), "Time zone preferences")

    async def changeTimeZone(self, author: discord.User | discord.Member, isCommand: bool = True) -> bool:
        """Changing a personal time zone.

        Parameters:
        author (discord.Member): The command author.
        isCommand (bool): If the command calling comes from the actual slash command.

        Returns:
        bool: If function executed successfully.
        """
        log.info(f"{author.id} [{author.display_name}] Is updating their time zone preferences")

        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        timezoneOk = False
        color = discord.Color.gold()
        while not timezoneOk:
            embed = discord.Embed(
                title=":clock1: What's your preferred time zone?",
                description=(f"Your current time zone preference is `{memberTimeZones[str(author.id)]}`." if str(author.id) in memberTimeZones else "You don't have a preferred time zone set.") + "\n\nEnter a number from the list below.\nEnter any time zone name from the column \"**TZ DATABASE NAME**\" in this [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)." + "\nEnter `none` to erase current preferences." * isCommand,
                color=color
            )
            embed.add_field(name="Popular Time Zones", value="\n".join(f"**{idx}.** {tz}" for idx, tz in enumerate(TIME_ZONES, 1)))
            embed.set_footer(text="Enter `cancel` to abort this command.")
            color = discord.Color.red()
            try:
                msg = await author.send(embed=embed)
            except Exception as e:
                log.exception(f"{author.id} [{author.display_name}]")
                return False
            dmChannel = msg.channel
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                timeZone = response.content.strip()
                with open(MEMBER_TIME_ZONES_FILE) as f:
                    memberTimeZones = json.load(f)
                isInputNotNone = True
                if timeZone.lower() == "cancel":
                    return False
                elif timeZone.isdigit() and int(timeZone) <= len(TIME_ZONES) and int(timeZone) > 0:
                    timeZone = pytz.timezone(list(TIME_ZONES.values())[int(timeZone) - 1])
                    memberTimeZones[str(author.id)] = timeZone.zone
                    timezoneOk = True
                else:
                    try:
                        timeZone = pytz.timezone(timeZone)
                        memberTimeZones[str(author.id)] = timeZone.zone
                        timezoneOk = True
                    except pytz.exceptions.UnknownTimeZoneError:
                        if str(author.id) in memberTimeZones:
                            del memberTimeZones[str(author.id)]
                        if timeZone.lower() == "none" and isCommand:
                            isInputNotNone = False
                            timezoneOk = True

            except asyncio.TimeoutError:
                await dmChannel.send(embed=discord.Embed(title=":clock3: You were too slow, aborting!", color=discord.Color.red()))
                return False

        with open(MEMBER_TIME_ZONES_FILE, "w") as f:
            json.dump(memberTimeZones, f, indent=4)
        embed = discord.Embed(title=f"✅ Time zone preferences changed!", description=f"Updated to `{timeZone.zone}`!" if isInputNotNone else "Preference removed!", color=discord.Color.green())
        await dmChannel.send(embed=embed)
        return True

# ===== </Change Time Zone> =====


# ===== <Views and Buttons> =====

class ScheduleView(discord.ui.View):
    """Handling all schedule views."""
    def __init__(self, *, authorId: int = None, previousMessageView = None, **kwargs):
        super().__init__(**kwargs)
        self.timeout = None
        self.authorId = authorId
        self.previousMessageView = previousMessageView

class ScheduleButton(discord.ui.Button):
    """Handling all schedule buttons."""
    def __init__(self, instance, message: discord.Message | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.message = message

    async def callback(self, interaction: discord.Interaction):
        await self.instance.buttonHandling(self.message, self, interaction)

class ScheduleSelect(discord.ui.Select):
    """Handling all schedule dropdowns."""
    def __init__(self, instance, eventMsg: discord.Message, placeholder: str, minValues: int, maxValues: int, customId: str, row: int, options: list[discord.SelectOption], disabled: bool = False, eventMsgView: discord.ui.View | None = None, *args, **kwargs):
        super().__init__(placeholder=placeholder, min_values=minValues, max_values=maxValues, custom_id=customId, row=row, options=options, disabled=disabled, *args, **kwargs)
        self.eventMsg = eventMsg
        self.instance = instance
        self.eventMsgView = eventMsgView

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.instance.selectHandling(self, interaction, self.eventMsg, self.eventMsgView)

class ScheduleModal(discord.ui.Modal):
    """Handling all schedule modals."""
    def __init__(self, instance, title: str, customId: str, eventMsg: discord.Message, view: discord.ui.View | None = None) -> None:
        super().__init__(title=title, custom_id=customId)
        self.instance = instance
        self.eventMsg = eventMsg
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        await self.instance.modalHandling(self, interaction, self.eventMsg, self.view)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        # await interaction.response.send_message("Something went wrong. cope.", ephemeral=True)
        log.exception(error)

# ===== </Views and Buttons> =====


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Schedule(bot))
