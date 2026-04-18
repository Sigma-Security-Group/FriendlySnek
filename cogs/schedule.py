import os, re, json, asyncio, discord, logging
import pytz  # type: ignore

from math import ceil
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse as datetimeParse  # type: ignore
from dateutil.tz import gettz
from typing import *
from random import random, randint, choice

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
DATEUTIL_TZINFOS = {
    "UTC": gettz("UTC"),
    "GMT": gettz("UTC"),
    "BST": gettz("Europe/London"),
    "CET": gettz("Europe/Brussels"),
    "CEST": gettz("Europe/Brussels"),
    "EET": gettz("Europe/Sofia"),
    "EEST": gettz("Europe/Sofia"),
    "EST": gettz("America/New_York"),
    "EDT": gettz("America/New_York"),
    "CST": gettz("America/Chicago"),
    "CDT": gettz("America/Chicago"),
    "MST": gettz("America/Denver"),
    "MDT": gettz("America/Denver"),
    "PST": gettz("America/Los_Angeles"),
    "PDT": gettz("America/Los_Angeles"),
    "JST": gettz("Asia/Tokyo"),
    "AWST": gettz("Australia/Perth"),
    "ACWST": gettz("Australia/Eucla"),
    "ACST": gettz("Australia/Adelaide"),
    "AEST": gettz("Australia/Sydney"),
    "AEDT": gettz("Australia/Sydney")
}
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
    "Templates": {
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


def parseUserDatetime(value: str) -> datetime:
    """Parse free-form user datetime input with common timezone abbreviations."""
    return datetimeParse(value, tzinfos=DATEUTIL_TZINFOS)

class Schedule(commands.Cog):
    """Schedule Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @staticmethod
    async def _sendInteractionResponse(
        interaction: discord.Interaction,
        *,
        content: str | None = None,
        embed: discord.Embed = discord.Embed(),
        embeds: List[discord.Embed] = [],
        ephemeral: bool = True,
        delete_after: float | None = None,
        view: discord.ui.View = discord.ui.View()
    ) -> None:
        if not embeds and embed:
            embeds = [embed]
        if interaction.response.is_done():
            await interaction.followup.send(content=content, embeds=embeds, ephemeral=ephemeral, view=view)
        else:
            await interaction.response.send_message(content=content, embeds=embeds, ephemeral=ephemeral, delete_after=delete_after, view=view)


    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Schedule"))
        self.bot.cogsReady["schedule"] = True

        # Backfill missing event keys/ids in storage for persistent buttons.
        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)

            changed = False
            for event in events:
                keysBefore = set(event.keys())
                eventIdBefore = event.get("eventId")
                Schedule.applyMissingEventKeys(event, keySet="event")
                eventIdAfter = Schedule.ensureEventId(event, events)
                if keysBefore != set(event.keys()) or eventIdBefore != eventIdAfter:
                    changed = True

            if changed:
                with open(EVENTS_FILE, "w") as f:
                    json.dump(events, f, indent=4)
        except Exception as e:
            log.exception(f"Schedule on_ready: failed to backfill events data: {e}")

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Schedule on_ready: guild is None")
        else:
            try:
                if await Schedule.scheduleRequiresRefresh(guild):
                    log.info("Schedule on_ready: schedule mismatch detected, refreshing schedule")
                    await Schedule.updateSchedule(guild)
            except Exception as e:
                log.exception(f"Schedule on_ready: failed to reconcile schedule: {e}")

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

                embed = discord.Embed(
                    title="Event auto deleted",
                    description=f"Your {event['type'].lower()} has ended: `{event['title']}`\n" \
                    f"It has been automatically removed from the schedule. {PEEPO_POP}\n\n" \
                    f"{event['type'].title()} start: {discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}\n" \
                    f"{event['type'].title()} end: {discord.utils.format_dt(UTC.localize(datetime.strptime(event['endTime'], TIME_FORMAT)), style='F')}",
                    color=discord.Color.orange()
                )
                try:
                    await author.send(embed=embed)
                except Exception:
                    log.warning(f"Schedule tenMinTask: Failed to DM author '{author.display_name}' about autodeleted event '{event['title']}'")

        for event in deletedEvents:
            events.remove(event)
        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)

        if deletedEvents and len(events) == 0:
            await Schedule.updateSchedule(guild)


    @staticmethod
    async def tasknoShowsPing(guild: discord.Guild, channelCommand: discord.VoiceChannel, channelDeployed: discord.VoiceChannel, channelEventDeployed: discord.VoiceChannel) -> None:
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
                membersInVC = channelCommand.members + channelDeployed.members + channelEventDeployed.members
                membersUnscheduled += ([member for member in membersAccepted if member not in membersInVC] + [member for member in membersInVC if member not in membersAccepted and member.id != event["authorId"]])

        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)
        if len(membersUnscheduled) == 0:
            return

        log.debug(f"Schedule tasknoShowsPing: Pinging unscheduled members: {', '.join([member.display_name for member in membersUnscheduled])}")
        await channelArmaDiscussion.send(" ".join(member.mention for member in membersUnscheduled) + f"\nIf you are in-game, please:\n* Get in {channelCommand.mention} or {channelDeployed.mention}\n* Hit accept ✅ on the <#{SCHEDULE}>\nIf you are not making it to this {event['type'].lower()}, please hit decline ❌ on the <#{SCHEDULE}>")


    @staticmethod
    async def tasknoShowsLogging(guild: discord.Guild, channelCommand: discord.VoiceChannel, channelDeployed: discord.VoiceChannel, channelEventDeployed: discord.VoiceChannel) -> None:
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
                membersInVC = channelCommand.members + channelDeployed.members + channelEventDeployed.members
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

        log.debug(f"Schedule tasknoShowsLogging: No-show members: {', '.join([member.display_name for member in noShowMembersListForLogging])}")

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
        view.add_item(ScheduleButton(interaction.message, style=discord.ButtonStyle.success, label="Add entry", custom_id=f"schedule_button_noshow_add_{member.id}"))

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

        view.add_item(ScheduleButton(interaction.message, style=discord.ButtonStyle.danger, label="Remove entry", custom_id=f"schedule_button_noshow_remove_{member.id}"))
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
        channelEventDeployed = guild.get_channel(EVENT_DEPLOYED)
        if not isinstance(channelEventDeployed, discord.VoiceChannel):
            log.exception("Schedule tenMinTask: channelEventDeployed not discord.VoiceChannel")
            return

        await Schedule.tasknoShowsPing(guild, channelCommand, channelDeployed, channelEventDeployed)

        # === Log no-show players. ===
        await Schedule.tasknoShowsLogging(guild, channelCommand, channelDeployed, channelEventDeployed)


# ===== </Tasks> =====


# ===== </Track-a-Candidate> =====
    @staticmethod
    async def trackCandidateAttendance(guild: discord.Guild, tracker: discord.Member, member: discord.Member) -> str:
        """Track one candidate's operation attendance."""
        OPERATIONS_REQUIRED_TO_ATTEND = 3

        log.info(f"{tracker.id} [{tracker.display_name}] is tracking candidate {member.id} [{member.display_name}]")

        try:
            with open(CANDIDATE_TRACKING_FILE) as f:
                candidateTracking = json.load(f)
        except Exception:
            candidateTracking = {}

        channelCommendations = guild.get_channel(COMMENDATIONS)
        if not isinstance(channelCommendations, discord.TextChannel):
            log.exception("Schedule trackCandidateAttendance: channelCommendations not discord.TextChannel")
            return f"Failed to track {member.display_name}: Commendations channel not found."
        roleUnitStaff = guild.get_role(UNIT_STAFF)
        if roleUnitStaff is None:
            log.exception("Schedule trackCandidateAttendance: roleUnitStaff is None")
            return f"Failed to track {member.display_name}: Unit Staff role not found."

        key = str(member.id)
        if candidateTracking.get(key) is None:
            candidateTracking[key] = 0

        candidateTracking[key] += 1
        if candidateTracking[key] < OPERATIONS_REQUIRED_TO_ATTEND:
            embed = discord.Embed(title="Track-a-Candidate", description=f"{member.mention} has attended {candidateTracking[key]} operations.", color=discord.Color.dark_blue())
            embed.set_footer(text=f"Tracked by {tracker.display_name}")
            await channelCommendations.send(embed=embed)
            result = "Tracking submitted!"
        else:
            embed = discord.Embed(
                title="Candidate Graduated!",
                description=f"{member.mention} has attended {OPERATIONS_REQUIRED_TO_ATTEND} operations and has now graduated from Candidate! Congratulations!\n",
                color=discord.Color.purple()
            )

            await channelCommendations.send(f"{roleUnitStaff.mention} This candidate need a levelup!", embed=embed)
            del candidateTracking[key]
            result = "Candidate has graduated!"

        with open(CANDIDATE_TRACKING_FILE, "w") as f:
              json.dump(candidateTracking, f, indent=4)

        return result

    @discord.app_commands.command(name="track-a-candidate")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_ZEUS)
    @discord.app_commands.describe(member="Member to track")
    async def trackACandidate(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """Track a candidate's amount of operations attended.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        member (discord.Member): Member to track.

        Returns:
        None.
        """
        if interaction.guild is None:
            log.exception("Schedule trackACandidate: guild is None")
            return
        if not isinstance(interaction.user, discord.Member):
            log.exception("Schedule trackACandidate: interaction.user not discord.Member")
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await Schedule.trackCandidateAttendance(interaction.guild, interaction.user, member)
        await interaction.followup.send(result, ephemeral=True)
        return
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] is tracking candidate {member.id} [{member.display_name}]")

        try:
            with open(CANDIDATE_TRACKING_FILE) as f:
                candidateTracking = json.load(f)
        except Exception:
            candidateTracking = {}

        channelCommendations = interaction.guild.get_channel(COMMENDATIONS)
        if not isinstance(channelCommendations, discord.TextChannel):
            log.exception("Schedule trackACandidate: channelCommendations not discord.TextChannel")
            return
        roleUnitStaff = interaction.guild.get_role(UNIT_STAFF)
        if roleUnitStaff is None:
            log.exception("Schedule trackACandidate: roleUnitStaff is None")
            return

        key = str(member.id)
        if candidateTracking.get(key) is None:
            candidateTracking[key] = 0

        candidateTracking[key] += 1
        if candidateTracking[key] < OPERATIONS_REQUIRED_TO_ATTEND:
            await interaction.followup.send("Tracking submitted!", ephemeral=True)
            embed = discord.Embed(title="Track-a-Candidate", description=f"{member.mention} has attended {candidateTracking[key]} operations.", color=discord.Color.dark_blue())
            embed.set_footer(text=f"Tracked by {interaction.user.display_name}")
            await channelCommendations.send(embed=embed)
        else:
            embed = discord.Embed(
                title="🎉 Candidate Graduated! 🎉",
                description=f"{member.mention} has attended {OPERATIONS_REQUIRED_TO_ATTEND} operations and has now graduated from Candidate! Congratulations!\n",
                color=discord.Color.purple()
            )

            await interaction.followup.send("Candidate has graduated!", ephemeral=True)
            await channelCommendations.send(f"{roleUnitStaff.mention} This candidate need a levelup!", embed=embed)
            del candidateTracking[key]


        with open(CANDIDATE_TRACKING_FILE, "w") as f:
              json.dump(candidateTracking, f, indent=4)

