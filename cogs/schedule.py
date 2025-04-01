import os, re, json, asyncio, discord, logging
import owo  # april fools
import pytz  # type: ignore

from math import ceil
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse as datetimeParse  # type: ignore
from typing import *

from discord.ext import commands, tasks  # type: ignore

from .workshopInterest import WorkshopInterest  # type: ignore
from utils import Utils  # type: ignore
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

SCHEDULE_EVENT_VIEW: Dict[str, Dict[str, discord.ButtonStyle | bool | int | None]] = {
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

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Schedule on_ready: guild is None")
            return

        await Schedule.updateSchedule(guild)
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

    @staticmethod
    async def saveEventToHistory(event: Dict, guild: discord.Guild, autoDeleted=False) -> None:
        """Saves a specific event to history.

        Parameters:
        event: The specified event.
        autoDeleted (bool): If the event was automatically deleted.

        Returns:
        None.
        """
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
                    channelWorkshopInterest = guild.get_channel(WORKSHOP_INTEREST)
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

    @staticmethod
    async def taskAutodeleteEvents(guild: discord.Guild) -> None:
        """Autodeletes expired events.

        Parameters:
        guild (discord.Guild): The Discord guild.

        Returns:
        None.
        """
        AUTODELETE_THRESHOLD_IN_MINUTES = 69

        channelSchedule = guild.get_channel(SCHEDULE)
        if not isinstance(channelSchedule, discord.TextChannel):
            log.exception("Schedule tenMinTask: channelSchedule not discord.TextChannel")
            return

        deletedEvents = []
        utcNow = datetime.now(timezone.utc)
        with open(EVENTS_FILE) as f:
            events = json.load(f)

        for event in events:
            endTime = UTC.localize(datetime.strptime(event["endTime"], TIME_FORMAT))
            if utcNow > endTime + timedelta(minutes=AUTODELETE_THRESHOLD_IN_MINUTES):
                if event["maxPlayers"] != "hidden":  # Save events that does not have hidden attendance
                    await Schedule.saveEventToHistory(event, guild, autoDeleted=True)
                log.debug(f"Schedule tenMinTask: Auto deleting event '{event['title']}'")
                deletedEvents.append(event)
                eventMessage = await channelSchedule.fetch_message(event["messageId"])
                await eventMessage.delete()
                author = guild.get_member(event["authorId"])
                if not author:
                    log.warning(f"Schedule tenMinTask: Could not find author '{event['authorId']}' of event '{event['title']}'")
                    continue

                embed = discord.Embed(title="Event auto deleted", description=f"Your {event['type'].lower()} has ended: `{event['title']}`\nIt has been automatically removed from the schedule. {PEEPO_POP}", color=discord.Color.orange())
                await author.send(embed=embed)
        for event in deletedEvents:
            events.remove(event)
        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)


    @staticmethod
    async def tasknoShowsPing(guild: discord.Guild, channelCommand: discord.TextChannel, channelDeployed: discord.TextChannel) -> None:
        """Handling no-show members by pinging.

        Parameters:
        guild (discord.Guild): The Discord guild.

        Returns:
        None.
        """
        NO_SHOW_PING_THRESHOLD_IN_MINUTES = 15

        channelArmaDiscussion = guild.get_channel(ARMA_DISCUSSION)
        if not isinstance(channelArmaDiscussion, discord.TextChannel):
            log.exception("Schedule tasknoShowsPing: channelArmaDiscussion not discord.TextChannel")
            return

        membersUnscheduled: List[discord.Member] = []
        with open(EVENTS_FILE) as f:
            events = json.load(f)

        for event in events:
            if event.get("checkedAcceptedReminders", False):
                continue
            if event.get("type", "Operation") != "Operation":
                continue
            startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
            if datetime.now(timezone.utc) > startTime + timedelta(minutes=NO_SHOW_PING_THRESHOLD_IN_MINUTES):
                event["checkedAcceptedReminders"] = True
                membersAccepted = [member for memberId in event["accepted"] + event["standby"] if (member := guild.get_member(memberId)) is not None]
                membersInVC = channelCommand.members + channelDeployed.members
                membersUnscheduled += ([member for member in membersAccepted if member not in membersInVC] + [member for member in membersInVC if member not in membersAccepted and member.id != event["authorId"]])

        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)
        if len(membersUnscheduled) == 0:
            return

        log.debug(f"Schedule tasknoShowsPing: Pinging unscheduled members: {', '.join([member.display_name for member in membersUnscheduled])}")
        await channelArmaDiscussion.send(" ".join(member.mention for member in membersUnscheduled) + f"\nIf you are in-game, please:\n* Get in {channelCommand.mention} or {channelDeployed.mention}\n* Hit accept ✅ on the <#{SCHEDULE}>\nIf you are not making it to this {event['type'].lower()}, please hit decline ❌ on the <#{SCHEDULE}>")


    @staticmethod
    async def tasknoShowsLogging(guild: discord.Guild, channelCommand: discord.TextChannel, channelDeployed: discord.TextChannel) -> None:
        """Handling no-show members by logging.

        Parameters:
        guild (discord.Guild): The Discord guild.

        Returns:
        None.
        """
        NO_SHOW_LOG_THRESHOLD_IN_MINUTES = 45

        getReservedRoleName = lambda resRoles, userId: next((key for key, value in resRoles.items() if value == userId), None) if resRoles is not None else None

        noShowEvents = []
        with open(EVENTS_FILE) as f:
            events = json.load(f)

        # Fetch no-show members
        for event in events:
            if event.get("checkedNoShowLogging", False):
                continue
            if event.get("type", "Operation") != "Operation":
                continue

            startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
            if datetime.now(timezone.utc) > startTime + timedelta(minutes=NO_SHOW_LOG_THRESHOLD_IN_MINUTES):
                event["checkedNoShowLogging"] = True

                membersAccepted = [member for memberId in event["accepted"] if (member := guild.get_member(memberId)) is not None]
                membersInVC = channelCommand.members + channelDeployed.members
                membersAcceptedNotInSchedule = [member for member in membersAccepted if member not in membersInVC]
                noShowEvents.append({
                    "members": membersAcceptedNotInSchedule,
                    "event": event
                })

        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)

        if not noShowEvents:
            return

        noShowMembersListForLogging = []
        with open(NO_SHOW_FILE) as f:
            noShowFile = json.load(f)

        # Log no-show members in JSON
        for noShowEvent in noShowEvents:
            for noShowMember in noShowEvent["members"]:
                noShowMembersListForLogging.append(noShowMember)
                if str(noShowMember.id) not in noShowFile:
                    noShowFile[str(noShowMember.id)] = []
                startTime = int(datetime.timestamp(UTC.localize(datetime.strptime(noShowEvent["event"]["time"], TIME_FORMAT))))
                reservedRole = getReservedRoleName(noShowEvent["event"]["reservableRoles"], noShowMember.id)
                noShowFile[str(noShowMember.id)].append({"date": startTime, "operationName": noShowEvent["event"]["title"], "reservedRole": reservedRole})

        with open(NO_SHOW_FILE, "w") as f:
            json.dump(noShowFile, f, indent=4)

        if not noShowMembersListForLogging:
            return

        log.debug(f"Schedule tasknoShowsLogging: No-show members, {', '.join([member.display_name for member in noShowMembersListForLogging])}")

        # Log no-show members in Discord
        channelAdvisorStaffComms = guild.get_channel(ADVISOR_STAFF_COMMS)
        if not isinstance(channelAdvisorStaffComms, discord.TextChannel):
            log.exception("Schedule tenMinTask: channelAdvisorStaffComms not discord.TextChannel")
            return

        embed = discord.Embed(title="No-show members", description=f"The following members have been registered as no-show", color=discord.Color.red())
        for noShowEvent in noShowEvents:
            noShowEventEmbedFieldValue = []
            for noShowMember in noShowEvent["members"]:
                # Warn if member has 3 no-shows in the last 90 days
                warningMsg = ""
                noshowCount = len([entry for entry in noShowFile[str(noShowMember.id)] if datetime.fromtimestamp(entry["date"], timezone.utc) > datetime.now(timezone.utc) - timedelta(days=NOSHOW_ARCHIVE_THRESHOLD_IN_DAYS)])
                if noshowCount >= 3:
                    warningMsg = f"⚠️ {noshowCount} no-shows in the last 90 days"

                reservedRole = getReservedRoleName(noShowEvent["event"]["reservableRoles"], noShowMember.id)
                noShowEventEmbedFieldValue.append(noShowMember.display_name + (f" -- **{reservedRole}**" * bool(reservedRole)) + f" {warningMsg}")

            embed.add_field(name=noShowEvent["event"]["title"], value="\n".join(noShowEventEmbedFieldValue))

        await channelAdvisorStaffComms.send(embed=embed)


    @discord.app_commands.command(name="no-show")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_STAFF_ADVISOR)
    @discord.app_commands.describe(member = "Target member to check.")
    async def noShow(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """Checks no-show logs for specified member.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        member (discord.Member): The target member.

        Returns:
        None.
        """

        view = discord.ui.View(timeout=None)
        view.add_item(ScheduleButton(interaction.message, style=discord.ButtonStyle.success, label="Add entry", custom_id=f"schedule_noshow_add_{member.id}"))

        with open(NO_SHOW_FILE) as f:
            noShowFile = json.load(f)

        if str(member.id) not in noShowFile:
            embed = discord.Embed(title="Not Found", description="Target member does not have any recorded no-shows.", color=discord.Color.red())
            embed.set_author(name=member.display_name, icon_url=member.display_avatar)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=30.0)
            return

        embed = discord.Embed(color=discord.Color.orange())
        embed.set_author(name=member.display_name, icon_url=member.display_avatar)
        noShowsPresent = []
        noShowsArchive = []
        for noShow in noShowFile[str(member.id)]:
            noShowEntryTimestamp = datetime.fromtimestamp(noShow.get("date", 0), timezone.utc)
            date = discord.utils.format_dt(noShowEntryTimestamp, style="R")
            entry = f"{date} -- `{noShow.get('operationName', 'Operation UNKNOWN')}`"
            reservedRole = noShow.get('reservedRole', None)
            if reservedRole:
                entry += f" -- `{reservedRole}`"

            if noShowEntryTimestamp < datetime.now(timezone.utc) - timedelta(days=NOSHOW_ARCHIVE_THRESHOLD_IN_DAYS):
                noShowsArchive.append(entry)
            else:
                noShowsPresent.append(entry)

        if noShowsPresent:
            embed.add_field(name="Active", value="\n".join(noShowsPresent), inline=False)
        if noShowsArchive:
            embed.add_field(name=f"Archived (Older than {NOSHOW_ARCHIVE_THRESHOLD_IN_DAYS} days)", value="\n".join(noShowsArchive), inline=False)

        view.add_item(ScheduleButton(interaction.message, style=discord.ButtonStyle.danger, label="Remove entry", custom_id=f"schedule_noshow_remove_{member.id}"))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=180.0)


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

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Schedule tenMinTask: guild is None")
            return

        # === Check for old events and deletes them. ===
        await Schedule.taskAutodeleteEvents(guild)

        # === Ping no-show players. ===
        channelCommand = guild.get_channel(COMMAND)
        if not isinstance(channelCommand, discord.VoiceChannel):
            log.exception("Schedule tenMinTask: channelCommand not discord.VoiceChannel")
            return
        channelDeployed = guild.get_channel(DEPLOYED)
        if not isinstance(channelDeployed, discord.VoiceChannel):
            log.exception("Schedule tenMinTask: channelDeployed not discord.VoiceChannel")
            return

        await Schedule.tasknoShowsPing(guild, channelCommand, channelDeployed)

        # === Log no-show players. ===
        await Schedule.tasknoShowsLogging(guild, channelCommand, channelDeployed)


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

        if interaction.guild is None:
            log.exception("Schedule refreshSchedule: guild is None")
            return

        await Schedule.updateSchedule(interaction.guild)


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


