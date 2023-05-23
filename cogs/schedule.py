import os, re, json, asyncio, random, discord
import pytz  # type: ignore

from math import ceil
from copy import deepcopy
from datetime import datetime, timedelta
from dateutil.parser import parse as datetimeParse  # type: ignore

from discord import Embed, Color
from discord.ext import commands, tasks  # type: ignore

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
    "Archipelago",
    "Bukovina",
    "Bystrica",
    "Chernarus (Autumn)",
    "Chernarus (Summer)",
    "Chernarus (Winter)",
    "Colombia",
    "Desert",
    "Hellanmaa",
    "Hellanmaa winter",
    "Kunduz, Afghanistan",
    "Livonia",
    "Malden 2035",
    "Mutambara",
    "Niakala",
    "Porto",
    "Proving Grounds",
    "Pulau",
    "Rahmadi",
    "Sahrani",
    "Sanagasta, Pampa de la Viuda, La rioja, Argentina",
    "Shapur",
    "Southern Sahrani",
    "Stratis",
    "Takistan",
    "Takistan Mountains",
    "Tanoa",
    "United Sahrani",
    "Utes",
    "Virolahti",
    "Virtual Reality",
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

SCHEDULE_EVENT_VIEW = {
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

    "Linking": {  # Type == ws
        "required": True,
        "row": 2,
        "startDisabled": True,
        "customStyle": None
    },
    "Select Template: None": {  # Type in "(workshop", "event")
        "required": False,
        "row": 2,
        "startDisabled": True,
        "customStyle": None
    },
    "Save As Template": {  # Type in "(workshop", "event")
        "required": False,
        "row": 2,
        "startDisabled": True,
        "customStyle": None
    },
    "Update Template": {  # Type in "(workshop", "event") and Select Template is True
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
    """ Creates a JSON file with a dump if not exist.

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
jsonCreateNoExist(WORKSHOP_TEMPLATES_DELETED_FILE, [])
jsonCreateNoExist(REMINDERS_FILE, {})

try:
    with open("./.git/logs/refs/heads/main") as f:
        commitHash = f.readlines()[-1].split()[1][:7]  # The commit hash that the bot is running on (last line, second column, first 7 characters)
except Exception as e:
    log.exception(e)


class Schedule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Schedule"), flush=True)
        cogsReady["schedule"] = True

        await self.updateSchedule()
        if not self.tenMinTask.is_running():
            self.tenMinTask.start()

    async def cancelCommand(self, channel: discord.DMChannel, abortText: str) -> None:
        """ Sends an abort response to the user.

        Parameters:
        channel (discord.DMChannel): The users DM channel where the message is sent.
        abortText (str): The embed title - what is aborted.

        Returns:
        None.
        """
        await channel.send(embed=Embed(title=f"❌ {abortText} canceled!", color=Color.red()))

    async def checkDMChannel(self, user: discord.User | discord.Member) -> discord.channel.DMChannel:
        return await user.create_dm() if user.dm_channel is None else user.dm_channel

    async def saveEventToHistory(self, event, autoDeleted=False) -> None:
        """ Saves a specific event to history.

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
                workshopInterest = json.load(f)
            if (workshop := workshopInterest.get(workshopInterestName)) is not None:
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
                        json.dump(workshopInterest, f, indent=4)
                    embed = self.bot.get_cog("WorkshopInterest").getWorkshopEmbed(guild, workshopInterestName)
                    workshopMessage = await self.bot.get_channel(WORKSHOP_INTEREST).fetch_message(workshop["messageId"])
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
        """ 10 minute interval tasks.

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
            utcNow = UTC.localize(datetime.utcnow())
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
            utcNow = UTC.localize(datetime.utcnow())

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
    @discord.app_commands.checks.has_any_role(UNIT_STAFF, SERVER_HAMSTER, CURATOR)
    async def refreshSchedule(self, interaction: discord.Interaction) -> None:
        """ Refreshes the schedule - Use if an event was deleted without using the reaction.

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
        """ refreshSchedule errors - dedicated for the discord.app_commands.errors.MissingAnyRole error.

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
            await interaction.response.send_message(embed=embed)

# ===== </Refresh Schedule> =====


# ===== <Schedule Functions> =====

    async def updateSchedule(self) -> None:
        """ Updates the schedule channel with all messages.

        Parameters:
        None.

        Returns:
        None.
        """
        self.lastUpdate = datetime.utcnow()
        channel = self.bot.get_channel(SCHEDULE)
        if channel is None or not isinstance(channel, discord.channel.TextChannel):
            log.exception("updateSchedule: channel invalid type")
            return

        await channel.purge(limit=None, check=lambda m: m.author.id in FRIENDLY_SNEKS)

        await channel.send(f"__Welcome to the schedule channel!__\n🟩 Schedule operations: `/operation` (`/bop`)\n🟦 Workshops: `/workshop` (`/ws`)\n🟨 Generic events: `/event`\n\nThe datetime you see in here are based on __your local time zone__.\nChange timezone when scheduling events with `/changetimezone`.\n\nSuggestions/bugs contact: {', '.join([f'**{developerName.display_name}**' for name in DEVELOPERS if (developerName := channel.guild.get_member(name)) is not None])} -- <https://github.com/Sigma-Security-Group/FriendlySnek> `{commitHash}`")

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
        """ Generates an embed from the given event.

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
        """  """
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
        """ """
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

        fieldValue = "-" if previewDict["maxPlayers"] is None else "\u200B"
        embed.add_field(name=f"Accepted (0{fieldNameNumberSuffix}) ✅", value=fieldValue, inline=True)
        embed.add_field(name=f"Declined (0) ❌", value=fieldValue, inline=True)
        embed.add_field(name=f"Tentative (0) ❓", value=fieldValue, inline=True)

        return embed

    @staticmethod
    def isAllowedToEdit(user: discord.Member, eventAuthorId: int) -> bool:
        """  """
        return user.id == eventAuthorId or any(role.id == UNIT_STAFF or role.id == SERVER_HAMSTER for role in user.roles)


    async def buttonHandling(self, message: discord.Message | None, button: discord.ui.Button, interaction: discord.Interaction, authorId: int | None) -> None:
        """ Handling all schedule button interactions.

        Parameters:
        message (discord.Message | None): If the message is provided, it's used along with some specific button action.
        button (discord.ui.Button): The Discord button.
        interaction (discord.Interaction): The Discord interaction.
        authorId (int | None): ID of user who executed the command.

        Returns:
        None.
        """
        if isinstance(interaction.user, discord.User):
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

                embed = Embed(title=SCHEDULE_EVENT_CONFIRM_DELETE.format(f"{event['type'].lower()}: `{event['title']}`"), color=Color.orange())
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
                    utcNow = UTC.localize(datetime.utcnow())
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
                """
                -Type: Dropdown
                -Title: Modal
                -Description: Modal
                -Duration: Modal
                -Time: Modal

                -External URL: Modal
                -Reservable Roles: Modal
                -Map: Dropdowns
                -Max Players: Modal

                -Linking: Dropdowns
                    -AVAILABLE IF TYPE=(WS)
                    -IN EMBED: AUTHOR NAME OR SOME LINK
                Select Template: Dropdowns
                    AVAILABLE IF TYPE=(WS/EVENT)
                    GENERATE_SELECT_VIEW
                    WHEN SELECTED, REMOVE ALL PROGRESS ON ANY EMBED CREATED, OVERWRITE WITH TEMPLATE
                Save As Template: Modal (different template name)
                    AVAILABLE IF TYPE=(WS/EVENT)
                [UPDATE TEMPLATE]
                    IF TEMPLATE HAS BEEN SELECTED
                    SHOW SELECTED TEMPLATE, APPEND NAME AFTER "SAVE AS TEMPLATE"

                -Submit
                    FROM_EMBED_TO_DICT
                -Cancel
                    (are you sure?)

                * Not author cannot interact with event [TEST]
                """
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
                        placeholder = "Wazzup beijing" if previewEmbedDict["description"] == SCHEDULE_EVENT_PREVIEW_EMBED["description"] else previewEmbedDict["description"]
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
                        nextHalfHour = datetime.utcnow() + (datetime.min - datetime.utcnow()) % timedelta(minutes=30)

                        placeholder = UTC.localize(nextHalfHour).astimezone(timeZone).strftime(TIME_FORMAT)
                        default = ""

                        if previewEmbedDict["time"] is not None:
                            default = placeholder = datetimeParse(previewEmbedDict["time"]).replace(tzinfo=pytz.utc).astimezone(timeZone).strftime(TIME_FORMAT)

                        await interaction.response.send_modal(generateModal(
                            style=discord.TextStyle.short,
                            placeholder=placeholder,
                            default=default,
                            required=True,
                            minLength=1,
                            maxLength=64
                        ))

                    case "external_url":
                        placeholder = "https://www.gnu.org" if previewEmbedDict["externalURL"] is None else previewEmbedDict["externalURL"]
                        default = "" if previewEmbedDict["externalURL"] is None else previewEmbedDict["externalURL"]
                        await interaction.response.send_modal(generateModal(discord.TextStyle.short, placeholder, default, False, None, 1024))

                    case "reservable_roles":
                        placeholder = "Actual\n2IC\nA-10C Pilot"
                        default = ""
                        if previewEmbedDict["reservableRoles"] is not None:
                            default = placeholder = "\n".join(previewEmbedDict["reservableRoles"])

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

                        previewEmbedDict["authorId"] = interaction.user.id
                        previewEmbedDict["templateName"] = templateName
                        previewEmbedDict["time"] = previewEmbedDict["endTime"] = None
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
                        await interaction.response.edit_message(content="Nvm guys, didn't wanna bop.", embed=None, view=None)


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
        """ Generates good select menu view - ceil(len(options)/25) dropdowns.

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

        if noneOption is True:
            options.insert(0, discord.SelectOption(label="None", emoji="🚫"))

        # Generate view
        view = ScheduleView()
        for i in range(ceil(len(options) / 25)):
            view.add_item(ScheduleSelect(instance=self, eventMsg=eventMsg, placeholder=placeholder, minValues=1, maxValues=1, customId=f"{customId}_REMOVE{i}", row=i, options=options[:25], eventMsgView=eventMsgView))
            options = options[25:]

        return view

    async def selectHandling(self, select: discord.ui.Select, interaction: discord.Interaction, eventMsg: discord.Message, eventMsgView: discord.ui.View | None) -> None:
        """ Handling all schedule select menu interactions.

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

            # Update eventMsg button style
            for child in eventMsgView.children:
                if isinstance(child, discord.ui.Button) and child.label is not None and child.label.lower().replace(" ", "_") == infoLabel:
                    child.style = discord.ButtonStyle.success
                    break

            # Do preview embed edits
            if infoLabel == "type":
                permittedEventTypesForTemplates = ("Workshop", "Event")
                previewEmbedDict["type"] = selectedValue
                for child in eventMsgView.children:
                    if not isinstance(child, discord.ui.Button) or child.label is None:
                        log.exception("Schedule selectHandling: not isinstance(child, discord.ui.Button) or child.label is None")
                        return


                    # (Un)lock buttons depending on current event type
                    if child.label == "Linking":
                        child.disabled = (selectedValue != "Workshop")
                        continue


                    if child.label.startswith("Select Template"):
                        # Quick disable if not permitted event type
                        if selectedValue not in permittedEventTypesForTemplates:
                            child.disabled = True
                            continue

                        # Disable if no templates exist
                        filename = f"data/{selectedValue.lower()}Templates.json"
                        jsonCreateNoExist(filename, [])
                        with open(filename) as f:
                            templates = json.load(f)
                        child.disabled = len(templates) == 0


                    if child.label == "Save As Template":
                        child.disabled = (selectedValue not in permittedEventTypesForTemplates)
                        continue


                    # Derive "Update Template" disabled attribute from Select Template name (if one has been selected)
                    if child.label == "Update Template":
                        for childv2 in eventMsgView.children:
                            if isinstance(childv2, discord.ui.Button) and childv2.label is not None and childv2.label.startswith("Select Template"):
                                child.disabled = ("".join(childv2.label.split(":")[1:]).strip() == "None")  # Text after colon (template selected)
                                break

            elif infoLabel == "map":
                if selectedValue == "None":
                    previewEmbedDict["map"] = None
                else:
                    previewEmbedDict["map"] = selectedValue

            elif infoLabel == "linking":
                if selectedValue == "None":
                    previewEmbedDict["workshopInterest"] = None
                else:
                    previewEmbedDict["workshopInterest"] = selectedValue

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
            #dmChannel = interaction.user.dm_channel
            #if dmChannel is None:
            #    log.exception("SelectHandling: dmChannel is None")
            #    return

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
                modal.add_item(discord.ui.TextInput(style=discord.TextStyle.long, label="Reservable Roles", default=(None if event["reservableRoles"] is None else "\n".join(event["reservableRoles"].keys())), placeholder="Co-Zeus\nActual\nJTAC\nF-35A Pilot", max_length=500, required=False))
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
                modal.add_item(discord.ui.TextInput(label="Duration", default=event["duration"], placeholder="2h30m", min_length=1, max_length=256))
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
                modal.add_item(discord.ui.TextInput(label="Time", default=datetimeParse(event["time"]).replace(tzinfo=UTC).astimezone(timeZone).strftime(TIME_FORMAT), placeholder="2069-04-20 04:20 PM", min_length=1, max_length=256))
                await interaction.response.send_modal(modal)

            log.info(f"{interaction.user.display_name} ({interaction.user}) edited the event: {event['title'] if 'title' in event else event['name']}.")

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


    #@staticmethod
    #def updateField(embed: discord.Embed, fieldNameQuery:str, fieldNameUpdate: str, fieldValue: str, fieldInline: bool) -> tuple[str, int]:
    #    """ Update a specific embed field.

    #    Parameters:
    #    embed (discord.Embed): The Discord Embed
    #    fieldNameQuery (str): Field name to look for.
    #    fieldNameUpdate (str): Updated name.
    #    fieldValue (str): Updated value.
    #    fieldInline (bool): Updated inline.

    #    Returns:
    #    tule[str, int]: tuple[0] either "update" or "new" string, indicating field execution. tuple[1] field index. (NOTE: Execution "update" doesn't manipulate fields, only "new" does)
    #    """
    #    allFields = ("Reservable Roles", "Time", "Duration", "Map", "External URL", "Accepted", "Declined", "Tentative")

    #    # FIELD EXISTS
    #    for idx, embedField in enumerate(embed.fields):
    #        if embedField.name == "\u200B":
    #            continue

    #        #log.debug(f"updateField: {embedField.name}") ### DO NOT LOG THE NAME, RAISES CHARMAP ERROR FROM EMOJIS LMFAO
    #        if embedField.name is not None and embedField.name.startswith(fieldNameQuery):
    #            return ("update", idx)

    #    # FIELD DOESN'T EXIST
    #    else:
    #        # Count real fields in embed
    #        activeFieldInEmbedCount = 0
    #        for idx, allField in enumerate(allFields):
    #            if allField == fieldNameQuery:
    #                break
    #            for embedField in embed.fields:
    #                if embedField.name is not None and embedField.name.startswith(allField):
    #                    activeFieldInEmbedCount += 1
    #                    break

    #        # Add blank fields to count
    #        realFieldsRemaining = activeFieldInEmbedCount
    #        for embedField in embed.fields:
    #            if realFieldsRemaining == 0:
    #                break
    #            if embedField.name is not None and embedField.name != "\u200B":
    #                realFieldsRemaining -= 1
    #            elif embedField.name == "\u200B":
    #                activeFieldInEmbedCount += 1

    #        embed.insert_field_at(activeFieldInEmbedCount, name=fieldNameUpdate, value=fieldValue, inline=fieldInline)
    #        return ("new", activeFieldInEmbedCount)


    async def modalHandling(self, modal: discord.ui.Modal, interaction: discord.Interaction, eventMsg: discord.Message, view: discord.ui.View | None) -> None:
        if not isinstance(interaction.user, discord.Member):
            log.exception("Schedule modalHandling: interaction.user is not discord.Member")
            return
        value = modal.children[0].value.strip()

        # == Creating Event ==

        if modal.custom_id.startswith("modal_create_") and view is not None:
            infoLabel = modal.custom_id[len("modal_create_"):]
            # Update button style
            for child in view.children:
                if isinstance(child, discord.ui.Button) and child.label is not None and child.label.lower().replace(" ", "_") == infoLabel:
                    if value == "":
                        child.style = discord.ButtonStyle.danger if SCHEDULE_EVENT_VIEW[infoLabel.replace("_", " ").title().replace("Url", "URL")]["required"] else discord.ButtonStyle.secondary
                    else:
                        child.style = discord.ButtonStyle.success
                    break

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
                    except ValueError:
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
                    previewEmbedDict["reservableRoles"] = None if value == "" else {role: None for role in value.split("\n")}

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
                    # Write to file
                    filename = f"data/{previewEmbedDict['type'].lower()}Templates.json"
                    jsonCreateNoExist(filename, [])
                    with open(filename) as f:
                        templates = json.load(f)
                    templateOverwritten = (False, 0)
                    for idx, template in enumerate(templates):
                        if template["title"] == previewEmbedDict["title"]:
                            templateOverwritten = (True, idx)
                            break
                    if templateOverwritten[0]:
                        templates.pop(templateOverwritten[1])
                    previewEmbedDict["templateName"] = value
                    previewEmbedDict["time"] = previewEmbedDict["endTime"] = None
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
                        elif child.label == "Save As Template":
                            child.style = discord.ButtonStyle.secondary
                        elif child.label == "Update Template":
                            child.disabled = False

                    # Reply & edit msg
                    await interaction.response.send_message(f"✅ Saved {('[Overwritten] ') * templateOverwritten[0]}template as: `{value}`", ephemeral=True, delete_after=10.0)
                    await eventMsg.edit(view=view)
                    return

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
            if len(reservableRoles) > 25:
                await interaction.response.send_message(embed=Embed(title="❌ Ain't supporting over 25 roles bruh", color=Color.red()), ephemeral=True, delete_after=10.0)
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

    async def eventTitle(self, interaction: discord.Interaction, eventType: str, isOperation:bool = False) -> str | None:
        """ Handles the title part of scheduling an event.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        eventType (str): The type of event, e.g. Operation.
        isOperation (bool): If it's an operation (add description & name generation).

        Returns:
        str | None: str if title, None if error.
        """

        dmChannel = await self.checkDMChannel(interaction.user)
        color = Color.gold()
        while True:
            embed = Embed(title=f":pencil2: What is the title of your {eventType}?", description=None if isOperation is False else "Operation names should start with the word `Operation`.\nE.g. Operation Red Tide.\n\nEnter `regenerate` to renew the generated operation names.", color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)

            # Add generated operation names
            if isOperation is True:
                with open(OPERATION_NAME_ADJECTIVES) as f:
                    adjectives = f.readlines()
                    adj = [random.choice(adjectives).strip("\n") for _ in range(10)]

                with open(OPERATION_NAME_NOUNS) as f:
                    nouns = f.readlines()
                    nou = [random.choice(nouns).strip("\n") for _ in range(10)]

                titles = [f"{adj[i].capitalize()} {nou[i].capitalize()}" for i in range(10)]
                embed.add_field(name="Generated Operation Names", value="\n".join(titles))

            await dmChannel.send(embed=embed)
            color = Color.orange()
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                title = response.content.strip()
                if title.lower() == "cancel" or title == "":
                    await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                    return None
            except asyncio.TimeoutError:
                await dmChannel.send(embed=EMBED_TIMEOUT)
                return None

            if isOperation is False or title.lower() != "regenerate":
                return title.replace("\n", "")

    async def eventDescription(self, interaction: discord.Interaction, eventType: str, currentDesc: str = "") -> str | None:
        """ Handles the description part of scheduling an event.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        eventType (str): The type of event, e.g. Operation.
        currentDesc (str): Already set description; will be prompted.

        Returns:
        str | None: str if description, None if error.
        """

        dmChannel = await self.checkDMChannel(interaction.user)
        embed = Embed(title=":notepad_spiral: What is the description?", description=None if currentDesc == "" else f"Current description:\n```{currentDesc[:4000]}\n```", color=Color.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)

        try:
            response = await self.bot.wait_for("message", timeout=TIME_THIRTY_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
            description = response.content.strip()
            if description.lower() == "cancel":
                await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                return None
        except asyncio.TimeoutError:
            await dmChannel.send(embed=EMBED_TIMEOUT)
            return None

        return description

    async def eventURL(self, interaction: discord.Interaction, eventType: str) -> bool | str | None:
        """ Handles the URL part of scheduling an event.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        eventType (str): The type of event, e.g. Operation.

        Returns:
        bool | str | None: False if error, str if URL, None if no URL.
        """

        dmChannel = await self.checkDMChannel(interaction.user)
        embed = Embed(title=":notebook_with_decorative_cover: Enter `none` or a URL", description="E.g. Signup sheet, Briefing, OPORD, etc.", color=Color.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
            externalURL = response.content.strip()
            if externalURL.lower() == "cancel":
                await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                return False
            if externalURL.lower() == "none" or externalURL == "":
                return None
        except asyncio.TimeoutError:
            await dmChannel.send(embed=EMBED_TIMEOUT)
            return False

        return externalURL

    async def eventReserveRole(self, interaction: discord.Interaction, eventType: str, currentRoles: str | None = None, event: dict | None = None) -> bool | dict | None:
        """ Handles the reservable roles part of scheduling an event.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        eventType (str): The type of event, e.g. Operation.
        currentRoles (str | None): Already set roles; will be prompted.
        event (dict | None): Sent along with currentRoles.

        Returns:
        bool | dict | None: False if error, dict if roles (role names as keys), None if no roles.
        """

        dmChannel = await self.checkDMChannel(interaction.user)
        color = Color.gold()
        while True:
            embed = Embed(title="Reservable Roles", description="Enter `none` if there are none.\n\nOtherwise, type each reservable role in a new line (Shift + Enter)." + ("" if currentRoles is None else "\n(Editing the name of a role will make it vacant, but roles which keep their exact names will keep their reservations)."), color=color)
            if currentRoles is not None:
                embed.add_field(name="Current reservable roles", value=f"```txt\n{currentRoles}\n```")

            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                reservables = response.content.strip()
            except asyncio.TimeoutError:
                await dmChannel.send(embed=EMBED_TIMEOUT)
                return False

            if reservables.lower() == "cancel":
                await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                return False

            reservableRoles = None
            if reservables.lower() == "none" or reservables == "":
                return None

            reservableRoles = [role.strip() for role in reservables.split("\n") if len(role.strip()) > 0]

            if len(reservableRoles) > 25:
                await dmChannel.send(embed=Embed(description="bruh, tf u gonna do with that many roles? Up to 25 roles are supported.", color=Color.red()))
                return False

            # Values all None
            if currentRoles is None:
                return {role: None for role in reservableRoles}

            # Check event
            if event is None:
                log.exception("eventReserveRoles: event is None")
                return False

            # Save values when same keys
            return {role: event["reservableRoles"][role] if role in event["reservableRoles"] else None for role in reservableRoles}

    async def eventMap(self, interaction: discord.Interaction, eventType: str) -> bool | str | None:
        """ Handles the map part of scheduling an event.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        eventType (str): The type of event, e.g. Operation.

        Returns:
        bool | str | None: False if error, str if map, None if no map.
        """

        dmChannel = await self.checkDMChannel(interaction.user)
        color = Color.gold()
        while True:
            embed = Embed(title=":globe_with_meridians: Choose a map", description=f"Enter `none` or a number from **1** - **{len(MAPS)}**.", color=color)
            color = Color.red()
            embed.add_field(name="Map", value="\n".join(f"**{idx}.** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                eventMap = response.content.strip()
            except asyncio.TimeoutError:
                await dmChannel.send(embed=EMBED_TIMEOUT)
                return False

            if eventMap.lower() == "cancel":
                await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                return False
            if eventMap.isdigit() and 0 < int(eventMap) <= len(MAPS):
                return MAPS[int(eventMap) - 1]
            elif eventMap.lower() == "none" or eventMap == "":
                return None

    async def eventAttendance(self, interaction: discord.Interaction, eventType: str) -> bool | int | str | None:
        """ Handles the attendance part of scheduling an event.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        eventType (str): The type of event, e.g. Operation.

        Returns:
        bool | int | str | None: False if error, int if limit, str if other alternative, None if no limit.
        """

        dmChannel = await self.checkDMChannel(interaction.user)
        color = Color.gold()
        while True:
            embed = Embed(title=":family_man_boy_boy: What is the maximum number of attendees?", description="Enter a number to set a limit.\nEnter `none` to set no limit.\nEnter `anonymous` to count attendance anonymously.\nEnter `hidden` to not count attendance.", color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                maxPlayers = response.content.strip().lower()
            except asyncio.TimeoutError:
                await dmChannel.send(embed=EMBED_TIMEOUT)
                return False

            if maxPlayers == "cancel":
                await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                return False

            if maxPlayers == "none" or (maxPlayers.isdigit() and (int(maxPlayers) == 0 or int(maxPlayers) > MAX_SERVER_ATTENDANCE)):
                return None
            elif maxPlayers.isdigit():
                return int(maxPlayers)
            elif maxPlayers in ("anonymous", "hidden"):
                return maxPlayers

    def getDetailsFromDuration(self, duration: str) -> tuple:
        """ Extracts hours, minutes and delta time from user duration.

        Parameters:
        duration (str): A duration.

        Returns:
        tuple: tuple with hours, minutes, delta zipped.
        """

        hours = int(duration.split("h")[0].strip()) if "h" in duration else 0
        minutes = int(duration.split("h")[-1].replace("m", "").strip()) if duration.strip()[-1] != "h" else 0
        delta = timedelta(hours=hours, minutes=minutes)
        return hours, minutes, delta

    async def eventDuration(self, interaction: discord.Interaction) -> tuple | None:
        """ Handles the duration part of scheduling an event.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        tuple | None: tuple with (hours, minutes, delta) zipped. None if fail.
        """

        dmChannel = await self.checkDMChannel(interaction.user)
        color = Color.gold()
        duration = "INVALID INPUT"
        while not re.match(r"^\s*((([1-9]\d*)?\d\s*h(\s*([0-5])?\d\s*m?)?)|(([0-5])?\d\s*m))\s*$", duration):
            embed = Embed(title=f"What is the duration?", description="E.g.\n`30m`\n`2h`\n`4h 30m`\n`2h30`", color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                duration = response.content.strip().lower()

                if duration == "cancel":
                    await self.cancelCommand(dmChannel, f"Event scheduling")
                    return None
            except asyncio.TimeoutError:
                await dmChannel.send(embed=EMBED_TIMEOUT)
                return None


        # Change user time zone if needed
        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        if not str(interaction.user.id) in memberTimeZones:
            timeZoneOutput = await self.changeTimeZone(interaction.user, isCommand=False)
            if not timeZoneOutput:
                await self.cancelCommand(dmChannel, "Event scheduling")
                return None

        return self.getDetailsFromDuration(duration)

    async def eventTime(self, interaction: discord.Interaction, eventType: str, collidingEventTypes: tuple, delta: timedelta) -> tuple | None:
        """ Handles the time part of scheduling an event; prompts, collision, etc.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        eventType (str): The type of event, e.g. Operation.
        collidingEventTypes (tuple): A tuple of eventtypes that you want to collide with.
        delta (timedelta): Difference in time from start to end.

        Returns:
        tuple | None: A tuple which contains the (event start time and end time). None if fail.
        """

        dmChannel = await self.checkDMChannel(interaction.user)
        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)


        timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
        eventCollision = True
        while eventCollision:


            eventCollision = False
            while True:

                # Gets starttime of event
                color = Color.gold()
                while True:
                    embed = Embed(title=f"What is the time of the {eventType.lower()}?", description=SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(timeZone.zone), color=color)
                    utcNow = datetime.utcnow()
                    nextHalfHour = utcNow + (datetime.min - utcNow) % timedelta(minutes=30)
                    embed.add_field(name="Example", value=UTC.localize(nextHalfHour).astimezone(timeZone).strftime(TIME_FORMAT))
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    color = Color.red()
                    await dmChannel.send(embed=embed)
                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                        startTime = response.content.strip()
                        if startTime.lower() == "cancel" or startTime == "":
                            await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                            return None
                    except asyncio.TimeoutError:
                        await dmChannel.send(embed=EMBED_TIMEOUT)
                        return None
                    try:
                        startTime = datetimeParse(startTime)
                        break
                    except ValueError:
                        pass

                startTime = timeZone.localize(startTime).astimezone(UTC)
                if startTime > UTC.localize(utcNow):  # Set time is in the future
                    break

                # Set time is in the past
                if (delta := UTC.localize(utcNow) - startTime) > timedelta(hours=1) and delta < timedelta(days=1):  # Time is between 1 hour and one day ago.
                    newStartTime = startTime + timedelta(days=1)
                    embed = Embed(title="Time was detected to be in the past 24h and was set to tomorrow.", description=f"Input time: {discord.utils.format_dt(startTime, style='F')}.\nSelected time: {discord.utils.format_dt(newStartTime, style='F')}.", color=Color.orange())
                    await dmChannel.send(embed=embed)
                    startTime = newStartTime
                    break
                else:  # Set time older than 24 hours
                    embed = Embed(title="It appears that the selected time is in the past. Are you sure you want to set it to this?", description="Enter `yes` or `y` to keep this time.\nEnter anything else to change it to another time.", color=Color.orange())
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    await dmChannel.send(embed=embed)
                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, author=interaction.user, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                        keepStartTime = response.content.strip().lower()
                        if keepStartTime == "cancel" or keepStartTime == "":
                            await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                            return None
                    except asyncio.TimeoutError:
                        await dmChannel.send(embed=EMBED_TIMEOUT)
                        return None
                    if keepStartTime in ("yes", "y"):
                        break


            endTime = startTime + delta
            with open(EVENTS_FILE) as f:
                events = json.load(f)

            exitForLoop = False
            for event in events:
                if exitForLoop:
                    break

                while True:
                    if event.get("type", eventType) not in collidingEventTypes:
                        break
                    eventStartTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))  # Target event start time
                    eventEndTime = UTC.localize(datetime.strptime(event["endTime"], TIME_FORMAT))  # Target event end time
                    if (eventStartTime <= startTime < eventEndTime) or (eventStartTime <= endTime < eventEndTime) or (startTime <= eventStartTime < endTime):  # If scheduled event and target event overlap
                        eventCollision = True
                        embed = Embed(title=f"❌ This time collides with the event: `{event['title']}`!", description=SCHEDULE_EVENT_ERROR_DESCRIPTION, color=Color.red())
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        await dmChannel.send(embed=embed)
                    elif eventEndTime < startTime and eventEndTime + timedelta(hours=1) > startTime:
                        eventCollision = True
                        embed = Embed(title=f"❌ Your {eventType.lower()} would start less than an hour after `{event['title']}` ends!", description=SCHEDULE_EVENT_ERROR_DESCRIPTION, color=Color.red())
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        await dmChannel.send(embed=embed)
                    elif endTime < eventStartTime and endTime + timedelta(hours=1) > eventStartTime:
                        eventCollision = True
                        embed = Embed(title=f"❌ `{event['title'].lower()}` starts less than an hour after your event ends!", description=SCHEDULE_EVENT_ERROR_DESCRIPTION, color=Color.red())
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        await dmChannel.send(embed=embed)

                    if eventCollision is False:
                        break

                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                        collisionResponse = response.content.strip().lower()
                    except asyncio.TimeoutError:
                        await dmChannel.send(embed=EMBED_TIMEOUT)
                        return None

                    if collisionResponse == "cancel" or collisionResponse == "":
                        await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                        return None
                    elif collisionResponse == "edit":
                        exitForLoop = True
                        break
                    elif collisionResponse == "override":
                        eventCollision = False
                        exitForLoop = True
                        break

        return (startTime, endTime)

    async def eventFinalizing(self, interaction: discord.Interaction, newEvent: dict) -> bool:
        """ Handles the finalizing part of scheduling an event.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        newEvent (dict): The new event.

        Returns:
        bool: Function success
        """

        dmChannel = await self.checkDMChannel(interaction.user)

        # Update events file
        try:
            jsonCreateNoExist(EVENTS_FILE, [])
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            events.append(newEvent)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            log.exception(f"{interaction.user} | {e}")
            return False

        # Send verification to user
        embed = Embed(title=f"✅ {newEvent['type']} created!", color=Color.green())
        await dmChannel.send(embed=embed)
        log.info(f"{interaction.user.display_name} ({interaction.user}) created the operation: {newEvent['title']}")

        await self.updateSchedule()

        # Announce new bop
        for event in events:
            if event["title"] == newEvent["title"]:
                msgId = event["messageId"]
        await interaction.followup.send(f"`{newEvent['title']}` is now on [schedule](<https://discord.com/channels/{GUILD_ID}/{SCHEDULE}/{msgId}>)!")
        return True

    async def editEvent(self, interaction: discord.Interaction, event: dict, eventMsg: discord.Message) -> None:
        """ Edits a preexisting event.

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

    @discord.app_commands.command(name="event")
    @discord.app_commands.guilds(GUILD)
    async def scheduleEvent(self, interaction: discord.Interaction) -> None:
        """ Create an event to add to the schedule.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        log.info(f"{interaction.user.display_name} ({interaction.user}) is creating an event...")

        view = ScheduleView()
        for label, data in SCHEDULE_EVENT_VIEW.items():
            style = discord.ButtonStyle.danger if data["required"] is True else discord.ButtonStyle.secondary
            if data["customStyle"] is not None:
                style = data["customStyle"]
            view.add_item(ScheduleButton(
                self,
                None,
                interaction.user.id,
                style=style,
                label=label,
                custom_id=f"event_schedule_{label.lower().replace(' ', '_')}",
                row=data["row"],
                disabled=data["startDisabled"]
            ))

        embed=Embed(title=SCHEDULE_EVENT_PREVIEW_EMBED["title"], description=SCHEDULE_EVENT_PREVIEW_EMBED["description"])
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
        """ Convert your local time to a dynamic Discord timestamp.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        time (str): Inputted time to be converted.
        message (str): Optionally adding a message before the timestamp.
        timezone (str): Optional custom time zone, which is separate from the user set preferred time zone.
        informative (discord.app_commands.Choice[str]): If the user want's the informative embed - displaying all timestamps with desc, etc.

        Returns:
        None.
        """
        await interaction.response.defer()

        # Get the inputted time
        try:
            timeParsed = datetimeParse(time)
        except ValueError:
            await interaction.edit_original_response(embed=Embed(title="❌ Invalid time", description="Provide a valid time!", color=Color.red()))
            return

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
        """ Change your time zone preferences for your next scheduled event. """
        await interaction.response.send_message("Changing time zone preferences...")
        timeZoneOutput = await self.changeTimeZone(interaction.user, isCommand=True)
        if not timeZoneOutput:
            await self.cancelCommand(await self.checkDMChannel(interaction.user), "Time zone preferences")

    async def changeTimeZone(self, author: discord.User | discord.Member, isCommand: bool = True) -> bool:
        """ Changing a personal time zone.

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
            embed = Embed(title=":clock1: What's your preferred time zone?", description=(SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(memberTimeZones[str(author.id)]) if str(author.id) in memberTimeZones else "You don't have a preferred time zone set.") + "\n\nEnter a number from the list below.\nEnter any time zone name from the column \"**TZ DATABASE NAME**\" in this [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)." + "\nEnter `none` to erase current preferences." * isCommand, color=color)
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = None

class ScheduleButton(discord.ui.Button):
    def __init__(self, instance, message: discord.Message | None, authorId: int | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.message = message
        self.authorId = authorId

    async def callback(self, interaction: discord.Interaction):
        await self.instance.buttonHandling(self.message, self, interaction, self.authorId)

class ScheduleSelect(discord.ui.Select):
    def __init__(self, instance, eventMsg: discord.Message, placeholder: str, minValues: int, maxValues: int, customId: str, row: int, options: list[discord.SelectOption], disabled: bool = False, eventMsgView: discord.ui.View | None = None, *args, **kwargs):
        super().__init__(placeholder=placeholder, min_values=minValues, max_values=maxValues, custom_id=customId, row=row, options=options, disabled=disabled, *args, **kwargs)
        self.eventMsg = eventMsg
        self.instance = instance
        self.eventMsgView = eventMsgView

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.instance.selectHandling(self, interaction, self.eventMsg, self.eventMsgView)

class ScheduleModal(discord.ui.Modal):
    def __init__(self, instance, title: str, customId: str, eventMsg: discord.Message, view: discord.ui.View | None = None) -> None:
        super().__init__(title=title, custom_id=customId)
        self.instance = instance
        self.eventMsg = eventMsg
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        await self.instance.modalHandling(self, interaction, self.eventMsg, self.view)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message("Something went wrong. cope.", ephemeral=True)

        log.exception(error)

# ===== </Views and Buttons> =====


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Schedule(bot))