# ===== </Track-a-Candidate> =====


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
            log.exception("Schedule aar: channelCommand is None")
            return

        await interaction.response.send_message("AAR has started, Thanks for running a bop!", ephemeral=True)

        deployed_members = channelDeployed.members.copy()
        command_members = channelCommand.members.copy()
        for member in deployed_members:
            try:
                await member.move_to(channelCommand)
            except Exception:
                log.warning(f"Schedule aar: failed to move {member.id} [{member.display_name}]")

        membersPresent = list({member.id: member for member in command_members + deployed_members}.values())
        candidateMembers = [member for member in membersPresent if any(role.id == CANDIDATE for role in member.roles)]
        if candidateMembers:
            channelZeusZone = guild.get_channel(ZEUS_ZONE)
            if not isinstance(channelZeusZone, discord.TextChannel):
                log.exception("Schedule aar: channelZeusZone not discord.TextChannel")
                return

            candidateLimit = DISCORD_LIMITS["interactions"]["select_menu_option"]
            candidateMembersSelectable = candidateMembers[:candidateLimit]
            candidateMembersManual = candidateMembers[candidateLimit:]
            candidateMentions = "\n".join(candidate.mention for candidate in candidateMembersSelectable)
            plural = "s" if len(candidateMembers) > 1 else ""
            manualTrackingText = ""
            if candidateMembersManual:
                manualTrackingText = f"\n\n{len(candidateMembersManual)} additional candidate{'' if len(candidateMembersManual) == 1 else 's'} must be tracked manually due to Discord's dropdown limit."
            embed = discord.Embed(
                title="Candidate Attendance",
                description=f"The following candidate{plural} attended this operation:\n{candidateMentions}\n\nPlease confirm their attendance below.{manualTrackingText}",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"AAR started by {interaction.user.display_name}")
            view = AARCandidateAttendanceView(interaction.user.id, candidateMembersSelectable)
            await channelZeusZone.send(f"{interaction.user.mention}", embed=embed, view=view)


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
    def generateEventId(existingIds: Set[str] | None = None) -> str:
        """Generates a deterministic unique event id."""
        existingIds = existingIds or set()
        maxNumericId = 0
        for existingId in existingIds:
            if existingId.isdigit():
                maxNumericId = max(maxNumericId, int(existingId))

        nextId = maxNumericId + 1
        candidate = str(nextId)
        while candidate in existingIds:
            nextId += 1
            candidate = str(nextId)
        return candidate

    @staticmethod
    def ensureEventId(event: Dict, events: List[Dict] | None = None) -> str:
        """Ensures an event has a unique numeric id and returns it."""
        existingIds: Set[str] = set()
        if events is not None:
            for other in events:
                if other is event:
                    continue
                otherId = other.get("eventId")
                if isinstance(otherId, str) and otherId.isdigit():
                    existingIds.add(otherId)

        eventId = event.get("eventId")
        if not isinstance(eventId, str) or not eventId.isdigit() or eventId in existingIds:
            eventId = Schedule.generateEventId(existingIds)
            event["eventId"] = eventId
        return eventId

    @staticmethod
    def parsePersistentScheduleCustomId(customId: str) -> tuple[str, str] | None:
        """Parses persistent event action custom_id values."""
        match = re.match(r"^schedule_button_event_(?P<action>accept|accept_reserve|decline|tentative|reserve|edit|config)_(?P<event_id>\d+)$", customId)
        if not match:
            return None
        return match.group("event_id"), match.group("action")

    @staticmethod
    def getEventByEventId(events: List[Dict], eventId: str) -> Dict | None:
        """Fetches an event by persistent event id."""
        for event in events:
            if str(event.get("eventId")) == str(eventId):
                return event
        return None

    @staticmethod
    async def getEventMessageByEventId(guild: discord.Guild, eventId: str, events: List[Dict] | None = None) -> tuple[Dict | None, discord.Message | None]:
        """Fetches the current event record and current schedule message for an event id."""
        if events is None:
            with open(EVENTS_FILE) as f:
                events = json.load(f)

        event = Schedule.getEventByEventId(events, eventId)
        if event is None:
            return None, None

        eventMessageId = event.get("messageId")
        if not isinstance(eventMessageId, int):
            return event, None

        channelSchedule = guild.get_channel(SCHEDULE)
        if not isinstance(channelSchedule, discord.TextChannel):
            log.exception("Schedule getEventMessageByEventId: channelSchedule not discord.TextChannel")
            return event, None

        try:
            eventMsg = await channelSchedule.fetch_message(eventMessageId)
        except Exception:
            return event, None

        return event, eventMsg

    @staticmethod
    async def _sendPersistentEventMissing(interaction: discord.Interaction, eventId: str) -> None:
        """Replies with a user-facing message for missing/expired events."""
        embed = discord.Embed(
            title="Event unavailable",
            description=f"This event no longer exists or has expired. (`{eventId}`)",
            color=discord.Color.red()
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=15.0)

    @staticmethod
    async def handlePersistentEventAction(interaction: discord.Interaction, customId: str) -> None:
        """Routes persistent schedule event action buttons."""
        parsed = Schedule.parsePersistentScheduleCustomId(customId)
        if parsed is None:
            log.exception(f"Schedule handlePersistentEventAction: invalid custom_id '{customId}'")
            return
        eventId, action = parsed

        if not isinstance(interaction.user, discord.Member):
            log.exception("Schedule handlePersistentEventAction: interaction.user not discord.Member")
            return
        if interaction.guild is None:
            log.exception("Schedule handlePersistentEventAction: interaction.guild is None")
            return
        if interaction.message is None:
            log.exception("Schedule handlePersistentEventAction: interaction.message is None")
            return

        with open(EVENTS_FILE) as f:
            events = json.load(f)

        event = Schedule.getEventByEventId(events, eventId)
        if event is None:
            await Schedule._sendPersistentEventMissing(interaction, eventId)
            return

        match action:
            case "accept":
                await Schedule._handlePersistentRSVPAction(interaction, events, event, "accepted")
            case "decline":
                await Schedule._handlePersistentRSVPAction(interaction, events, event, "declined")
            case "tentative":
                await Schedule._handlePersistentRSVPAction(interaction, events, event, "tentative")
            case "reserve" | "accept_reserve":
                await Schedule._handlePersistentReserveAction(interaction, events, event)
            case "config":
                await Schedule._handlePersistentConfigAction(interaction, event)
            case "edit":
                await Schedule._handlePersistentEditAction(interaction, event)
            case _:
                log.exception(f"Schedule handlePersistentEventAction: unsupported action '{action}'")

    @staticmethod
    async def _handlePersistentRSVPAction(interaction: discord.Interaction, events: List[Dict], event: Dict, rsvpAction: Literal["accepted", "declined", "tentative"]) -> None:
        if await Schedule.blockVerifiedRoleRSVP(interaction, event):
            return

        if interaction.guild is None:
            log.exception("Schedule _handlePersistentRSVPAction: interaction.guild is None")
            return

        isAcceptAndReserve = event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"]

        # Promote from standby if leaving accepted and there are standby members
        if interaction.user.id in event["accepted"] and not isAcceptAndReserve and len(event["standby"]) > 0:
            standbyMemberId = event["standby"].pop(0)
            event["accepted"].append(standbyMemberId)

            standbyMember = interaction.guild.get_member(standbyMemberId)
            if standbyMember is None:
                log.warning(f"Schedule _handlePersistentRSVPAction: Failed to fetch promoted member '{standbyMemberId}'")
            else:
                embed = discord.Embed(
                    title=f"✅ Accepted to {event['type'].lower()}",
                    description=f"You have been promoted from standby to accepted in `{event['title']}`\nTime: {discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}\nDuration: {event['duration']}",
                    color=discord.Color.green()
                )
                try:
                    await standbyMember.send(embed=embed)
                except Exception:
                    log.warning(f"Schedule _handlePersistentRSVPAction: Failed to DM {standbyMemberId} [{standbyMember.display_name}] about acceptance")

        # Toggle RSVP
        rsvpOptions = ("accepted", "declined", "tentative", "standby")
        if interaction.user.id in event[rsvpAction]:
            event[rsvpAction].remove(interaction.user.id)
        elif rsvpAction == "accepted" and interaction.user.id in event["standby"]:
            event["standby"].remove(interaction.user.id)
        else:
            for option in rsvpOptions:
                if interaction.user.id in event[option]:
                    event[option].remove(interaction.user.id)

            if rsvpAction == "accepted" and isinstance(event["maxPlayers"], int) and len(event["accepted"]) >= event["maxPlayers"]:
                event["standby"].append(interaction.user.id)
            else:
                event[rsvpAction].append(interaction.user.id)

        hadReservedARole = False
        if event["reservableRoles"] is not None:
            for btnRoleName in event["reservableRoles"]:
                if event["reservableRoles"][btnRoleName] == interaction.user.id:
                    event["reservableRoles"][btnRoleName] = None
                    hadReservedARole = True

        # Notify standby members
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
                    log.warning(f"Schedule _handlePersistentRSVPAction: Failed to get member with id '{standbyMemberId}'")
                    continue
                try:
                    await standbyMember.send(embed=embed)
                except Exception:
                    log.warning(f"Schedule _handlePersistentRSVPAction: Failed to DM {standbyMember.id} [{standbyMember.display_name}] about vacant roles")

        # Candidate accepted notification
        if (
            rsvpAction == "accepted"
            and event.get("type", "").lower() == "operation"
            and interaction.user.id in event["accepted"]
            and isinstance(interaction.user, discord.Member)
            and any(role.id == CANDIDATE for role in interaction.user.roles)
        ):
            channelRecruitmentHr = interaction.guild.get_channel(RECRUITMENT_AND_HR)
            if not isinstance(channelRecruitmentHr, discord.TextChannel):
                log.exception("Schedule _handlePersistentRSVPAction: channelRecruitmentHr not discord.TextChannel")
            elif not await Schedule.hasCandidatePinged(interaction.user.id, event["title"], channelRecruitmentHr):
                embed = discord.Embed(title="Candidate Accept", description=f"{interaction.user.mention} accepted operation `{event['title']}`", color=discord.Color.blue())
                embed.set_footer(text=f"Candidate ID: {interaction.user.id}")
                await channelRecruitmentHr.send(embed=embed)

        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)

        await interaction.response.edit_message(embed=Schedule.getEventEmbed(event, interaction.guild), view=Schedule.getEventView(event))

    @staticmethod
    async def _handlePersistentReserveAction(interaction: discord.Interaction, events: List[Dict], event: Dict) -> None:
        # Reservable role blacklist check
        with open(ROLE_RESERVATION_BLACKLIST_FILE) as f:
            blacklist = json.load(f)
        if any(interaction.user.id == member["id"] for member in blacklist):
            await interaction.response.send_message(embed=discord.Embed(title="❌ Sorry, seems like you are not allowed to reserve any roles!", description="If you have any questions about this situation, please contact Unit Staff.", color=discord.Color.red()), ephemeral=True, delete_after=60.0)
            return

        if await Schedule.blockVerifiedRoleRSVP(interaction, event):
            return

        if interaction.guild is None:
            log.exception("Schedule _handlePersistentReserveAction: interaction.guild is None")
            return

        if interaction.message is None:
            log.exception("Schedule _handlePersistentReserveAction: interaction.message is None")
            return

        isAcceptAndReserve = event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"]
        playerCapReached = isinstance(event["maxPlayers"], int) and len(event["accepted"]) >= event["maxPlayers"]

        # Full event without reserve or standby option
        if not isAcceptAndReserve and playerCapReached and interaction.user.id not in event["accepted"]:
            await interaction.response.send_message(embed=discord.Embed(title="❌ Sorry, seems like there's no space left in the :b:op!", color=discord.Color.red()), ephemeral=True, delete_after=60.0)
            return

        # Accept and reserve flow with standby list
        if isAcceptAndReserve and interaction.user.id in event["standby"] and (all(event["reservableRoles"].values()) or playerCapReached):
            event["standby"].remove(interaction.user.id)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
            await interaction.response.edit_message(embed=Schedule.getEventEmbed(event, interaction.guild), view=Schedule.getEventView(event))
            return

        # Accept and move to standby list
        if isAcceptAndReserve and playerCapReached and interaction.user.id not in event["accepted"] and interaction.user.id not in event["standby"]:
            Schedule.clearUserRSVP(event, interaction.user.id)
            event["standby"].append(interaction.user.id)

            await interaction.response.send_message(embed=discord.Embed(title="✅ On standby list", description="The event player limit is reached!\nYou have been placed on the standby list. If an accepted member leaves, you will be notified about the vacant roles!", color=discord.Color.green()), ephemeral=True, delete_after=60.0)

            if interaction.channel is None or isinstance(interaction.channel, discord.ForumChannel) or isinstance(interaction.channel, discord.CategoryChannel):
                log.exception("Schedule _handlePersistentReserveAction: interaction.channel is invalid type")
                return
            msg = await interaction.channel.fetch_message(interaction.message.id)
            await msg.edit(embed=Schedule.getEventEmbed(event, interaction.guild), view=Schedule.getEventView(event))

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
            return

        # Show reservation options
        if not isinstance(interaction.user, discord.Member):
            log.exception("Schedule _handlePersistentReserveAction: interaction.user not discord.Member")
            return

        vacantRoles = [btnRoleName for btnRoleName, memberId in event["reservableRoles"].items() if (memberId is None or interaction.user.guild.get_member(memberId) is None) and 1 <= len(btnRoleName) <= 100]
        view = ScheduleView()
        options = []
        if len(vacantRoles) > 0:
            for role in vacantRoles:
                options.append(discord.SelectOption(label=role))
            view.add_item(ScheduleSelect(eventMsg=interaction.message, placeholder="Select a role.", minValues=1, maxValues=1, customId="schedule_select_reserve_role", userId=interaction.user.id, row=0, options=options))

        for roleName in event["reservableRoles"]:
            if event["reservableRoles"][roleName] == interaction.user.id:
                view.add_item(ScheduleButton(interaction.message, row=1, label="Unreserve Current Role", style=discord.ButtonStyle.danger, custom_id="schedule_button_reserve_role_unreserve"))
                break

        isStandbyButton = False
        if isAcceptAndReserve and any(event["reservableRoles"].values()) and interaction.user.id not in event["standby"]:
            isStandbyButton = True
            view.add_item(ScheduleButton(interaction.message, row=1, label="Standby", style=discord.ButtonStyle.success, custom_id="schedule_button_standby_toggle"))

        msgContent = interaction.user.mention
        if len(view.children) <= 0 + isStandbyButton:
            msgContent += " All roles are reserved!"
        await interaction.response.send_message(content=msgContent, view=view, ephemeral=True, delete_after=60.0)

    @staticmethod
    async def _handlePersistentConfigAction(interaction: discord.Interaction, event: Dict) -> None:
        if not isinstance(interaction.user, discord.Member):
            log.exception("Schedule _handlePersistentConfigAction: interaction.user not discord.Member")
            return

        if Schedule.isAllowedToEdit(interaction.user, event["authorId"]) is False:
            await interaction.response.send_message("Only the host, Unit Staff and Server Hampters can configure the event!", ephemeral=True, delete_after=60.0)
            return

        eventId = Schedule.ensureEventId(event)
        view = ScheduleView()
        view.add_item(ScheduleEventEditButton(eventId))
        view.add_item(ScheduleButton(interaction.message, row=0, label="Delete", style=discord.ButtonStyle.danger, custom_id=f"schedule_button_event_delete_{eventId}"))
        view.add_item(ScheduleButton(interaction.message, row=0, label="List RSVP", style=discord.ButtonStyle.secondary, custom_id=f"schedule_button_event_list_rsvp_{eventId}"))
        await interaction.response.send_message(content=f"{interaction.user.mention} What would you like to configure?", view=view, ephemeral=True, delete_after=30.0)

    @staticmethod
    async def _handlePersistentEditAction(interaction: discord.Interaction, event: Dict) -> None:
        if not isinstance(interaction.user, discord.Member):
            log.exception("Schedule _handlePersistentEditAction: interaction.user not discord.Member")
            return

        if Schedule.isAllowedToEdit(interaction.user, event["authorId"]) is False:
            await interaction.response.send_message("Restart the editing process.\nThe button points to an event you aren't allowed to edit.", ephemeral=True, delete_after=5.0)
            return

        eventMsg = interaction.message
        if eventMsg is None:
            log.exception("Schedule _handlePersistentEditAction: interaction.message is None")
            return

        if interaction.guild is None:
            log.exception("Schedule _handlePersistentEditAction: interaction.guild is None")
            return

        eventMessageId = event.get("messageId")
        if isinstance(eventMessageId, int) and eventMsg.id != eventMessageId:
            channelSchedule = interaction.guild.get_channel(SCHEDULE)
            if not isinstance(channelSchedule, discord.TextChannel):
                log.exception("Schedule _handlePersistentEditAction: channelSchedule not discord.TextChannel")
                return
            try:
                eventMsg = await channelSchedule.fetch_message(eventMessageId)
            except Exception:
                await Schedule._sendPersistentEventMissing(interaction, str(event.get("eventId", "UNKNOWN")))
                return

        await Schedule.editEvent(interaction, event, eventMsg)


    @staticmethod
    async def updateSchedule(guild: discord.Guild) -> None:
        """Updates the schedule channel with all messages."""
        channelSchedule = guild.get_channel(SCHEDULE)
        if not isinstance(channelSchedule, discord.TextChannel):
            log.exception("Schedule updateSchedule: channelSchedule not discord.TextChannel")
            return

        scheduleIntroMessage = f"__Welcome to the schedule channel!__\n🟩 Schedule operations: `/operation` (`/bop`)\n🟦 Workshops: `/workshop` (`/ws`)\n🟨 Generic events: `/event`\n\nThe datetime you see in here are based on __your local time zone__.\nChange timezone when scheduling events with `/changetimezone`.\n\nSuggestions/bugs contact: {', '.join([f'**{developerName.display_name}**' for name in DEVELOPERS if (developerName := channelSchedule.guild.get_member(name)) is not None])} -- <https://github.com/Sigma-Security-Group/FriendlySnek>"

        # Do not purge intro message if unchanged
        isFoundMessageIntro = False
        await channelSchedule.purge(limit=None,
                            check=lambda m: (
                                m.author.id in FRIENDLY_SNEKS and m.content != scheduleIntroMessage
                            )
        )
        # Search for intro message
        async for message in channelSchedule.history(limit=10, oldest_first=True):
            if message.content == scheduleIntroMessage:
                isFoundMessageIntro = True
                break

        # Send intro message if not found
        if not isFoundMessageIntro:
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
                Schedule.ensureEventId(event, events)
                msg = await channelSchedule.send(embed=Schedule.getEventEmbed(event, guild), view=Schedule.getEventView(event), files=Schedule.getEventFiles(event))
                event["messageId"] = msg.id
                newEvents.append(event)

            with open(EVENTS_FILE, "w") as f:
                json.dump(newEvents, f, indent=4)
        except Exception as e:
            log.exception(e)

    @staticmethod
    def getScheduleIntroMessage(channelSchedule: discord.TextChannel) -> str:
        """Gets the current schedule introduction message."""
        return f"__Welcome to the schedule channel!__\n🟩 Schedule operations: `/operation` (`/bop`)\n🟦 Workshops: `/workshop` (`/ws`)\n🟨 Generic events: `/event`\n\nThe datetime you see in here are based on __your local time zone__.\nChange timezone when scheduling events with `/changetimezone`.\n\nSuggestions/bugs contact: {', '.join([f'**{developerName.display_name}**' for name in DEVELOPERS if (developerName := channelSchedule.guild.get_member(name)) is not None])} -- <https://github.com/Sigma-Security-Group/FriendlySnek>"

    @staticmethod
    def getScheduleAttachmentNames(event: Dict) -> List[str]:
        """Gets normalized attachment filenames for an event."""
        attachmentNames = []
        for eventFile in event.get("files", []):
            try:
                filenameShort = eventFile.split("_", 2)[2]
            except Exception:
                filenameShort = eventFile

            if filenameShort not in attachmentNames:
                attachmentNames.append(filenameShort)
        return attachmentNames

    @staticmethod
    def getMessageComponentCustomIds(message: discord.Message) -> List[str]:
        """Gets custom_id values from a Discord message's components."""
        customIds: List[str] = []
        for row in message.components:
            for child in getattr(row, "children", []):
                customId = getattr(child, "custom_id", None)
                if customId is not None:
                    customIds.append(customId)
        return customIds

    @staticmethod
    def getViewCustomIds(view: discord.ui.View) -> List[str]:
        """Gets custom_id values from a Discord UI view."""
        return [item.custom_id for item in view.children if getattr(item, "custom_id", None) is not None]

    @staticmethod
    async def scheduleRequiresRefresh(guild: discord.Guild) -> bool:
        """Checks if the posted schedule channel differs from local events storage."""
        channelSchedule = guild.get_channel(SCHEDULE)
        if not isinstance(channelSchedule, discord.TextChannel):
            log.exception("Schedule scheduleRequiresRefresh: channelSchedule not discord.TextChannel")
            return False

        with open(EVENTS_FILE) as f:
            events = json.load(f)

        expectedEvents: List[Dict] = []
        for event in sorted(events, key=lambda e: datetime.strptime(e["time"], TIME_FORMAT), reverse=True):
            Schedule.applyMissingEventKeys(event, keySet="event")
            Schedule.ensureEventId(event, events)
            expectedEvents.append(event)

        botMessages = [message async for message in channelSchedule.history(limit=None, oldest_first=True) if message.author.id in FRIENDLY_SNEKS]
        scheduleIntroMessage = Schedule.getScheduleIntroMessage(channelSchedule)
        introMessages = [message for message in botMessages if message.content == scheduleIntroMessage]
        nonIntroMessages = [message for message in botMessages if message.content != scheduleIntroMessage]

        if len(introMessages) != 1:
            log.info(f"Schedule scheduleRequiresRefresh: expected 1 intro message, found {len(introMessages)}")
            return True

        if len(expectedEvents) == 0:
            emptyScheduleMessages = ["...\nNo bop?\n...\nSnek is sad", ":cry:"]
            currentMessages = [message.content for message in nonIntroMessages]
            if currentMessages != emptyScheduleMessages:
                log.info("Schedule scheduleRequiresRefresh: empty schedule placeholder messages differ")
                return True
            return False

        if len(nonIntroMessages) != len(expectedEvents):
            log.info(f"Schedule scheduleRequiresRefresh: expected {len(expectedEvents)} event messages, found {len(nonIntroMessages)}")
            return True

        for event, message in zip(expectedEvents, nonIntroMessages):
            if event.get("messageId") != message.id:
                log.info(f"Schedule scheduleRequiresRefresh: message id mismatch for eventId {event.get('eventId')}")
                return True

            expectedEmbed = Schedule.getEventEmbed(event, guild).to_dict()
            actualEmbed = message.embeds[0].to_dict() if len(message.embeds) > 0 else None
            if actualEmbed != expectedEmbed:
                log.info(f"Schedule scheduleRequiresRefresh: embed mismatch for eventId {event.get('eventId')}")
                return True

            expectedAttachments = Schedule.getScheduleAttachmentNames(event)
            actualAttachments = [attachment.filename for attachment in message.attachments]
            if actualAttachments != expectedAttachments:
                log.info(f"Schedule scheduleRequiresRefresh: attachment mismatch for eventId {event.get('eventId')}")
                return True

            expectedCustomIds = Schedule.getViewCustomIds(Schedule.getEventView(event))
            actualCustomIds = Schedule.getMessageComponentCustomIds(message)
            if actualCustomIds != expectedCustomIds:
                log.info(f"Schedule scheduleRequiresRefresh: component mismatch for eventId {event.get('eventId')}")
                return True

        return False

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
            event.setdefault("eventId", None)
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
                validKeys = {"title", "description", "externalURL", "reservableRoles", "maxPlayers", "map", "duration", "files", "templateName", "workshopInterest"}
                invalidKeys = set(event.keys()) - validKeys
                for key in invalidKeys:
                    del event[key]

    @staticmethod
    def isDefaultCreateTextField(key: str, value: Any) -> bool:
        """Checks if a create text field is blank or still using preview defaults."""
        if key not in ("title", "description"):
            return False
        if value is None:
            return True
        value = str(value).strip()
        return value == "" or value == SCHEDULE_EVENT_PREVIEW_EMBED[key]

    @staticmethod
    def getInvalidDefaultCreateTextFields(event: Dict) -> List[str]:
        return [
            label
            for label, key in (("Title", "title"), ("Description", "description"))
            if Schedule.isDefaultCreateTextField(key, event.get(key))
        ]

    @staticmethod
    def getEventEmbed(event: Dict, guild: discord.Guild) -> discord.Embed:
        """Generates an embed from the given event.

        Parameters:
        event (Dict): The event.

        Returns:
        discord.Embed: The generated embed.
        """
        embed = discord.Embed(title=event["title"], description=event["description"], color=EVENT_TYPE_COLORS[event.get("type", "Operation")])

        # Reservable Roles
        if event["reservableRoles"] is not None:
            embed.add_field(name="\u200B", value="\u200B", inline=False)
            resRolesTaken = len([1 for memberId in event["reservableRoles"].values() if memberId is not None])
            resRolesDescription = []
            for roleName, memberId in event["reservableRoles"].items():
                if memberId is None:
                    resRolesDescription.append(f"{roleName} - **VACANT**")
                    continue

                member = guild.get_member(memberId)
                if member is None:
                    # Remove invalid members
                    event["reservableRoles"][roleName] = None
                else:
                    resRolesDescription.append(f"{roleName} - *{member.display_name}*")

            embed.add_field(
                name=f"Reservable Roles ({resRolesTaken}/{len(event['reservableRoles'])}) 👤",
                value="\n".join(resRolesDescription), inline=False
            )

        # Duration and Time
        durationHours = int(event["duration"].split("h")[0].strip()) if "h" in event["duration"] else 0
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        embed.add_field(name="Time", value=f"{discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')} - {discord.utils.format_dt(UTC.localize(datetime.strptime(event['endTime'], TIME_FORMAT)), style='t' if durationHours < 24 else 'F')}", inline=(durationHours < 24))
        embed.add_field(name="Duration", value=event["duration"], inline=True)

        # Map
        if event["map"] is not None:
            embed.add_field(name="Map", value=event["map"], inline=False)

        # External URL
        if event["externalURL"] is not None:
            embed.add_field(name="\u200B", value="\u200B", inline=False)
            embed.add_field(name="External URL", value=event["externalURL"], inline=False)
        embed.add_field(name="\u200B", value="\u200B", inline=False)

        # RSVP Lists
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
            embed.add_field(name=f"Accepted ({len(accepted)}) ✅" if event["maxPlayers"] is None else f"Accepted ({len(accepted)}/{event['maxPlayers']}) ✅", value="\n".join(accepted) if len(accepted) > 0 else "-", inline=True)
            embed.add_field(name=f"Declined ({len(declined)}) ❌", value=("\n".join(declined)) if len(declined) > 0 else "-", inline=True)
            embed.add_field(name=f"Tentative ({len(tentative)}) ❓", value="\n".join(tentative) if len(tentative) > 0 else "-", inline=True)
            if len(standby) > 0:
                embed.add_field(name=f"Standby ({len(standby)}) :clock3:", value="\n".join(standby), inline=False)

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
        eventId = Schedule.ensureEventId(event)

        # Add attendance buttons if maxPlayers is not hidden
        if event["maxPlayers"] != "hidden":
            isAcceptAndReserve = event["reservableRoles"] and len(event["reservableRoles"]) == event["maxPlayers"]

            if isAcceptAndReserve:
                items.append(ScheduleAcceptAndReserveButton(eventId))
            else:
                items.append(ScheduleAcceptButton(eventId))

            items.extend([
                ScheduleDeclineButton(eventId),
                ScheduleTentativeButton(eventId)
            ])
            if event["reservableRoles"] is not None and not isAcceptAndReserve:
                items.append(ScheduleReserveButton(eventId))

        items.append(ScheduleEventConfigButton(eventId))
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
        eventFilesForRemoval = []

        for eventFile in event["files"]:
            try:
                filenameShort = eventFile.split("_", 2)[2]
                # Check if file already in discordFiles
                if any(f.filename == filenameShort for f in discordFiles):
                    # Remove duplicate entry from event["files"]
                    eventFilesForRemoval.append(eventFile)
                    continue
                with open(f"tmp/fileUpload/{eventFile}", "rb") as f:
                    discordFiles.append(discord.File(f, filename=filenameShort))
            except Exception as e:
                log.warning(f"Schedule getEventFiles: Failed to open file '{eventFile}': {e}")
                # Remove from the event files
                eventFilesForRemoval.append(eventFile)

        # Remove files that were not found or duplicates
        for eventFile in eventFilesForRemoval:
            if eventFile in event["files"]:
                event["files"].remove(eventFile)

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
    def isTemplateType(eventType: str | None) -> bool:
        return eventType in ("Workshop", "Event")

    @staticmethod
    def getTemplateFile(eventType: str) -> str:
        return f"data/{eventType.lower()}Templates.json"

    @staticmethod
    def loadTemplates(eventType: str) -> List[Dict]:
        with open(Schedule.getTemplateFile(eventType)) as f:
            templates: List[Dict] = json.load(f)
        return templates

    @staticmethod
    def saveTemplates(eventType: str, templates: List[Dict]) -> None:
        templates.sort(key=lambda template : template["templateName"])
        with open(Schedule.getTemplateFile(eventType), "w") as f:
            json.dump(templates, f, indent=4)

    @staticmethod
    def findTemplateIndex(templates: List[Dict], templateName: str) -> int | None:
        for idx, template in enumerate(templates):
            if template.get("templateName", None) == templateName:
                return idx
        return None

    @staticmethod
    def loadDeletedTemplates() -> List[Dict]:
        if not os.path.exists(TEMPLATES_DELETED_FILE):
            return []
        with open(TEMPLATES_DELETED_FILE) as f:
            deletedTemplates: List[Dict] = json.load(f)
        return deletedTemplates

    @staticmethod
    def saveDeletedTemplates(entries: List[Dict]) -> None:
        with open(TEMPLATES_DELETED_FILE, "w") as f:
            json.dump(entries, f, indent=4)

    @staticmethod
    def getSelectedTemplateName(view: discord.ui.View | None) -> str | None:
        selectedTemplateName = getattr(view, "selectedTemplateName", None)
        if not isinstance(selectedTemplateName, str) or selectedTemplateName == "None":
            return None
        return selectedTemplateName

    @staticmethod
    def setSelectedTemplateName(view: discord.ui.View | None, templateName: str | None) -> None:
        if view is not None:
            setattr(view, "selectedTemplateName", templateName)

    @staticmethod
    def buildPreviewFooterText(guild: discord.Guild, authorId: int, selectedTemplateName: str | None = None) -> str:
        author = guild.get_member(authorId)
        footer = f"Created by {'Unknown User' if author is None else author.display_name}"
        if selectedTemplateName:
            footer += f" | Template: {selectedTemplateName}"
        return footer

    @staticmethod
    def refreshTemplateButton(view: discord.ui.View | None, eventType: str | None) -> None:
        if view is None:
            return
        for child in view.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "schedule_button_create_templates":
                child.disabled = not Schedule.isTemplateType(eventType)
                child.style = discord.ButtonStyle.success if Schedule.getSelectedTemplateName(view) else discord.ButtonStyle.secondary
                child.emoji = None
                break

    @staticmethod
    def generateTemplateManagementView(eventMsg: discord.Message, userId: int, eventMsgView: discord.ui.View) -> discord.ui.View:
        view = ScheduleView(authorId=userId, previousMessageView=eventMsgView)
        selectedTemplateName = Schedule.getSelectedTemplateName(eventMsgView)
        eventType = Schedule.fromPreviewEmbedToDict(eventMsg.embeds[0]).get("type", None)
        isTemplateType = Schedule.isTemplateType(eventType)

        items = [
            ScheduleButton(eventMsg, row=0, label="Select template", style=discord.ButtonStyle.primary, custom_id="schedule_button_create_templates_select", disabled=not isTemplateType),
            ScheduleButton(eventMsg, row=0, label="Save as", style=discord.ButtonStyle.success, custom_id="schedule_button_create_templates_save_as", disabled=not isTemplateType),
            ScheduleButton(eventMsg, row=0, label="Update", style=discord.ButtonStyle.success, custom_id="schedule_button_create_templates_update", disabled=(not isTemplateType) or (selectedTemplateName is None)),
            ScheduleButton(eventMsg, row=1, label="Rename", style=discord.ButtonStyle.secondary, custom_id="schedule_button_create_templates_rename", disabled=(not isTemplateType) or (selectedTemplateName is None)),
            ScheduleButton(eventMsg, row=1, label="Delete", style=discord.ButtonStyle.danger, custom_id="schedule_button_create_templates_delete", disabled=(not isTemplateType) or (selectedTemplateName is None))
        ]
        for item in items:
            view.add_item(item)

        return view

    @staticmethod
    def fromDictToPreviewEmbed(previewDict: Dict, guild: discord.Guild, selectedTemplateName: str | None = None) -> discord.Embed:
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
        embed.set_footer(text=Schedule.buildPreviewFooterText(guild, previewDict["authorId"], selectedTemplateName))
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
    def fromDictToPreviewView(previewDict: Dict, selectedTemplate: str | None) -> discord.ui.View:
        """Generates preview view from event dict."""
        view = ScheduleView(authorId=previewDict["authorId"], selectedTemplateName=(None if selectedTemplate in (None, "None") else selectedTemplate))
        for label, data in SCHEDULE_EVENT_VIEW.items():
            style = discord.ButtonStyle.secondary
            previewDictKey = label.lower().replace("url", "URL").replace("linking", "workshopInterest").replace(" ", "")
            if label in ("Title", "Description") and Schedule.isDefaultCreateTextField(previewDictKey, previewDict.get(previewDictKey)):
                style = discord.ButtonStyle.danger
            elif label == "Type" or (previewDictKey in previewDict and previewDict[previewDictKey] is not None):
                style = discord.ButtonStyle.success
            elif isinstance(data["customStyle"], discord.ButtonStyle):
                style = data["customStyle"]
            elif data["required"]:
                style = discord.ButtonStyle.danger


            button = ScheduleButton(
                None,
                style=style,
                label=label,
                custom_id=f"schedule_button_create_{label.lower().replace(' ', '_')}",
                row=data["row"],
                disabled=data["startDisabled"]
            )

            # (Un)lock buttons depending on current event type
            if label == "Linking":
                button.disabled = (previewDict["type"] != "Workshop")  # Only workshop

            elif label == "Templates":
                button.disabled = not Schedule.isTemplateType(previewDict["type"])
                button.style = discord.ButtonStyle.success if Schedule.getSelectedTemplateName(view) else discord.ButtonStyle.secondary

            view.add_item(button)

        Schedule.refreshTemplateButton(view, previewDict["type"])
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
    def generateSelectView(options: List[discord.SelectOption], noneOption: bool, setOptionLabel: str | None, eventMsg: discord.Message, placeholder: str, customId: str, userId: int, eventMsgView: discord.ui.View | None = None, eventId: str | None = None):
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
        for i in range(ceil(len(options) / DISCORD_LIMITS["interactions"]["select_menu_option"])):
            view.add_item(ScheduleSelect(eventMsg=eventMsg, eventId=eventId, placeholder=placeholder, minValues=1, maxValues=1, customId=f"{customId}_REMOVE{i}", userId=userId, row=i, options=options[:DISCORD_LIMITS["interactions"]["select_menu_option"]], eventMsgView=eventMsgView))
            options = options[DISCORD_LIMITS["interactions"]["select_menu_option"]:]

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
        log.debug(f"{interaction.user.id} [{interaction.user.display_name}] Is editing the event '{event['title']}'")
        options = []
        for editOption in editOptions:
            options.append(discord.SelectOption(label=editOption))

        view = ScheduleView()
        view.add_item(ScheduleSelect(eventMsg=eventMsg, eventId=Schedule.ensureEventId(event), placeholder="Select what to edit.", minValues=1, maxValues=1, customId="schedule_select_edit_field", userId=interaction.user.id, row=0, options=options))

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
        log.debug(f"{interaction.user.id} [{interaction.user.display_name}] Is creating an {preselectedType.lower()}")

        previewDict = {
            "authorId": interaction.user.id,
            "type": preselectedType,
            "title": SCHEDULE_EVENT_PREVIEW_EMBED["title"],
            "description": SCHEDULE_EVENT_PREVIEW_EMBED["description"]
        }
        view = Schedule.fromDictToPreviewView(previewDict, None)
        Schedule.applyMissingEventKeys(previewDict, keySet="event")
        embed = Schedule.fromDictToPreviewEmbed(previewDict, interaction.guild)
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
        view.add_item(ScheduleButton(None, style=discord.ButtonStyle.success, label="Change Time Zone", custom_id="schedule_button_change_time_zone"))
        if setTimeZone:
            view.add_item(ScheduleButton(None, style=discord.ButtonStyle.danger, label="Remove preferences", custom_id="schedule_button_remove_time_zone"))

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=180.0)