# ===== </AAR> ====


# ===== <Schedule Functions> =====

    @staticmethod
    def clearUserRSVP(event: Dict, userId: int) -> None:
        """Clears a specific user from all RSVP.

        Parameters:
        event (Dict): The event.
        userId (int): Target user id.

        Returns:
        None.
        """
        RSVP_OPTIONS = ("accepted", "declined", "tentative", "standby")
        for rsvpOption in RSVP_OPTIONS:
            if userId in event[rsvpOption]:
                event[rsvpOption].remove(userId)

        if event["reservableRoles"]:
            for reservableRole in event["reservableRoles"]:
                if event["reservableRoles"][reservableRole] == userId:
                    event["reservableRoles"][reservableRole] = None


    @staticmethod
    async def updateSchedule(guild: discord.Guild) -> None:
        """Updates the schedule channel with all messages."""
        channelSchedule = guild.get_channel(SCHEDULE)
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

            newEvents: List[Dict] = []
            for event in sorted(events, key=lambda e: datetime.strptime(e["time"], TIME_FORMAT), reverse=True):
                Schedule.applyMissingEventKeys(event, keySet="event")
                msg = await channelSchedule.send(embed=Schedule.getEventEmbed(event, guild), view=Schedule.getEventView(event), files=Schedule.getEventFiles(event))
                event["messageId"] = msg.id
                newEvents.append(event)

            with open(EVENTS_FILE, "w") as f:
                json.dump(newEvents, f, indent=4)
        except Exception as e:
            log.exception(e)

    @staticmethod
    def applyMissingEventKeys(event: Dict, *, keySet: Literal["event", "template"], removeKeys:bool = False) -> None:
        """Applies missing keys to the event.

        Parameters:
        event (Dict): The event.
        keySet (Literal): The applied key set.

        Returns:
        None.
        """
        event.setdefault("type", None)
        event.setdefault("time", None)
        event.setdefault("endTime", None)
        event.setdefault("title", None)
        event.setdefault("description", None)
        event.setdefault("externalURL", None)
        event.setdefault("reservableRoles", None)
        event.setdefault("maxPlayers", None)
        event.setdefault("map", None)
        event.setdefault("duration", None)
        event.setdefault("files", [])

        if keySet == "event":
            event.setdefault("authorId", None)
            event.setdefault("messageId", None)
            event.setdefault("accepted", [])
            event.setdefault("declined", [])
            event.setdefault("tentative", [])
            event.setdefault("standby", [])
            event.setdefault("checkedAcceptedReminders", False)
            event.setdefault("checkedNoShowLogging", False)
        elif keySet == "template":
            event.setdefault("templateName", None)
            if removeKeys:
                validKeys = {"title", "description", "externalURL", "reservableRoles", "maxPlayers", "map", "duration", "files", "templateName"}
                invalidKeys = set(event.keys()) - validKeys
                for key in invalidKeys:
                    del event[key]

    @staticmethod
    def getEventEmbed(event: Dict, guild: discord.Guild) -> discord.Embed:
        """Generates an embed from the given event.

        Parameters:
        event (Dict): The event.

        Returns:
        discord.Embed: The generated embed.
        """
        # owo april fools
        embed = discord.Embed(title=event["title"], description=owo.owo(event["description"]), color=EVENT_TYPE_COLORS[event.get("type", "Operation")])

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

    @staticmethod
    def getEventView(event: Dict) -> discord.ui.View:
        view = ScheduleView()
        items = []

        # Add attendance buttons if maxPlayers is not hidden
        if event["maxPlayers"] != "hidden":
            isAcceptAndReserve = event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"]

            if isAcceptAndReserve:
                items.append(ScheduleButton(None, row=0, label="Accept & Reserve", style=discord.ButtonStyle.success, custom_id="reserve"))
            else:
                items.append(ScheduleButton(None, row=0, label="Accept", style=discord.ButtonStyle.success, custom_id="accepted"))

            items.extend([
                ScheduleButton(None, row=0, label="Decline", style=discord.ButtonStyle.danger, custom_id="declined"),
                ScheduleButton(None, row=0, label="Tentative", style=discord.ButtonStyle.secondary, custom_id="tentative")
            ])
            if event["reservableRoles"] is not None and not isAcceptAndReserve:
                items.append(ScheduleButton(None, row=0, label="Reserve", style=discord.ButtonStyle.secondary, custom_id="reserve"))

        items.append(ScheduleButton(None, row=0, emoji="⚙️", style=discord.ButtonStyle.secondary, custom_id="config"))
        for item in items:
            view.add_item(item)

        return view

    @staticmethod
    def getEventFiles(event: Dict) -> List[discord.File]:
        """Generates a list of files from the given event.

        Parameters:
        event (Dict): The event.

        Returns:
        List[discord.File]: The list of files.
        """
        if "files" not in event or not event["files"]:
            return []

        discordFiles = []
        for eventFile in event["files"]:
            try:
                with open(f"tmp/fileUpload/{eventFile}", "rb") as f:
                    discordFiles.append(discord.File(f, filename=eventFile.split("_", 2)[2]))
            except Exception as e:
                pass

        return discordFiles

    @staticmethod
    def getUserFileUploads(userId: str, isDiscordFormat = False, fullFilename = False) -> List[discord.File] | List[str]:
        """Filters uploaded files to specified user id.

        Parameters:
        userId (str): User id for filter.
        isDiscordFormat (bool): Return as List[discord.File]
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

    @staticmethod
    def fromPreviewEmbedToDict(embed: discord.Embed) -> Dict:
        """Generates event dict from preview embed."""
        # Finds a field's position if found (int), if none found (None)
        findFieldPos = lambda fieldName : None if embed.fields is None else (
            indexes[0] if len(
                indexes := [idx for idx, field in enumerate(embed.fields) if field.name is not None and field.name.startswith(fieldName)]
            ) > 0 else None
        )

        outputDict = {}
        Schedule.applyMissingEventKeys(outputDict, keySet="event")

        outputDict["title"] = embed.title
        outputDict["description"] = embed.description
        outputDict["externalURL"] = None if (findFieldPosURL := findFieldPos("External URL")) is None else embed.fields[findFieldPosURL].value
        outputDict["map"] = None if (findFieldPosMap := findFieldPos("Map")) is None else embed.fields[findFieldPosMap].value
        outputDict["duration"] = None if (findFieldPosDuration := findFieldPos("Duration")) is None else embed.fields[findFieldPosDuration].value
        outputDict["type"] = [eventType for eventType in EVENT_TYPE_COLORS if EVENT_TYPE_COLORS[eventType] == embed.color][0] if embed.color in EVENT_TYPE_COLORS.values() else None

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
        if outputDict.get("type", None) == "Workshop":
            outputDict["workshopInterest"] = None
            if embed.author.name is not None:
                workshop = embed.author.name[len("Linking: "):]
                outputDict["workshopInterest"] = None if workshop == "None" else workshop

        fieldPos = findFieldPos("Files")
        if fieldPos is not None:
            filesFieldValue = embed.fields[fieldPos].value
            outputDict["files"] = filesFieldValue.split("\n")

        return outputDict

    @staticmethod
    def fromDictToPreviewEmbed(previewDict: Dict, guild: discord.Guild) -> discord.Embed:
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
                hours, minutes, delta = Schedule.getDetailsFromDuration(previewDict["duration"])
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

    @staticmethod
    def fromDictToPreviewView(previewDict: Dict, selectedTemplate: str) -> discord.ui.View:
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
    async def hasCandidatePinged(candidateId: int, operationTitle: str, channelRecruitmentHr: discord.TextChannel) -> bool:
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
                return True
        return False

    @staticmethod
    async def blockVerifiedRoleRSVP(interaction: discord.Interaction, event: Dict) -> bool:
        """Checks if user has Verified role, and feedbacks blocking

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        event (Dict): Target event.

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

    @staticmethod
    def generateSelectView(options: List[discord.SelectOption], noneOption: bool, setOptionLabel: str | None, eventMsg: discord.Message, placeholder: str, customId: str, userId: int, eventMsgView: discord.ui.View | None = None):
        """Generates good select menu view - ceil(len(options)/25) dropdowns.

        Parameters:
        options (List[discord.SelectOption]): All select menu options
        noneOption (bool): Adds an option for None.
        setOptionLabel (str): Removes this (selected) option from the options.
        eventMsg (discord.Message): The event message.
        placeholder (str): Menu placeholder.
        customId (str): Custom ID of select menu.
        userId (int): Userid for unique custom id.
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
            view.add_item(ScheduleSelect(eventMsg=eventMsg, placeholder=placeholder, minValues=1, maxValues=1, customId=f"{customId}_REMOVE{i}", userId=userId, row=i, options=options[:25], eventMsgView=eventMsgView))
            options = options[25:]

        return view

    @staticmethod
    def getDetailsFromDuration(duration: str) -> Tuple[int, int, timedelta] | None:
        """Extracts hours, minutes and delta time from user duration.

        Parameters:
        duration (str): A duration.

        Returns:
        tuple: tuple with hours, minutes, delta zipped.
        """
        try:
            duration = duration.lower()
            hours = int(duration.split("h")[0].strip()) if "h" in duration else 0
            minutes = int(duration.split("h")[-1].replace("m", "").strip()) if duration.strip()[-1] != "h" else 0
            delta = timedelta(hours=hours, minutes=minutes)
        except Exception:
            return None
        return hours, minutes, delta

    @staticmethod
    async def editEvent(interaction: discord.Interaction, event: Dict, eventMsg: discord.Message) -> None:
        """Edits a preexisting event.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        event (Dict): The event.
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
        view.add_item(ScheduleSelect(eventMsg=eventMsg, placeholder="Select what to edit.", minValues=1, maxValues=1, customId="edit_select", userId=interaction.user.id, row=0, options=options))

        await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)


# ===== </Schedule Functions> =====


# ===== <Event> =====

    @discord.app_commands.command(name="bop")
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_ZEUS)
    @discord.app_commands.guilds(GUILD)
    async def scheduleOperation(self, interaction: discord.Interaction) -> None:
        """Create an operation to add to the schedule."""
        await Schedule.scheduleEventInteraction(interaction, "Operation")

    @discord.app_commands.command(name="ws")
    @discord.app_commands.guilds(GUILD)
    async def scheduleWorkshop(self, interaction: discord.Interaction) -> None:
        """Create a workshop to add to the schedule."""
        await Schedule.scheduleEventInteraction(interaction, "Workshop")

    @discord.app_commands.command(name="event")
    @discord.app_commands.guilds(GUILD)
    async def scheduleEvent(self, interaction: discord.Interaction) -> None:
        """Create an event to add to the schedule."""
        await Schedule.scheduleEventInteraction(interaction, "Event")

    @staticmethod
    async def scheduleEventInteraction(interaction: discord.Interaction, preselectedType: str) -> None:
        """Create an event to add to the schedule."""
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Is creating an {preselectedType.lower()}")

        previewDict = {
            "authorId": interaction.user.id,
            "type": preselectedType
        }
        view = Schedule.fromDictToPreviewView(previewDict, "None")

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
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid filesize", description="Max allowed filesize is 25 MB!", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
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

            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid file extension", description="This file extension is blacklisted for security purposes.", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
            return


        # Block files with same name per user
        filenameCap = file.filename[:200]
        filenameExists = any([re.match(fr"\d+_{interaction.user.id}_{filenameCap}", file) for file in os.listdir("tmp/fileUpload/")])
        if filenameExists:
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid filename", description="You have already uploaded a file with this name before!", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
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
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid time", description="Provide a valid time!", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
            return

        await interaction.response.defer()

        if not timezone:  # User's time zone
            # Get user time zone
            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)

            if str(interaction.user.id) not in memberTimeZones:
                await interaction.edit_original_response(embed=discord.Embed(title="❌ Apply timezone", description="You must provide a time zone. Execute the command `/changetimezone`", color=discord.Color.red()))
                return

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
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Is updating their time zone preferences")

        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        setTimeZone = memberTimeZones[str(interaction.user.id)] if str(interaction.user.id) in memberTimeZones else None
        embed = discord.Embed(
            title=":clock1: Change Time Zone",
            description=(f"Your current time zone preference is `{setTimeZone}`." if setTimeZone else "You don't have a preferred time zone set.")
                + "\n\nTo change time zone, press the button and enter any time zone name from the column \"**TZ DATABASE NAME**\" in this [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).\n\nNOTE: This is only used when scheduling events - **NOT** when viewing them in #schedule!",
            color=discord.Color.gold()
        )

        view = ScheduleView()
        view.add_item(ScheduleButton(None, style=discord.ButtonStyle.success, label="Change Time Zone", custom_id="schedule_change_time_zone"))
        if setTimeZone:
            view.add_item(ScheduleButton(None, style=discord.ButtonStyle.danger, label="Remove preferences", custom_id="schedule_remove_time_zone"))

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=180.0)


