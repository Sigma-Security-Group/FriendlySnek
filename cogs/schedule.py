import os, re, json, asyncio, discord
import pytz  # type: ignore

from math import ceil
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse as datetimeParse  # type: ignore

from discord import Embed, Color
from discord.ext import commands, tasks  # type: ignore

from .workshopInterest import WorkshopInterest  # type: ignore
from secret import DEBUG
from constants import *
from __main__ import log, cogsReady
if DEBUG:
    from constants.debug import *


EMBED_TIMEOUT = Embed(title=ERROR_TIMEOUT, color=Color.red())
EMBED_INVALID = Embed(title="❌ Invalid input", color=Color.red())

OPERATION_NAME_ADJECTIVES = "constants/opAdjectives.txt"
OPERATION_NAME_NOUNS = "constants/opNouns.txt"

MAX_SERVER_ATTENDANCE = 50

# Training map first, then the rest in alphabetical order
MAPS = [
    "Training Map",
    "Altis",
    "Bukovina",
    "Bystrica",
    "Chernarus (Autumn)",
    "Chernarus (Summer)",
    "Chernarus (Winter)",
    "Colombia",
    "Desert",
    "Dingor",
    "Farabad",
    "Fjord",
    # "Front Amazonia",
    "Green Sea",
    "Isla Pera",
    # "Kardazak",
    "Korsac",
    "Korsac (Winter)",
    # "Kunduz, Afghanistan",
    "Kunduz River",
    "Lingor",
    "Livonia",
    "Malden 2035",
    # "Mutambara",
    # "Niakala",
    # "Novogorsk",
    "Porto",
    "Proving Grounds",
    "Rahmadi",
    # "Rosche, Germany",
    # "Sa'hatra",
    "Sahrani",
    # "Saint Kapaulio",
    "Scottish Highlands",
    "Shapur",
    "Southern Sahrani",
    "Stratis",
    # "Sumava",
    "Takistan",
    "Takistan Mountains",
    "Tanoa",
    "Tembelan Island",
    "United Sahrani",
    "Utes",
    # "Uzbin Valley",
    "Virolahti",
    "Virtual Reality",
    "Yulakia",
    "Zargabad"
]

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
    "Operation": Color.green(),
    "Workshop": Color.blue(),
    "Event": Color.gold()
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

def jsonCreateNoExist(filename: str, dump: list | dict) -> None:
    """Creates a JSON file with a dump if not exist.

    Parameters:
    filename (str): The files name.
    dump (list | dict): What to dump.

    Returns:
    None.
    """
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump(dump, f, indent=4)

jsonCreateNoExist(MEMBER_TIME_ZONES_FILE, {})
jsonCreateNoExist(EVENTS_HISTORY_FILE, [])
jsonCreateNoExist(WORKSHOP_TEMPLATES_FILE, [])
#jsonCreateNoExist(WORKSHOP_TEMPLATES_DELETED_FILE, [])
jsonCreateNoExist(REMINDERS_FILE, {})
jsonCreateNoExist(ROLE_RESERVATION_BLACKLIST_FILE, [])

# try:
#     with open("./.git/logs/refs/heads/main") as f:
#         commitHash = f.readlines()[-1].split()[1][:7]  # The commit hash that the bot is running on (last line, second column, first 7 characters)
# except Exception as e:
#     log.exception(e)