# ===== </Change Time Zone> =====


# ===== <Views and Buttons> =====

class ScheduleView(discord.ui.View):
    """Handling all schedule views."""
    def __init__(self, *, authorId: int | None = None, previousMessageView = None, selectedTemplateName: str | None = None, **kwargs):
        super().__init__(timeout=None, **kwargs)
        self._ownerId = authorId
        self.previousMessageView = previousMessageView
        self.selectedTemplateName = selectedTemplateName

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self._ownerId is not None and interaction.user.id != self._ownerId:
            await interaction.response.send_message(f"{interaction.user.mention} Only the one who executed the command may interact with the buttons!", ephemeral=True, delete_after=10.0)
            return False
        return True


class AARCandidateAttendanceView(discord.ui.View):
    """Tracks candidate attendance from AAR prompt controls."""
    def __init__(self, authorId: int, candidates: List[discord.Member]):
        super().__init__(timeout=None)
        self.authorId = authorId
        self.candidateIds = [candidate.id for candidate in candidates]
        self.selectedCandidateIds: List[int] = []
        self.submitted = False

        # If only 1 candidate, skip select menu and just have 2 buttons for participated/absent
        if len(candidates) == 1:
            candidateId = candidates[0].id
            self.add_item(AARCandidateAttendanceButton(
                candidateId=candidateId,
                authorId=authorId,
                participated=True,
                label="Participated",
                style=discord.ButtonStyle.success,
                custom_id=f"schedule_button_aar_candidate_participated_{candidateId}_{authorId}"
            ))
            self.add_item(AARCandidateAttendanceButton(
                candidateId=candidateId,
                authorId=authorId,
                participated=False,
                label="Absent",
                style=discord.ButtonStyle.danger,
                custom_id=f"schedule_button_aar_candidate_absent_{candidateId}_{authorId}"
            ))
            return

        # Multiple candidates, use select menu
        self.add_item(AARCandidateAttendanceSelect(
            authorId=authorId,
            candidates=candidates,
            custom_id=f"schedule_select_aar_candidate_attendance_{authorId}"
        ))
        self.add_item(AARCandidateAttendanceSubmitButton(
            authorId=authorId,
            custom_id=f"schedule_button_aar_candidate_submit_{authorId}"
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            log.exception("AARCandidateAttendanceView interaction_check: interaction.user not discord.Member")
            return False

        if interaction.user.id == self.authorId:
            return True

        if any(role.id in (UNIT_STAFF, SNEK_LORD) for role in interaction.user.roles):
            return True

        await interaction.response.send_message("Only the AAR runner, Unit Staff, or Snek Lord can confirm candidate attendance.", ephemeral=True, delete_after=10.0)
        return False

    def _membersFromIds(self, guild: discord.Guild, candidateIds: List[int]) -> Tuple[List[discord.Member], List[int]]:
        members = []
        missingIds = []
        for candidateId in candidateIds:
            member = guild.get_member(candidateId)
            if member is None:
                missingIds.append(candidateId)
                continue
            members.append(member)
        return members, missingIds

    def _resultEmbed(self, title: str, trackedMembers: List[discord.Member], absentMembers: List[discord.Member], skippedIds: List[int], tracker: discord.Member) -> discord.Embed:
        descriptionParts = []
        if trackedMembers:
            descriptionParts.append("Tracked:\n" + "\n".join(member.mention for member in trackedMembers))
        if absentMembers:
            descriptionParts.append("Not tracked:\n" + "\n".join(member.mention for member in absentMembers))
        if skippedIds:
            descriptionParts.append("Skipped:\n" + "\n".join(str(candidateId) for candidateId in skippedIds))
        if not descriptionParts:
            descriptionParts.append("No candidate attendance was tracked.")

        embed = discord.Embed(title=title, description="\n\n".join(descriptionParts), color=discord.Color.green())
        embed.set_footer(text=f"Confirmed by {tracker.display_name}")
        return embed

    async def submitAttendance(self, interaction: discord.Interaction, selectedCandidateIds: List[int]) -> None:
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("AARCandidateAttendanceView submitAttendance: interaction.guild not discord.Guild")
            return
        if not isinstance(interaction.user, discord.Member):
            log.exception("AARCandidateAttendanceView submitAttendance: interaction.user not discord.Member")
            return
        if interaction.message is None:
            log.exception("AARCandidateAttendanceView submitAttendance: interaction.message is None")
            return

        if self.submitted:
            await interaction.response.send_message("Candidate attendance has already been confirmed from this message.", ephemeral=True, delete_after=10.0)
            return
        self.submitted = True
        await interaction.response.defer(ephemeral=True, thinking=True)

        selectedCandidateIds = [candidateId for candidateId in selectedCandidateIds if candidateId in self.candidateIds]
        trackedMembers, skippedIds = self._membersFromIds(interaction.guild, selectedCandidateIds)
        absentCandidateIds = [candidateId for candidateId in self.candidateIds if candidateId not in selectedCandidateIds]
        absentMembers, missingAbsentIds = self._membersFromIds(interaction.guild, absentCandidateIds)
        skippedIds.extend(missingAbsentIds)

        results = []
        for member in trackedMembers:
            results.append(f"{member.display_name}: {await Schedule.trackCandidateAttendance(interaction.guild, interaction.user, member)}")

        embed = self._resultEmbed("Candidate Attendance Confirmed", trackedMembers, absentMembers, skippedIds, interaction.user)
        await interaction.message.edit(embed=embed, view=None)

        if skippedIds:
            log.warning(f"AARCandidateAttendanceView submitAttendance: skipped candidate ids {skippedIds}")
        if not results:
            results.append("No candidate attendance was tracked.")
        if skippedIds:
            results.append(f"Skipped missing candidate ids: {', '.join(str(candidateId) for candidateId in skippedIds)}")
        await interaction.followup.send("\n".join(results), ephemeral=True)


class AARCandidateAttendanceSelect(discord.ui.Select):
    def __init__(self, authorId: int, candidates: List[discord.Member], *args, **kwargs):
        options = [
            discord.SelectOption(
                label=candidate.display_name[:DISCORD_LIMITS["interactions"]["select_option_description"]],
                value=str(candidate.id),
                description=str(candidate)[:DISCORD_LIMITS["interactions"]["select_option_description"]]
            )
            for candidate in candidates
        ]
        super().__init__(
            *args,
            placeholder="Select candidates who participated.",
            min_values=1,
            max_values=len(options),
            row=0,
            options=options,
            **kwargs
        )
        self.authorId = authorId

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(self.view, AARCandidateAttendanceView):
            log.exception("AARCandidateAttendanceSelect callback: self.view not AARCandidateAttendanceView")
            return

        self.view.selectedCandidateIds = [int(value) for value in self.values]
        await interaction.response.send_message(f"Selected {len(self.values)} candidate(s). Press Submit to track attendance.", ephemeral=True, delete_after=10.0)


class AARCandidateAttendanceSubmitButton(discord.ui.Button):
    def __init__(self, authorId: int, *args, **kwargs):
        super().__init__(*args, label="Submit", style=discord.ButtonStyle.success, row=1, **kwargs)
        self.authorId = authorId

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(self.view, AARCandidateAttendanceView):
            log.exception("AARCandidateAttendanceSubmitButton callback: self.view not AARCandidateAttendanceView")
            return

        await self.view.submitAttendance(interaction, self.view.selectedCandidateIds)


class AARCandidateAttendanceButton(discord.ui.Button):
    def __init__(self, candidateId: int, authorId: int, participated: bool, *args, **kwargs):
        super().__init__(*args, row=0, **kwargs)
        self.candidateId = candidateId
        self.authorId = authorId
        self.participated = participated

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(self.view, AARCandidateAttendanceView):
            log.exception("AARCandidateAttendanceButton callback: self.view not AARCandidateAttendanceView")
            return

        await self.view.submitAttendance(interaction, [self.candidateId] if self.participated else [])


class BaseScheduleEventDynamicButton(discord.ui.DynamicItem[discord.ui.Button], template=r"^$"):
    """Base class for persistent schedule event buttons."""
    ACTION = ""
    LABEL = ""
    STYLE = discord.ButtonStyle.secondary
    EMOJI: str | None = None

    def __init__(self, eventId: str):
        self.eventId = eventId
        kwargs: Dict[str, Any] = {
            "row": 0,
            "style": self.STYLE,
            "custom_id": f"schedule_button_event_{self.ACTION}_{eventId}"
        }
        if self.LABEL:
            kwargs["label"] = self.LABEL
        if self.EMOJI:
            kwargs["emoji"] = self.EMOJI
        super().__init__(discord.ui.Button(**kwargs))

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        return cls(match.group("event_id"))

    async def callback(self, interaction: discord.Interaction):
        customId = interaction.data.get("custom_id") if isinstance(interaction.data, dict) else None
        if not isinstance(customId, str):
            log.exception("BaseScheduleEventDynamicButton callback: custom_id missing")
            return
        await Schedule.handlePersistentEventAction(interaction, customId)


class ScheduleAcceptButton(BaseScheduleEventDynamicButton, template=r"schedule_button_event_accept_(?P<event_id>\d+)"):
    ACTION = "accept"
    LABEL = "Accept"
    STYLE = discord.ButtonStyle.success


class ScheduleAcceptAndReserveButton(BaseScheduleEventDynamicButton, template=r"schedule_button_event_accept_reserve_(?P<event_id>\d+)"):
    ACTION = "accept_reserve"
    LABEL = "Accept & Reserve"
    STYLE = discord.ButtonStyle.success


class ScheduleDeclineButton(BaseScheduleEventDynamicButton, template=r"schedule_button_event_decline_(?P<event_id>\d+)"):
    ACTION = "decline"
    LABEL = "Decline"
    STYLE = discord.ButtonStyle.danger


class ScheduleTentativeButton(BaseScheduleEventDynamicButton, template=r"schedule_button_event_tentative_(?P<event_id>\d+)"):
    ACTION = "tentative"
    LABEL = "Tentative"
    STYLE = discord.ButtonStyle.secondary


class ScheduleReserveButton(BaseScheduleEventDynamicButton, template=r"schedule_button_event_reserve_(?P<event_id>\d+)"):
    ACTION = "reserve"
    LABEL = "Reserve"
    STYLE = discord.ButtonStyle.secondary


class ScheduleEventEditButton(BaseScheduleEventDynamicButton, template=r"schedule_button_event_edit_(?P<event_id>\d+)"):
    ACTION = "edit"
    LABEL = "Edit"
    STYLE = discord.ButtonStyle.primary


class ScheduleEventConfigButton(BaseScheduleEventDynamicButton, template=r"schedule_button_event_config_(?P<event_id>\d+)"):
    ACTION = "config"
    STYLE = discord.ButtonStyle.secondary
    EMOJI = "⚙️"


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

        customId = interaction.data["custom_id"]

        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)

            scheduleNeedsUpdate = True
            fetchMsg = False

            if customId == "schedule_button_standby_toggle":
                event = [event for event in events if event["messageId"] == self.message.id][0]

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

            elif customId == "schedule_button_reserve_role_unreserve":
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

            elif re.fullmatch(r"schedule_button_event_delete_\d+", customId):
                eventId = customId[len("schedule_button_event_delete_"):]

                event, _ = await Schedule.getEventMessageByEventId(interaction.guild, eventId, events)
                if event is None:
                    await Schedule._sendPersistentEventMissing(interaction, eventId)
                    return

                if Schedule.isAllowedToEdit(interaction.user, event["authorId"]) is False:
                    await interaction.response.send_message("Only the host, Unit Staff and Server Hampters can configure the event!", ephemeral=True, delete_after=60.0)
                    return

                scheduleNeedsUpdate = False

                embed = discord.Embed(title=f"Are you sure you want to delete this {event['type'].lower()}: `{event['title']}`?", color=discord.Color.orange())
                view = ScheduleView()
                items = [
                    ScheduleButton(self.message, row=0, label="Delete", style=discord.ButtonStyle.success, custom_id=f"schedule_button_event_delete_confirm_{eventId}"),
                    ScheduleButton(self.message, row=0, label="Cancel", style=discord.ButtonStyle.danger, custom_id=f"schedule_button_event_delete_cancel_{eventId}"),
                ]
                for item in items:
                    view.add_item(item)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=60.0)

            elif customId.startswith("schedule_button_event_delete_confirm_"):
                scheduleNeedsUpdate = False

                if self.view is None:
                    log.exception("ScheduleButton callback delete_event_confirm: self.view is None")
                    return

                eventId = customId[len("schedule_button_event_delete_confirm_"):]

                # Disable buttons
                for button in self.view.children:
                    button.disabled = True
                await interaction.response.edit_message(view=self.view)

                # Delete event
                event, eventMsg = await Schedule.getEventMessageByEventId(interaction.guild, eventId, events)
                if event is None:
                    await Schedule._sendPersistentEventMissing(interaction, eventId)
                    return

                if Schedule.isAllowedToEdit(interaction.user, event["authorId"]) is False:
                    await interaction.followup.send("Only the host, Unit Staff and Server Hampters can configure the event!", ephemeral=True)
                    return

                if eventMsg is None:
                    await Schedule._sendPersistentEventMissing(interaction, eventId)
                    return

                await eventMsg.delete()
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
                                except Exception:
                                    log.warning(f"{member.id} [{member.display_name}]")
                except Exception:
                    log.exception(f"{interaction.user.id} [{interaction.user.display_name}]")
                events.remove(event)

            elif customId.startswith("schedule_button_event_delete_cancel_"):
                if self.view is None:
                    log.exception("ScheduleButton callback delete_event_cancel: self.view is None")
                    return

                for item in self.view.children:
                    item.disabled = True
                await interaction.response.edit_message(view=self.view)
                await interaction.followup.send(embed=discord.Embed(title=f"❌ Event deletion canceled!", color=discord.Color.red()), ephemeral=True)
                return

            elif customId.startswith("schedule_button_event_list_rsvp_"):
                eventId = customId[len("schedule_button_event_list_rsvp_"):]

                event = Schedule.getEventByEventId(events, eventId)
                if event is None:
                    await Schedule._sendPersistentEventMissing(interaction, eventId)
                    return

                if Schedule.isAllowedToEdit(interaction.user, event["authorId"]) is False:
                    await interaction.response.send_message("Only the host, Unit Staff and Server Hampters can configure the event!", ephemeral=True, delete_after=60.0)
                    return

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

                embed = discord.Embed(title=f"RSVP Listing", description=description.strip()[:DISCORD_LIMITS["message_embed"]["embed_description"]], color=discord.Color.gold())
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=60.0)
                return

            elif customId is not None and customId.startswith("schedule_button_create_"):
                if self.view is None:
                    log.exception("ScheduleButton callback event_schedule_: self.view is None")
                    return

                buttonLabel = customId[len("schedule_button_create_"):]
                previewView = self.view.previousMessageView if self.view.previousMessageView is not None else self.view
                if previewView is None:
                    log.exception("ScheduleButton callback event_schedule_: previewView is None")
                    return
                eventMsg = self.message if self.message is not None else interaction.message

                generateModal = lambda style, placeholder, default, required, minLength, maxLength: ScheduleModal(
                        title="Create event", customId=f"schedule_modal_create_{buttonLabel}", userId=interaction.user.id, eventMsg=eventMsg, view=previewView
                    ).add_item(
                        discord.ui.TextInput(
                            label=buttonLabel.replace("_", " ").capitalize(),
                            style=style,
                            placeholder=placeholder[:DISCORD_LIMITS["interactions"]["text_input_placeholder"]] if placeholder else placeholder,
                            default=default[:DISCORD_LIMITS["interactions"]["text_input_value"]] if default else default,
                            required=required,
                            min_length=max(minLength, 0) if minLength else minLength,
                            max_length=min(maxLength, DISCORD_LIMITS["interactions"]["text_input_value"]) if maxLength else maxLength
                        )
                    )

                previewEmbedDict = Schedule.fromPreviewEmbedToDict(eventMsg.embeds[0])

                requiredInfoRemaining = [
                    child.label for child in previewView.children
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
                            eventMsg,
                            "Select event type.",
                            "schedule_select_create_type",
                            interaction.user.id,
                            previewView
                        ),
                            ephemeral=True,
                            delete_after=60.0
                        )

                    case "title":
                        placeholder = "Operation Honda Civic" if previewEmbedDict["title"] == SCHEDULE_EVENT_PREVIEW_EMBED["title"] else previewEmbedDict["title"]
                        default = None if previewEmbedDict["title"] == SCHEDULE_EVENT_PREVIEW_EMBED["title"] else previewEmbedDict["title"]
                        await interaction.response.send_modal(generateModal(discord.TextStyle.short, placeholder, default, True, 1, DISCORD_LIMITS["message_embed"]["embed_title"]))

                    case "description":
                        placeholder = "Our mission is..." if previewEmbedDict["description"] == SCHEDULE_EVENT_PREVIEW_EMBED["description"] else previewEmbedDict["description"]
                        default = None if previewEmbedDict["description"] == SCHEDULE_EVENT_PREVIEW_EMBED["description"] else previewEmbedDict["description"]
                        await interaction.response.send_modal(generateModal(discord.TextStyle.long, placeholder, default, True, 1, DISCORD_LIMITS["interactions"]["text_input_value"]))

                    case "duration":
                        placeholder = "2h30m" if previewEmbedDict["duration"] is None else previewEmbedDict["duration"]
                        default = "" if previewEmbedDict["duration"] is None else previewEmbedDict["duration"]
                        await interaction.response.send_modal(generateModal(discord.TextStyle.short, placeholder, default, True, 1, 16))

                    case "time":
                        # Set user time zone
                        with open(MEMBER_TIME_ZONES_FILE) as f:
                            memberTimeZones = json.load(f)
                        if str(interaction.user.id) not in memberTimeZones:
                            await interaction.response.send_message(embed=discord.Embed(title="❌ Apply timezone", description="You must provide a time zone. Enter one in the time field, or use `/changetimezone` to store your time zone persistently.", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
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
                        placeholder = "[OPORD](https://www.gnu.org)" if previewEmbedDict["externalURL"] is None else previewEmbedDict["externalURL"]
                        default = "" if previewEmbedDict["externalURL"] is None else previewEmbedDict["externalURL"]
                        await interaction.response.send_modal(generateModal(discord.TextStyle.short, placeholder, default, False, None, DISCORD_LIMITS["message_embed"]["embed_field_value"]))

                    case "reservable_roles":
                        placeholder = "Co-Zeus\nActual\nJTAC\nF-35A Pilot"
                        default = "Co-Zeus\nActual\n2IC\nCMD Medic\nH1 Rifleman 1\nH1 Rifleman 2\nH1 Rifleman 3\nH2 TL\nH2 2IC\nH2 Medic\nH2 Rifleman 1\nH2 Rifleman 2\nH2 Rifleman 3"
                        if previewEmbedDict["reservableRoles"] is not None:
                            resRolesOriginal = "\n".join(previewEmbedDict["reservableRoles"])
                            placeholder = resRolesOriginal
                            default = resRolesOriginal[:512]  # Program limit, avoid overriding embed field value limit

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
                            eventMsg,
                            "Select a map.",
                            "schedule_select_create_map",
                            interaction.user.id,
                            previewView
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
                            eventMsg,
                            "Link event to a workshop.",
                            "schedule_select_create_linking",
                            interaction.user.id,
                            previewView
                        ),
                            ephemeral=True,
                            delete_after=60.0
                        )


                    # FILES
                    case "files":
                        view = ScheduleView(authorId=interaction.user.id, previousMessageView=previewView)
                        items = [
                            ScheduleButton(eventMsg, row=0, label="Add", style=discord.ButtonStyle.success, custom_id="schedule_button_create_files_add", disabled=(len(previewEmbedDict["files"]) == 10)),
                            ScheduleButton(eventMsg, row=0, label="Remove", style=discord.ButtonStyle.danger, custom_id="schedule_button_create_files_remove", disabled=(len(previewEmbedDict["files"]) == 0)),
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
                            view = Schedule.generateSelectView(options, False, None, messageNew, "Select a file.", "schedule_select_create_files_add", interaction.user.id, self.view.previousMessageView)

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
                            view = Schedule.generateSelectView(options, False, None, messageNew, "Select a file.", "schedule_select_create_files_remove", interaction.user.id, self.view.previousMessageView)

                        await interaction.response.edit_message(embed=embed, view=view)


                    # TEMPLATES
                    case "templates":
                        embed = discord.Embed(
                            title="Templates",
                            description=f"Selected template: `{Schedule.getSelectedTemplateName(previewView) or 'None'}`",
                            color=discord.Color.gold()
                        )
                        await interaction.response.send_message(
                            interaction.user.mention,
                            embed=embed,
                            view=Schedule.generateTemplateManagementView(eventMsg, interaction.user.id, previewView),
                            ephemeral=True,
                            delete_after=15.0
                        )

                    case "templates_select":
                        templates = Schedule.loadTemplates(previewEmbedDict["type"]) if Schedule.isTemplateType(previewEmbedDict["type"]) else []
                        options = [discord.SelectOption(label=template["templateName"], description=template["description"][:DISCORD_LIMITS["interactions"]["select_option_description"]]) for template in sorted(templates, key=lambda template : template["templateName"])]
                        await interaction.response.send_message(interaction.user.mention, view=Schedule.generateSelectView(
                            options,
                            True,
                            Schedule.getSelectedTemplateName(previewView),
                            eventMsg,
                            "Select a template.",
                            "schedule_select_create_select_template",
                            interaction.user.id,
                            previewView
                        ),
                            ephemeral=True,
                            delete_after=30.0
                        )

                    case "templates_save_as":
                        if (len(requiredInfoRemaining) >= 2) or (len(requiredInfoRemaining) == 1 and ("Time" not in requiredInfoRemaining)):
                            await interaction.response.send_message(f"{interaction.user.mention} Before saving the event as a template, you need to fill out the mandatory (red buttons) information!", ephemeral=True, delete_after=10.0)
                            return

                        await interaction.response.send_modal(generateModal(
                            style=discord.TextStyle.short,
                            placeholder="Fixed Wing Workshop + Cert",
                            default=None,
                            required=True,
                            minLength=1,
                            maxLength=64  # Arbitrary limit
                        ))

                    case "templates_update":
                        if (len(requiredInfoRemaining) >= 2) or (len(requiredInfoRemaining) == 1 and ("Time" not in requiredInfoRemaining)):
                            await interaction.response.send_message(f"{interaction.user.mention} Before updating the template, you need to fill out the mandatory (red buttons) information!", ephemeral=True, delete_after=10.0)
                            return

                        templateName = Schedule.getSelectedTemplateName(previewView)
                        if templateName is None:
                            await interaction.response.send_message(embed=discord.Embed(title="❌ No template selected", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                            return

                        eventType = previewEmbedDict["type"]
                        Schedule.applyMissingEventKeys(previewEmbedDict, keySet="template", removeKeys=True)
                        templates = Schedule.loadTemplates(eventType)
                        templateIndex = Schedule.findTemplateIndex(templates, templateName)
                        if templateIndex is None:
                            await interaction.response.send_message(embed=discord.Embed(title="❌ Template not found", description=f"`{templateName}` no longer exists.", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                            return

                        previewEmbedDict["templateName"] = templateName
                        if previewEmbedDict in templates:
                            embed = discord.Embed(title="❌ No diff", description="The new template data does not differ from the old template.\nTemplate not updated.", color=discord.Color.red())
                            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)
                            return

                        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Updated template '{templateName}'")
                        templates[templateIndex] = previewEmbedDict
                        Schedule.saveTemplates(eventType, templates)

                        # Reply
                        embed = discord.Embed(title="✅ Updated", description=f"Updated template: `{templateName}`", color=discord.Color.green())
                        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)

                    case "templates_rename":
                        templateName = Schedule.getSelectedTemplateName(previewView)
                        if templateName is None:
                            await interaction.response.send_message(embed=discord.Embed(title="❌ No template selected", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                            return
                        await interaction.response.send_modal(generateModal(
                            style=discord.TextStyle.short,
                            placeholder=templateName,
                            default=templateName,
                            required=True,
                            minLength=1,
                            maxLength=64  # Arbitrary limit
                        ))

                    case "templates_delete":
                        templateName = Schedule.getSelectedTemplateName(previewView)
                        if templateName is None:
                            await interaction.response.send_message(embed=discord.Embed(title="❌ No template selected", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                            return
                        embed = discord.Embed(title="Delete template?", description=f"Are you sure you want to delete `{templateName}`?", color=discord.Color.orange())
                        view = ScheduleView(authorId=interaction.user.id, previousMessageView=previewView)
                        items = [
                            ScheduleButton(eventMsg, row=0, label="Delete", style=discord.ButtonStyle.danger, custom_id="schedule_button_create_templates_delete_confirm"),
                            ScheduleButton(eventMsg, row=0, label="Cancel", style=discord.ButtonStyle.secondary, custom_id="schedule_button_create_templates_delete_cancel"),
                        ]
                        for item in items:
                            view.add_item(item)
                        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=30.0)

                    case "templates_delete_confirm":
                        templateName = Schedule.getSelectedTemplateName(previewView)
                        if templateName is None:
                            await interaction.response.send_message(embed=discord.Embed(title="❌ No template selected", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                            return
                        templates = Schedule.loadTemplates(previewEmbedDict["type"])
                        templateIndex = Schedule.findTemplateIndex(templates, templateName)
                        if templateIndex is None:
                            await interaction.response.send_message(embed=discord.Embed(title="❌ Template not found", description=f"`{templateName}` no longer exists.", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                            return
                        templateDeleted = deepcopy(templates[templateIndex])
                        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Deleted template '{templateName}'")
                        templates.pop(templateIndex)
                        Schedule.saveTemplates(previewEmbedDict["type"], templates)
                        deletedTemplates = Schedule.loadDeletedTemplates()
                        deletedTemplates.append({
                            "templateName": templateName,
                            "type": previewEmbedDict["type"],
                            "title": templateDeleted.get("title", None),
                            "description": templateDeleted.get("description", None),
                            "reservableRoles": templateDeleted.get("reservableRoles", None),
                            "duration": templateDeleted.get("duration", None),
                            "map": templateDeleted.get("map", None),
                            "externalURL": templateDeleted.get("externalURL", None),
                            "maxPlayers": templateDeleted.get("maxPlayers", None),
                            "workshopInterest": templateDeleted.get("workshopInterest", None),
                            "deletedAt": int(datetime.now(timezone.utc).timestamp()),
                            "deletedBy": interaction.user.id
                        })
                        Schedule.saveDeletedTemplates(deletedTemplates)
                        Schedule.setSelectedTemplateName(previewView, None)
                        Schedule.refreshTemplateButton(previewView, previewEmbedDict["type"])
                        await interaction.response.edit_message(view=None)
                        await eventMsg.edit(embed=Schedule.fromDictToPreviewEmbed(previewEmbedDict, interaction.guild, None), view=previewView)
                        await interaction.followup.send(embed=discord.Embed(title="✅ Deleted", description=f"Deleted template: `{templateName}`", color=discord.Color.green()), ephemeral=True)

                    case "templates_delete_cancel":
                        await interaction.response.edit_message(view=None)
                        await interaction.followup.send(embed=discord.Embed(title="❌ Deletion canceled", color=discord.Color.red()), ephemeral=True)

                    # EVENT FINISHING
                    case "submit":
                        # Check if all mandatory fields are filled
                        invalidDefaultFields = Schedule.getInvalidDefaultCreateTextFields(previewEmbedDict)
                        if invalidDefaultFields:
                            for child in previewView.children:
                                if isinstance(child, discord.ui.Button) and child.label in invalidDefaultFields:
                                    child.style = discord.ButtonStyle.danger
                            await eventMsg.edit(embed=Schedule.fromDictToPreviewEmbed(previewEmbedDict, interaction.guild, Schedule.getSelectedTemplateName(previewView)), view=previewView)
                            await interaction.response.send_message(f"{interaction.user.mention} Before creating the event, you need to replace the default title and description.", ephemeral=True, delete_after=10.0)
                            return

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
                        previewEmbedDict["eventId"] = Schedule.ensureEventId(previewEmbedDict, events)
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
                            ScheduleButton(interaction.message, row=0, label="Cancel", style=discord.ButtonStyle.danger, custom_id="schedule_button_create_cancel_confirm"),
                            ScheduleButton(interaction.message, row=0, label="No, I changed my mind", style=discord.ButtonStyle.secondary, custom_id="schedule_button_create_cancel_decline"),
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
                        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Cancelled '{previewEmbedDict['type']}' creation")

                    case "cancel_decline":
                        if self.message is None:
                            log.exception("ScheduleButton callback cancel_decline: self.message is None")
                            return
                        for child in self.view.children:
                            if isinstance(child, discord.ui.Button):
                                child.disabled = True
                        await interaction.response.edit_message(view=self.view)
                        await interaction.followup.send(content="Alright, I won't cancel the scheduling.", ephemeral=True)

                return

            elif customId.startswith("schedule_button_event_edit_files_add_"):
                eventId = customId[len("schedule_button_event_edit_files_add_"):]
                _, messageNew = await Schedule.getEventMessageByEventId(interaction.guild, eventId, events)
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
                    view = Schedule.generateSelectView(options, False, None, messageNew, "Select a file.", "schedule_select_edit_files_add", interaction.user.id, self.view.previousMessageView, eventId=eventId)

                await interaction.response.edit_message(embed=embed, view=view)
                return

            elif customId.startswith("schedule_button_event_edit_files_remove_"):
                eventId = customId[len("schedule_button_event_edit_files_remove_"):]
                _, messageNew = await Schedule.getEventMessageByEventId(interaction.guild, eventId, events)
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
                    view = Schedule.generateSelectView(options, False, None, messageNew, "Select a file.", "schedule_select_edit_files_remove", interaction.user.id, self.view.previousMessageView, eventId=eventId)

                await interaction.response.edit_message(embed=embed, view=view)
                return

            elif customId == "schedule_button_change_time_zone":
                default = None
                with open(MEMBER_TIME_ZONES_FILE) as f:
                    memberTimeZones = json.load(f)
                if str(interaction.user.id) in memberTimeZones:
                    default = memberTimeZones[str(interaction.user.id)]

                modal = ScheduleModal(
                    title="Change time zone",
                    customId="schedule_modal_change_time_zone",
                    userId=interaction.user.id,
                    eventMsg=interaction.message,
                )
                modal.add_item(discord.ui.TextInput(label="Time zone", default=default, placeholder="Europe/London", min_length=1, max_length=256))
                await interaction.response.send_modal(modal)
                return

            elif customId == "schedule_button_remove_time_zone":
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

            elif customId.startswith("schedule_button_noshow_add_"):
                targetUserId = customId[len("schedule_button_noshow_add_"):]
                modal = ScheduleModal(
                    title="Add no-show entry",
                    customId=f"schedule_modal_noshow_add_{targetUserId}",
                    userId=interaction.user.id,
                    eventMsg=interaction.message,
                )
                modal.add_item(discord.ui.TextInput(label="Operation startime (UTC)", placeholder="2069-04-20 04:20 PM", min_length=1, max_length=256))
                modal.add_item(discord.ui.TextInput(label="Operation Title", placeholder="Operation Honda Civic", min_length=1, max_length=256))
                modal.add_item(discord.ui.TextInput(label="User reserved role", placeholder="Actual", min_length=1, max_length=256, required=False))
                await interaction.response.send_modal(modal)
                return

            elif customId.startswith("schedule_button_noshow_remove_"):
                targetUserId = customId[len("schedule_button_noshow_remove_"):]
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
                    options.append(discord.SelectOption(label=entry.get("operationName", "Operation UNKNOWN"), description=noShowEntryTimestamp, value=str(date)))

                await interaction.response.send_message(interaction.user.mention, view=Schedule.generateSelectView(
                    options=options,
                    noneOption=False,
                    setOptionLabel=None,
                    eventMsg=interaction.message,
                    placeholder="Select no-show entry.",
                    customId=f"schedule_select_noshow_entry_{targetUserId}",
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
                except Exception:
                    log.exception(f"{interaction.user.id} | [{interaction.user.display_name}]")

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
            if len(events) == 0:
                await Schedule.updateSchedule(interaction.guild)
        except Exception:
            log.exception(f"{interaction.user.id} | [{interaction.user.display_name}]")

class ScheduleSelect(discord.ui.Select):
    """Handling all schedule dropdowns."""
    def __init__(self, eventMsg: discord.Message, placeholder: str, minValues: int, maxValues: int, customId: str, userId: int, row: int, options: List[discord.SelectOption], disabled: bool = False, eventMsgView: discord.ui.View | None = None, eventId: str | None = None, *args, **kwargs):
        # Append userId to customId to not collide on multi-user simultaneous execution
        super().__init__(placeholder=placeholder, min_values=minValues, max_values=maxValues, custom_id=f"{customId}_{userId}", row=row, options=options, disabled=disabled, *args, **kwargs)
        self.eventMsg = eventMsg
        self.eventMsgView = eventMsgView
        self.eventId = eventId

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("ScheduleSelect callback: interaction.guild not discord.Guild")
            return

        customId = "_".join(interaction.data["custom_id"].split("_")[:-1])  # Remove authorId

        if not isinstance(interaction.user, discord.Member):
            log.exception("ScheduleSelect callback: interaction.user not discord.Member")
            return

        selectedValue = self.values[0]

        if customId.startswith("schedule_select_create_"):
            if self.eventMsgView is None:
                log.exception("ScheduleSelect callback: self.eventMsgView is None")
                return

            infoLabel = customId[len("schedule_select_create_"):].split("_REMOVE")[0]  # e.g. "type"

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
                    previewEmbedDict["type"] = selectedValue
                    templateName = None

                    # Update view
                    previewView = Schedule.fromDictToPreviewView(previewEmbedDict, templateName)
                    self.eventMsgView.clear_items()
                    for item in previewView.children:
                        self.eventMsgView.add_item(item)
                    Schedule.setSelectedTemplateName(self.eventMsgView, None)

                case "map":
                    previewEmbedDict["map"] = None if previewEmbedDict["map"] == "None" else selectedValue

                case "linking":
                    previewEmbedDict["workshopInterest"] = None if selectedValue == "None" else selectedValue

                case "select_template":
                    selectedTemplateName = None if selectedValue == "None" else selectedValue
                    Schedule.setSelectedTemplateName(self.eventMsgView, selectedTemplateName)
                    Schedule.refreshTemplateButton(self.eventMsgView, previewEmbedDict["type"])

                    if selectedTemplateName is None:
                        await eventMsgNew.edit(embed=Schedule.fromDictToPreviewEmbed(previewEmbedDict, interaction.guild, None), view=self.eventMsgView)
                        return

                    # Insert template info into preview embed and view
                    templates = Schedule.loadTemplates(previewEmbedDict["type"])
                    for template in templates:
                        if template.get("templateName", None) == selectedTemplateName:
                            template["authorId"] = interaction.user.id
                            Schedule.applyMissingEventKeys(template, keySet="template")
                            template["type"] = previewEmbedDict["type"]
                            embed = Schedule.fromDictToPreviewEmbed(template, interaction.guild, selectedTemplateName)
                            for child in self.eventMsgView.children:
                                if not isinstance(child, discord.ui.Button) or child.label is None:
                                    continue

                                # Time is required but will not be saved in templates
                                if child.label == "Time":
                                    child.style = discord.ButtonStyle.danger
                                    continue

                                if child.label in ("Title", "Description") and Schedule.isDefaultCreateTextField(child.label.lower(), template.get(child.label.lower())):
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
                                if child.label == "Templates" or child.style == discord.ButtonStyle.primary:
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
                    ScheduleButton(eventMsgNew, row=0, label="Add", style=discord.ButtonStyle.success, custom_id="schedule_button_create_files_add", disabled=(len(previewEmbedDict["files"]) == 10)),
                    ScheduleButton(eventMsgNew, row=0, label="Remove", style=discord.ButtonStyle.danger, custom_id="schedule_button_create_files_remove", disabled=(len(previewEmbedDict["files"]) == 0))
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
            await eventMsgNew.edit(embed=Schedule.fromDictToPreviewEmbed(previewEmbedDict, interaction.guild, Schedule.getSelectedTemplateName(self.eventMsgView)), view=self.eventMsgView)


        elif customId.startswith("schedule_select_noshow_entry_"):
            userId = customId[len("schedule_select_noshow_entry_"):]
            userId = "_".join(userId.split("_")[:-1])  # Remove "_REMOVE0"

            with open(NO_SHOW_FILE) as f:
                noShowFile = json.load(f)

            if userId not in noShowFile:
                embed = discord.Embed(title="User not found", description="Target user not found in no-show entries", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)
                return

            for entry in noShowFile[userId]:
                date = entry.get("date", "0")
                if int(selectedValue) == int(date):
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


        elif customId == "schedule_select_reserve_role":
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


        elif customId == "schedule_select_edit_field":
            if self.eventId is None:
                log.exception("ScheduleSelect callback edit_select: self.eventId is None")
                return

            with open(EVENTS_FILE) as f:
                events = json.load(f)
            event, eventMsg = await Schedule.getEventMessageByEventId(interaction.guild, self.eventId, events)
            if event is None or eventMsg is None:
                await Schedule._sendPersistentEventMissing(interaction, self.eventId)
                return

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
                    view = Schedule.generateSelectView(options, False, eventType, eventMsg, "Select event type.", "schedule_select_edit_type", interaction.user.id, eventId=self.eventId)

                    await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

                # Editing Title
                case "Title":
                    modal = ScheduleModal("Title", "schedule_modal_edit_title", interaction.user.id, eventMsg, eventId=self.eventId)
                    modal.add_item(discord.ui.TextInput(
                        label="Title",
                        placeholder="Operation Honda Civic",
                        default=event["title"],
                        max_length=DISCORD_LIMITS["message_embed"]["embed_title"]
                    ))
                    await interaction.response.send_modal(modal)

                # Editing Linking
                case "Linking":
                    with open(WORKSHOP_INTEREST_FILE) as f:
                        wsIntOptions = json.load(f).keys()

                    options = [discord.SelectOption(label=wsName) for wsName in wsIntOptions]
                    view = Schedule.generateSelectView(options, True, event["map"], eventMsg, "Link event to a workshop.", "schedule_select_edit_linking", interaction.user.id, eventId=self.eventId)
                    await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

                # Editing Description
                case "Description":
                    modal = ScheduleModal("Description", "schedule_modal_edit_description", interaction.user.id, eventMsg, eventId=self.eventId)
                    modal.add_item(discord.ui.TextInput(
                        label="Description",
                        style=discord.TextStyle.long,
                        placeholder="Our mission is...",
                        default=event["description"]
                    ))
                    await interaction.response.send_modal(modal)

                # Editing URL
                case "External URL":
                    modal = ScheduleModal("External URL", "schedule_modal_edit_externalURL", interaction.user.id, eventMsg, eventId=self.eventId)
                    modal.add_item(discord.ui.TextInput(
                        label="URL",
                        style=discord.TextStyle.long,
                        placeholder="[OPORD](https://www.gnu.org)",
                        default=event["externalURL"],
                        required=False,
                        max_length=DISCORD_LIMITS["message_embed"]["embed_field_value"]
                    ))
                    await interaction.response.send_modal(modal)

                # Editing Reservable Roles
                case "Reservable Roles":
                    modal = ScheduleModal("Reservable Roles", "schedule_modal_edit_reservableRoles", interaction.user.id, eventMsg, eventId=self.eventId)
                    modal.add_item(discord.ui.TextInput(
                        label="Reservable Roles",
                        style=discord.TextStyle.long,
                        placeholder=("Co-Zeus\nActual\nJTAC\nF-35A Pilot" if event["reservableRoles"] is None else "\n".join(event["reservableRoles"].keys())[:DISCORD_LIMITS["interactions"]["text_input_placeholder"]]),
                        default=(None if event["reservableRoles"] is None else "\n".join(event["reservableRoles"].keys())),
                        required=False,
                        max_length=512
                    ))
                    await interaction.response.send_modal(modal)

                # Editing Map
                case "Map":
                    with open(GENERIC_DATA_FILE) as f:
                        genericData = json.load(f)
                        if "modpackMaps" not in genericData:
                            log.exception("ScheduleButton callback: modpackMaps not in genericData")
                            return
                    options = [discord.SelectOption(label=mapName) for mapName in genericData["modpackMaps"]]
                    view = Schedule.generateSelectView(options, True, event["map"], eventMsg, "Select a map.", "schedule_select_edit_map", interaction.user.id, eventId=self.eventId)
                    await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

                # Editing Attendence
                case "Max Players":
                    modal = ScheduleModal("Attendees", "schedule_modal_edit_maxPlayers", interaction.user.id, eventMsg, eventId=self.eventId)
                    modal.add_item(discord.ui.TextInput(
                        label="Attendees",
                        placeholder="Number / None / Anonymous / Hidden",
                        default=event["maxPlayers"],
                        max_length=9  # len("Anonymous")
                    ))
                    await interaction.response.send_modal(modal)

                # Editing Duration
                case "Duration":
                    modal = ScheduleModal("Duration", "schedule_modal_edit_duration", interaction.user.id, eventMsg, eventId=self.eventId)
                    modal.add_item(discord.ui.TextInput(
                        label="Duration",
                        placeholder="2h30m",
                        default=event["duration"],
                        max_length=16  # Arbitrary
                    ))
                    await interaction.response.send_modal(modal)

                # Editing Time
                case "Time":
                    # Set user time zone
                    with open(MEMBER_TIME_ZONES_FILE) as f:
                        memberTimeZones = json.load(f)
                    if str(interaction.user.id) not in memberTimeZones:
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Apply timezone", description="You must provide a time zone. Enter one in the time field, or use `/changetimezone` to store your time zone persistently.", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                        return

                    # Send modal
                    timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
                    modal = ScheduleModal("Time", "schedule_modal_edit_time", interaction.user.id, eventMsg, eventId=self.eventId)
                    modal.add_item(discord.ui.TextInput(
                        label="Time",
                        placeholder="2069-04-20 04:20 PM",
                        default=datetimeParse(event["time"]).replace(tzinfo=UTC).astimezone(timeZone).strftime(TIME_FORMAT),
                        max_length=32  # Arbitrary
                    ))
                    await interaction.response.send_modal(modal)

                # Editing Files
                case "Files":
                    view = ScheduleView(authorId=interaction.user.id)
                    items = [
                        ScheduleButton(eventMsg, row=0, label="Add", style=discord.ButtonStyle.success, custom_id=f"schedule_button_event_edit_files_add_{self.eventId}", disabled=(len(eventMsg.attachments) == 10)),
                        ScheduleButton(eventMsg, row=0, label="Remove", style=discord.ButtonStyle.danger, custom_id=f"schedule_button_event_edit_files_remove_{self.eventId}", disabled=(not eventMsg.attachments)),
                    ]
                    for item in items:
                        view.add_item(item)

                    embed = discord.Embed(title="Attaching files", description="You may attach up to 10 files to your event.\nUpload them first using the command `/fileupload`.", color=discord.Color.gold())
                    await interaction.response.send_message(interaction.user.mention, embed=embed, view=view, ephemeral=True, delete_after=300.0)

            log.debug(f"{interaction.user.id} [{interaction.user.display_name}] Edited the event '{event['title'] if 'title' in event else event['templateName']}'")

        # All select menu options in edit_select
        elif customId.startswith("schedule_select_edit_"):
            if self.eventId is None:
                log.exception("ScheduleSelect callback edit_select_: self.eventId is None")
                return

            eventKey = customId[len("schedule_select_edit_"):].split("_REMOVE")[0]  # e.g. "files_add"

            with open(EVENTS_FILE) as f:
                events = json.load(f)
            event, eventMsg = await Schedule.getEventMessageByEventId(interaction.guild, self.eventId, events)
            if event is None or eventMsg is None:
                await Schedule._sendPersistentEventMissing(interaction, self.eventId)
                return

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
                    with open(f"tmp/fileUpload/{filenameFull}", "rb") as f:
                        await eventMsg.add_files(discord.File(f, filename=filenameShort))

                case "files_remove":
                    eventAttachmentDict = {eventAttachment.filename: eventAttachment for eventAttachment in eventMsg.attachments}
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
                    await eventMsg.remove_attachments(eventAttachmentDict[selectedValue])

                case _:
                    event[eventKey] = None if selectedValue == "None" else selectedValue

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)

            await eventMsg.edit(embed=Schedule.getEventEmbed(event, interaction.guild))
            await interaction.response.send_message(embed=discord.Embed(title="✅ Event edited", color=discord.Color.green()), ephemeral=True, delete_after=5.0)



class ScheduleModal(discord.ui.Modal):
    """Handling all schedule modals."""
    def __init__(self, title: str, customId: str, userId: int, eventMsg: discord.Message, view: discord.ui.View | None = None, eventId: str | None = None) -> None:
        # Append userId to customId to not collide on multi-user simultaneous execution
        super().__init__(title=title, custom_id=f"{customId}_{userId}")
        self.eventMsg = eventMsg
        self.view = view
        self.eventId = eventId

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("ScheduleModal on_submit: interaction.guild not discord.Guild")
            return

        customId = "_".join(interaction.data["custom_id"].split("_")[:-1])  # Remove authorId

        if not isinstance(interaction.user, discord.Member):
            log.exception("ScheduleModal on_submit: interaction.user not discord.Member")
            return
        value: str = self.children[0].value.strip()


        if customId.startswith("schedule_modal_noshow_add_"):
            targetUserId = customId[len("schedule_modal_noshow_add_"):]

            # Operation name
            opName = self.children[1].value.strip()

            # Reserved role
            resRoles = self.children[2].value.strip()

            try:
                parsedDate = parseUserDatetime(value)
                if parsedDate.tzinfo is None:
                    parsedDate = parsedDate.replace(tzinfo=timezone.utc)
                dateTimestamp = int(parsedDate.astimezone(timezone.utc).timestamp())
            except Exception as e:
                log.warning(e)
                embedDescription = f"**Operation Name:** `{opName}`"
                if resRoles:
                    embedDescription += f"\n**Reserved Role:** `{resRoles}`"
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
                    "operationName": opName or "Operation UNKNOWN",
                    "reservedRole": resRoles or None
                }
            )
            with open(NO_SHOW_FILE, "w") as f:
                json.dump(noShowFile, f, indent=4)

            embedDescription = f"**Date:** {datetime.fromtimestamp(dateTimestamp, timezone.utc).strftime(TIME_FORMAT)}\n**Operation Name:** `{opName}`"
            if resRoles:
                embedDescription += f"\n**Reserved Role:** `{resRoles}`"
            embed = discord.Embed(title="Entry added", description=embedDescription, color=discord.Color.green())
            await interaction.response.send_message("Execute /no-show again to view the updated listing.", embed=embed, ephemeral=True, delete_after=30.0)
            return


        if customId == "schedule_modal_change_time_zone":
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

        if customId.startswith("schedule_modal_create_") and self.view is not None:
            infoLabel = customId[len("schedule_modal_create_"):]
            followupMsg = {}

            # Update embed
            previewEmbedDict = Schedule.fromPreviewEmbedToDict(self.eventMsg.embeds[0])
            previewEmbedDict["authorId"] = interaction.user.id

            match infoLabel:
                case "title":
                    previewEmbedDict["title"] = SCHEDULE_EVENT_PREVIEW_EMBED["title"] if Schedule.isDefaultCreateTextField("title", value) else value

                case "description":
                    previewEmbedDict["description"] = SCHEDULE_EVENT_PREVIEW_EMBED["description"] if Schedule.isDefaultCreateTextField("description", value) else value

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

                    if startTime.tzinfo is None:
                        startTime = timeZone.localize(startTime).astimezone(pytz.utc)
                    else:
                        startTime = startTime.astimezone(pytz.utc)
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
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Too many roles", description=f"Due to Discord character limitation, we've set the cap to 20 roles.\nLink your order, e.g. OPORD, under URL if you require more flexibility.\n\nYour roles:\n{value}"[:DISCORD_LIMITS["message_embed"]["embed_description"]], color=discord.Color.red()), ephemeral=True, delete_after=10.0)
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

                case "templates_save_as":
                    eventType = previewEmbedDict["type"]
                    templateDict = deepcopy(previewEmbedDict)
                    templateDict["templateName"] = value
                    templates = Schedule.loadTemplates(eventType)

                    Schedule.applyMissingEventKeys(templateDict, keySet="template", removeKeys=True)

                    if templateDict in templates:
                        await interaction.response.send_message(embed=discord.Embed(title="❌ No diff", description="The new template data does not differ from the old template.\nTemplate not overwritten.", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                        return

                    if Schedule.findTemplateIndex(templates, templateDict["templateName"]) is not None:
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Duplicate template", description=f"A template named `{value}` already exists.", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                        return

                    log.info(f"{interaction.user.id} [{interaction.user.display_name}] Saved as new template: '{templateDict['templateName']}'")

                    templates.append(templateDict)
                    Schedule.saveTemplates(eventType, templates)
                    Schedule.setSelectedTemplateName(self.view, value)
                    Schedule.refreshTemplateButton(self.view, eventType)

                    # Reply & edit msg
                    embed = discord.Embed(title="✅ Saved as a new template", description=f"Saved template as: `{value}`", color=discord.Color.green())
                    await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10.0)
                    await self.eventMsg.edit(embed=Schedule.fromDictToPreviewEmbed(previewEmbedDict, interaction.guild, value), view=self.view)
                    return

                case "templates_rename":
                    selectedTemplateName = Schedule.getSelectedTemplateName(self.view)
                    if selectedTemplateName is None:
                        await interaction.response.send_message(embed=discord.Embed(title="❌ No template selected", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                        return

                    templates = Schedule.loadTemplates(previewEmbedDict["type"])
                    templateIndex = Schedule.findTemplateIndex(templates, selectedTemplateName)
                    if templateIndex is None:
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Template not found", description=f"`{selectedTemplateName}` no longer exists.", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                        return

                    duplicateIndex = Schedule.findTemplateIndex(templates, value)
                    if duplicateIndex is not None and duplicateIndex != templateIndex:
                        await interaction.response.send_message(embed=discord.Embed(title="❌ Duplicate template", description=f"A template named `{value}` already exists.", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
                        return

                    log.info(f"{interaction.user.id} [{interaction.user.display_name}] Renamed template '{selectedTemplateName}' to '{value}'")
                    templates[templateIndex]["templateName"] = value
                    Schedule.saveTemplates(previewEmbedDict["type"], templates)
                    Schedule.setSelectedTemplateName(self.view, value)
                    Schedule.refreshTemplateButton(self.view, previewEmbedDict["type"])
                    await interaction.response.send_message(embed=discord.Embed(title="✅ Renamed", description=f"Renamed template to: `{value}`", color=discord.Color.green()), ephemeral=True, delete_after=10.0)
                    await self.eventMsg.edit(embed=Schedule.fromDictToPreviewEmbed(previewEmbedDict, interaction.guild, value), view=self.view)
                    return

            # Update button style
            for child in self.view.children:
                if isinstance(child, discord.ui.Button) and child.label is not None and child.label.lower().replace(" ", "_") == infoLabel:
                    if infoLabel in ("title", "description") and Schedule.isDefaultCreateTextField(infoLabel, previewEmbedDict[infoLabel]):
                        child.style = discord.ButtonStyle.danger
                    elif value == "":
                        child.style = discord.ButtonStyle.danger if SCHEDULE_EVENT_VIEW[infoLabel.replace("_", " ").title().replace("Url", "URL")]["required"] else discord.ButtonStyle.secondary
                    else:
                        child.style = discord.ButtonStyle.success
                    break

            await interaction.response.edit_message(embed=Schedule.fromDictToPreviewEmbed(previewEmbedDict, interaction.guild, Schedule.getSelectedTemplateName(self.view)), view=self.view)
            if followupMsg:
                await interaction.followup.send(followupMsg["content"] if "content" in followupMsg else None, embed=(followupMsg["embed"] if "embed" in followupMsg else None), ephemeral=True)
            return

        # == Editing Event ==

        if self.eventId is None:
            log.exception("ScheduleModal on_submit: self.eventId is None")
            return

        followupMsg = {}
        with open(EVENTS_FILE) as f:
            events = json.load(f)
        event, eventMsg = await Schedule.getEventMessageByEventId(interaction.guild, self.eventId, events)
        if event is None or eventMsg is None:
            await Schedule._sendPersistentEventMissing(interaction, self.eventId)
            return

        if value == "":
            event[customId[len("schedule_modal_edit_"):]] = None

        elif customId == "schedule_modal_edit_reservableRoles":
            reservableRoles = value.split("\n")
            if len(reservableRoles) > 20:
                await interaction.response.send_message(embed=discord.Embed(title="❌ Too many roles", description=f"Due to Discord character limitation, we've set the cap to 20 roles.\nLink your order, e.g. OPORD, under URL if you require more flexibility.\n\nYour roles:\n{value}"[:DISCORD_LIMITS["message_embed"]["embed_description"]], color=discord.Color.red()), ephemeral=True, delete_after=10.0)
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

        elif customId == "schedule_modal_edit_maxPlayers":
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

        elif customId == "schedule_modal_edit_duration":
            durationOld = event["duration"]
            endTimeOld = event.get("endTime")

            if not re.match(r"^\s*((([1-9]\d*)?\d\s*h(\s*([0-5])?\d\s*m?)?)|(([0-5])?\d\s*m))\s*$", value):
                await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                return

            durationDetails = Schedule.getDetailsFromDuration(value)
            if not durationDetails:
                await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                return
            hours, minutes, delta = durationDetails

            event["duration"] = f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}"

            # Check if new duration and old duration is the same
            if event["duration"] == durationOld:
                await interaction.response.send_message(interaction.user.mention, embed=discord.Embed(title="❌ No changes made", description="The new duration is the same as the old duration.", color=discord.Color.red()), ephemeral=True, delete_after=10.0)
                return

            # Update event endTime if no template
            if "endTime" in event:
                startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
                endTime = startTime + delta
                event["endTime"] = endTime.strftime(TIME_FORMAT)

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)

            await eventMsg.edit(embed=Schedule.getEventEmbed(event, interaction.guild), view=Schedule.getEventView(event))

            # Notify attendees of duration change
            # Send before time-hogging processes - fix interaction failed
            await interaction.response.send_message(interaction.user.mention, embed=discord.Embed(title="✅ Event edited", color=discord.Color.green()), ephemeral=True, delete_after=5.0)

            previewEmbed = discord.Embed(
                title=f":clock3: The duration has changed for: {event['title']}!",
                description=f"From: {durationOld}\n\u2004\u2004\u2004\u205F\u200ATo: {event['duration']}",
                color=discord.Color.orange()
            )
            if endTimeOld is not None and event.get("endTime") is not None:
                previewEmbed.add_field(
                    name="End time",
                    value=f"From: {discord.utils.format_dt(UTC.localize(datetime.strptime(endTimeOld, TIME_FORMAT)), style='F')}\n\u2004\u2004\u2004\u205F\u200ATo: {discord.utils.format_dt(UTC.localize(datetime.strptime(event['endTime'], TIME_FORMAT)), style='F')}",
                    inline=False
                )
            previewEmbed.add_field(name="\u200B", value=eventMsg.jump_url, inline=False)
            previewEmbed.set_footer(text=f"By: {interaction.user}")
            for memberId in event["accepted"] + event["declined"] + event["tentative"] + event["standby"]:
                member = interaction.guild.get_member(memberId)
                if member is not None:
                    try:
                        await member.send(embed=previewEmbed)
                    except Exception:
                        log.warning(f"Failed to DM {member.id} [{member.display_name}] about event duration change")

            return

        elif customId == "schedule_modal_edit_time":
            startTimeOld = event["time"]
            durationDetails = Schedule.getDetailsFromDuration(event["duration"])
            if not durationDetails:
                await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                return
            hours, minutes, delta = durationDetails

            try:
                startTime = parseUserDatetime(value)
            except ValueError:
                await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                return

            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)
            timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
            if startTime.tzinfo is None:
                startTime = timeZone.localize(startTime).astimezone(UTC)
            else:
                startTime = startTime.astimezone(UTC)

            # Check if new time and old time is the same
            if startTime.strftime(TIME_FORMAT) == startTimeOld:
                await interaction.response.send_message(interaction.user.mention, embed=discord.Embed(title="❌ No changes made", description="The new time is the same as the old time.", color=discord.Color.red()), ephemeral=True, delete_after=10.0)
                return

            endTime = startTime + delta
            event["time"] = startTime.strftime(TIME_FORMAT)
            event["endTime"] = endTime.strftime(TIME_FORMAT)

            # Notify attendees of time change
            # Send before time-hogging processes - fix interaction failed
            await interaction.response.send_message(interaction.user.mention, embed=discord.Embed(title="✅ Event edited", color=discord.Color.green()), ephemeral=True, delete_after=15.0)

            previewEmbed = discord.Embed(
                title=f":clock3: The starting time has changed for: {event['title']}!",
                description=f"From: {discord.utils.format_dt(UTC.localize(datetime.strptime(startTimeOld, TIME_FORMAT)), style='F')}\n\u2004\u2004\u2004\u205F\u200ATo: {discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}",
                color=discord.Color.orange()
            )
            previewEmbed.add_field(name="\u200B", value=eventMsg.jump_url, inline=False)
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

            return


        else:
            event[customId[len("schedule_modal_edit_"):]] = value

        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)

        await eventMsg.edit(embed=Schedule.getEventEmbed(event, interaction.guild), view=Schedule.getEventView(event))
        await interaction.response.send_message(interaction.user.mention, embed=discord.Embed(title="✅ Event edited", color=discord.Color.green()), ephemeral=True, delete_after=5.0)

        if followupMsg:
            await interaction.followup.send(followupMsg["content"] if "content" in followupMsg else None, embed=(followupMsg["embed"] if "embed" in followupMsg else None), ephemeral=True)


    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        # await interaction.response.send_message("Something went wrong. cope.", ephemeral=True)
        log.exception(error)

# ===== </Views and Buttons> =====


async def setup(bot: commands.Bot) -> None:
    Schedule.noShow.error(Utils.onSlashError)
    Schedule.trackACandidate.error(Utils.onSlashError)
    Schedule.refreshSchedule.error(Utils.onSlashError)
    Schedule.aar.error(Utils.onSlashError)
    Schedule.scheduleOperation.error(Utils.onSlashError)
    await bot.add_cog(Schedule(bot))
    bot.add_dynamic_items(
        ScheduleAcceptButton,
        ScheduleAcceptAndReserveButton,
        ScheduleDeclineButton,
        ScheduleTentativeButton,
        ScheduleReserveButton,
        ScheduleEventEditButton,
        ScheduleEventConfigButton
    )