# ===== </Change Time Zone> =====


# ===== <Views and Buttons> =====

class ScheduleView(discord.ui.View):
    """Handling all schedule views."""
    def __init__(self, *, authorId: int = None, previousMessageView = None, **kwargs):
        super().__init__(timeout=None, **kwargs)
        self.authorId = authorId
        self.previousMessageView = previousMessageView

class ScheduleButton(discord.ui.Button):
    """Handling all schedule buttons."""
    def __init__(self, message: discord.Message | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            log.exception("ScheduleButton callback: interaction.user not discord.Member")
            return

        if interaction.message is None:
            log.exception("ScheduleButton callback: interaction.message is None")
            return

        if not isinstance(interaction.guild, discord.Guild):
            log.exception("ScheduleButton callback: interaction.guild not discord.Guild")
            return

        embedDeclineRsvpSelf = discord.Embed(title="❌ RSVP", description="You cannot RSVP to your own event!", color=discord.Color.red())

        customId = interaction.data["custom_id"]

        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)

            scheduleNeedsUpdate = True
            fetchMsg = False
            eventList: List[Dict] = [event for event in events if event["messageId"] == interaction.message.id]

            rsvpOptions = ("accepted", "declined", "tentative", "standby")
            if customId in rsvpOptions:
                event = eventList[0]

                # Decline if author
                if event["authorId"] == interaction.user.id:
                    await interaction.response.send_message(interaction.user.mention, embed=embedDeclineRsvpSelf, ephemeral=True, delete_after=30.0)
                    return

                if await Schedule.blockVerifiedRoleRSVP(interaction, event):
                    return

                isAcceptAndReserve = event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"]

                # Promote standby to accepted if not AcceptAndReserve
                if interaction.user.id in event["accepted"] and not isAcceptAndReserve and len(event["standby"]) > 0:
                    standbyMemberId = event["standby"].pop(0)
                    event["accepted"].append(standbyMemberId)

                    # Notify (DM) promoted member
                    standbyMember = interaction.guild.get_member(standbyMemberId)
                    if standbyMember is None:
                        log.warning(f"ScheduleButton callback: Failed to fetch promoted accepted member '{standbyMemberId}'")
                    else:
                        embed = discord.Embed(title=f"✅ Accepted to {event['type'].lower()}", description=f"You have been promoted from standby to accepted in `{event['title']}`\nTime: {discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}\nDuration: {event['duration']}", color=discord.Color.green())
                        try:
                            await standbyMember.send(embed=embed)
                        except Exception:
                            log.warning(f"ScheduleButton callback: Failed to DM {standbyMemberId} [{standbyMember.display_name}] about acceptance")

                # User click on button twice - remove
                if interaction.user.id in event[customId]:
                    event[customId].remove(interaction.user.id)
                elif customId == "accepted" and interaction.user.id in event["standby"]:
                    event["standby"].remove(interaction.user.id)

                # "New" button
                else:
                    for option in rsvpOptions:
                        if interaction.user.id in event[option]:
                            event[option].remove(interaction.user.id)

                    # Place in standby if player cap is reached
                    if customId == "accepted" and isinstance(event["maxPlayers"], int) and len(event["accepted"]) >= event["maxPlayers"]:
                        event["standby"].append(interaction.user.id)
                    else:
                        event[customId].append(interaction.user.id)

                # Remove player from reservable role
                hadReservedARole = False
                if event["reservableRoles"] is not None:
                    for btnRoleName in event["reservableRoles"]:
                        if event["reservableRoles"][btnRoleName] == interaction.user.id:
                            event["reservableRoles"][btnRoleName] = None
                            hadReservedARole = True

                # User removes self from reserved role - Notify people on standby
                if isAcceptAndReserve and hadReservedARole and len(event["standby"]) > 0:
                    vacantRoles = "\n".join([f"`{role}`" for role, reservedUser in event["reservableRoles"].items() if not reservedUser])
                    embed = discord.Embed(
                        title="Role(s) vacant",
                        description=f"The following role(s) are now vacant for event `{event['title']}`:\n{vacantRoles}",
                        color=discord.Color.green()
                    )

                    for standbyMemberId in event["standby"]:
                        standbyMember = interaction.guild.get_member(standbyMemberId)
                        if standbyMember is None:
                            log.warning(f"ScheduleButton callback: Failed to get member with id '{standbyMemberId}'")
                            continue

                        try:
                            await standbyMember.send(embed=embed)
                        except Exception:
                            log.warning(f"ScheduleButton callback: Failed to DM {standbyMember.id} [{standbyMember.display_name}] about vacant roles")


            # Ping Recruitment Team if candidate accepts
            if customId == "accepted" and eventList[0]["type"].lower() == "operation" and interaction.user.id in eventList[0]["accepted"] and any([True for role in interaction.user.roles if role.id == CANDIDATE]):
                if not isinstance(interaction.guild, discord.Guild):
                    log.exception("ScheduleButton callback: interaction.guild not discord.Guild")
                    return
                channelRecruitmentHr = interaction.guild.get_channel(RECRUITMENT_AND_HR)
                if not isinstance(channelRecruitmentHr, discord.TextChannel):
                    log.exception("ScheduleButton callback: channelRecruitmentHr not discord.TextChannel")
                    return
                if not await Schedule.hasCandidatePinged(interaction.user.id, eventList[0]["title"], channelRecruitmentHr):
                    embed = discord.Embed(title="Candidate Accept", description=f"{interaction.user.mention} accepted operation `{eventList[0]['title']}`", color=discord.Color.blue())
                    embed.set_footer(text=f"Candidate ID: {interaction.user.id}")
                    await channelRecruitmentHr.send(embed=embed)

            elif customId == "standby_btn":
                event = [event for event in events if event["messageId"] == self.message.id][0]

                # Decline if author
                if event["authorId"] == interaction.user.id:
                    await interaction.response.send_message(interaction.user.mention, embed=embedDeclineRsvpSelf, ephemeral=True, delete_after=30.0)
                    return

                Schedule.clearUserRSVP(event, interaction.user.id)

                if interaction.user.id in event["standby"]:
                    await interaction.response.send_message(embed=discord.Embed(title="✅ Standby", description="Removed from standby list", color=discord.Color.green()), ephemeral=True, delete_after=60.0)
                else:
                    event["standby"].append(interaction.user.id)
                    await interaction.response.send_message(embed=discord.Embed(title="✅ Standby", description="You're on the standby list. If an accepted member leaves, you will be notified about the vacant roles!", color=discord.Color.green()), ephemeral=True, delete_after=60.0)

                with open(EVENTS_FILE, "w") as f:
                    json.dump(events, f, indent=4)

                embed = Schedule.getEventEmbed(event, interaction.guild)
                await self.message.edit(embed=embed)
                return

            elif customId == "reserve":
                # Check if blacklisted
                with open(ROLE_RESERVATION_BLACKLIST_FILE) as f:
                    blacklist = json.load(f)
                if any(interaction.user.id == member["id"] for member in blacklist):
                    await interaction.response.send_message(embed=discord.Embed(title="❌ Sorry, seems like you are not allowed to reserve any roles!", description="If you have any questions about this situation, please contact Unit Staff.", color=discord.Color.red()), ephemeral=True, delete_after=60.0)
                    return

                event = eventList[0]
                scheduleNeedsUpdate = False

                # Decline if author
                if event["authorId"] == interaction.user.id:
                    await interaction.response.send_message(interaction.user.mention, embed=embedDeclineRsvpSelf, ephemeral=True, delete_after=30.0)
                    return

                if await Schedule.blockVerifiedRoleRSVP(interaction, event):
                    return

                isAcceptAndReserve = event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"]
                playerCapReached = isinstance(event["maxPlayers"], int) and len(event["accepted"]) >= event["maxPlayers"]

                # Normal reservation, but no space left
                if not isAcceptAndReserve and playerCapReached and interaction.user.id not in event["accepted"]:
                    await interaction.response.send_message(embed=discord.Embed(title="❌ Sorry, seems like there's no space left in the :b:op!", color=discord.Color.red()), ephemeral=True, delete_after=60.0)
                    return

                # Remove from standby; if no vacant roles, or player cap reached
                if isAcceptAndReserve and interaction.user.id in event["standby"] and (all(event["reservableRoles"].values()) or playerCapReached):
                    event["standby"].remove(interaction.user.id)
                    embed = Schedule.getEventEmbed(event, interaction.guild)
                    await interaction.response.edit_message(embed=embed)

                    with open(EVENTS_FILE, "w") as f:
                        json.dump(events, f, indent=4)
                    return

                # Add to standby if player cap reached and not on list
                if isAcceptAndReserve and playerCapReached and interaction.user.id not in event["accepted"] and interaction.user.id not in event["standby"]:
                    Schedule.clearUserRSVP(event, interaction.user.id)
                    event["standby"].append(interaction.user.id)

                    await interaction.response.send_message(embed=discord.Embed(title="✅ On standby list", description="The event player limit is reached!\nYou have been placed on the standby list. If an accepted member leaves, you will be notified about the vacant roles!", color=discord.Color.green()), ephemeral=True, delete_after=60.0)

                    if interaction.channel is None or isinstance(interaction.channel, discord.ForumChannel) or isinstance(interaction.channel, discord.CategoryChannel):
                        log.exception("ScheduleButton callback: interaction.channel is invalid type")
                        return
                    embed = Schedule.getEventEmbed(event, interaction.guild)
                    originalMsgId = interaction.message.id
                    msg = await interaction.channel.fetch_message(originalMsgId)
                    await msg.edit(embed=embed)

                    with open(EVENTS_FILE, "w") as f:
                        json.dump(events, f, indent=4)
                    return


                # Select role to (un)reserve
                if not isinstance(interaction.user, discord.Member):
                    log.exception("ScheduleButton callback: interaction.user not discord.Member")
                    return

                vacantRoles = [btnRoleName for btnRoleName, memberId in event["reservableRoles"].items() if (memberId is None or interaction.user.guild.get_member(memberId) is None) and 1 <= len(btnRoleName) <= 100]

                view = ScheduleView()
                options = []

                if len(vacantRoles) > 0:
                    for role in vacantRoles:
                        options.append(discord.SelectOption(label=role))
                    view.add_item(ScheduleSelect(eventMsg=interaction.message, placeholder="Select a role.", minValues=1, maxValues=1, customId="reserve_role_select", userId=interaction.user.id, row=0, options=options))


                # Disable button if user hasn't reserved
                for roleName in event["reservableRoles"]:
                    if event["reservableRoles"][roleName] == interaction.user.id:
                        view.add_item(ScheduleButton(interaction.message, row=1, label="Unreserve Current Role", style=discord.ButtonStyle.danger, custom_id="reserve_role_unreserve"))
                        break

                # Standby button; if any role reserved, but not accepted
                isStandbyButton = False
                if isAcceptAndReserve and any(event["reservableRoles"].values()) and interaction.user.id not in event["standby"]:
                    isStandbyButton = True
                    view.add_item(ScheduleButton(interaction.message, row=1, label="Standby", style=discord.ButtonStyle.success, custom_id="standby_btn"))

                msgContent = interaction.user.mention
                if len(view.children) <= 0 + isStandbyButton:
                    msgContent += " All roles are reserved!"

                await interaction.response.send_message(content=msgContent, view=view, ephemeral=True, delete_after=60.0)
                return

            elif customId == "reserve_role_unreserve":
                scheduleNeedsUpdate = False
                if self.message is None:
                    log.exception("ScheduleButton callback reserve_role_unreserve: self.message is None")
                    return
                event = [event for event in events if event["messageId"] == self.message.id][0]

                # Disable all discord.ui.Item
                if self.view is None:
                    log.exception("ScheduleButton callback reserve_role_unreserve: self.view is None")
                    return

                for child in self.view.children:
                    child.disabled = True
                await interaction.response.edit_message(view=self.view)

                # Unreserve role
                for roleName in event["reservableRoles"]:
                    if event["reservableRoles"][roleName] != interaction.user.id:
                        continue

                    event["reservableRoles"][roleName] = None
                    await interaction.followup.send(embed=discord.Embed(title=f"✅ Role unreserved: `{roleName}`", color=discord.Color.green()), ephemeral=True)

                    # Event view has button "Accept & Reserve"
                    if event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"] and interaction.user.id in event["accepted"]:
                        event["accepted"].remove(interaction.user.id)
                    await self.message.edit(embed=Schedule.getEventEmbed(event, interaction.guild))

                    # Notify people on standby that reservable role(s) are vacant
                    if len(event["standby"]) > 0 and isinstance(event["maxPlayers"], int) and len(event["accepted"]) < event["maxPlayers"] and event["reservableRoles"] and not all(event["reservableRoles"].values()):
                        if not isinstance(interaction.guild, discord.Guild):
                            log.exception("ScheduleButton callback: interaction.guild not discord.Guild")
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
                                log.warning(f"ScheduleButton callback: Failed to get member with id '{standbyMemberId}'")
                                continue

                            try:
                                await standbyMember.send(embed=embed)
                            except Exception:
                                log.warning(f"ScheduleButton callback: Failed to DM {standbyMember.id} [{standbyMember.display_name}] about vacant roles")
                        break

            elif customId == "config":
                event = eventList[0]
                scheduleNeedsUpdate = False

                if Schedule.isAllowedToEdit(interaction.user, event["authorId"]) is False:
                    await interaction.response.send_message("Only the host, Unit Staff and Server Hampters can configure the event!", ephemeral=True, delete_after=60.0)
                    return

                view = ScheduleView()
                view.add_item(ScheduleButton(interaction.message, row=0, label="Edit", style=discord.ButtonStyle.primary, custom_id="edit"))
                view.add_item(ScheduleButton(interaction.message, row=0, label="Delete", style=discord.ButtonStyle.danger, custom_id="delete"))
                view.add_item(ScheduleButton(interaction.message, row=0, label="List RSVP", style=discord.ButtonStyle.secondary, custom_id="event_list_accepted"))
                await interaction.response.send_message(content=f"{interaction.user.mention} What would you like to configure?", view=view, ephemeral=True, delete_after=30.0)

            elif customId == "edit":
                scheduleNeedsUpdate = False
                if self.message is None:
                    log.exception("ScheduleButton callback edit: self.message is None")
                    return

                event = [event for event in events if event["messageId"] == self.message.id][0]
                if Schedule.isAllowedToEdit(interaction.user, event["authorId"]) is False:
                    await interaction.response.send_message("Restart the editing process.\nThe button points to an event you aren't allowed to edit.", ephemeral=True, delete_after=5.0)
                    return
                await Schedule.editEvent(interaction, event, self.message)

            elif customId == "delete":
                if self.message is None:
                    log.exception("ScheduleButton callback delete: self.message is None")
                    return

                event = [event for event in events if event["messageId"] == self.message.id][0]
                scheduleNeedsUpdate = False

                embed = discord.Embed(title=f"Are you sure you want to delete this {event['type'].lower()}: `{event['title']}`?", color=discord.Color.orange())
                view = ScheduleView()
                items = [
                    ScheduleButton(self.message, row=0, label="Delete", style=discord.ButtonStyle.success, custom_id="delete_event_confirm"),
                    ScheduleButton(self.message, row=0, label="Cancel", style=discord.ButtonStyle.danger, custom_id="delete_event_cancel"),
                ]
                for item in items:
                    view.add_item(item)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=60.0)

            elif customId == "delete_event_confirm":
                scheduleNeedsUpdate = False

                if self.view is None:
                    log.exception("ScheduleButton callback delete_event_confirm: self.view is None")
                    return

                if self.message is None:
                    log.exception("ScheduleButton callback delete_event_confirm: self.message is None")
                    return

                # Disable buttons
                for button in self.view.children:
                    button.disabled = True
                await interaction.response.edit_message(view=self.view)

                # Delete event
                event = [event for event in events if event["messageId"] == self.message.id][0]
                await self.message.delete()
                try:
                    log.info(f"{interaction.user.id} [{interaction.user.display_name}] deleted the event '{event['title']}'")
                    await interaction.followup.send(embed=discord.Embed(title=f"✅ {event['type']} deleted!", color=discord.Color.green()), ephemeral=True)

                    # Notify attendees
                    utcNow = datetime.now(timezone.utc)
                    startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
                    if event["maxPlayers"] != "hidden" and utcNow > startTime + timedelta(minutes=30):
                        await Schedule.saveEventToHistory(event, interaction.guild)
                    else:
                        for memberId in event["accepted"] + event["declined"] + event["tentative"] + event["standby"]:
                            member = interaction.guild.get_member(memberId)
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

            elif customId == "delete_event_cancel":
                if self.view is None:
                    log.exception("ScheduleButton callback delete_event_cancel: self.view is None")
                    return

                for item in self.view.children:
                    item.disabled = True
                await interaction.response.edit_message(view=self.view)
                await interaction.followup.send(embed=discord.Embed(title=f"❌ Event deletion canceled!", color=discord.Color.red()), ephemeral=True)
                return

            elif customId == "event_list_accepted":
                if self.message is None:
                    log.exception("ScheduleButton callback event_list_accepted: self.message is None")
                    return

                event = [event for event in events if event["messageId"] == self.message.id][0]

                description = ""
                accepted = [member.mention for memberId in event["accepted"] if (member := interaction.guild.get_member(memberId)) is not None]
                description += f"**Accepted ({len(accepted)}):**\n`{' '.join(accepted)}`\n\n" if accepted else ""

                standby = [member.mention for memberId in event["standby"] if (member := interaction.guild.get_member(memberId)) is not None]
                if standby:
                    description += f"**Standby ({len(standby)}):**\n`{' '.join(standby)}`\n\n"

                tentative = [member.mention for memberId in event["tentative"] if (member := interaction.guild.get_member(memberId)) is not None]
                if tentative:
                    description += f"**Tentative ({len(tentative)}):**\n`{' '.join(tentative)}`\n\n"

                declined = [member.mention for memberId in event["declined"] if (member := interaction.guild.get_member(memberId)) is not None]
                if declined:
                    description += f"**Declined ({len(declined)}):**\n`{' '.join(declined)}`"

                if not description:
                    description = "No RSVPs yet!"

                embed = discord.Embed(title=f"RSVP Listing", description=description.strip()[:4096], color=discord.Color.gold())
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=60.0)
                return

            elif customId is not None and customId.startswith("event_schedule_"):
                if self.view is None:
                    log.exception("ScheduleButton callback event_schedule_: self.view is None")
                    return

                if interaction.user.id != self.view.authorId:
                    await interaction.response.send_message(f"{interaction.user.mention} Only the one who executed the command may interact with the buttons!", ephemeral=True, delete_after=10.0)
                    return

                buttonLabel = customId[len("event_schedule_"):]

                generateModal = lambda style, placeholder, default, required, minLength, maxLength: ScheduleModal(
                        title="Create event", customId=f"modal_create_{buttonLabel}", userId=interaction.user.id, eventMsg=interaction.message, view=self.view
                    ).add_item(
                        discord.ui.TextInput(
                            label=buttonLabel.replace("_", " ").capitalize(), style=style, placeholder=placeholder, default=default, required=required, min_length=minLength, max_length=maxLength
                        )
                    )

                previewEmbedDict = Schedule.fromPreviewEmbedToDict(interaction.message.embeds[0])

                requiredInfoRemaining = [
                    child.label for child in self.view.children
                    if isinstance(child, discord.ui.Button) and child.style == discord.ButtonStyle.danger and child.disabled == False
                ]

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
                        await interaction.response.send_message(interaction.user.mention, view=Schedule.generateSelectView(
                            typeOptions,
                            False,
                            previewEmbedDict["type"] or "",
                            interaction.message,
                            "Select event type.",
                            "select_create_type",
                            interaction.user.id,
                            self.view
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
                            await interaction.response.send_message(embed=discord.Embed(title="❌ Apply timezone", description="You must provide a time zone. Execute the command `/changetimezone`", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
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
                                log.warning("ScheduleButton callback map: modpackMaps not in genericData")
                                return

                        options = [discord.SelectOption(label=mapName) for mapName in genericData["modpackMaps"]]
                        await interaction.response.send_message(interaction.user.mention, view=Schedule.generateSelectView(
                            options,
                            True,
                            previewEmbedDict["map"],
                            interaction.message,
                            "Select a map.",
                            "select_create_map",
                            interaction.user.id,
                            self.view
                        ),
                            ephemeral=True,
                            delete_after=60.0
                        )

                    case "max_players":
                        default = str(previewEmbedDict["maxPlayers"])

                        # Correct no input to default=""
                        if previewEmbedDict["maxPlayers"] == "hidden" and self.style == discord.ButtonStyle.danger:
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
                        await interaction.response.send_message(interaction.user.mention, view=Schedule.generateSelectView(
                            options,
                            True,
                            previewEmbedDict["workshopInterest"] if "workshopInterest" in previewEmbedDict else "",
                            interaction.message,
                            "Link event to a workshop.",
                            "select_create_linking",
                            interaction.user.id,
                            self.view
                        ),
                            ephemeral=True,
                            delete_after=60.0
                        )


                    # FILES
                    case "files":
                        view = ScheduleView(authorId=interaction.user.id, previousMessageView=self.view)
                        items = [
                            ScheduleButton(interaction.message, row=0, label="Add", style=discord.ButtonStyle.success, custom_id="event_schedule_files_add", disabled=(len(previewEmbedDict["files"]) == 10)),
                            ScheduleButton(interaction.message, row=0, label="Remove", style=discord.ButtonStyle.danger, custom_id="event_schedule_files_remove", disabled=(len(previewEmbedDict["files"]) == 0)),
                        ]
                        for item in items:
                            view.add_item(item)

                        embed = discord.Embed(title="Attaching files", description="You may attach up to 10 files to your event.\nUpload them first using the command `/fileupload`.", color=discord.Color.gold())
                        await interaction.response.send_message(interaction.user.mention, embed=embed, view=view, ephemeral=True, delete_after=300.0)

                    case "files_add":
                        messageNew = await interaction.channel.fetch_message(self.message.id)
                        if not isinstance(messageNew, discord.Message):
                            log.exception("ScheduleButton callback files_add: messageNew not discord.Message")
                            return
                        previewEmbedDict = Schedule.fromPreviewEmbedToDict(messageNew.embeds[0])
                        options = [discord.SelectOption(label=fileUpload) for fileUpload in Schedule.getUserFileUploads(str(interaction.user.id)) if fileUpload not in previewEmbedDict["files"]]

                        if len(options) == 0:
                            embed = discord.Embed(title="Attaching files [Add]", description="You have not uploaded any files yet.\nTo upload new files; run the command `/fileupload`.", color=discord.Color.red())
                            view = None
                        else:
                            embed = discord.Embed(title="Attaching files [Add]", description="Select a file to upload from the select menus below.\nTo upload new files; run the command `/fileupload`.", color=discord.Color.gold())
                            view = Schedule.generateSelectView(options, False, None, messageNew, "Select a file.", "select_create_files_add", interaction.user.id, self.view.previousMessageView)

                        await interaction.response.edit_message(embed=embed, view=view)

                    case "files_remove":
                        messageNew = await interaction.channel.fetch_message(self.message.id)
                        if not isinstance(messageNew, discord.Message):
                            log.exception("ScheduleButton callback files_remove: messageNew not discord.Message")
                            return
                        previewEmbedDict = Schedule.fromPreviewEmbedToDict(messageNew.embeds[0])
                        options = [discord.SelectOption(label=previewFile) for previewFile in previewEmbedDict["files"]]

                        if len(options) == 0:
                            embed = discord.Embed(title="Attaching files [Remove]", description="You have not selected any file to be attached.\nTo select a file, press the `Add` button.", color=discord.Color.red())
                            view = None
                        else:
                            embed = discord.Embed(title="Attaching files [Remove]", description="Select a file to remove from the select menus below.", color=discord.Color.gold())
                            view = Schedule.generateSelectView(options, False, None, messageNew, "Select a file.", "select_create_files_remove", interaction.user.id, self.view.previousMessageView)

                        await interaction.response.edit_message(embed=embed, view=view)


                    # TEMPLATES
                    case "save_as_template":
                        if (len(requiredInfoRemaining) >= 2) or (len(requiredInfoRemaining) == 1 and ("Time" not in requiredInfoRemaining)):
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
                        if (len(requiredInfoRemaining) >= 2) or (len(requiredInfoRemaining) == 1 and ("Time" not in requiredInfoRemaining)):
                            await interaction.response.send_message(f"{interaction.user.mention} Before updating the template, you need to fill out the mandatory (red buttons) information!", ephemeral=True, delete_after=10.0)
                            return

                        # Fetch template name from button label
                        templateName = ""
                        for child in self.view.children:
                            if isinstance(child, discord.ui.Button) and child.label is not None and child.label.startswith("Select Template"):
                                templateName = "".join(child.label.split(":")[1:]).strip()
                                break
                        if templateName == "":
                            log.exception("ScheduleButton callback: templateName is empty")
                            return

                        # Write to file
                        filename = f"data/{previewEmbedDict['type'].lower()}Templates.json"
                        Schedule.applyMissingEventKeys(previewEmbedDict, keySet="template", removeKeys=True)
                        with open(filename) as f:
                            templates = json.load(f)

                        templateIndex = None
                        for idx, template in enumerate(templates):
                            if template.get("templateName", None) == templateName:
                                templateIndex = idx
                                break
                        else:
                            log.exception("ScheduleButton callback: templateIndex not found")
                            return

                        previewEmbedDict["templateName"] = templateName
                        if previewEmbedDict in templates:
                            embed = discord.Embed(title="❌ No diff", description="The new template data does not differ from the old template.\nTemplate not updated.", color=discord.Color.red())
                            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)
                            return

                        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Updated template '{templateName}'")
                        templates[templateIndex] = previewEmbedDict
                        with open(filename, "w") as f:
                            json.dump(templates, f, indent=4)

                        # Reply
                        embed = discord.Embed(title="✅ Updated", description=f"Updated template: `{templateName}`", color=discord.Color.green())
                        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)


                    # EVENT FINISHING
                    case "submit":
                        # Check if all mandatory fields are filled
                        if len(requiredInfoRemaining) != 0:
                            await interaction.response.send_message(f"{interaction.user.mention} Before creating the event, you need to fill out the mandatory (red buttons) information!", ephemeral=True, delete_after=10.0)
                            return

                        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Created a '{previewEmbedDict['type']}' titled '{previewEmbedDict['title']}'")
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
                        await Schedule.updateSchedule(interaction.guild)

                        # Workshop interest ping
                        workshopInterestValue = previewEmbedDict.get("workshopInterest", None)
                        if workshopInterestValue:
                            with open(WORKSHOP_INTEREST_FILE) as f:
                                fileWSINT = json.load(f)
                            targetWorkshopMembers = [wsDetails.get("members", []) for wsName, wsDetails in fileWSINT.items() if workshopInterestValue == wsName][0]
                            if targetWorkshopMembers:
                                channelArmaDiscussion = interaction.guild.get_channel(ARMA_DISCUSSION)
                                if not isinstance(channelArmaDiscussion, discord.TextChannel):
                                    log.exception("ScheduleButton callback: channelArmaDiscussion not discord.TextChannel")
                                    return

                                msg = ""
                                for memberId in targetWorkshopMembers:
                                    msg += workshopMember.mention + " " if (workshopMember := interaction.guild.get_member(memberId)) else ""
                                await channelArmaDiscussion.send(f"{msg}\n**{previewEmbedDict['title']}** is up on <#{SCHEDULE}> - which you are interested in.\nNo longer interested? Unlist yourself in <#{WORKSHOP_INTEREST}>")


                        # Operation Pings
                        if previewEmbedDict["type"].lower() == "operation":
                            roleOperationPings = interaction.guild.get_role(OPERATION_PINGS)
                            if not isinstance(roleOperationPings, discord.Role):
                                log.exception("ScheduleButton callback: roleOperationPings not discord.Role")
                                return

                            channelOperationAnnouncements = interaction.guild.get_channel(OPERATION_ANNOUNCEMENTS)
                            if not isinstance(channelOperationAnnouncements, discord.TextChannel):
                                log.exception("ScheduleButton callback: channelOperationAnnouncements not discord.TextChannel")
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
                            ScheduleButton(interaction.message, row=0, label="Cancel", style=discord.ButtonStyle.success, custom_id="event_schedule_cancel_confirm"),
                            ScheduleButton(interaction.message, row=0, label="No, I changed my mind", style=discord.ButtonStyle.danger, custom_id="event_schedule_cancel_decline"),
                        ]
                        for item in items:
                            view.add_item(item)
                        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=60.0)

                    case "cancel_confirm":
                        if self.message is None:
                            log.exception("ScheduleButton callback cancel_confirm: self.message is None")
                            return
                        for child in self.view.children:
                            if isinstance(child, discord.ui.Button):
                                child.disabled = True
                        await interaction.response.edit_message(view=self.view)
                        await self.message.edit(content="Nvm guys, didn't wanna bop.", embed=None, view=None)

                    case "cancel_decline":
                        if self.message is None:
                            log.exception("ScheduleButton callback cancel_decline: self.message is None")
                            return
                        for child in self.view.children:
                            if isinstance(child, discord.ui.Button):
                                child.disabled = True
                        await interaction.response.edit_message(view=self.view)
                        await interaction.followup.send(content="Alright, I won't cancel the scheduling.", ephemeral=True)

                if buttonLabel.startswith("select_template"):
                    filename = f"data/{previewEmbedDict['type'].lower()}Templates.json"
                    with open(filename) as f:
                        templates: List[Dict] = json.load(f)
                    templates.sort(key=lambda template : template["templateName"])

                    options = [discord.SelectOption(label=template["templateName"], description=template["description"][:100]) for template in templates]
                    setOptionLabel = ""
                    for child in self.view.children:
                        if isinstance(child, discord.ui.Button) and child.label is not None and child.label.startswith("Select Template"):
                            setOptionLabel = "".join(child.label.split(":")[1:]).strip()

                    await interaction.response.send_message(interaction.user.mention, view=Schedule.generateSelectView(
                        options,
                        True,
                        setOptionLabel,
                        interaction.message,
                        "Select a template.",
                        "select_create_select_template",
                        interaction.user.id,
                        self.view
                    ),
                        ephemeral=True,
                        delete_after=60.0
                    )


                return

            elif customId == "event_edit_files_add":
                messageNew = await interaction.channel.fetch_message(self.message.id)
                if not isinstance(messageNew, discord.Message):
                    log.exception("ScheduleButton callback event_edit_files_add: messageNew not discord.Message")
                    return

                attachmentFilenames = [attachment.filename for attachment in messageNew.attachments]

                # Load all files uploaded by user, that isn't already attached to message
                options = [discord.SelectOption(label=fileUpload) for fileUpload in Schedule.getUserFileUploads(str(interaction.user.id)) if fileUpload not in attachmentFilenames]

                if len(options) == 0:
                    embed = discord.Embed(title="Attaching files [Add]", description="You do not have any new files to attach.\nTo upload new files; run the command `/fileupload`.", color=discord.Color.red())
                    view = None
                else:
                    embed = discord.Embed(title="Attaching files [Add]", description="Select a file to upload from the select menus below.\nTo upload new files; run the command `/fileupload`.", color=discord.Color.gold())
                    view = Schedule.generateSelectView(options, False, None, messageNew, "Select a file.", "edit_select_files_add", interaction.user.id, self.view.previousMessageView)

                await interaction.response.edit_message(embed=embed, view=view)
                return

            elif customId == "event_edit_files_remove":
                messageNew = await interaction.channel.fetch_message(self.message.id)
                if not isinstance(messageNew, discord.Message):
                    log.exception("ScheduleButton callback event_edit_files_remove: messageNew not discord.Message")
                    return

                attachmentFilenames = [attachment.filename for attachment in messageNew.attachments]
                options = [discord.SelectOption(label=fileUpload) for fileUpload in Schedule.getUserFileUploads(str(interaction.user.id)) if fileUpload in attachmentFilenames]

                if len(options) == 0:
                    embed = discord.Embed(title="Attaching files [Remove]", description="You have not selected any file to be attached.\nTo select a file, press the `Add` button.", color=discord.Color.red())
                    view = None
                else:
                    embed = discord.Embed(title="Attaching files [Remove]", description="Select a file to remove from the select menus below.", color=discord.Color.gold())
                    view = Schedule.generateSelectView(options, False, None, messageNew, "Select a file.", "edit_select_files_remove", interaction.user.id, self.view.previousMessageView)

                await interaction.response.edit_message(embed=embed, view=view)
                return

            elif customId == "schedule_change_time_zone":
                default = None
                with open(MEMBER_TIME_ZONES_FILE) as f:
                    memberTimeZones = json.load(f)
                if str(interaction.user.id) in memberTimeZones:
                    default = memberTimeZones[str(interaction.user.id)]

                modal = ScheduleModal(
                    title="Change time zone",
                    customId="modal_change_time_zone",
                    userId=interaction.user.id,
                    eventMsg=interaction.message,
                )
                modal.add_item(discord.ui.TextInput(label="Time zone", default=default, placeholder="Europe/London", min_length=1, max_length=256))
                await interaction.response.send_modal(modal)
                return

            elif customId == "schedule_remove_time_zone":
                with open(MEMBER_TIME_ZONES_FILE) as f:
                    memberTimeZones = json.load(f)

                if str(interaction.user.id) in memberTimeZones:
                    del memberTimeZones[str(interaction.user.id)]
                    with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                        json.dump(memberTimeZones, f, indent=4)

                    embed = discord.Embed(title="✅ Time zone removed", description="Your configuration is now removed.", color=discord.Color.green())
                    await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10.0)

                else:
                    embed = discord.Embed(title="❌ Invalid", description="No time zone set!", color=discord.Color.red())
                    await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10.0)
                return

            elif customId.startswith("schedule_noshow_add_"):
                targetUserId = customId[len("schedule_noshow_add_"):]
                modal = ScheduleModal(
                    title="Add no-show entry",
                    customId=f"modal_noshow_add_{targetUserId}",
                    userId=interaction.user.id,
                    eventMsg=interaction.message,
                )
                modal.add_item(discord.ui.TextInput(label="Operation startime (UTC)", placeholder="2069-04-20 04:20 PM", min_length=1, max_length=256))
                modal.add_item(discord.ui.TextInput(label="Operation Title", placeholder="Operation Honda Civic", min_length=1, max_length=256))
                modal.add_item(discord.ui.TextInput(label="User reserved role", placeholder="Actual", min_length=1, max_length=256, required=False))
                await interaction.response.send_modal(modal)
                return

            elif customId.startswith("schedule_noshow_remove_"):
                targetUserId = customId[len("schedule_noshow_remove_"):]
                with open(NO_SHOW_FILE) as f:
                    noShowFile = json.load(f)

                if targetUserId not in noShowFile:
                    embed = discord.Embed(title="User not found", description="Target user not found in no show entries", color=discord.Color.red())
                    await interaction.response.send_message(embed=embed)
                    return

                options = []
                for entry in noShowFile[targetUserId]:
                    date = entry.get("date", 0)
                    noShowEntryTimestamp = datetime.fromtimestamp(date, timezone.utc).strftime(TIME_FORMAT)
                    options.append(discord.SelectOption(label=entry.get("operationName", "Operation UNKNOWN"), description=noShowEntryTimestamp, value=date))

                await interaction.response.send_message(interaction.user.mention, view=Schedule.generateSelectView(
                    options=options,
                    noneOption=False,
                    setOptionLabel=None,
                    eventMsg=interaction.message,
                    placeholder="Select no-show entry.",
                    customId=f"select_noshow_entry_{targetUserId}",
                    userId=interaction.user.id,
                    eventMsgView=self.view
                ),
                    ephemeral=True,
                    delete_after=60.0
                )
                return


            if scheduleNeedsUpdate:
                try:
                    embed = Schedule.getEventEmbed(event, interaction.guild)
                    if fetchMsg:  # Could be better - could be worse...
                        if interaction.channel is None or isinstance(interaction.channel, discord.ForumChannel) or isinstance(interaction.channel, discord.CategoryChannel):
                            log.exception("ScheduleButton callback: interaction.channel is invalid type")
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