class Schedule(commands.Cog):
    """Schedule Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Schedule"), flush=True)
        cogsReady["schedule"] = True

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
        await channel.send(embed=Embed(title=f"❌ {abortText} canceled!", color=Color.red()))

    @staticmethod
    async def checkDMChannel(user: discord.User | discord.Member) -> discord.channel.DMChannel:
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
            log.exception("saveEventToHistory: guild is None")
            return

        if event.get("type", "Operation") == "Workshop" and (workshopInterestName := event.get("workshopInterest")) is not None:
            with open(WORKSHOP_INTEREST_FILE) as f:
                workshopInterestFile = json.load(f)
            if (workshop := workshopInterestFile.get(workshopInterestName)) is not None:
                accepted = event["accepted"]
                if isinstance(event["maxPlayers"], int):  # If int: maxPlayer limit
                    accepted = accepted[:event["maxPlayers"]]
                updateWorkshopInterest = False
                for memberId in accepted:
                    if memberId in workshop["members"]:
                        updateWorkshopInterest = True
                        workshop["members"].remove(memberId)
                if updateWorkshopInterest:
                    with open(WORKSHOP_INTEREST_FILE, "w") as f:
                        json.dump(workshopInterestFile, f, indent=4)
                    channelWorkshopInterest = self.bot.get_channel(WORKSHOP_INTEREST)
                    if not isinstance(channelWorkshopInterest, discord.TextChannel):
                        log.exception("Schedule saveEventToHistory: channelWorkshopInterest is not discord.TextChannel")
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
        while not self.bot.ready:
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
                    log.debug(f"Auto deleting event: {event['title']}")
                    deletedEvents.append(event)
                    eventMessage = await self.bot.get_channel(SCHEDULE).fetch_message(event["messageId"])
                    await eventMessage.delete()
                    author = self.bot.get_guild(GUILD_ID).get_member(event["authorId"])
                    embed = Embed(title="Event auto deleted", description=f"You forgot to delete your event: `{event['title']}`\nI have now done it for you. Don't do it again {PEPE_GUN}", color=Color.orange())
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
            log.exception("tenMinTask: guild is None")
            return

        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            utcNow = datetime.now(timezone.utc)

            channel = self.bot.get_channel(ARMA_DISCUSSION)
            if channel is None or not isinstance(channel, discord.channel.TextChannel):
                log.exception("tenMinTask: channel is invalid type")
                return

            for event in events:
                if event.get("checkedAcceptedReminders", False):
                    continue
                if event.get("type", "Operation") != "Operation":
                    continue
                startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
                if utcNow > startTime + timedelta(minutes=30):
                    acceptedMembers = [member for memberId in event["accepted"] if (member := guild.get_member(memberId)) is not None]
                    onlineMembers = self.bot.get_channel(COMMAND).members + self.bot.get_channel(DEPLOYED).members
                    acceptedMembersNotOnline = []
                    onlineMembersNotAccepted = []
                    for member in acceptedMembers:
                        if member not in onlineMembers and member not in acceptedMembersNotOnline:
                            acceptedMembersNotOnline.append(member)
                    for member in onlineMembers:
                        if member.id != event["authorId"] and member not in acceptedMembers and member not in onlineMembersNotAccepted:
                            onlineMembersNotAccepted.append(member)

                    event["checkedAcceptedReminders"] = True
                    with open(EVENTS_FILE, "w") as f:
                        json.dump(events, f, indent=4)
                    if len(acceptedMembersNotOnline) > 0:
                        log.debug(f"Pinging members in accepted not in VC: {', '.join([member.display_name for member in acceptedMembersNotOnline])}")
                        await channel.send(" ".join(member.mention for member in acceptedMembersNotOnline) + f" If you are in-game, please get in <#{COMMAND}> or <#{DEPLOYED}>. If you are not making it to this {event['type'].lower()}, please hit decline ❌ on the <#{SCHEDULE}>.")
                    if len(onlineMembersNotAccepted) > 0:
                        log.debug(f"Pinging members in VC not in accepted: {', '.join([member.display_name for member in onlineMembersNotAccepted])}")
                        await channel.send(" ".join(member.mention for member in onlineMembersNotAccepted) + f" If you are in-game, please hit accept ✅ on the <#{SCHEDULE}>.")
        except Exception as e:
            log.exception(e)

# ===== </Tasks> =====


# ===== <Refresh Schedule> =====

    @discord.app_commands.command(name="refreshschedule")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(UNIT_STAFF, SERVER_HAMSTER, CURATOR, SNEK_LORD)
    async def refreshSchedule(self, interaction: discord.Interaction) -> None:
        """Refreshes the schedule - Use if an event was deleted without using the reaction.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        await interaction.response.send_message(f"Refreshing <#{SCHEDULE}>...")
        log.info(f"{interaction.user.display_name} ({interaction.user}) is refreshing the schedule...")
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
                log.exception("OnRefreshScheduleError: guild is None")
                return

            embed = Embed(title="❌ Missing permissions", description=f"You do not have the permissions to refresh the schedule!\nThe permitted roles are: {', '.join([guild.get_role(role).name for role in (UNIT_STAFF, SERVER_HAMSTER, CURATOR)])}.", color=Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)

# ===== </Refresh Schedule> =====
# ===== <Zeus Commands> ====
# Move from Deployed to Command
    @discord.app_commands.command(name="aar")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(CMD_AAR_LIMIT)
    async def aar(self, interaction: discord.Interaction) -> None:
        """ Move all users in Deployed to Command voice channel. """
        log.info(f"{interaction.user.display_name} ({interaction.user}) is starting an AAR...")

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("aar: guild is None")
            return

        channelDeployed = guild.get_channel(DEPLOYED)
        if not isinstance(channelDeployed, discord.VoiceChannel):
            log.exception("aar: channelDeployed is None")
            return

        channelCommand = guild.get_channel(COMMAND)
        if not isinstance(channelCommand, discord.VoiceChannel):
            log.exception("aar: channelDeployed is None")
            return

        deployed_members = channelDeployed.members
        for member in deployed_members:
            log.debug(f"Moving {member.display_name} to Command ( {COMMAND} )")
            try:
                await member.move_to(channelCommand)
            except Exception:
                log.warning(f"Snek did a booboo moving {member.display_name}")
        await interaction.response.send_message("AAR has started, Thanks for running a bop!", ephemeral=True)

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
                log.exception("OnAarError: guild is None")
                return

            embed = Embed(title="❌ Missing permissions", description=f"You do not have the permissions to move all users to command!\nThe permitted roles are: {', '.join([guild.get_role(role).name for role in CMD_AAR_LIMIT])}.", color=Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)