class ScheduleSelect(discord.ui.Select):
    """Handling all schedule dropdowns."""
    def __init__(self, eventMsg: discord.Message, placeholder: str, minValues: int, maxValues: int, customId: str, userId: int, row: int, options: List[discord.SelectOption], disabled: bool = False, eventMsgView: discord.ui.View | None = None, *args, **kwargs):
        # Append userId to customId to not collide on multi-user simultaneous execution
        super().__init__(placeholder=placeholder, min_values=minValues, max_values=maxValues, custom_id=f"{customId}_{userId}", row=row, options=options, disabled=disabled, *args, **kwargs)
        self.eventMsg = eventMsg
        self.eventMsgView = eventMsgView

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("ScheduleSelect callback: interaction.guild not discord.Guild")
            return

        customId = "_".join(interaction.data["custom_id"].split("_")[:-1])  # Remove authorId

        if not isinstance(interaction.user, discord.Member):
            log.exception("ScheduleSelect callback: interaction.user not discord.Member")
            return

        selectedValue = self.values[0]

        if customId.startswith("select_create_"):
            if self.eventMsgView is None:
                log.exception("ScheduleSelect callback: self.eventMsgView is None")
                return

            infoLabel = customId[len("select_create_"):].split("_REMOVE")[0]  # e.g. "type"

            # Disable all discord.ui.Item if not in blacklist
            CASES_WHEN_SELECT_MENU_EDITS_AWAY = ("files_add", "files_remove")
            if infoLabel not in CASES_WHEN_SELECT_MENU_EDITS_AWAY:
                if self.view is None:
                    log.exception("ScheduleSelect callback: self.view is None")
                    return
                for child in self.view.children:
                    child.disabled = True
                await interaction.response.edit_message(view=self.view)

            eventMsgNew = await interaction.channel.fetch_message(self.eventMsg.id)
            if not isinstance(eventMsgNew, discord.Message):
                log.exception("ScheduleSelect callback: eventMsgNew not discord.Message")
                return

            previewEmbedDict = Schedule.fromPreviewEmbedToDict(eventMsgNew.embeds[0])
            previewEmbedDict["authorId"] = interaction.user.id


            # Do preview embed edits
            match infoLabel:
                case "type":
                    log.debug(f"{interaction.user.id} [{interaction.user.display_name}] selected event type '{selectedValue}'")
                    previewEmbedDict["type"] = selectedValue

                    templateName = "None"
                    # Fetch templateName
                    for child in self.eventMsgView.children:
                        if isinstance(child, discord.ui.Button) and child.label is not None and child.label.startswith("Select Template: "):
                            templateName = ":".join(child.label.split(":")[1:]).strip()
                            break

                    # Update view
                    previewView = Schedule.fromDictToPreviewView(previewEmbedDict, templateName)
                    self.eventMsgView.clear_items()
                    for item in previewView.children:
                        self.eventMsgView.add_item(item)

                case "map":
                    previewEmbedDict["map"] = None if previewEmbedDict["map"] == "None" else selectedValue

                case "linking":
                    previewEmbedDict["workshopInterest"] = None if selectedValue == "None" else selectedValue

                case "select_template":
                    # Update template buttons label & disabled
                    for child in self.eventMsgView.children:
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
                        if template.get("templateName", None) == selectedValue:
                            template["authorId"] = interaction.user.id
                            Schedule.applyMissingEventKeys(template, keySet="template")
                            template["type"] = previewEmbedDict["type"]
                            embed = Schedule.fromDictToPreviewEmbed(template, interaction.guild)
                            for child in self.eventMsgView.children:
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
                                child.style = discord.ButtonStyle.secondary if jsonKey not in template or template[jsonKey] is None else discord.ButtonStyle.success

                            await eventMsgNew.edit(embed=embed, view=self.eventMsgView)
                            return


            if infoLabel == "files_add":
                if len(previewEmbedDict["files"]) < 10:
                    previewEmbedDict["files"].append(selectedValue)
            elif infoLabel == "files_remove":
                if selectedValue in previewEmbedDict["files"]:
                    previewEmbedDict["files"].remove(selectedValue)


            if infoLabel.startswith("files"):
                view = ScheduleView(authorId=interaction.user.id, previousMessageView=self.eventMsgView)
                items = [
                    ScheduleButton(eventMsgNew, row=0, label="Add", style=discord.ButtonStyle.success, custom_id="event_schedule_files_add", disabled=(len(previewEmbedDict["files"]) == 10)),
                    ScheduleButton(eventMsgNew, row=0, label="Remove", style=discord.ButtonStyle.danger, custom_id="event_schedule_files_remove", disabled=(len(previewEmbedDict["files"]) == 0))
                ]
                for item in items:
                    view.add_item(item)

                embed = discord.Embed(title="Attaching files", description="You may attach up to 10 files to your event.\nUpload them first using the command `/fileupload`.", color=discord.Color.gold())
                await interaction.response.edit_message(embed=embed, view=view)

            # Update eventMsg button style
            for child in self.eventMsgView.children:
                if isinstance(child, discord.ui.Button) and child.label is not None and child.label.lower().replace(" ", "_") == infoLabel:
                    child.style = discord.ButtonStyle.success
                    break

            # Edit preview embed & view
            await eventMsgNew.edit(embed=Schedule.fromDictToPreviewEmbed(previewEmbedDict, interaction.guild), view=self.eventMsgView)


        elif customId.startswith("select_noshow_entry_"):
            userId = customId[len("select_noshow_entry_"):]
            userId = "_".join(userId.split("_")[:-1])  # Remove "_REMOVE0"

            with open(NO_SHOW_FILE) as f:
                noShowFile = json.load(f)

            if userId not in noShowFile:
                embed = discord.Embed(title="User not found", description="Target user not found in no-show entries", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)
                return

            for entry in noShowFile[userId]:
                date = entry.get("date", "0")
                if int(selectedValue) == date:
                    date = discord.utils.format_dt(datetime.fromtimestamp(date, timezone.utc), style="R")
                    embedDescription = f"**Date:** {date}\n**Operation Name:** `{entry.get('operationName', 'Operation UNKNOWN')}`"
                    if entry.get("reservedRole", None):
                        embedDescription += f"\n**Reserved Role:** `{entry['reservedRole']}`"
                    embed = discord.Embed(title="Entry removed", description=embedDescription, color=discord.Color.green())
                    await interaction.response.send_message("Execute /no-show again to view the updated listing.", embed=embed, ephemeral=True, delete_after=30.0)
                    break
            else:
                embed = discord.Embed(title="Entry not found", description=f"Target entry not found in no-show entries. Selected value '{selectedValue}'", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)
                return

            noShowFile[userId].remove(entry)
            if len(noShowFile[userId]) == 0:
                noShowFile.pop(userId, None)

            with open(NO_SHOW_FILE, "w") as f:
                json.dump(noShowFile, f, indent=4)
            return


        elif customId == "reserve_role_select":
            # Disable all discord.ui.Item
            if self.view is None:
                log.exception("ScheduleSelect callback reserve_role_select: self.view is None")
                return

            await interaction.response.edit_message(view=None)

            with open(EVENTS_FILE) as f:
                events = json.load(f)
            event = [event for event in events if event["messageId"] == self.eventMsg.id][0]

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
            await self.eventMsg.edit(embed=Schedule.getEventEmbed(event, interaction.guild))
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)

            # Ping Recruitment Team if candidate reserves
            if event["type"].lower() == "operation" and any([True for role in interaction.user.roles if role.id == CANDIDATE]):
                if not isinstance(interaction.guild, discord.Guild):
                    log.exception("ScheduleSelect callback: interaction.guild not discord.Guild")
                    return
                channelRecruitmentHr = interaction.guild.get_channel(RECRUITMENT_AND_HR)
                if not isinstance(channelRecruitmentHr, discord.TextChannel):
                    log.exception("ScheduleSelect callback: channelRecruitmentHr not discord.TextChannel")
                    return
                if not await Schedule.hasCandidatePinged(interaction.user.id, event["title"], channelRecruitmentHr):
                    embed = discord.Embed(title="Candidate Accept", description=f"{interaction.user.mention} accepted operation `{event['title']}`\nReserved role `{selectedValue}`", color=discord.Color.blue())
                    embed.set_footer(text=f"Candidate ID: {interaction.user.id}")
                    await channelRecruitmentHr.send(embed=embed)


        elif customId == "edit_select":
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            event = [event for event in events if event["messageId"] == self.eventMsg.id][0]

            if Schedule.isAllowedToEdit(interaction.user, event["authorId"]) is False:
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
                    view = Schedule.generateSelectView(options, False, eventType, self.eventMsg, "Select event type.", "edit_select_type", interaction.user.id)

                    await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

                # Editing Title
                case "Title":
                    modal = ScheduleModal("Title", "modal_title", interaction.user.id, self.eventMsg)
                    modal.add_item(discord.ui.TextInput(label="Title", default=event["title"], placeholder="Operation Honda Civic", min_length=1, max_length=256))
                    await interaction.response.send_modal(modal)

                # Editing Linking
                case "Linking":
                    with open(WORKSHOP_INTEREST_FILE) as f:
                        wsIntOptions = json.load(f).keys()

                    options = [discord.SelectOption(label=wsName) for wsName in wsIntOptions]
                    view = Schedule.generateSelectView(options, True, event["map"], self.eventMsg, "Link event to a workshop.", "edit_select_linking", interaction.user.id)
                    await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

                # Editing Description
                case "Description":
                    modal = ScheduleModal("Description", "modal_description", interaction.user.id, self.eventMsg)
                    modal.add_item(discord.ui.TextInput(style=discord.TextStyle.long, label="Description", default=event["description"], placeholder="Bomb oogaboogas", min_length=1, max_length=4000))
                    await interaction.response.send_modal(modal)

                # Editing URL
                case "External URL":
                    modal = ScheduleModal("External URL", "modal_externalURL", interaction.user.id, self.eventMsg)
                    modal.add_item(discord.ui.TextInput(style=discord.TextStyle.long, label="URL", default=event["externalURL"], placeholder="OPORD: https://www.gnu.org/", max_length=1024, required=False))
                    await interaction.response.send_modal(modal)

                # Editing Reservable Roles
                case "Reservable Roles":
                    modal = ScheduleModal("Reservable Roles", "modal_reservableRoles", interaction.user.id, self.eventMsg)
                    modal.add_item(discord.ui.TextInput(style=discord.TextStyle.long, label="Reservable Roles", default=(None if event["reservableRoles"] is None else "\n".join(event["reservableRoles"].keys())), placeholder="Co-Zeus\nActual\nJTAC\nF-35A Pilot", max_length=512, required=False))
                    await interaction.response.send_modal(modal)

                # Editing Map
                case "Map":
                    with open(GENERIC_DATA_FILE) as f:
                        genericData = json.load(f)
                        if "modpackMaps" not in genericData:
                            log.exception("ScheduleButton callback: modpackMaps not in genericData")
                            return
                    options = [discord.SelectOption(label=mapName) for mapName in genericData["modpackMaps"]]
                    view = Schedule.generateSelectView(options, True, event["map"], self.eventMsg, "Select a map.", "edit_select_map", interaction.user.id)
                    await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

                # Editing Attendence
                case "Max Players":
                    modal = ScheduleModal("Attendees", "modal_maxPlayers", interaction.user.id, self.eventMsg)
                    modal.add_item(discord.ui.TextInput(label="Attendees", default=event["maxPlayers"], placeholder="Number / None / Anonymous / Hidden", min_length=1, max_length=9))
                    await interaction.response.send_modal(modal)

                # Editing Duration
                case "Duration":
                    modal = ScheduleModal("Duration", "modal_duration", interaction.user.id, self.eventMsg)
                    modal.add_item(discord.ui.TextInput(label="Duration", default=event["duration"], placeholder="2h30m", min_length=1, max_length=16))
                    await interaction.response.send_modal(modal)

                # Editing Time
                case "Time":
                    # Set user time zone
                    with open(MEMBER_TIME_ZONES_FILE) as f:
                        memberTimeZones = json.load(f)
                    if str(interaction.user.id) not in memberTimeZones:
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Apply timezone", description="You must provide a time zone. Execute the command `/changetimezone`", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                        return

                    # Send modal
                    timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
                    modal = ScheduleModal("Time", "modal_time", interaction.user.id, self.eventMsg)
                    modal.add_item(discord.ui.TextInput(label="Time", default=datetimeParse(event["time"]).replace(tzinfo=UTC).astimezone(timeZone).strftime(TIME_FORMAT), placeholder="2069-04-20 04:20 PM", min_length=1, max_length=32))
                    await interaction.response.send_modal(modal)

                # Editing Files
                case "Files":
                    view = ScheduleView(authorId=interaction.user.id)
                    items = [
                        ScheduleButton(self.eventMsg, row=0, label="Add", style=discord.ButtonStyle.success, custom_id="event_edit_files_add", disabled=(len(self.eventMsg.attachments) == 10)),
                        ScheduleButton(self.eventMsg, row=0, label="Remove", style=discord.ButtonStyle.danger, custom_id="event_edit_files_remove", disabled=(not self.eventMsg.attachments)),
                    ]
                    for item in items:
                        view.add_item(item)

                    embed = discord.Embed(title="Attaching files", description="You may attach up to 10 files to your event.\nUpload them first using the command `/fileupload`.", color=discord.Color.gold())
                    await interaction.response.send_message(interaction.user.mention, embed=embed, view=view, ephemeral=True, delete_after=300.0)

            log.info(f"{interaction.user.id} [{interaction.user.display_name}] Edited the event '{event['title'] if 'title' in event else event['templateName']}'")

        # All select menu options in edit_select
        elif customId.startswith("edit_select_"):
            eventKey = customId[len("edit_select_"):].split("_REMOVE")[0]  # e.g. "files_add"

            with open(EVENTS_FILE) as f:
                events = json.load(f)
            event = [event for event in events if event["messageId"] == self.eventMsg.id][0]

            match eventKey:
                case "files_add":
                    allUserFiles = Schedule.getUserFileUploads(str(interaction.user.id), fullFilename=True)
                    specifiedFileList = [file for file in allUserFiles if file.split("_", 2)[2] == selectedValue]
                    if not specifiedFileList:
                        log.exception(f"ScheduleSelect callback files_add: Could not find '{selectedValue}' in specifiedFileList")
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Interaction failed", description="Could not find file in fileuploads!", color=discord.Color.red()), ephemeral=True, delete_after=5.0)
                        return

                    filenameFull = specifiedFileList[0]
                    if filenameFull in event["files"]:
                        await interaction.response.send_message(embed=discord.Embed(title="❌ File already added", color=discord.Color.red()), ephemeral=True, delete_after=5.0)
                        return

                    filenameShort = filenameFull.split("_", 2)[2]
                    event["files"].append(filenameFull)
                    eventMsgNew = await interaction.channel.fetch_message(self.eventMsg.id)
                    with open(f"tmp/fileUpload/{filenameFull}", "rb") as f:
                        await eventMsgNew.add_files(discord.File(f, filename=filenameShort))

                case "files_remove":
                    eventMsgNew = await interaction.channel.fetch_message(self.eventMsg.id)
                    eventAttachmentDict = {eventAttachment.filename: eventAttachment for eventAttachment in eventMsgNew.attachments}
                    if selectedValue not in eventAttachmentDict:
                        log.exception(f"ScheduleSelect callback files_remove: Could not find '{selectedValue}' in self.eventMsg.attachments")
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Interaction failed", description="Could not find attachment in message!", color=discord.Color.red()), ephemeral=True, delete_after=5.0)
                        return

                    allUserFiles = Schedule.getUserFileUploads(str(interaction.user.id), fullFilename=True)
                    filenameFull = [file for file in allUserFiles if file.split("_", 2)[2] == selectedValue][0]
                    if filenameFull not in event["files"]:
                        log.exception(f"ScheduleSelect callback files_remove: filenameFull '{filenameFull}' not in event['files']")
                        await interaction.response.send_message(embed=discord.Embed(title="❌ File already removed", color=discord.Color.red()), ephemeral=True, delete_after=5.0)
                        return

                    event["files"].remove(filenameFull)
                    await eventMsgNew.remove_attachments(eventAttachmentDict[selectedValue])

                case _:
                    event[eventKey] = None if selectedValue == "None" else selectedValue

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)

            await self.eventMsg.edit(embed=Schedule.getEventEmbed(event, interaction.guild))
            await interaction.response.send_message(embed=discord.Embed(title="✅ Event edited", color=discord.Color.green()), ephemeral=True, delete_after=5.0)