# ===== <Schedule Functions> =====

    async def updateSchedule(self) -> None:
        """Updates the schedule channel with all messages."""
        channel = self.bot.get_channel(SCHEDULE)
        if channel is None or not isinstance(channel, discord.channel.TextChannel):
            log.exception("updateSchedule: channel invalid type")
            return

        await channel.purge(limit=None, check=lambda m: m.author.id in FRIENDLY_SNEKS)

        await channel.send(f"__Welcome to the schedule channel!__\n🟩 Schedule operations: `/operation` (`/bop`)\n🟦 Workshops: `/workshop` (`/ws`)\n🟨 Generic events: `/event`\n\nThe datetime you see in here are based on __your local time zone__.\nChange timezone when scheduling events with `/changetimezone`.\n\nSuggestions/bugs contact: {', '.join([f'**{developerName.display_name}**' for name in DEVELOPERS if (developerName := channel.guild.get_member(name)) is not None])} -- <https://github.com/Sigma-Security-Group/FriendlySnek>")  #  `{commitHash}`")

        jsonCreateNoExist(EVENTS_FILE, [])
        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            if len(events) == 0:
                await channel.send("...\nNo bop?\n...\nSnek is sad")
                await channel.send(":cry:")
                return

            newEvents: list[dict] = []
            with open(EVENTS_FILE, "w") as f:
                json.dump(newEvents, f, indent=4)
            for event in sorted(events, key=lambda e: datetime.strptime(e["time"], TIME_FORMAT), reverse=True):
                msg = await channel.send(embed=self.getEventEmbed(event), view=self.getEventView(event))
                event["messageId"] = msg.id
                newEvents.append(event)
                with open(EVENTS_FILE, "w") as f:
                    json.dump(newEvents, f, indent=4)
        except Exception as e:
            log.exception(e)

    def getEventEmbed(self, event: dict) -> Embed:
        """Generates an embed from the given event.

        Parameters:
        event (dict): The event.

        Returns:
        Embed: The generated embed.
        """
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Schedule getEventEmbed: guild is None")
            return Embed()

        embed = Embed(title=event["title"], description=event["description"], color=EVENT_TYPE_COLORS[event.get("type", "Operation")])

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

        accepted = [member.display_name for memberId in event["accepted"] if (member := guild.get_member(memberId)) is not None]
        standby = []
        if isinstance(event["maxPlayers"], int) and len(accepted) > event["maxPlayers"]:
            accepted, standby = accepted[:event["maxPlayers"]], accepted[event["maxPlayers"]:]
        declined = [member.display_name for memberId in event["declined"] if (member := guild.get_member(memberId)) is not None]
        tentative = [member.display_name for memberId in event["tentative"] if (member := guild.get_member(memberId)) is not None]

        # No limit || limit
        if event["maxPlayers"] is None or isinstance(event["maxPlayers"], int):
            embed.add_field(name=f"Accepted ({len(accepted)}) ✅" if event["maxPlayers"] is None else f"Accepted ({len(accepted)}/{event['maxPlayers']}) ✅", value="\n".join(name for name in accepted) if len(accepted) > 0 else "-", inline=True)
            embed.add_field(name=f"Declined ({len(declined)}) ❌", value=("\n".join("❌ " + name for name in declined)) if len(declined) > 0 else "-", inline=True)
            embed.add_field(name=f"Tentative ({len(tentative)}) ❓", value="\n".join(name for name in tentative) if len(tentative) > 0 else "-", inline=True)
            if len(standby) > 0:
                embed.add_field(name=f"Standby ({len(standby)}) :clock3:", value="\n".join(name for name in standby), inline=False)

        # Anonymous
        elif event["maxPlayers"] == "anonymous":
            embed.add_field(name=f"Accepted ({len(accepted + standby)}) ✅", value="\u200B", inline=True)
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
            items.extend([
                ScheduleButton(self, None, row=0, label="Accept", style=discord.ButtonStyle.success, custom_id="accepted"),
                ScheduleButton(self, None, row=0, label="Decline", style=discord.ButtonStyle.danger, custom_id="declined"),
                ScheduleButton(self, None, row=0, label="Tentative", style=discord.ButtonStyle.secondary, custom_id="tentative")
            ])
            if event["reservableRoles"] is not None:
                items.append(ScheduleButton(self, None, row=0, label="Reserve", style=discord.ButtonStyle.secondary, custom_id="reserve"))

        items.append(ScheduleButton(self, None, row=0, emoji="⚙️", style=discord.ButtonStyle.secondary, custom_id="config"))
        for item in items:
            view.add_item(item)

        return view

    @staticmethod
    def fromPreviewEmbedToDict(embed: discord.Embed) -> dict:
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
            "type": [eventType for eventType in EVENT_TYPE_COLORS if EVENT_TYPE_COLORS[eventType] == embed.color][0] if embed.color in EVENT_TYPE_COLORS.values() else None
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

        return outputDict

    def fromDictToPreviewEmbed(self, previewDict: dict) -> discord.Embed:
        """Generates event dict from preview embed."""
        # Title, Description, Color
        embed = Embed(title=previewDict["title"], description=previewDict["description"], color=None if previewDict["type"] is None else EVENT_TYPE_COLORS[previewDict["type"]])

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

        # Author, Footer, Timestamp
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Schedule fromDictToPreviewEmbed: guild is None")
            return Embed(title="Error")
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
        embed.add_field(name=f"Declined (0) ❌", value=fieldValue, inline=True)
        embed.add_field(name=f"Tentative (0) ❓", value=fieldValue, inline=True)

        return embed

    def fromDictToPreviewView(self, previewDict: dict, selectedTemplate: str) -> discord.ui.View:
        """Generates preview view from event dict."""
        view = ScheduleView()
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
                previewDict["authorId"],
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
                    jsonCreateNoExist(filename, [])
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


    async def buttonHandling(self, message: discord.Message | None, button: discord.ui.Button, interaction: discord.Interaction, authorId: int | None) -> None:
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
            log.exception("ButtonHandling: user not discord.Member")
            return

        if interaction.message is None:
            log.exception("ButtonHandling: interaction.message is None")
            return

        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)

            scheduleNeedsUpdate = True
            fetchMsg = False
            eventList: list[dict] = [event for event in events if event["messageId"] == interaction.message.id]

            rsvpOptions = ("accepted", "declined", "tentative")
            if button.custom_id in rsvpOptions:
                event = eventList[0]

                # User click on button twice - remove
                if interaction.user.id in event[button.custom_id]:
                    event[button.custom_id].remove(interaction.user.id)

                # "New" button
                else:
                    for option in rsvpOptions:
                        if interaction.user.id in event[option]:
                            event[option].remove(interaction.user.id)
                    event[button.custom_id].append(interaction.user.id)

                # Remove player from reservable role
                if event["reservableRoles"] is not None:
                    for btnRoleName in event["reservableRoles"]:
                        if event["reservableRoles"][btnRoleName] == interaction.user.id:
                            event["reservableRoles"][btnRoleName] = None

            elif button.custom_id == "reserve":
                with open(ROLE_RESERVATION_BLACKLIST_FILE) as f:
                    blacklist = json.load(f)
                if any(interaction.user.id == member["id"] for member in blacklist):
                    await interaction.response.send_message(embed=Embed(title="❌ Sorry, seems like are not allowed to reserve any roles!", description="If you have any questions about this situation, please contact Unit Staff.", color=Color.red()), ephemeral=True, delete_after=60.0)
                    return

                event = eventList[0]
                scheduleNeedsUpdate = False

                if isinstance(event["maxPlayers"], int) and len(event["accepted"]) >= event["maxPlayers"] and (interaction.user.id not in event["accepted"] or event["accepted"].index(interaction.user.id) >= event["maxPlayers"]):
                    await interaction.response.send_message(embed=Embed(title="❌ Sorry, seems like there's no space left in the :b:op!", color=Color.red()), ephemeral=True, delete_after=60.0)
                    return

                if not isinstance(interaction.user, discord.Member):
                    log.exception("reserveRole interaction.user not discord.Member")
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
                    log.exception("reserve_role_unreserve: message is None ")
                    return
                event = [event for event in events if event["messageId"] == message.id][0]

                # Disable all discord.ui.Item
                if button.view is None:
                    log.exception("reserve_role_unreserve button.view is None")
                    return

                for child in button.view.children:
                    child.disabled = True
                await interaction.response.edit_message(view=button.view)

                # Unreserve role
                for roleName in event["reservableRoles"]:
                    if event["reservableRoles"][roleName] == interaction.user.id:
                        event["reservableRoles"][roleName] = None
                        await interaction.followup.send(embed=Embed(title=f"✅ Role unreserved: `{roleName}`", color=Color.green()), ephemeral=True)
                        await message.edit(embed=self.getEventEmbed(event))
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
                await interaction.response.send_message(content=f"{interaction.user.mention} What would you like to configure?", view=view, ephemeral=True, delete_after=60.0)

            elif button.custom_id == "edit":
                scheduleNeedsUpdate = False
                if message is None:
                    log.exception("buttonHandling delete: edit message is None")
                    return

                event = [event for event in events if event["messageId"] == message.id][0]
                await self.editEvent(interaction, event, message)

            elif button.custom_id == "delete":
                if message is None:
                    log.exception("buttonHandling delete: button message is None")
                    return

                event = [event for event in events if event["messageId"] == message.id][0]
                scheduleNeedsUpdate = False

                if message is None:
                    log.exception("buttonHandling delete: button message is None")
                    return

                embed = Embed(title=f"Are you sure you want to delete this {event['type'].lower()}: `{event['title']}`?", color=Color.orange())
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
                    log.exception("buttonHandling delete_event_confim: button.view is None")
                    return

                if message is None:
                    log.exception("buttonHandling delete_event_confim: button message is None")
                    return

                # Disable buttons
                for button in button.view.children:
                    button.disabled = True
                await interaction.response.edit_message(view=button.view)

                # Delete event
                event = [event for event in events if event["messageId"] == message.id][0]
                await message.delete()
                try:
                    log.info(f"{interaction.user.display_name} ({interaction.user}) deleted the event: {event['title']}")
                    await interaction.followup.send(embed=Embed(title=f"✅ {event['type']} deleted!", color=Color.green()), ephemeral=True)

                    # Notify attendees
                    utcNow = datetime.now(timezone.utc)
                    startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
                    if event["maxPlayers"] != "hidden" and utcNow > startTime + timedelta(minutes=30):
                        await self.saveEventToHistory(event)
                    else:
                        guild = self.bot.get_guild(GUILD_ID)
                        if guild is None:
                            log.exception("buttonHandling delete_event_confim: guild is None")
                            return

                        for memberId in event["accepted"] + event["declined"] + event["tentative"]:
                            member = guild.get_member(memberId)
                            if member is not None:
                                embed = Embed(title=f"🗑 {event.get('type', 'Operation')} deleted: {event['title']}!", description=f"The {event.get('type', 'Operation').lower()} was scheduled to run:\n{discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}", color=Color.red())
                                embed.set_footer(text=f"By: {interaction.user}")
                                try:
                                    await member.send(embed=embed)
                                except Exception as e:
                                    log.warning(f"{member} | {e}")
                except Exception as e:
                    log.exception(f"{interaction.user} | {e}")
                events.remove(event)

            elif button.custom_id == "delete_event_cancel":
                if button.view is None:
                    log.exception("ButtonHandling delete_event_cancel: button.view is None")
                    return

                for item in button.view.children:
                    item.disabled = True
                await interaction.response.edit_message(view=button.view)
                await interaction.followup.send(embed=Embed(title=f"❌ Event deletion canceled!", color=Color.red()), ephemeral=True)
                return

            elif button.custom_id is not None and button.custom_id.startswith("event_schedule_"):
                if button.view is None:
                    log.exception("Schedule buttonHandling: button.view is None")
                    return

                if interaction.user.id != authorId:
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
                        typeOptions = [
                            discord.SelectOption(emoji="🟩", label="Operation"),
                            discord.SelectOption(emoji="🟦", label="Workshop"),
                            discord.SelectOption(emoji="🟨", label="Event")
                        ]
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
                                await interaction.followup.send(embed=Embed(title="❌ Timezone configuration canceled", description="You must provide a time zone in your DMs!", color=Color.red()))
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
                        options = [discord.SelectOption(label=mapName) for mapName in MAPS]
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
                            log.exception("Schedule buttonHandling: templateName == \"\"")
                            return
                        log.info(f"{interaction.user} updated the template: {templateName}")
                        # Write to file
                        filename = f"data/{previewEmbedDict['type'].lower()}Templates.json"
                        jsonCreateNoExist(filename, [])
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
                        # Check if all mandatory fields are filled
                        if isAllRequiredInfoFilled() is False:
                            await interaction.response.send_message(f"{interaction.user.mention} Before creating the event, you need to fill out the mandatory (red buttons) information!", ephemeral=True, delete_after=10.0)
                            return

                        # Append event to JSON
                        jsonCreateNoExist(EVENTS_FILE, [])
                        with open(EVENTS_FILE) as f:
                            events = json.load(f)
                        previewEmbedDict["authorId"] = interaction.user.id
                        events.append(previewEmbedDict)
                        with open(EVENTS_FILE, "w") as f:
                            json.dump(events, f, indent=4)

                        # Reply
                        await interaction.response.edit_message(content=f"`{previewEmbedDict['title']}` is now on <#{SCHEDULE}>!", embed=None, view=None)

                        # Update schedule
                        await self.updateSchedule()

                    case "cancel":
                        embed = Embed(title="Are you sure you want to cancel this event scheduling?", color=Color.orange())
                        view = ScheduleView()
                        items = [
                            ScheduleButton(self, interaction.message, interaction.user.id, row=0, label="Cancel", style=discord.ButtonStyle.success, custom_id="event_schedule_cancel_confirm"),
                            ScheduleButton(self, interaction.message, interaction.user.id, row=0, label="No, I changed my mind", style=discord.ButtonStyle.danger, custom_id="event_schedule_cancel_decline"),
                        ]
                        for item in items:
                            view.add_item(item)
                        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=60.0)

                    case "cancel_confirm":
                        if message is None:
                            log.exception("Schedule buttonHandling: message is None")
                            return
                        for child in button.view.children:
                            if isinstance(child, discord.ui.Button):
                                child.disabled = True
                        await interaction.response.edit_message(view=button.view)
                        await message.edit(content="Nvm guys, didn't wanna bop.", embed=None, view=None)

                    case "cancel_decline":
                        if message is None:
                            log.exception("Schedule buttonHandling: message is None")
                            return
                        for child in button.view.children:
                            if isinstance(child, discord.ui.Button):
                                child.disabled = True
                        await interaction.response.edit_message(view=button.view)
                        await interaction.followup.send(content="Alright, I won't cancel the scheduling.", ephemeral=True)

                if buttonLabel.startswith("select_template"):
                    filename = f"data/{previewEmbedDict['type'].lower()}Templates.json"
                    jsonCreateNoExist(filename, [])
                    with open(filename) as f:
                        templates = json.load(f)

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


            if scheduleNeedsUpdate:
                try:
                    embed = self.getEventEmbed(event)
                    if fetchMsg:  # Could be better - could be worse...
                        if interaction.channel is None or isinstance(interaction.channel, discord.channel.ForumChannel) or isinstance(interaction.channel, discord.channel.CategoryChannel):
                            log.exception("ButtonHandling scheduleNeedsUpdate: interaction.channel is invalid type")
                            return

                        originalMsgId = interaction.message.id
                        msg = await interaction.channel.fetch_message(originalMsgId)
                        await msg.edit(embed=embed)
                    else:
                        await interaction.response.edit_message(embed=embed)
                except Exception as e:
                    log.exception(f"{interaction.user} | {e}")

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            log.exception(f"{interaction.user} | {e}")

    def generateSelectView(self, options: list[discord.SelectOption], noneOption: bool, setOptionLabel: str, eventMsg: discord.Message, placeholder: str, customId: str, eventMsgView: discord.ui.View | None = None):
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
        for idx, option in enumerate(options):
            if option.label == setOptionLabel:
                options.pop(idx)
                break

        if noneOption:
            options.insert(0, discord.SelectOption(label="None", emoji="🚫"))

        # Generate view
        view = ScheduleView()
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
            log.exception("Schedule SelectHandling: interaction.user is not discord.Member")
            return

        selectedValue = select.values[0]

        if select.custom_id.startswith("select_create_"):
            if eventMsgView is None:
                log.exception("Schedule SelectHandling: eventMsgView is None")
                return

            infoLabel = select.custom_id[len("select_create_"):].split("_REMOVE")[0]  # e.g. "type"

            # Disable all discord.ui.Item
            if select.view is None:
                log.exception("Schedule SelectHandling: select.view is None")
                return
            for child in select.view.children:
                child.disabled = True
            await interaction.response.edit_message(view=select.view)

            previewEmbedDict = self.fromPreviewEmbedToDict(eventMsg.embeds[0])
            previewEmbedDict["authorId"] = interaction.user.id


            # Do preview embed edits
            if infoLabel == "type":
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

            elif infoLabel == "map":
                previewEmbedDict["map"] = None if previewEmbedDict["map"] == "None" else selectedValue

            elif infoLabel == "linking":
                previewEmbedDict["workshopInterest"] = None if selectedValue == "None" else selectedValue

            elif infoLabel == "select_template":
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
                jsonCreateNoExist(filename, [])
                with open(filename) as f:
                    templates = json.load(f)
                for template in templates:
                    if template["templateName"] == selectedValue:
                        template["authorId"] = interaction.user.id
                        template["time"] = template["endTime"] = None
                        template["type"] = previewEmbedDict['type']
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
                            if child.label == "Linking":
                                if embed.footer.icon_url is not None:
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

                        await eventMsg.edit(embed=embed, view=eventMsgView)
                        return


            # Update eventMsg button style
            for child in eventMsgView.children:
                if isinstance(child, discord.ui.Button) and child.label is not None and child.label.lower().replace(" ", "_") == infoLabel:
                    child.style = discord.ButtonStyle.success
                    break

            # Edit preview embed & view
            await eventMsg.edit(embed=self.fromDictToPreviewEmbed(previewEmbedDict), view=eventMsgView)



        elif select.custom_id == "reserve_role_select":
            # Disable all discord.ui.Item
            if select.view is None:
                log.exception("selectHandling select.view is None")
                return

            for child in select.view.children:
                child.disabled = True
            await interaction.response.edit_message(view=select.view)

            # Remove user from any reserved roles
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            event = [event for event in events if event["messageId"] == eventMsg.id][0]
            for roleName in event["reservableRoles"]:
                if event["reservableRoles"][roleName] == interaction.user.id:
                    event["reservableRoles"][roleName] = None
                    break

            # Reserve desired role
            event["reservableRoles"][selectedValue] = interaction.user.id
            await interaction.followup.send(embed=Embed(title=f"✅ Role reserved: `{selectedValue}`", color=Color.green()), ephemeral=True)

            # Put the user in accepted
            if interaction.user.id in event["declined"]:
                event["declined"].remove(interaction.user.id)
            if interaction.user.id in event["tentative"]:
                event["tentative"].remove(interaction.user.id)
            if interaction.user.id not in event["accepted"]:
                event["accepted"].append(interaction.user.id)

            # Write changes
            await eventMsg.edit(embed=self.getEventEmbed(event))
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)


        elif select.custom_id == "edit_select":
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            event = [event for event in events if event["messageId"] == eventMsg.id][0]

            if self.isAllowedToEdit(interaction.user, event["authorId"]) is False:
                await interaction.response.send_message("Please restart the editing process.", ephemeral=True, delete_after=60.0)
                return

            eventType = event.get("type", "Operation")

            # Editing Type
            if selectedValue == "Type":
                options = [
                    discord.SelectOption(emoji="🟩", label="Operation"),
                    discord.SelectOption(emoji="🟦", label="Workshop"),
                    discord.SelectOption(emoji="🟨", label="Event")
                ]
                view = self.generateSelectView(options, False, eventType, eventMsg, "Select event type.", "edit_select_type")

                await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

            # Editing Title
            elif selectedValue == "Title":
                modal = ScheduleModal(self, "Title", "modal_title", eventMsg)
                modal.add_item(discord.ui.TextInput(label="Title", default=event["title"], placeholder="Operation Honda Civic", min_length=1, max_length=256))
                await interaction.response.send_modal(modal)

            # Editing Linking
            elif selectedValue == "Linking":
                with open(WORKSHOP_INTEREST_FILE) as f:
                    wsIntOptions = json.load(f).keys()

                options = [discord.SelectOption(label=wsName) for wsName in wsIntOptions]
                view = self.generateSelectView(options, True, event["map"], eventMsg, "Link event to a workshop.", "edit_select_linking")
                await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

            # Editing Description
            elif selectedValue == "Description":
                modal = ScheduleModal(self, "Description", "modal_description", eventMsg)
                modal.add_item(discord.ui.TextInput(style=discord.TextStyle.long, label="Description", default=event["description"], placeholder="Bomb oogaboogas", min_length=1, max_length=4000))
                await interaction.response.send_modal(modal)

            # Editing URL
            elif selectedValue == "External URL":
                modal = ScheduleModal(self, "External URL", "modal_externalURL", eventMsg)
                modal.add_item(discord.ui.TextInput(style=discord.TextStyle.long, label="URL", default=event["externalURL"], placeholder="OPORD: https://www.gnu.org/", max_length=1024, required=False))
                await interaction.response.send_modal(modal)

            # Editing Reservable Roles
            elif selectedValue == "Reservable Roles":
                modal = ScheduleModal(self, "Reservable Roles", "modal_reservableRoles", eventMsg)
                modal.add_item(discord.ui.TextInput(style=discord.TextStyle.long, label="Reservable Roles", default=(None if event["reservableRoles"] is None else "\n".join(event["reservableRoles"].keys())), placeholder="Co-Zeus\nActual\nJTAC\nF-35A Pilot", max_length=512, required=False))
                await interaction.response.send_modal(modal)

            # Editing Map
            elif selectedValue == "Map":
                options = [discord.SelectOption(label=mapName) for mapName in MAPS]
                view = self.generateSelectView(options, True, event["map"], eventMsg, "Select a map.", "edit_select_map")
                await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)

            # Editing Attendence
            elif selectedValue == "Max Players":
                modal = ScheduleModal(self, "Attendees", "modal_maxPlayers", eventMsg)
                modal.add_item(discord.ui.TextInput(label="Attendees", default=event["maxPlayers"], placeholder="Number / None / Anonymous / Hidden", min_length=1, max_length=9))
                await interaction.response.send_modal(modal)

            # Editing Duration
            elif selectedValue == "Duration":
                modal = ScheduleModal(self, "Duration", "modal_duration", eventMsg)
                modal.add_item(discord.ui.TextInput(label="Duration", default=event["duration"], placeholder="2h30m", min_length=1, max_length=16))
                await interaction.response.send_modal(modal)

            # Editing Time
            elif selectedValue == "Time":
                # Set user time zone
                with open(MEMBER_TIME_ZONES_FILE) as f:
                    memberTimeZones = json.load(f)
                if str(interaction.user.id) not in memberTimeZones:
                    await interaction.response.send_message("Please retry after you've set a time zone in DMs!", ephemeral=True, delete_after=60.0)
                    timeZoneOutput = await self.changeTimeZone(interaction.user)
                    if timeZoneOutput is False:
                        await interaction.followup.send(embed=Embed(title="❌ Event Editing canceled", description="You must provide a time zone in your DMs!", color=Color.red()))
                    return

                # Send modal
                timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
                modal = ScheduleModal(self, "Time", "modal_time", eventMsg)
                modal.add_item(discord.ui.TextInput(label="Time", default=datetimeParse(event["time"]).replace(tzinfo=UTC).astimezone(timeZone).strftime(TIME_FORMAT), placeholder="2069-04-20 04:20 PM", min_length=1, max_length=32))
                await interaction.response.send_modal(modal)

            log.info(f"{interaction.user.display_name} ({interaction.user}) edited the event: {event['title'] if 'title' in event else event['templateName']}.")

        # All select menu options in edit_select
        elif select.custom_id.startswith("edit_select_"):
            with open(EVENTS_FILE) as f:
                events = json.load(f)

            eventKey = select.custom_id[len("edit_select_"):].split("_REMOVE")[0]
            eventValue = None if selectedValue == "None" else selectedValue

            event = [event for event in events if event["messageId"] == eventMsg.id][0]
            event[eventKey] = eventValue

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)

            await eventMsg.edit(embed=self.getEventEmbed(event))
            await interaction.response.send_message(embed=Embed(title="✅ Event edited", color=Color.green()), ephemeral=True, delete_after=5.0)

    async def modalHandling(self, modal: discord.ui.Modal, interaction: discord.Interaction, eventMsg: discord.Message, view: discord.ui.View | None) -> None:
        if not isinstance(interaction.user, discord.Member):
            log.exception("Schedule modalHandling: interaction.user is not discord.Member")
            return
        value = modal.children[0].value.strip()

        # == Creating Event ==

        if modal.custom_id.startswith("modal_create_") and view is not None:
            infoLabel = modal.custom_id[len("modal_create_"):]

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
                        startTime = datetimeParse(value)
                    except Exception:
                        await interaction.response.send_message(interaction.user.mention, embed=EMBED_INVALID, ephemeral=True, delete_after=10.0)
                        return

                    # Set time
                    startTime = timeZone.localize(startTime).astimezone(pytz.utc)
                    previewEmbedDict["time"] = startTime.strftime(TIME_FORMAT)
                    previewEmbedDict["endTime"] = None
                    # Set endTime if duration available
                    if previewEmbedDict["duration"] is not None:
                        hours, minutes, delta = self.getDetailsFromDuration(previewEmbedDict["duration"])
                        previewEmbedDict["endTime"] = (startTime + delta).strftime(TIME_FORMAT)

                case "external_url":
                    previewEmbedDict["externalURL"] = value or None

                case "reservable_roles":
                    previewEmbedDict["reservableRoles"] = None if value == "" else {role.strip(): None for role in value.split("\n") if role.strip() != ""}
                    if len(previewEmbedDict["reservableRoles"]) > 20:
                        previewEmbedDict["reservableRoles"] = None
                        await interaction.response.send_message(embed=Embed(title="❌ Too many roles", description=f"Due to Discord character limitation, we've set the cap to 20 roles.\nLink your order, e.g. OPORD, under URL if you require more flexibility.\n\nYour roles:\n{value}"[:4096], color=Color.red()), ephemeral=True, delete_after=10.0)
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
                    jsonCreateNoExist(filename, [])
                    with open(filename) as f:
                        templates = json.load(f)
                    templateOverwritten = (False, 0)
                    for idx, template in enumerate(templates):
                        if template["templateName"] == previewEmbedDict["templateName"]:
                            templateOverwritten = (True, idx)
                            break
                    log.info(f"{interaction.user} saved {('[Overwritten] ') * templateOverwritten[0]}a template as: {previewEmbedDict['templateName']}")
                    if templateOverwritten[0]:
                        templates.pop(templateOverwritten[1])
                    for shit in SCHEDULE_TEMPLATE_REMOVE_FROM_EVENT:
                        previewEmbedDict.pop(shit, None)

                    templates.append(previewEmbedDict)
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
                await interaction.response.send_message(embed=Embed(title="❌ Too many roles", description=f"Due to Discord character limitation, we've set the cap to 20 roles.\nLink your order, e.g. OPORD, under URL if you require more flexibility.\n\nYour roles:\n{value}"[:4096], color=Color.red()), ephemeral=True, delete_after=10.0)
                return

            # No res roles or all roles are unoccupied
            elif event["reservableRoles"] is None or all([id is None for id in event["reservableRoles"].values()]):
                event["reservableRoles"] = {role: None for role in reservableRoles}

            # Res roles are set and some occupied
            else:
                event["reservableRoles"] = {role: event["reservableRoles"][role] if role in event["reservableRoles"] else None for role in reservableRoles}

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
                log.exception("editEvent: guild is None")
                return None

            previewEmbed = Embed(title=f":clock3: The starting time has changed for: {event['title']}!", description=f"From: {discord.utils.format_dt(UTC.localize(datetime.strptime(startTimeOld, TIME_FORMAT)), style='F')}\n\u2000\u2000To: {discord.utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}", color=Color.orange())
            previewEmbed.add_field(name="\u200B", value=eventMsg.jump_url, inline=False)
            previewEmbed.set_footer(text=f"By: {interaction.user}")
            for memberId in event["accepted"] + event["declined"] + event["tentative"]:
                member = guild.get_member(memberId)
                if member is not None:
                    try:
                        await member.send(embed=previewEmbed)
                    except Exception as e:
                        log.exception(f"{member} | {e}")

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)

            # === Reorder events ===
            # Save message ID order
            msgIds = []
            for eve in events:
                msgIds.append(eve["messageId"])

            # Sort events
            sortedEvents = sorted(events, key=lambda e: datetime.strptime(e["time"], TIME_FORMAT), reverse=True)

            schedule = await guild.fetch_channel(SCHEDULE)
            if not isinstance(schedule, discord.channel.TextChannel):
                log.exception("ModalHandling: schedule is not discord.channel.TextChannel")
                return

            anyEventChange = False
            for idx, eve in enumerate(sortedEvents):
                # If msg is in a different position
                if eve["messageId"] != msgIds[idx]:
                    anyEventChange = True
                    eve["messageId"] = msgIds[idx]

                    # Edit msg to match position
                    msg = await schedule.fetch_message(msgIds[idx])
                    await msg.edit(embed=self.getEventEmbed(sortedEvents[idx]), view=self.getEventView(sortedEvents[idx]))

            if anyEventChange is False:
                msg = await schedule.fetch_message(event["messageId"])
                await msg.edit(embed=self.getEventEmbed(event), view=self.getEventView(event))


            with open(EVENTS_FILE, "w") as f:
                json.dump(sortedEvents, f, indent=4)
            await interaction.response.send_message(interaction.user.mention, embed=Embed(title="✅ Event edited", color=Color.green()), ephemeral=True, delete_after=5.0)
            return


        else:
            event[modal.custom_id[len("modal_"):]] = value

        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)

        await eventMsg.edit(embed=self.getEventEmbed(event), view=self.getEventView(event))
        await interaction.response.send_message(interaction.user.mention, embed=Embed(title="✅ Event edited", color=Color.green()), ephemeral=True, delete_after=5.0)

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
            "Time"
        )
        log.info(f"{interaction.user.display_name} ({interaction.user}) is editing the event: {event['title']}")
        options = []
        for editOption in editOptions:
            options.append(discord.SelectOption(label=editOption))

        view = ScheduleView()
        view.add_item(ScheduleSelect(instance=self, eventMsg=eventMsg, placeholder="Select what to edit.", minValues=1, maxValues=1, customId="edit_select", row=0, options=options))

        await interaction.response.send_message(view=view, ephemeral=True, delete_after=60.0)