class ScheduleModal(discord.ui.Modal):
    """Handling all schedule modals."""
    def __init__(self, title: str, customId: str, userId: int, eventMsg: discord.Message, view: discord.ui.View | None = None) -> None:
        # Append userId to customId to not collide on multi-user simultaneous execution
        super().__init__(title=title, custom_id=f"{customId}_{userId}")
        self.eventMsg = eventMsg
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("ScheduleModal on_submit: interaction.guild not discord.Guild")
            return

        customId = "_".join(interaction.data["custom_id"].split("_")[:-1])  # Remove authorId

        if not isinstance(interaction.user, discord.Member):
            log.exception("ScheduleModal on_submit: interaction.user not discord.Member")
            return
        value: str = self.children[0].value.strip()


        if customId.startswith("modal_noshow_add_"):
            targetUserId = customId[len("modal_noshow_add_"):]

            # Operation name
            value1 = self.children[1].value.strip()

            # Reserved role
            value2 = self.children[2].value.strip()

            try:
                dateTimestamp = int(datetimeParse(value).astimezone(timezone.utc).timestamp())
            except Exception as e:
                print(e)
                embedDescription = f"**Operation Name:** `{value1}`"
                if value2:
                    embedDescription += f"\n**Reserved Role:** `{value2}`"
                embed = discord.Embed(title="Invalid datetime", description=embedDescription, color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)
                return

            with open(NO_SHOW_FILE) as f:
                noShowFile = json.load(f)

            if targetUserId not in noShowFile:
                noShowFile[targetUserId] = []

            noShowFile[targetUserId].append(
                {
                    "date": dateTimestamp,
                    "operationName": value1 or "Operation UNKNOWN",
                    "reservedRole": value2 or None
                }
            )
            with open(NO_SHOW_FILE, "w") as f:
                json.dump(noShowFile, f, indent=4)

            embedDescription = f"**Date:** {datetime.fromtimestamp(dateTimestamp, timezone.utc).strftime(TIME_FORMAT)}\n**Operation Name:** `{value1}`"
            if value2:
                embedDescription += f"\n**Reserved Role:** `{value2}`"
            embed = discord.Embed(title="Entry added", description=embedDescription, color=discord.Color.green())
            await interaction.response.send_message("Execute /no-show again to view the updated listing.", embed=embed, ephemeral=True, delete_after=30.0)
            return


        if customId == "modal_change_time_zone":
            timezoneOk = False
            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)

            try:
                timeZone = pytz.timezone(value)
                memberTimeZones[str(interaction.user.id)] = timeZone.zone
                timezoneOk = True
            except pytz.exceptions.UnknownTimeZoneError:
                pass

            if timezoneOk:
                with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                    json.dump(memberTimeZones, f, indent=4)

                embed = discord.Embed(title="✅ Time zone set", description=f"Your time zone is now set to `{timeZone.zone}`.", color=discord.Color.green())
            else:
                embed = discord.Embed(title="❌ Invalid time zone", description="Please provide a valid time zone.", color=discord.Color.red())

            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10.0)
            return

        # == Creating Event ==

        if customId.startswith("modal_create_") and self.view is not None:
            infoLabel = customId[len("modal_create_"):]
            followupMsg = {}

            # Update embed
            previewEmbedDict = Schedule.fromPreviewEmbedToDict(self.eventMsg.embeds[0])
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

                    durationDetails = Schedule.getDetailsFromDuration(value)
                    if not durationDetails:
                        await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                        return
                    hours, minutes, delta = durationDetails
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
                        durationDetails = Schedule.getDetailsFromDuration(previewEmbedDict["duration"])
                        if not durationDetails:
                            await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                            return
                        hours, minutes, delta = durationDetails
                        previewEmbedDict["endTime"] = (startTime + delta).strftime(TIME_FORMAT)

                    collision = Schedule.eventCollisionCheck(startTime, (startTime + delta) if previewEmbedDict["endTime"] else startTime+timedelta(minutes=30))
                    if collision:
                        followupMsg["content"] = interaction.user.mention
                        followupMsg["embed"] = discord.Embed(title="❌ There is a collision with another event!", description=collision, color=discord.Color.red())
                        followupMsg["embed"].set_footer(text="You may still continue with the provided time - but not recommended.")

                    if startTime < datetime.now(timezone.utc):
                        followupMsg["content"] = interaction.user.mention
                        followupMsg["embed"] = discord.Embed(title="⚠️ Operation set in the past!", description="You've entered a time that is in the past!", color=discord.Color.orange())

                case "external_url":
                    previewEmbedDict["externalURL"] = value or None

                case "reservable_roles":
                    previewEmbedDict["reservableRoles"] = None if value == "" else {role.strip(): None for role in value.split("\n") if role.strip() != ""}
                    if previewEmbedDict["reservableRoles"] and len(previewEmbedDict["reservableRoles"]) > 20:
                        previewEmbedDict["reservableRoles"] = None
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Too many roles", description=f"Due to Discord character limitation, we've set the cap to 20 roles.\nLink your order, e.g. OPORD, under URL if you require more flexibility.\n\nYour roles:\n{value}"[:4096], color=discord.Color.red()), ephemeral=True, delete_after=10.0)
                        return

                    # Check if too few slots
                    if previewEmbedDict["reservableRoles"] and isinstance(previewEmbedDict["maxPlayers"], int) and previewEmbedDict["maxPlayers"] < len(previewEmbedDict["reservableRoles"]):
                        followupMsg["content"] = interaction.user.mention
                        followupMsg["embed"] = discord.Embed(title="⚠️ Too few slots", description="You have more reservable roles than slots available.\nPlease increase the number of slots or remove some roles.", color=discord.Color.orange())
                        followupMsg["embed"].set_footer(text="You may still continue with the provided slots - but not recommended.")

                case "max_players":
                    valueLower = value.lower()
                    if valueLower not in ("none", "hidden", "anonymous") and not value.isdigit():
                        await interaction.response.send_message(embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                        return

                    if valueLower == "none":
                        previewEmbedDict["maxPlayers"] = None
                    elif value.isdigit():
                        previewEmbedDict["maxPlayers"] = 50 if int(value) > MAX_SERVER_ATTENDANCE else max(int(value), 1)
                    else:
                        previewEmbedDict["maxPlayers"] = valueLower

                    # Check if too few slots
                    if previewEmbedDict["reservableRoles"] and isinstance(previewEmbedDict["maxPlayers"], int) and previewEmbedDict["maxPlayers"] < len(previewEmbedDict["reservableRoles"]):
                        followupMsg["content"] = interaction.user.mention
                        followupMsg["embed"] = discord.Embed(title="⚠️ Too few slots", description="You have more reservable roles than slots available.\nPlease increase the number of slots or remove some roles.", color=discord.Color.orange())
                        followupMsg["embed"].set_footer(text="You may still continue with the provided slots - but not recommended.")

                case "save_as_template":
                    previewEmbedDict["templateName"] = value

                    # Write to file
                    filename = f"data/{previewEmbedDict['type'].lower()}Templates.json"
                    with open(filename) as f:
                        templates: List[Dict] = json.load(f)

                    Schedule.applyMissingEventKeys(previewEmbedDict, keySet="template", removeKeys=True)

                    if previewEmbedDict in templates:
                        await interaction.response.send_message(embed=discord.Embed(title="❌ No diff", description="The new template data does not differ from the old template.\nTemplate not overwritten.", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                        return

                    templateOverwritten = (False, 0)
                    for idx, template in enumerate(templates):
                        if template["templateName"] == previewEmbedDict["templateName"]:
                            templateOverwritten = (True, idx)
                            break

                    status = "[Overwritten]" if templateOverwritten[0] else "[New]"
                    log.info(f"{interaction.user.id} [{interaction.user.display_name}] Saved {status} a template as '{previewEmbedDict['templateName']}'")
                    if templateOverwritten[0]:
                        templates.pop(templateOverwritten[1])

                    templates.append(previewEmbedDict)
                    templates.sort(key=lambda template : template["templateName"])
                    with open(filename, "w") as f:
                        json.dump(templates, f, indent=4)

                    # Update label
                    for child in self.view.children:
                        if not isinstance(child, discord.ui.Button) or child.label is None:
                            continue
                        if child.label.startswith("Select Template"):
                            child.label = f"Select Template: {value}"
                            child.disabled = False
                        elif child.label == "Update Template":
                            child.disabled = False

                    # Reply & edit msg
                    embed = discord.Embed(title=f"✅ Saved {status}", description=f"Saved template as: `{value}`", color=discord.Color.green())
                    await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10.0)
                    await self.eventMsg.edit(view=self.view)
                    return

            # Update button style
            for child in self.view.children:
                if isinstance(child, discord.ui.Button) and child.label is not None and child.label.lower().replace(" ", "_") == infoLabel:
                    if value == "":
                        child.style = discord.ButtonStyle.danger if SCHEDULE_EVENT_VIEW[infoLabel.replace("_", " ").title().replace("Url", "URL")]["required"] else discord.ButtonStyle.secondary
                    else:
                        child.style = discord.ButtonStyle.success
                    break

            await interaction.response.edit_message(embed=Schedule.fromDictToPreviewEmbed(previewEmbedDict, interaction.guild), view=self.view)
            if followupMsg:
                await interaction.followup.send(followupMsg["content"] if "content" in followupMsg else None, embed=(followupMsg["embed"] if "embed" in followupMsg else None), ephemeral=True)
            return

        # == Editing Event ==

        followupMsg = {}
        with open(EVENTS_FILE) as f:
            events = json.load(f)
        event = [event for event in events if event["messageId"] == self.eventMsg.id][0]

        if value == "":
            event[customId[len("modal_"):]] = None

        elif customId == "modal_reservableRoles":
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

            # Check if too few slots
            if event["reservableRoles"] and isinstance(event["maxPlayers"], int) and event["maxPlayers"] < len(event["reservableRoles"]):
                followupMsg["content"] = interaction.user.mention
                followupMsg["embed"] = discord.Embed(title="⚠️ Too few slots", description="You have more reservable roles than slots available.\nPlease increase the number of slots or remove some roles.", color=discord.Color.orange())
                followupMsg["embed"].set_footer(text="You may still continue with the provided slots - but not recommended.")

        elif customId == "modal_maxPlayers":
            valueLower = value.lower()
            if valueLower == "none":
                event["maxPlayers"] = None
            elif valueLower in ("anonymous", "hidden"):
                event["maxPlayers"] = valueLower
            elif value.isdigit() and 0 < int(value):
                event["maxPlayers"] = min(int(value), MAX_SERVER_ATTENDANCE)
            else:
                await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                return

            # Check if too few slots
            if event["reservableRoles"] and isinstance(event["maxPlayers"], int) and event["maxPlayers"] < len(event["reservableRoles"]):
                followupMsg["content"] = interaction.user.mention
                followupMsg["embed"] = discord.Embed(title="⚠️ Too few slots", description="You have more reservable roles than slots available.\nPlease increase the number of slots or remove some roles.", color=discord.Color.orange())
                followupMsg["embed"].set_footer(text="You may still continue with the provided slots - but not recommended.")

        elif customId == "modal_duration":
            durationDetails = Schedule.getDetailsFromDuration(value)
            if not durationDetails:
                await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                return
            hours, minutes, delta = durationDetails

            event["duration"] = f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}"

            # Update event endTime if no template
            if "endTime" in event:
                startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
                endTime = startTime + delta
                event["endTime"] = endTime.strftime(TIME_FORMAT)

        elif customId == "modal_time":
            startTimeOld = event["time"]
            durationDetails = Schedule.getDetailsFromDuration(event["duration"])
            if not durationDetails:
                await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                return
            hours, minutes, delta = durationDetails

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
            # Send before time-hogging processes - fix interaction failed
            await interaction.response.send_message(interaction.user.mention, embed=discord.Embed(title="✅ Event edited", color=discord.Color.green()), ephemeral=True, delete_after=15.0)

            previewEmbed = discord.Embed(title=f":clock3: The starting time has changed for: {event['title']}!", description=f"From: {discord.utils.format_dt(UTC.localize(datetime.strptime(startTimeOld, TIME_FORMAT)), style='F')}\n\u2000\u2000To: {discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}", color=discord.Color.orange())
            previewEmbed.add_field(name="\u200B", value=self.eventMsg.jump_url, inline=False)
            previewEmbed.set_footer(text=f"By: {interaction.user}")
            for memberId in event["accepted"] + event["declined"] + event["tentative"] + event["standby"]:
                member = interaction.guild.get_member(memberId)
                if member is not None:
                    try:
                        await member.send(embed=previewEmbed)
                    except Exception:
                        log.warning(f"Failed to DM {member.id} [{member.display_name}] about event time change")

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)

            # === Reorder events ===
            # Save message ID order
            msgIds = []
            for eve in events:
                msgIds.append(eve["messageId"])

            # Sort events
            sortedEvents = sorted(events, key=lambda e: datetime.strptime(e["time"], TIME_FORMAT), reverse=True)

            channelSchedule = await interaction.guild.fetch_channel(SCHEDULE)
            if not isinstance(channelSchedule, discord.TextChannel):
                log.exception("ScheduleModal on_submit: channelSchedule not discord.TextChannel")
                return

            anyEventChange = False
            for idx, eve in enumerate(sortedEvents):
                # If msg is in a different position
                if eve["messageId"] != msgIds[idx]:
                    anyEventChange = True
                    eve["messageId"] = msgIds[idx]

                    # Edit msg to match position
                    msg = await channelSchedule.fetch_message(msgIds[idx])
                    await msg.edit(embed=Schedule.getEventEmbed(sortedEvents[idx], interaction.guild), view=Schedule.getEventView(sortedEvents[idx]), attachments=Schedule.getEventFiles(sortedEvents[idx]))

            if anyEventChange is False:
                msg = await channelSchedule.fetch_message(event["messageId"])
                await msg.edit(embed=Schedule.getEventEmbed(event, interaction.guild), view=Schedule.getEventView(event))


            with open(EVENTS_FILE, "w") as f:
                json.dump(sortedEvents, f, indent=4)

            # If events are reordered and user have elevated privileges and may edit other events than self-made - warn them
            if anyEventChange and ((interaction.user.id in DEVELOPERS) or any(role.id == UNIT_STAFF or role.id == SERVER_HAMSTER for role in interaction.user.roles)):
                embed = discord.Embed(title="⚠️ Restart the editing process ⚠️", description="Delete all ephemeral messages, or you may risk editing some other event!", color=discord.Color.yellow())
                embed.set_footer(text=f"Only {interaction.guild.get_role(UNIT_STAFF).name}, {interaction.guild.get_role(SERVER_HAMSTER).name} & {interaction.guild.get_role(SNEK_LORD).name} have risk of causing this.")
                await interaction.followup.send(embed=embed, ephemeral=True)
            return


        else:
            event[customId[len("modal_"):]] = value

        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)

        await self.eventMsg.edit(embed=Schedule.getEventEmbed(event, interaction.guild), view=Schedule.getEventView(event))
        await interaction.response.send_message(interaction.user.mention, embed=discord.Embed(title="✅ Event edited", color=discord.Color.green()), ephemeral=True, delete_after=5.0)

        if followupMsg:
            await interaction.followup.send(followupMsg["content"] if "content" in followupMsg else None, embed=(followupMsg["embed"] if "embed" in followupMsg else None), ephemeral=True)


    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        # await interaction.response.send_message("Something went wrong. cope.", ephemeral=True)
        log.exception(error)

# ===== </Views and Buttons> =====


async def setup(bot: commands.Bot) -> None:
    Schedule.noShow.error(Utils.onSlashError)
    Schedule.refreshSchedule.error(Utils.onSlashError)
    Schedule.aar.error(Utils.onSlashError)
    Schedule.scheduleOperation.error(Utils.onSlashError)
    await bot.add_cog(Schedule(bot))