# ===== </Schedule Functions> =====


# ===== <Event> =====

    @discord.app_commands.command(name="bop")
    @discord.app_commands.guilds(GUILD)
    async def scheduleOperation(self, interaction: discord.Interaction) -> None:
        """Create an operation to add to the schedule."""
        await self.scheduleEventInteraction(interaction, "Operation")

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
        log.info(f"{interaction.user.display_name} ({interaction.user}) is creating an {preselectedType.lower()}...")

        previewDict = {
            "authorId": interaction.user.id,
            "type": preselectedType
        }
        view = self.fromDictToPreviewView(previewDict, "None")

        embed=Embed(title=SCHEDULE_EVENT_PREVIEW_EMBED["title"], description=SCHEDULE_EVENT_PREVIEW_EMBED["description"], color=EVENT_TYPE_COLORS[preselectedType])
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        embed.set_footer(text=f"Created by {interaction.user.display_name}")
        await interaction.response.send_message("Schedule an event using the buttons, and get a live preview!", embed=embed, view=view)


# ===== </Event> =====


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
            await interaction.response.send_message(embed=Embed(title="❌ Invalid time", description="Provide a valid time!", color=Color.red()), ephemeral=True)
            return

        await interaction.response.defer()

        if not timezone:  # User's time zone
            # Get user time zone
            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)

            if not str(interaction.user.id) in memberTimeZones:
                timeZoneOutput = await self.changeTimeZone(interaction.user, isCommand=False)
                if not timeZoneOutput:
                    await self.cancelCommand(await self.checkDMChannel(interaction.user), "Timestamp creation")
                    await interaction.edit_original_response(embed=Embed(title="❌ Timestamp creation canceled", description="You must provide a time zone in your DMs!", color=Color.red()))
                    return
                with open(MEMBER_TIME_ZONES_FILE) as f:
                    memberTimeZones = json.load(f)
            timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])

        else:  # Custom time zone
            try:
                timeZone = pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                await interaction.edit_original_response(embed=Embed(title="❌ Invalid time zone", description="Provide a valid time zone!", color=Color.red()))
                return

        # Output timestamp
        timeParsed = timeZone.localize(timeParsed)
        await interaction.edit_original_response(content = f"{message} {discord.utils.format_dt(timeParsed, 'F')}")
        if informative is not None:
            embed = Embed(color=Color.green())
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
        """Change your time zone preferences for your next scheduled event. """
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
        log.info(f"{author.display_name} ({author}) is updating their time zone preferences...")

        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        timezoneOk = False
        color = Color.gold()
        while not timezoneOk:
            embed = Embed(
                title=":clock1: What's your preferred time zone?",
                description=(f"Your current time zone preference is `{memberTimeZones[str(author.id)]}`." if str(author.id) in memberTimeZones else "You don't have a preferred time zone set.") + "\n\nEnter a number from the list below.\nEnter any time zone name from the column \"**TZ DATABASE NAME**\" in this [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)." + "\nEnter `none` to erase current preferences." * isCommand,
                color=color
            )
            embed.add_field(name="Popular Time Zones", value="\n".join(f"**{idx}.** {tz}" for idx, tz in enumerate(TIME_ZONES, 1)))
            embed.set_footer(text="Enter `cancel` to abort this command.")
            color = Color.red()
            try:
                msg = await author.send(embed=embed)
            except Exception as e:
                log.exception(f"{author} | {e}")
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
                await dmChannel.send(embed=EMBED_TIMEOUT)
                return False

        with open(MEMBER_TIME_ZONES_FILE, "w") as f:
            json.dump(memberTimeZones, f, indent=4)
        embed = Embed(title=f"✅ Time zone preferences changed!", description=f"Updated to `{timeZone.zone}`!" if isInputNotNone else "Preference removed!", color=Color.green())
        await dmChannel.send(embed=embed)
        return True

# ===== </Change Time Zone> =====


# ===== <Views and Buttons> =====

class ScheduleView(discord.ui.View):
    """Handling all schedule views."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = None

class ScheduleButton(discord.ui.Button):
    """Handling all schedule buttons."""
    def __init__(self, instance, message: discord.Message | None, authorId: int | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.message = message
        self.authorId = authorId

    async def callback(self, interaction: discord.Interaction):
        await self.instance.buttonHandling(self.message, self, interaction, self.authorId)

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
        # try:
        await self.instance.modalHandling(self, interaction, self.eventMsg, self.view)
        # except Exception as e:
        #     log.exception(f"Modal Handling Failed\n{e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        # await interaction.response.send_message("Something went wrong. cope.", ephemeral=True)
        log.exception(error)

# ===== </Views and Buttons> =====


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Schedule(bot))
