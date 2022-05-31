from secret import DEBUG
import asyncio
import json
import os
import re
import pytz
import random

from copy import deepcopy
from datetime import datetime, timedelta
from dateutil.parser import parse as datetimeParse

import discord
from discord import app_commands, Embed, Color, utils
from discord.ext import commands, tasks

from constants import *
from __main__ import log, cogsReady
if DEBUG:
    from constants.debug import *


TIMEOUT_EMBED = Embed(title=ERROR_TIMEOUT, color=Color.red())

EVENTS_FILE = "data/events.json"
MEMBER_TIME_ZONES_FILE = "data/memberTimeZones.json"
EVENTS_HISTORY_FILE = "data/eventsHistory.json"
WORKSHOP_TEMPLATES_FILE = "data/workshopTemplates.json"
WORKSHOP_TEMPLATES_DELETED_FILE = "data/workshopDeletedTemplates.json"
WORKSHOP_INTEREST_FILE = "data/workshopInterest.json"

OPERATION_NAME_ADJECTIVES = "constants/opAdjectives.txt"
OPERATION_NAME_NOUNS = "constants/opNouns.txt"

MAX_SERVER_ATTENDANCE = 50

# Training map first, then the rest in alphabetical order
MAPS = [
    "Training Map",
    "Al Salman, Iraq",
    "Altis",
    "Anizay",
    "Chernarus",
    "Desert",
    "Fapovo",
    "Hellanmaa Winter",
    "Hellanmaa",
    "Isla Abramia",
    "Kidal",
    "Kujari",
    "Kunduz",
    "Laghisola",
    "Lingor/Dingor Island",
    "Livonia",
    "Malden 2035",
    "Porto",
    "Pulau",
    "Sahrani",
    "Shapur",
    "Stratis",
    "Takistan",
    "Tanoa",
    "Utes",
    "Uzbin Valley",
    "Vinjesvingen",
    "Virolahti",
    "Zargabad",
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
    "Australian Eastern Time (Sydney)": "Australia/Sydney",
}

TIMESTAMP_STYLES = {
    "t": "Short Time",
    "T": "Long Time",
    "d": "Short Date",
    "D": "Long Date",
    "f": "Short Date Time",
    "F": "Long Date Time",
    "R": "Relative Time",
}

if not os.path.exists(EVENTS_HISTORY_FILE):
    with open(EVENTS_HISTORY_FILE, "w") as f:
        json.dump([], f, indent=4)

if not os.path.exists(WORKSHOP_TEMPLATES_FILE):
    with open(WORKSHOP_TEMPLATES_FILE, "w") as f:
        json.dump([], f, indent=4)

if not os.path.exists(WORKSHOP_TEMPLATES_DELETED_FILE):
    with open(WORKSHOP_TEMPLATES_DELETED_FILE, "w") as f:
        json.dump([], f, indent=4)


class Schedule(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Schedule"), flush=True)
        cogsReady["schedule"] = True

        await self.updateSchedule()
        try:
            self.autoDeleteEvents.start()
        except Exception:
            log.warning(LOG_COULDNT_START.format("autoDeleteEvents scheduler"))
        try:
            self.checkAcceptedReminder.start()
        except Exception:
            log.warning(LOG_COULDNT_START.format("checkAcceptedReminder scheduler"))

    async def cancelCommand(self, channel: discord.DMChannel, abortText:str) -> None:
        """ Sends an abort response to the user.

        Parameters:
        channel (discord.DMChannel): The users DM channel where the message is sent.
        abortText (str): The embed title - what is aborted.

        Returns:
        None.
        """
        await channel.send(embed=Embed(title=f"❌ {abortText} canceled!", color=Color.red()))

    async def saveEventToHistory(self, event, autoDeleted=False) -> None:
        """ X.

        Parameters:
        event: X.
        autoDeleted (bool): X.

        Returns:
        None.
        """
        guild = self.bot.get_guild(GUILD_ID)
        if event.get("type", "Operation") == "Workshop":
            if (workshopInterestName := event.get("workshopInterest")) is not None:
                with open(WORKSHOP_INTEREST_FILE) as f:
                    workshopInterest = json.load(f)
                if (workshop := workshopInterest.get(workshopInterestName)) is not None:
                    accepted = event["accepted"]
                    if event["maxPlayers"] is not None:
                        accepted = accepted[:event["maxPlayers"]]
                    updateWorkshopInterest = False
                    for memberId in accepted:
                        if memberId in workshop["members"]:
                            updateWorkshopInterest = True
                            workshop["members"].remove(memberId)
                    if updateWorkshopInterest:
                        with open(WORKSHOP_INTEREST_FILE, "w") as f:
                            json.dump(workshopInterest, f, indent=4)
                        embed = self.bot.get_cog("WorkshopInterest").getWorkshopEmbed(workshop)
                        workshopMessage = await self.bot.get_channel(WORKSHOP_INTEREST).fetch_message(workshop["messageId"])
                        await workshopMessage.edit(embed=embed)

        with open(EVENTS_HISTORY_FILE) as f:
            eventsHistory = json.load(f)
        eventCopy = deepcopy(event)
        eventCopy["autoDeleted"] = autoDeleted
        eventCopy["authorName"] = member.display_name if (member := guild.get_member(eventCopy["authorId"])) is not None else "UNKNOWN"
        eventCopy["acceptedNames"] = [member.display_name if (member := guild.get_member(memberId)) is not None else "UNKNOWN" for memberId in eventCopy["accepted"]]
        eventCopy["declinedNames"] = [member.display_name if (member := guild.get_member(memberId)) is not None else "UNKNOWN" for memberId in eventCopy["declined"]]
        eventCopy["declinedForTimingNames"] = [member.display_name if (member := guild.get_member(memberId)) is not None else "UNKNOWN" for memberId in eventCopy.get("declinedForTiming", [])]
        eventCopy["tentativeNames"] = [member.display_name if (member := guild.get_member(memberId)) is not None else "UNKNOWN" for memberId in eventCopy["tentative"]]
        eventCopy["reservableRolesNames"] = {role: ((member.display_name if (member := guild.get_member(memberId)) is not None else "UNKNOWN") if memberId is not None else "VACANT") for role, memberId in eventCopy["reservableRoles"].items()} if eventCopy["reservableRoles"] is not None else {}
        eventsHistory.append(eventCopy)
        with open(EVENTS_HISTORY_FILE, "w") as f:
            json.dump(eventsHistory, f, indent=4)

    @tasks.loop(minutes=10)
    async def autoDeleteEvents(self) -> None:
        """ Check for old events and deletes them.

        Parameters:
        None.

        Returns:
        None.
        """
        while not self.bot.ready:
            await asyncio.sleep(1)
        log.debug(LOG_CHECKING.format("to auto delete events"))
        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            utcNow = UTC.localize(datetime.utcnow())
            deletedEvents = []
            for event in events:
                endTime = UTC.localize(datetime.strptime(event["endTime"], TIME_FORMAT))
                if utcNow > endTime + timedelta(minutes=69):
                    log.debug(f"Auto deleting: {event['title']}.")
                    deletedEvents.append(event)
                    eventMessage = await self.bot.get_channel(SCHEDULE).fetch_message(event["messageId"])
                    await eventMessage.delete()
                    # author = self.bot.get_guild(SERVER).get_member(event["authorId"])
                    # await self.bot.get_channel(ARMA_DISCUSSION).send(f"{author.mention} You silly goose, you forgot to delete your operation. I'm not your mother, but this time I will do it for you")
                    if event["maxPlayers"] != -1:  # Save events that does not have hidden attendance
                        await self.saveEventToHistory(event, autoDeleted=True)
            if len(deletedEvents) == 0:
                log.debug("No events were auto deleted!")
            for event in deletedEvents:
                events.remove(event)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            log.exception(e)

    @tasks.loop(minutes=10)
    async def checkAcceptedReminder(self) -> None:
        """ X.

        Parameters:
        None.

        Returns:
        None.
        """
        while not self.bot.ready:
            await asyncio.sleep(1)
        guild = self.bot.get_guild(GUILD_ID)
        log.debug(LOG_CHECKING.format("for accepted reminders"))
        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            utcNow = UTC.localize(datetime.utcnow())
            channel = self.bot.get_channel(ARMA_DISCUSSION)
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
                        log.debug(f"Pinging members in accepted not in VC: {', '.join([member.display_name for member in acceptedMembersNotOnline])}...")
                        await channel.send(" ".join(member.mention for member in acceptedMembersNotOnline) + f" If you are in-game, please get in <#{COMMAND}> or <#{DEPLOYED}>. If you are not making it to this {event['type'].lower()}, please hit decline ❌ on the <#{SCHEDULE}>.")
                    if len(onlineMembersNotAccepted) > 0:
                        log.debug(f"Pinging members in VC not in accepted: {', '.join([member.display_name for member in onlineMembersNotAccepted])}...")
                        await channel.send(" ".join(member.mention for member in onlineMembersNotAccepted) + f" If you are in-game, please hit accept ✅ on the <#{SCHEDULE}>.")
        except Exception as e:
            log.exception(e)

    @app_commands.command(name="refreshschedule")
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_any_role(UNIT_STAFF, SERVER_HAMSTER, CURATOR)
    async def refreshSchedule(self, interaction: discord.Interaction) -> None:
        """ Refreshes the schedule - Use if an event was deleted without using the reaction. """
        await interaction.response.send_message(f"Refreshing <#{SCHEDULE}>...")
        log.info(f"{interaction.user.display_name} ({interaction.user}) is refreshing the schedule...")
        await self.updateSchedule()

    @refreshSchedule.error
    async def onRefreshScheduleError(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """ refreshSchedule errors - dedicated for the discord.app_commands.errors.MissingAnyRole error.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        error (app_commands.AppCommandError): The end user error.

        Returns:
        None.
        """
        if type(error) == discord.app_commands.errors.MissingAnyRole:
            guild = self.bot.get_guild(GUILD_ID)
            embed = Embed(title="❌ Missing permissions", description=f"You do not have the permissions to refresh the schedule!\nThe permitted roles are: {', '.join([guild.get_role(role).name for role in (UNIT_STAFF, SERVER_HAMSTER, CURATOR)])}.", color=Color.red())
            await interaction.response.send_message(embed=embed)

    async def updateSchedule(self) -> None:
        """ Updates the schedule channel with all messages.

        Parameters:
        None.

        Returns:
        None.
        """
        self.lastUpdate = datetime.utcnow()
        channel = self.bot.get_channel(SCHEDULE)
        await channel.purge(limit=None, check=lambda m: m.author.id in FRIENDLY_SNEKS)

        row = discord.ui.View()
        row.timeout = None
        issueButton = ScheduleButtons(self, None, row=0, emoji="📩", label="Create Ticket", style=discord.ButtonStyle.secondary, custom_id="issues_and_suggestions")
        row.add_item(item=issueButton)

        await channel.send(f"Welcome to the schedule channel!\nTo schedule an operation you can use the `/operation` command (or `/bop`) and follow the instructions in your DMs.\nFor a workshop use `/workshop` or `/ws`.\nLastly, for generic events use `/event`.\n\nIf you haven't set a preferred time zone yet you will be prompted to do so when you schedule any kind of event. If you want to set, change or delete your time zone preference you may do so with the `/changetimezone` command.\n\nThe times you see on the schedule are based on __your local time zone__.\n\nThe event colors can be used to quickly identify what type of event it is:\n🟩 Operation `/operation` or `/bop`.\n🟦 Workshop `/workshop` or `/ws`.\n🟨 Event `/event`.\n\nGithub: <https://github.com/Sigma-Security-Group/FriendlySnek>.\n\nIf you have any suggestions for new features or encounter any bugs, please contact: {', '.join([f'**{channel.guild.get_member(name).display_name}**' for name in DEVELOPERS if channel.guild.get_member(name) is not None])} - or simply click the button below!", view=row)

        if os.path.exists(EVENTS_FILE):
            try:
                with open(EVENTS_FILE) as f:
                    events = json.load(f)
                if len(events) == 0:
                    await channel.send("...\nNo bop?\n...\nSnek is sad")
                    await channel.send(":cry:")
                for event in sorted(events, key=lambda e: datetime.strptime(e["time"], TIME_FORMAT), reverse=True):
                    embed = self.getEventEmbed(event)

                    row = discord.ui.View()
                    row.timeout = None
                    buttons = [
                        ScheduleButtons(self, None, row=0, label="Accept", style=discord.ButtonStyle.success, custom_id="accept"),
                        ScheduleButtons(self, None, row=0, label="Decline", style=discord.ButtonStyle.danger, custom_id="decline"),
                        ScheduleButtons(self, None, row=0, label="Decline (Time)", style=discord.ButtonStyle.danger, custom_id="declineForTiming"),
                        ScheduleButtons(self, None, row=0, label="Tentative", style=discord.ButtonStyle.primary, custom_id="tentative")
                    ]
                    if event["reservableRoles"] is not None:
                        buttons.append(ScheduleButtons(self, None, row=0, label="Reserve", style=discord.ButtonStyle.secondary, custom_id="reserve"))

                    buttons.extend([
                        ScheduleButtons(self, None, row=1, label="Edit", style=discord.ButtonStyle.secondary, custom_id="edit"),
                        ScheduleButtons(self, None, row=1, label="Delete", style=discord.ButtonStyle.secondary, custom_id="delete")
                    ])
                    [row.add_item(item=button) for button in buttons]

                    msg = await channel.send(embed=embed, view=row)
                    event["messageId"] = msg.id
                with open(EVENTS_FILE, "w") as f:
                    json.dump(events, f, indent=4)
            except Exception as e:
                log.exception(e)
        else:
            with open(EVENTS_FILE, "w") as f:
                json.dump([], f, indent=4)
        if not os.path.exists(MEMBER_TIME_ZONES_FILE):
            with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                json.dump({}, f, indent=4)

    def getEventEmbed(self, event) -> Embed:
        """ Generates an embed from the given event.

        Parameters:
        event: X.

        Returns:
        Embed.
        """
        guild = self.bot.get_guild(GUILD_ID)

        colors = {
            "Operation": Color.green(),
            "Workshop": Color.blue(),
            "Event": Color.gold()
        }
        embed = Embed(title=event["title"], description=event["description"], color=colors[event.get("type", "Operation")])

        if event["reservableRoles"] is not None:
            embed.add_field(name="\u200B", value="\u200B", inline=False)
            embed.add_field(name=f"Reservable Roles ({len([role for role, memberId in event['reservableRoles'].items() if memberId is not None])}/{len(event['reservableRoles'])}) 👤", value="\n".join(f"{roleName} - {('*' + member.display_name + '*' if (member := guild.get_member(memberId)) is not None else '**VACANT**') if memberId is not None else '**VACANT**'}" for roleName, memberId in event["reservableRoles"].items()), inline=False)
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        embed.add_field(name="Time", value=f"{utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')} - {utils.format_dt(UTC.localize(datetime.strptime(event['endTime'], TIME_FORMAT)), style='t')}", inline=False)
        embed.add_field(name="Duration", value=event["duration"], inline=False)
        if event["map"] is not None:
            embed.add_field(name="Map", value=event["map"], inline=False)
        if event["externalURL"] is not None:
            embed.add_field(name="\u200B", value="\u200B", inline=False)
            embed.add_field(name="External URL", value=event["externalURL"], inline=False)
        embed.add_field(name="\u200B", value="\u200B", inline=False)

        accepted = [member.display_name for memberId in event["accepted"] if (member := guild.get_member(memberId)) is not None]
        standby = []
        if event["maxPlayers"] is not None and len(accepted) > event["maxPlayers"]:
            accepted, standby = accepted[:event["maxPlayers"]], accepted[event["maxPlayers"]:]
        declined = [member.display_name for memberId in event["declined"] if (member := guild.get_member(memberId)) is not None]
        declinedForTiming = [member.display_name for memberId in event.get("declinedForTiming", []) if (member := guild.get_member(memberId)) is not None]
        tentative = [member.display_name for memberId in event["tentative"] if (member := guild.get_member(memberId)) is not None]

        if event["maxPlayers"] is None or (event["maxPlayers"] is not None and event["maxPlayers"] > 0):
            embed.add_field(name=f"Accepted ({len(accepted)}/{event['maxPlayers']}) ✅" if event["maxPlayers"] is not None else f"Accepted ({len(accepted)}) ✅", value="\n".join(name for name in accepted) if len(accepted) > 0 else "-", inline=True)
            embed.add_field(name=f"Declined ({len(declinedForTiming)}) ⏱/❌ ({len(declined)})", value=("\n".join("⏱ " + name for name in declinedForTiming) + "\n" * (len(declinedForTiming) > 0 and len(declined) > 0) + "\n".join("❌ " + name for name in declined)) if len(declined) + len(declinedForTiming) > 0 else "-", inline=True)
            embed.add_field(name=f"Tentative ({len(tentative)}) ❓", value="\n".join(name for name in tentative) if len(tentative) > 0 else "-", inline=True)
            if len(standby) > 0:
                embed.add_field(name=f"Standby ({len(standby)}) :clock3:", value="\n".join(name for name in standby), inline=False)
        elif event["maxPlayers"] != -1:
            embed.add_field(name=f"Accepted ({len(accepted + standby)}) ✅", value="\u200B", inline=True)
            embed.add_field(name=f"Declined ({len(declinedForTiming)}) ⏱/❌ ({len(declined)})", value="\u200B", inline=True)
            embed.add_field(name=f"Tentative ({len(tentative)}) ❓", value="\u200B", inline=True)

        author = guild.get_member(event["authorId"])
        embed.set_footer(text=f"Created by {author.display_name}") if author else embed.set_footer(text="Created by Unknown User")
        embed.timestamp = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))

        return embed

    async def buttonHandling(self, message, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """ Handling all schedule button interactions.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        button (discord.ui.Button): The Discord button.

        Returns:
        None.
        """

        try:
            if not interaction.user.dm_channel:
                await interaction.user.create_dm()

            with open(EVENTS_FILE) as f:
                events = json.load(f)

            scheduleNeedsUpdate = True
            originalMsgId = interaction.message.id
            fetchMsg = False
            event = [event for event in events if event["messageId"] == interaction.message.id]
            if button.custom_id == "accept":
                event = event[0]
                if interaction.user.id in event["declined"]:
                    event["declined"].remove(interaction.user.id)
                if interaction.user.id in event["declinedForTiming"]:
                    event["declinedForTiming"].remove(interaction.user.id)
                if interaction.user.id in event["tentative"]:
                    event["tentative"].remove(interaction.user.id)
                if interaction.user.id not in event["accepted"]:
                    event["accepted"].append(interaction.user.id)

            elif button.custom_id == "decline":
                event = event[0]
                if interaction.user.id in event["accepted"]:
                    event["accepted"].remove(interaction.user.id)
                if interaction.user.id in event["declinedForTiming"]:
                    event["declinedForTiming"].remove(interaction.user.id)
                if interaction.user.id in event["tentative"]:
                    event["tentative"].remove(interaction.user.id)
                if interaction.user.id not in event["declined"] and interaction.user.id != KYANO:
                    event["declined"].append(interaction.user.id)
                if event["reservableRoles"] is not None:
                    for roleName in event["reservableRoles"]:
                        if event["reservableRoles"][roleName] == interaction.user.id:
                            event["reservableRoles"][roleName] = None

            elif button.custom_id == "declineForTiming":
                event = event[0]
                if interaction.user.id in event["accepted"]:
                    event["accepted"].remove(interaction.user.id)
                if interaction.user.id in event["tentative"]:
                    event["tentative"].remove(interaction.user.id)
                if interaction.user.id in event["declined"]:
                    event["declined"].remove(interaction.user.id)
                if interaction.user.id not in event["declinedForTiming"]:
                    event["declinedForTiming"].append(interaction.user.id)
                if event["reservableRoles"] is not None:
                    for roleName in event["reservableRoles"]:
                        if event["reservableRoles"][roleName] == interaction.user.id:
                            event["reservableRoles"][roleName] = None

            elif button.custom_id == "tentative":
                event = event[0]
                if interaction.user.id in event["accepted"]:
                    event["accepted"].remove(interaction.user.id)
                if interaction.user.id in event["declined"]:
                    event["declined"].remove(interaction.user.id)
                if interaction.user.id in event["declinedForTiming"]:
                    event["declinedForTiming"].remove(interaction.user.id)
                if interaction.user.id not in event["tentative"]:
                    event["tentative"].append(interaction.user.id)
                if event["reservableRoles"] is not None:
                    for roleName in event["reservableRoles"]:
                        if event["reservableRoles"][roleName] == interaction.user.id:
                            event["reservableRoles"][roleName] = None

            elif button.custom_id == "reserve":
                event = event[0]
                await interaction.response.send_message(RESPONSE_GOTO_DMS.format(interaction.user.dm_channel.jump_url), ephemeral=True)
                reservingOutput = await self.reserveRole(interaction.user, event)
                if not reservingOutput:
                    return
                fetchMsg = True

            elif button.custom_id == "edit":
                event = event[0]
                if interaction.user.id == event["authorId"] or any(role.id == UNIT_STAFF for role in interaction.user.roles):
                    await interaction.response.send_message(RESPONSE_GOTO_DMS.format(interaction.user.dm_channel.jump_url), ephemeral=True)
                    reorderEvents = await self.editEvent(interaction.user, event, isTemplateEdit=False)
                    if reorderEvents:
                        with open(EVENTS_FILE, "w") as f:
                            json.dump(events, f, indent=4)
                        await self.updateSchedule()
                        return
                else:
                    await interaction.response.send_message(RESPONSE_UNALLOWED.format("edit"), ephemeral=True)
                    return
                fetchMsg = True

            elif button.custom_id == "delete":
                event = event[0]
                if interaction.user.id == event["authorId"] or any(role.id == UNIT_STAFF for role in interaction.user.roles):
                    await interaction.response.send_message(RESPONSE_GOTO_DMS.format(interaction.user.dm_channel.jump_url), ephemeral=True)
                    eventDeleted = await self.deleteEvent(interaction.user, interaction.message, event)
                    if eventDeleted:
                        events.remove(event)
                else:
                    await interaction.response.send_message(RESPONSE_UNALLOWED.format("delete"), ephemeral=True)
                    return
                scheduleNeedsUpdate = False

            elif button.custom_id == "delete_event_confirm":
                scheduleNeedsUpdate = False
                for button in button.view.children:
                    button.disabled = True
                await interaction.response.edit_message(view=button.view)
                event = [event for event in events if event["messageId"] == message.id][0]
                await message.delete()
                try:
                    await interaction.user.dm_channel.send(embed=Embed(title=f"✅ {event['type']} deleted!", color=Color.green()))

                    utcNow = UTC.localize(datetime.utcnow())
                    startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
                    if event["maxPlayers"] != 0 and utcNow > startTime + timedelta(minutes=30):
                        await self.saveEventToHistory(event)
                    else:
                        guild = self.bot.get_guild(GUILD_ID)
                        for memberId in event["accepted"] + event.get("declinedForTiming", []) + event["tentative"]:
                            member = guild.get_member(memberId)
                            if member is not None:
                                embed = Embed(title=f"🗑 {event.get('type', 'Operation')} deleted: {event['title']}!", description=f"The {event.get('type', 'Operation').lower()} was scheduled to run:\n{utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}", color=Color.red())
                                try:
                                    await member.send(embed=embed)
                                except Exception as e:
                                    log.exception(f"{member} | {e}")
                except Exception as e:
                    log.exception(e)
                events.remove(event)

            elif button.custom_id == "delete_event_cancel":
                for button in button.view.children:
                    button.disabled = True
                await interaction.response.edit_message(view=button.view)
                await self.cancelCommand(interaction.user.dm_channel, "Event deletion")
                return

            elif button.custom_id == "issues_and_suggestions":
                log.info(f"{interaction.user.display_name} ({interaction.user}) created a ticket!")
                try:
                    scheduleNeedsUpdate = False
                    await interaction.response.send_message(RESPONSE_GOTO_DMS.format(interaction.user.dm_channel.jump_url), ephemeral=True)
                    embed = Embed(title="Ticket", description="Thank you for reaching out to us!\nPlease tell us what's on your mind in **one** message below!\nInclude screenshot(s) if suitable!", color=Color.orange())
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    msg = await interaction.user.send(embed=embed)
                    dmChannel = msg.channel
                except Exception as e:
                    log.exception(f"{interaction.user} | {e}")
                    return

                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, author=interaction.user, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    concern = response.content.strip()
                    if concern.lower() == "cancel":
                        await self.cancelCommand(dmChannel, "Ticket")
                        return
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return

                try:
                    embed = Embed(title="✅ Ticket sent", description="Thank you for contacting us!\nWe will respond as soon as possible.", color=Color.green())
                    devs = [interaction.guild.get_member(developer) for developer in DEVELOPERS if interaction.guild.get_member(developer) is not None]
                    embed.set_footer(text=f"Developers: {', '.join([dev.display_name for dev in devs])}")
                    msg = await interaction.user.send(embed=embed)
                except Exception as e:
                    log.exception(f"{interaction.user} | {e}")
                    return

                try:
                    embed = Embed(title="Incoming Ticket", description=f"Reporter: {interaction.user.mention}\n**Message:**\n{concern}", color=0xFF69B4, timestamp=datetime.now())
                    embed.set_footer(text=f"Reporter ID: {interaction.user.id}")
                    [await dev.send(embed=embed, files=([await attachment.to_file() for attachment in response.attachments] if len(response.attachments) > 0 else None)) for dev in devs]
                except Exception as e:
                    log.exception(f"{interaction.user} | {e}")

            if scheduleNeedsUpdate:
                try:
                    embed = self.getEventEmbed(event)
                    if fetchMsg:  # Could be better - could be worse...
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

    async def reserveRole(self, member: discord.Member, event) -> None:
        """ Reserving a single role on an event.

        Parameters:
        member (discord.Member): The Discord user.
        event: X.

        Returns:
        bool: Returns False on error and canceling - True on success.
        """
        reservationTime = datetime.utcnow()

        if event["maxPlayers"] is not None and len(event["accepted"]) >= event["maxPlayers"] and (member.id not in event["accepted"] or event["accepted"].index(member.id) >= event["maxPlayers"]):
            try:
                await member.send(embed=Embed(title="❌ Sorry, seems like there's no space left in the :b:op!", color=Color.red()))
            except Exception as e:
                log.exception(f"{member} | {e}")
            return False

        vacantRoles = [roleName for roleName, memberId in event["reservableRoles"].items() if memberId is None or member.guild.get_member(memberId) is None]
        currentRole = [roleName for roleName, memberId in event["reservableRoles"].items() if memberId == member.id][0] if member.id in event["reservableRoles"].values() else None

        reserveOk = False
        color = Color.gold()
        while not reserveOk:
            embed = Embed(title="Which role would you like to reserve?", description="Enter a number from the list.\nEnter `none` un-reserve any role you have occupied.", color=color)
            embed.add_field(name="Your current role", value=currentRole if currentRole is not None else "None", inline=False)
            embed.add_field(name="Vacant roles", value="\n".join(f"**{idx}.** {roleName}" for idx, roleName in enumerate(vacantRoles, 1)) if len(vacantRoles) > 0 else "None", inline=False)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()

            try:
                msg = await member.send(embed=embed)
            except Exception as e:
                log.exception(f"{member} | {e}")
                return False
            dmChannel = msg.channel
            try:
                response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, author=member, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                reservedRole = response.content.strip().lower()
                if reservedRole.isdigit() and int(reservedRole) <= len(vacantRoles) and int(reservedRole) > 0:
                    reservedRole = vacantRoles[int(reservedRole) - 1]
                    reserveOk = True
                elif reservedRole == "none":
                    reservedRole = None
                    reserveOk = True
                elif reservedRole == "cancel":
                    await self.cancelCommand(dmChannel, "Role reservation")
                    return False
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False

        if reservedRole is not None:  # User wants to reserve a role
            if event["reservableRoles"] is not None:
                for roleName in event["reservableRoles"]:
                    if event["reservableRoles"][roleName] == member.id:  # If they've already reserved a role
                        event["reservableRoles"][roleName] = None  # Remove it
                if event["reservableRoles"][reservedRole] is None or member.guild.get_member(event["reservableRoles"][reservedRole]) is None:
                    event["reservableRoles"][reservedRole] = member.id  # Reserve the specified role

                    # Put the user in accepted
                    if member.id in event["declined"]:
                        event["declined"].remove(member.id)
                    if member.id in event["declinedForTiming"]:
                        event["declinedForTiming"].remove(member.id)
                    if member.id in event["tentative"]:
                        event["tentative"].remove(member.id)
                    if member.id not in event["accepted"]:
                        event["accepted"].append(member.id)

        else:  # User wants to remove their role
            if event["reservableRoles"] is not None:
                for roleName in event["reservableRoles"]:
                    if event["reservableRoles"][roleName] == member.id:
                        event["reservableRoles"][roleName] = None

        if reservationTime > self.lastUpdate:
            await dmChannel.send(embed=Embed(title="✅ Role reservation completed!", color=Color.green()))
        else:
            await dmChannel.send(embed=Embed(title="❌ Schedule was updated while you were reserving a role. Try again!", color=Color.red()))
            log.debug(f"{member.display_name} ({member}) was reserving a role but schedule was updated!")
        return True

    async def eventTime(self, interaction: discord.Interaction, dmChannel: discord.DMChannel, eventType: str, collidingEventTypes: tuple, delta: timedelta) -> tuple:
        """ X.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        dmChannel (discord.DMChannel): The DMChannel the user reponse is from.
        eventType (str): The type of event, e.g. Operation
        collidingEventTypes (tuple): A tuple of eventtypes that you want to collide with.
        delta (timedelta): Difference in time from start to end.

        Returns:
        startTime, endTime (tuple): A tuple which contains the event start time and end time.
        """
        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
        eventCollision = True
        while eventCollision:
            eventCollision = False
            startTimeOk = False
            while not startTimeOk:
                isFormatCorrect = False
                color = Color.gold()
                while not isFormatCorrect:
                    embed = Embed(title=SCHEDULE_EVENT_TIME.format(eventType.lower()), description=SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(timeZone.zone), color=color)
                    utcNow = datetime.utcnow()
                    nextHalfHour = utcNow + (datetime.min - utcNow) % timedelta(minutes=30)
                    embed.add_field(name="Example", value=UTC.localize(nextHalfHour).astimezone(timeZone).strftime(TIME_FORMAT))
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    color = Color.red()
                    await dmChannel.send(embed=embed)
                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                        startTime = response.content.strip()
                        if startTime.lower() == "cancel":
                            await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                            return
                    except asyncio.TimeoutError:
                        await dmChannel.send(embed=TIMEOUT_EMBED)
                        return
                    try:
                        startTime = datetimeParse(startTime)
                        isFormatCorrect = True
                    except ValueError:
                        isFormatCorrect = False

                startTime = timeZone.localize(startTime).astimezone(UTC)
                if startTime < UTC.localize(utcNow):  # Set time is in the past
                    if (delta := UTC.localize(utcNow) - startTime) > timedelta(hours=1) and delta < timedelta(days=1):  # Set time in the past 24 hours
                        newStartTime = startTime + timedelta(days=1)
                        embed = Embed(title=SCHEDULE_EVENT_TIME_TOMORROW, description=SCHEDULE_EVENT_TIME_TOMORROW_PREVIEW.format(utils.format_dt(startTime, style="F"), utils.format_dt(newStartTime, style="F")), color=Color.orange())
                        await dmChannel.send(embed=embed)
                        startTime = newStartTime
                        startTimeOk = True
                    else:  # Set time older than 24 hours
                        embed = Embed(title=SCHEDULE_EVENT_TIME_PAST_QUESTION, description=SCHEDULE_EVENT_TIME_PAST_PROMPT, color=Color.orange())
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        await dmChannel.send(embed=embed)
                        try:
                            response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, author=interaction.user, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                            keepStartTime = response.content.strip().lower()
                            if keepStartTime == "cancel":
                                await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                                return
                        except asyncio.TimeoutError:
                            await dmChannel.send(embed=TIMEOUT_EMBED)
                            return False
                        if keepStartTime in ("yes", "y"):
                            startTimeOk = True
                else:
                    startTimeOk = True
            endTime = startTime + delta

            with open(EVENTS_FILE) as f:
                events = json.load(f)

            exitForLoop = False
            for event in events:
                if exitForLoop:
                    break
                validCollisionReponse = False
                while not validCollisionReponse:
                    if event.get("type", eventType) not in collidingEventTypes:
                        validCollisionReponse = True
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

                    if eventCollision:
                        try:
                            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                            collisionResponse = response.content.strip().lower()
                            if collisionResponse == "cancel":
                                await self.cancelCommand(dmChannel, f"{eventType} scheduling")
                                return
                            elif collisionResponse == "edit":
                                validCollisionReponse = True
                                startTimeOk = False
                                exitForLoop = True
                            elif collisionResponse == "override":
                                validCollisionReponse = True
                                eventCollision = False
                                exitForLoop = True

                        except asyncio.TimeoutError:
                            await dmChannel.send(embed=TIMEOUT_EMBED)
                            return
                    else:
                        validCollisionReponse = True

        return (startTime, endTime)

    async def editEvent(self, author: discord.Member, event, isTemplateEdit: bool = False) -> bool:
        """ X.

        Parameters:
        member (discord.Member): The Discord user.
        event: X.
        isTemplateEdit (bool): A boolean to check if the user is editing a template or not.

        Returns:
        bool.
        """
        editingTime = datetime.utcnow()
        editOk = False
        color = Color.gold()
        while not editOk:
            embed = Embed(title=":pencil2: What would you like to edit?", color=color)
            embed.add_field(name="**1** Title", value=f"```txt\n{event['title']}\n```", inline=False)
            embed.add_field(name="**2** Description", value=f"```txt\n{event['description'] if len(event['description']) < 500 else event['description'][:500] + ' [...]'}\n```", inline=False)
            embed.add_field(name="**3** External URL", value=f"```txt\n{event['externalURL']}\n```", inline=False)
            embed.add_field(name="**4** Reservable Roles", value="```txt\n" + "\n".join(event["reservableRoles"].keys()) + "\n```" if event["reservableRoles"] is not None else "None", inline=False)
            embed.add_field(name="**5** Map", value=f"```txt\n{event['map']}\n```", inline=False)
            # Switch from back end value to filthy user friendly words
            maxPlayersUser = event['maxPlayers']
            if maxPlayersUser == 0:
                maxPlayersUser = "Anonymous"
            elif maxPlayersUser == -1:
                maxPlayersUser = "Hidden"
            embed.add_field(name="**6** Max Players", value=f"```txt\n{maxPlayersUser}\n```", inline=False)

            if not isTemplateEdit:
                log.info(f"{author.display_name} ({author}) is editing the event: {event['title']}")
                embed.insert_field_at(0, name="**0** Type", value=f"```txt\n{event['type']}\n```", inline=False)
                embed.add_field(name="**7** Time", value=utils.format_dt(UTC.localize(datetime.strptime(event["time"], TIME_FORMAT)), style="F"), inline=False)
                embed.add_field(name="**8** Duration", value=f"```txt\n{event['duration']}\n```", inline=False)
                choiceNumbers:list = [str(x) for x in range(9)]
            else:
                embed.insert_field_at(0, name="**0** Template Name", value=f"```txt\n{event['name']}\n```", inline=False)
                embed.add_field(name="**7** Duration", value=f"```txt\n{event['duration']}\n```", inline=False)
                choiceNumbers:list = [str(x) for x in range(8)]
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()

            try:
                msg = await author.send(embed=embed)
            except Exception as e:
                log.exception(f"{author} | {e}")
                return False
            dmChannel = msg.channel
            try:
                response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                choice = response.content.strip()
                if choice.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Event editing")
                    return False
                elif choice in choiceNumbers:
                    editOk = True
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False
        reorderEvents = False


        async def editEventDuration(isTemplateEdit:bool) -> bool:
            """ Editing the duration of an event or template.

            Parameters:
            isTemplateEdit (bool): If the event is a template.

            Returns:
            bool: If function executed successfully.
            """
            color = Color.gold()
            duration = "INVALID INPUT"
            while not re.match(SCHEDULE_EVENT_DURATION_REGEX, duration):
                embed = Embed(title=SCHEDULE_EVENT_DURATION_QUESTION.format("event"), description=SCHEDULE_EVENT_DURATION_PROMPT, color=color)
                embed.set_footer(text=SCHEDULE_CANCEL)
                color = Color.red()
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    duration = response.content.strip().lower()
                    if duration == "cancel":
                        await self.cancelCommand(dmChannel, "Event editing")
                        return False
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return False
            hours = int(duration.split("h")[0].strip()) if "h" in duration else 0
            minutes = int(duration.split("h")[-1].replace("m", "").strip()) if duration[-1] != "h" else 0
            event["duration"] = f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}"
            if not isTemplateEdit:
                startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT))
                delta = timedelta(hours=hours, minutes=minutes)
                endTime = startTime + delta
                event["endTime"] = endTime.strftime(TIME_FORMAT)
            return True


        match choice:
            case "0":
                if not isTemplateEdit:
                    eventTypeNum = None
                    color = Color.gold()
                    while eventTypeNum not in ("1", "2", "3"):
                        embed = Embed(title=":pencil2: What is the type of your event?", color=color)
                        embed.add_field(name="Type", value="**1** 🟩 Operation\n**2** 🟦 Workshop\n**3** 🟨 Event")
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        color = Color.red()
                        await dmChannel.send(embed=embed)
                        try:
                            response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                            eventTypeNum = response.content.strip()
                            if eventTypeNum.lower() == "cancel":
                                await self.cancelCommand(dmChannel, "Event editing")
                                return False
                        except asyncio.TimeoutError:
                            await dmChannel.send(embed=TIMEOUT_EMBED)
                            return False
                    event["type"] = {"1": "Operation", "2": "Workshop", "3": "Event"}.get(eventTypeNum, "Operation")
                else:  # Editing a template
                    embed = Embed(title=SCHEDULE_EVENT_TEMPLATE_SAVE_NAME_QUESTION, color=Color.gold())
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    await dmChannel.send(embed=embed)
                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                        templateName = response.content.strip()
                        if templateName.lower() == "cancel":
                            await self.cancelCommand(dmChannel, "Event editing")
                            return False
                    except asyncio.TimeoutError:
                        await dmChannel.send(embed=TIMEOUT_EMBED)
                        return False
                    event["name"] = templateName

            case "1":
                embed = Embed(title=SCHEDULE_EVENT_TITLE.format(event.get("type", "operation").lower()), color=Color.gold())
                embed.set_footer(text=SCHEDULE_CANCEL)
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    title = response.content.strip()
                    if title.lower() == "cancel":
                        await self.cancelCommand(dmChannel, "Event editing")
                        return False
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return False
                event["title"] = title

            case "2":
                embed = Embed(title=SCHEDULE_EVENT_DESCRIPTION_QUESTION, description=SCHEDULE_EVENT_DESCRIPTION.format(event["description"]), color=Color.gold())
                embed.set_footer(text=SCHEDULE_CANCEL)
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_THIRTY_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    description = response.content.strip()
                    if description.lower() == "cancel":
                        await self.cancelCommand(dmChannel, "Event editing")
                        return False
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return False
                event["description"] = description

            case "3":
                embed = Embed(title=SCHEDULE_EVENT_URL_TITLE, description=SCHEDULE_EVENT_URL_DESCRIPTION, color=Color.gold())
                embed.set_footer(text=SCHEDULE_CANCEL)
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    externalURL = response.content.strip()
                    if externalURL.lower() == "cancel":
                        await self.cancelCommand(dmChannel, "Event editing")
                        return False
                    elif externalURL.lower() == "none" or (len(externalURL) == 4 and "n" in externalURL.lower()):
                        externalURL = None
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return False
                event["externalURL"] = externalURL

            case "4":
                embed = Embed(title=SCHEDULE_EVENT_RESERVABLE, description=SCHEDULE_EVENT_RESERVABLE_DIALOG + "\n(Editing the name of a role will make it vacant, but roles which keep their exact names will keep their reservations).", color=Color.gold())
                embed.add_field(name="Current reservable roles", value=("```txt\n" + "\n".join(event["reservableRoles"].keys()) + "```") if event["reservableRoles"] is not None else "None")
                embed.set_footer(text=SCHEDULE_CANCEL)
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    reservables = response.content.strip()
                    if reservables.lower() == "cancel":
                        await self.cancelCommand(dmChannel, "Event editing")
                        return False
                    reservableRolesNo = reservables.lower() in ("none", "n")
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return False
                if not reservableRolesNo:
                    try:
                        reservableRoles = {role.strip(): event["reservableRoles"][role.strip()] if event["reservableRoles"] is not None and role.strip() in event["reservableRoles"] else None for role in reservables.split("\n") if len(role.strip()) > 0}
                    except asyncio.TimeoutError:
                        await dmChannel.send(embed=TIMEOUT_EMBED)
                        return False
                else:
                    reservableRoles = None
                event["reservableRoles"] = reservableRoles
                reorderEvents = True

            case "5":
                mapOK = False
                color = Color.gold()
                while not mapOK:
                    embed = Embed(title=SCHEDULE_EVENT_MAP_PROMPT, description=SCHEDULE_NUMBER_FROM_TO_OR_NONE.format(1, len(MAPS)), color=color)
                    color = Color.red()
                    embed.add_field(name="Map", value="\n".join(f"**{idx}.** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    await dmChannel.send(embed=embed)
                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                        eventMap = response.content.strip()
                        if eventMap.lower() == "cancel":
                            await self.cancelCommand(dmChannel, "Event editing")
                            return False
                        mapOK = True
                        if eventMap.isdigit() and int(eventMap) <= len(MAPS) and int(eventMap) > 0:
                            eventMap = MAPS[int(eventMap) - 1]
                        elif eventMap.lower() == "none":
                            eventMap = None
                        else:
                            mapOK = False
                    except asyncio.TimeoutError:
                        await dmChannel.send(embed=TIMEOUT_EMBED)
                        return False
                event["map"] = eventMap

            case "6":
                attendanceOk = False
                color = Color.gold()
                while not attendanceOk:
                    embed = Embed(title=SCHEDULE_EVENT_MAX_PLAYERS, description=SCHEDULE_EVENT_MAX_PLAYERS_DESCRIPTION, color=color)
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    color = Color.red()
                    await dmChannel.send(embed=embed)
                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                        maxPlayers = response.content.strip().lower()
                        attendanceOk = True
                        if maxPlayers == "cancel":
                            await self.cancelCommand(dmChannel, "Operation scheduling")
                            return
                        elif maxPlayers == "none" or maxPlayers.isdigit() and int(maxPlayers) == 0:
                            maxPlayers = None
                        elif maxPlayers == "anonymous":
                            maxPlayers = 0
                        elif maxPlayers == "hidden":
                            maxPlayers = -1
                        elif maxPlayers.isdigit() and int(maxPlayers) <= MAX_SERVER_ATTENDANCE:
                            maxPlayers = int(maxPlayers)
                        elif maxPlayers.isdigit() and int(maxPlayers) > MAX_SERVER_ATTENDANCE:
                            maxPlayers = None
                        else:
                            attendanceOk = False
                    except asyncio.TimeoutError:
                        await dmChannel.send(embed=TIMEOUT_EMBED)
                        return
                event["maxPlayers"] = maxPlayers

            case "7":
                if not isTemplateEdit:
                    with open(MEMBER_TIME_ZONES_FILE) as f:
                        memberTimeZones = json.load(f)

                    if str(author.id) in memberTimeZones:
                        try:
                            timeZone = pytz.timezone(memberTimeZones[str(author.id)])
                        except pytz.exceptions.UnknownTimeZoneError:
                            timeZone = UTC
                    else:
                        timeZoneOutput = await self.changeTimeZone(author, isCommand=False)
                        if not timeZoneOutput:
                            await self.cancelCommand(dmChannel, "Event editing")
                            return False
                        with open(MEMBER_TIME_ZONES_FILE) as f:
                            memberTimeZones = json.load(f)

                    timeZone = pytz.timezone(memberTimeZones[str(author.id)])
                    startTimeOk = False
                    while not startTimeOk:
                        isFormatCorrect = False
                        color = Color.gold()
                        while not isFormatCorrect:
                            embed = Embed(title=SCHEDULE_EVENT_TIME.format("event"), description=SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(timeZone.zone), color=color)
                            embed.add_field(name="Current Time", value=UTC.localize(datetime.strptime(event["time"], TIME_FORMAT)).astimezone(timeZone).strftime(TIME_FORMAT))
                            embed.set_footer(text=SCHEDULE_CANCEL)
                            color = Color.red()
                            await dmChannel.send(embed=embed)
                            try:
                                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                                startTime = response.content.strip()
                                if startTime.lower() == "cancel":
                                    await self.cancelCommand(dmChannel, "Event editing")
                                    return False
                            except asyncio.TimeoutError:
                                await dmChannel.send(embed=TIMEOUT_EMBED)
                                return False
                            try:
                                startTime = datetimeParse(startTime)
                                isFormatCorrect = True
                            except ValueError:
                                isFormatCorrect = False

                        startTime = timeZone.localize(startTime).astimezone(UTC)
                        utcNow = editingTime
                        if startTime < UTC.localize(utcNow):
                            if (delta := UTC.localize(utcNow) - startTime) > timedelta(hours=1) and delta < timedelta(days=1):
                                newStartTime = startTime + timedelta(days=1)
                                embed = Embed(title=SCHEDULE_EVENT_TIME_TOMORROW, description=SCHEDULE_EVENT_TIME_TOMORROW_PREVIEW.format(utils.format_dt(startTime, style="F"), utils.format_dt(newStartTime, style="F")), color=Color.orange())
                                await dmChannel.send(embed=embed)
                                startTime = newStartTime
                                startTimeOk = True
                            else:
                                embed = Embed(title=SCHEDULE_EVENT_TIME_PAST_QUESTION, description=SCHEDULE_EVENT_TIME_PAST_PROMPT, color=Color.orange())
                                embed.set_footer(text=SCHEDULE_CANCEL)
                                await dmChannel.send(embed=embed)
                                try:
                                    response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                                    keepStartTime = response.content.strip()
                                    if keepStartTime.lower() == "cancel":
                                        await self.cancelCommand(dmChannel, "Event editing")
                                        return False
                                except asyncio.TimeoutError:
                                    await dmChannel.send(embed=TIMEOUT_EMBED)
                                    return False
                                if keepStartTime.lower() in ("yes", "y"):
                                    startTimeOk = True
                        else:
                            startTimeOk = True

                    duration = event["duration"]
                    hours = int(duration.split("h")[0].strip()) if "h" in duration else 0
                    minutes = int(duration.split("h")[-1].replace("m", "").strip()) if duration.strip()[-1] != "h" else 0
                    delta = timedelta(hours=hours, minutes=minutes)
                    endTime = startTime + delta
                    oldStartTime = event["time"]
                    event["time"] = startTime.strftime(TIME_FORMAT)
                    event["endTime"] = endTime.strftime(TIME_FORMAT)
                    reorderEvents = True
                    guild = self.bot.get_guild(GUILD_ID)
                    embed = Embed(title=f":clock3: The starting time has changed for: {event['title']}!", description=f"From: {utils.format_dt(UTC.localize(datetime.strptime(oldStartTime, TIME_FORMAT)), style='F')}\n\u2000\u2000To: {utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT)), style='F')}", color=Color.orange())
                    for memberId in event["accepted"] + event.get("declinedForTiming", []) + event["tentative"]:
                        member = guild.get_member(memberId)
                        if member is not None:
                            try:
                                await member.send(embed=embed)
                            except Exception as e:
                                log.exception(f"{member} | {e}")
                else:  # Template
                    durationOutput = await editEventDuration(isTemplateEdit=True)
                    if not durationOutput:
                        return False

            case "8":
                if not isTemplateEdit:
                    durationOutput = await editEventDuration(isTemplateEdit=False)
                    if not durationOutput:
                        return False

        if not isTemplateEdit:
            if editingTime > self.lastUpdate:
                embed = Embed(title=f"✅ {event['type']} edited!", color=Color.green())
                await dmChannel.send(embed=embed)
                log.info(f"{author.display_name} ({author}) edited the event: {event['title']}.")
                return reorderEvents
            else:
                embed = Embed(title="❌ Schedule was updated while you were editing your operation. Try again!", color=Color.red())
                await dmChannel.send(embed=embed)
                log.info(f"{author.display_name} ({author}) was editing an event but schedule was updated!")
                return False
        else:  # Template
            embed = Embed(title=f"✅ Template edited!", color=Color.green())
            await dmChannel.send(embed=embed)
            log.warning(f"{author.display_name} ({author}) edited the template: {event['name']}!")

    async def deleteEvent(self, author: discord.Member, message: discord.Message, event) -> bool:
        """ X.

        Parameters:
        member (discord.Member): The Discord user.
        message (discord.Message): The event message.
        event: X.

        Returns:
        bool.
        """
        try:
            embed = Embed(title=SCHEDULE_EVENT_CONFIRM_DELETE.format(f"{event['type'].lower()}: `{event['title']}`"), color=Color.orange())
            row = discord.ui.View()
            row.timeout = TIME_ONE_MIN
            buttons = [
                ScheduleButtons(self, message, row=0, label="Delete", style=discord.ButtonStyle.success, custom_id="delete_event_confirm"),
                ScheduleButtons(self, message, row=0, label="Cancel", style=discord.ButtonStyle.danger, custom_id="delete_event_cancel"),
            ]
            [row.add_item(item=button) for button in buttons]
            await author.send(embed=embed, view=row)
        except Exception as e:
            log.exception(f"{author} | {e}")
            return False

    @app_commands.command(name="bop")
    @app_commands.guilds(GUILD)
    async def bop(self, interaction: discord.Interaction) -> None:
        """ Create an operation to add to the schedule. """
        await self.scheduleOperation(interaction)

    @app_commands.command(name="operation")
    @app_commands.guilds(GUILD)
    async def operation(self, interaction: discord.Interaction) -> None:
        """ Create an operation to add to the schedule. """
        await self.scheduleOperation(interaction)

    async def scheduleOperation(self, interaction: discord.Interaction) -> None:
        """ Scheduling an operation.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        await interaction.response.send_message(RESPONSE_EVENT_PROGRESS.format(":b:op."))
        log.info(f"{interaction.user.display_name} ({interaction.user}) is creating an operation...")

        authorId = interaction.user.id

        # Operation title
        titleOk = False
        color = Color.gold()
        while not titleOk:
            embed = Embed(title=SCHEDULE_EVENT_TITLE.format("operation"), description="Remeber, operation names should start with the word `Operation`\nE.g. Operation Red Tide.\n\nEnter `regenerate` to renew the generated operation names.", color=color)
            color = Color.orange()

            with open(OPERATION_NAME_ADJECTIVES) as f:
                adjectives = f.readlines()
                adj = [random.choice(adjectives).strip("\n") for _ in range(10)]

            with open(OPERATION_NAME_NOUNS) as f:
                nouns = f.readlines()
                nou = [random.choice(nouns).strip("\n") for _ in range(10)]

            titles = [f"{adj[x].capitalize()} {nou[x].capitalize()}" for x in range(10)]
            embed.add_field(name="Generated Operation Names", value="\n".join(titles))
            embed.set_footer(text=SCHEDULE_CANCEL)
            try:
                msg = await interaction.user.send(embed=embed)
            except Exception as e:
                log.exception(f"{interaction.user} | {e}")
                return
            dmChannel = msg.channel
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                title = response.content.strip()
                if title.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Operation scheduling")
                    return
                elif title.lower() == "regenerate":
                    titleOk = False
                else:
                    titleOk = True

            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

        # Operation description
        embed = Embed(title=SCHEDULE_EVENT_DESCRIPTION_QUESTION, color=Color.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_THIRTY_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
            description = response.content.strip()
            if description.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Operation scheduling")
                return
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        # Operation URL
        embed = Embed(title=SCHEDULE_EVENT_URL_TITLE, description=SCHEDULE_EVENT_URL_DESCRIPTION, color=Color.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
            externalURL = response.content.strip()
            if externalURL.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Operation scheduling")
                return
            if externalURL.lower() == "none" or (len(externalURL) == 4 and "n" in externalURL.lower()):
                externalURL = None
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        # Operation reservable roles
        embed = Embed(title=SCHEDULE_EVENT_RESERVABLE, description=SCHEDULE_EVENT_RESERVABLE_DIALOG, color=Color.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
            reservables = response.content.strip()
            if reservables.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Operation scheduling")
                return
            reservableRolesNo = reservables.lower() in ("none", "n")
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        if not reservableRolesNo:
            try:
                reservableRoles = {role.strip(): None for role in reservables.split("\n") if len(role.strip()) > 0}
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        else:
            reservableRoles = None

        # Operation map
        mapOK = False
        color = Color.gold()
        while not mapOK:
            embed = Embed(title=SCHEDULE_EVENT_MAP_PROMPT, description=SCHEDULE_NUMBER_FROM_TO_OR_NONE.format(1, len(MAPS)), color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            embed.add_field(name="Map", value="\n".join(f"**{idx}.** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                eventMap = response.content.strip()
                if eventMap.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Operation scheduling")
                    return
                mapOK = True
                if eventMap.isdigit() and int(eventMap) <= len(MAPS) and int(eventMap) > 0:
                    eventMap = MAPS[int(eventMap) - 1]
                elif eventMap.strip().lower() == "none":
                    eventMap = None
                else:
                    mapOK = False
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

        # Operation attendance
        attendanceOk = False
        color = Color.gold()
        while not attendanceOk:
            embed = Embed(title=SCHEDULE_EVENT_MAX_PLAYERS, description=SCHEDULE_EVENT_MAX_PLAYERS_DESCRIPTION, color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                maxPlayers = response.content.strip().lower()
                attendanceOk = True
                if maxPlayers == "cancel":
                    await self.cancelCommand(dmChannel, "Operation scheduling")
                    return
                elif maxPlayers == "none" or maxPlayers.isdigit() and int(maxPlayers) == 0:
                    maxPlayers = None
                elif maxPlayers == "anonymous":
                    maxPlayers = 0
                elif maxPlayers == "hidden":
                    maxPlayers = -1
                elif maxPlayers.isdigit() and int(maxPlayers) <= MAX_SERVER_ATTENDANCE:
                    maxPlayers = int(maxPlayers)
                elif maxPlayers.isdigit() and int(maxPlayers) > MAX_SERVER_ATTENDANCE:
                    maxPlayers = None
                else:
                    attendanceOk = False
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

        # Operation duration
        color = Color.gold()
        duration = "INVALID INPUT"
        while not re.match(SCHEDULE_EVENT_DURATION_REGEX, duration):
            embed = Embed(title=SCHEDULE_EVENT_DURATION_QUESTION.format("operation"), description=SCHEDULE_EVENT_DURATION_PROMPT, color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                duration = response.content.strip().lower()
                if duration == "cancel":
                    await self.cancelCommand(dmChannel, "Operation scheduling")
                    return
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        hours = int(duration.split("h")[0].strip()) if "h" in duration else 0
        minutes = int(duration.split("h")[-1].replace("m", "").strip()) if duration.strip()[-1] != "h" else 0
        delta = timedelta(hours=hours, minutes=minutes)

        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        if not str(interaction.user.id) in memberTimeZones:
            timeZoneOutput = await self.changeTimeZone(interaction.user, isCommand=False)
            if not timeZoneOutput:
                await self.cancelCommand(dmChannel, "Event editing")
                return False

        # Operation time
        eventTimes: tuple = await self.eventTime(interaction, dmChannel, "Operation", ("Operation", "Workshop"), delta)

        # Operation finalizing
        try:
            if os.path.exists(EVENTS_FILE):
                with open(EVENTS_FILE) as f:
                    events = json.load(f)
            else:
                events = []
            newEvent = {
                "authorId": authorId,
                "title": title,
                "description": description,
                "externalURL": externalURL,
                "reservableRoles": reservableRoles,
                "maxPlayers": maxPlayers,
                "map": eventMap,
                "time": eventTimes[0].strftime(TIME_FORMAT),
                "endTime": eventTimes[1].strftime(TIME_FORMAT),
                "duration": f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}",
                "messageId": None,
                "accepted": [],
                "declined": [],
                "declinedForTiming": [],
                "tentative": [],
                "type": "Operation"  # Operation, Workshop, Event
            }
            events.append(newEvent)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            log.exception(e)
            newEvent = None

        embed = Embed(title="✅ Operation created!", color=Color.green())
        await dmChannel.send(embed=embed)
        log.info(f"{interaction.user.display_name} ({interaction.user}) created the operation: {title}!")

        await self.updateSchedule()

        if newEvent is not None:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            await interaction.followup.send(RESPONSE_EVENT_DONE.format(newEvent["title"], GUILD_ID, SCHEDULE, events[-1]["messageId"]))

    @app_commands.command(name="ws")
    @app_commands.guilds(GUILD)
    async def ws(self, interaction: discord.Interaction) -> None:
        """ Create a workshop to add to the schedule. """
        await self.scheduleWorkshop(interaction)

    @app_commands.command(name="workshop")
    @app_commands.guilds(GUILD)
    async def workshop(self, interaction: discord.Interaction) -> None:
        """ Create a workshop to add to the schedule. """
        await self.scheduleWorkshop(interaction)

    async def scheduleWorkshop(self, interaction: discord.Interaction) -> None:
        """ Scheduling a workshop.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        await interaction.response.send_message(RESPONSE_EVENT_PROGRESS.format("workshop"))
        log.info(f"{interaction.user.display_name} ({interaction.user}) is creating a workshop...")

        authorId = interaction.user.id

        templateActionRepeat: bool = True
        color = Color.gold()
        while templateActionRepeat:
            with open(WORKSHOP_TEMPLATES_FILE) as f:
                workshopTemplates = json.load(f)
            embed = Embed(title=":clipboard: Templates", description="Enter a template number.\nEnter `none` to make a workshop from scratch.\n\nEdit template: `edit` + template number. E.g. `edit 2`.\nDelete template: `delete` + template number. E.g. `delete 4`. **IRREVERSIBLE!**", color=color)
            embed.add_field(name="Templates", value="\n".join(f"**{idx}.** {template['name']}" for idx, template in enumerate(workshopTemplates, 1)) if len(workshopTemplates) > 0 else "-")
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            try:
                msg = await interaction.user.send(embed=embed)
            except Exception as e:
                log.exception(f"{interaction.user} | {e}")
                return
            dmChannel = msg.channel

            try:
                response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                templateAction = response.content.strip()

                if templateAction.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Workshop scheduling")
                    return
                elif templateAction.lower() == "none":
                    templateActionRepeat = False
                    template = None
                elif re.search(SCHEDULE_EVENT_TEMPLATE_ACTION_REGEX, templateAction, re.IGNORECASE):
                    if templateAction.lower().startswith("delete"):
                        templateNumber = templateAction.split(" ")[-1]
                        if templateNumber.isdigit() and int(templateNumber) <= len(workshopTemplates) and int(templateNumber) > 0:
                            workshopTemplate = workshopTemplates[int(templateNumber) - 1]
                            try:
                                msg = await dmChannel.send(embed=Embed(title=SCHEDULE_EVENT_CONFIRM_DELETE.format(f"template: `{workshopTemplate['name']}`"), color=Color.orange()))
                            except Exception as e:
                                log.exception(f"{interaction.user} | {e}")
                                return
                            await msg.add_reaction("🗑")
                            try:
                                await self.bot.wait_for("reaction_add", timeout=TIME_ONE_MIN, check=lambda reaction, user, author=interaction.user: reaction.emoji == "🗑" and user == author)
                            except asyncio.TimeoutError:
                                await interaction.user.send(embed=TIMEOUT_EMBED)
                                return
                            log.warning(f"{interaction.user.display_name} ({interaction.user}) deleted the workshop template: {workshopTemplate['name']}!")

                            with open(WORKSHOP_TEMPLATES_DELETED_FILE) as f:
                                workshopTempaltesDeleted = json.load(f)
                            workshopTempaltesDeleted.append(workshopTemplates[int(templateAction.split(" ")[-1]) - 1])
                            with open(WORKSHOP_TEMPLATES_DELETED_FILE, "w") as f:
                                json.dump(workshopTempaltesDeleted, f, indent=4)

                            workshopTemplates.pop(int(templateAction.split(" ")[-1]) - 1)
                            with open(WORKSHOP_TEMPLATES_FILE, "w") as f:
                                json.dump(workshopTemplates, f, indent=4)
                            await dmChannel.send(embed=Embed(title="✅ Template deleted!", color=Color.green()))
                            color = Color.gold()

                    elif templateAction.lower().startswith("edit"):
                        templateNumber = templateAction.split(" ")[-1]
                        if templateNumber.isdigit() and int(templateNumber) <= len(workshopTemplates) and int(templateNumber) > 0:
                            workshopTemplate = workshopTemplates[int(templateNumber) - 1]
                            log.info(f"{interaction.user.display_name} ({interaction.user}) is editing the workshop template: {workshopTemplate['name']}...")
                            await self.editEvent(interaction.user, workshopTemplate, isTemplateEdit=True)

                            workshopTemplates[int(templateNumber) - 1] = workshopTemplate
                            with open(WORKSHOP_TEMPLATES_FILE, "w") as f:
                                json.dump(workshopTemplates, f, indent=4)
                            color = Color.gold()

                    else: # Select template
                        if templateAction.isdigit() and int(templateAction) <= len(workshopTemplates) and int(templateAction) > 0:
                            template = workshopTemplates[int(templateAction) - 1]
                            templateActionRepeat = False

            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

        # Workshop title
        if template is None:
            embed = Embed(title=SCHEDULE_EVENT_TITLE.format("workshop"), color=Color.gold())
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                title = response.content.strip()
                if title.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Workshop scheduling")
                    return
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        else:
            title = template["title"]

        # Workshop description
        if template is None:
            embed = Embed(title=SCHEDULE_EVENT_DESCRIPTION_QUESTION, color=Color.gold())
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_THIRTY_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                description = response.content.strip()
                if description.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Workshop scheduling")
                    return
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        else:
            description = template["description"]

        # Workshop URL
        if template is None:
            embed = Embed(title=SCHEDULE_EVENT_URL_TITLE, description=SCHEDULE_EVENT_URL_DESCRIPTION, color=Color.gold())
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                externalURL = response.content.strip()
                if externalURL.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Workshop scheduling")
                    return
                elif externalURL.lower() == "none" or (len(externalURL) == 4 and "n" in externalURL.lower()):
                    externalURL = None
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        else:
            externalURL = template["externalURL"]

        # Workshop reservable roles
        if template is None:
            embed = Embed(title=SCHEDULE_EVENT_RESERVABLE, description=SCHEDULE_EVENT_RESERVABLE_DIALOG, color=Color.gold())
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                reservables = response.content.strip()
                if reservables.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Workshop scheduling")
                    return
                reservableRolesNo = reservables.lower() in ("none", "n")
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
            if not reservableRolesNo:
                try:
                    reservableRoles = {role.strip(): None for role in reservables.split("\n") if len(role.strip()) > 0}
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return
            else:
                reservableRoles = None
        else:
            reservableRoles = template["reservableRoles"]

        # Workshop map
        if template is None:
            mapOk = False
            color=Color.gold()
            while not mapOk:
                embed = Embed(title=SCHEDULE_EVENT_MAP_PROMPT, description=SCHEDULE_NUMBER_FROM_TO_OR_NONE.format(1, len(MAPS)), color=color)
                color=Color.red()
                embed.add_field(name="Map", value="\n".join(f"**{idx}.** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
                embed.set_footer(text=SCHEDULE_CANCEL)
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                    eventMap = response.content.strip()
                    if eventMap.lower() == "cancel":
                        await self.cancelCommand(dmChannel, "Workshop scheduling")
                        return
                    if eventMap.isdigit() and int(eventMap) <= len(MAPS) and int(eventMap) > 0:
                        eventMap = MAPS[int(eventMap) - 1]
                        mapOk = True
                    elif eventMap.strip().lower() == "none":
                        eventMap = None
                        mapOk = True
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return
        else:
            eventMap = template["map"]

        # Workshop attendance
        if template is None:
            attendanceOk = False
            color = Color.gold()
            while not attendanceOk:
                embed = Embed(title=SCHEDULE_EVENT_MAX_PLAYERS, description=SCHEDULE_EVENT_MAX_PLAYERS_DESCRIPTION, color=color)
                embed.set_footer(text=SCHEDULE_CANCEL)
                color = Color.red()
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                    maxPlayers = response.content.strip().lower()
                    attendanceOk = True
                    if maxPlayers == "cancel":
                        await self.cancelCommand(dmChannel, "Operation scheduling")
                        return
                    elif maxPlayers == "none" or maxPlayers.isdigit() and int(maxPlayers) == 0:
                        maxPlayers = None
                    elif maxPlayers == "anonymous":
                        maxPlayers = 0
                    elif maxPlayers == "hidden":
                        maxPlayers = -1
                    elif maxPlayers.isdigit() and int(maxPlayers) <= MAX_SERVER_ATTENDANCE:
                        maxPlayers = int(maxPlayers)
                    elif maxPlayers.isdigit() and int(maxPlayers) > MAX_SERVER_ATTENDANCE:
                        maxPlayers = None
                    else:
                        attendanceOk = False
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return
        else:
            maxPlayers = template["maxPlayers"]

        # Workshop duration
        if template is None:
            color = Color.gold()
            duration = "INVALID INPUT"
            while not re.match(SCHEDULE_EVENT_DURATION_REGEX, duration):
                embed = Embed(title=SCHEDULE_EVENT_DURATION_QUESTION.format("workshop"), description=SCHEDULE_EVENT_DURATION_PROMPT, color=color)
                embed.set_footer(text=SCHEDULE_CANCEL)
                color=Color.red()
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                    duration = response.content.strip().lower()
                    if duration == "cancel":
                        await self.cancelCommand(dmChannel, "Workshop scheduling")
                        return
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return
        else:
            duration = template["duration"]

        hours = int(duration.split("h")[0].strip()) if "h" in duration else 0
        minutes = int(duration.split("h")[-1].replace("m", "").strip()) if duration.strip()[-1] != "h" else 0
        delta = timedelta(hours=hours, minutes=minutes)

        # Workshop linking
        if template is None:
            workshopInterestOk = False
            color = Color.gold()
            while not workshopInterestOk:
                with open(WORKSHOP_INTEREST_FILE) as f:
                    workshopInterestOptions = [{"name": name, "title": wsInterest["title"]} for name, wsInterest in json.load(f).items()]
                embed = Embed(title=":link: Which workshop waiting list is your workshop linked to?", description="When linking your workshop and finished scheduling it, it will automatically ping everyone interested in it.\nFurthermore, those that complete the workshop will be removed from the interest list!", color=color)
                embed.add_field(name="Workshop Lists", value="\n".join(f"**{idx}.** {wsInterest['title']}" for idx, wsInterest in enumerate(workshopInterestOptions, 1)))
                embed.set_footer(text=SCHEDULE_CANCEL)
                color = Color.red()
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                    workshopInterest = response.content.strip()
                    if workshopInterest.lower() == "cancel":
                        await self.cancelCommand(dmChannel, "Workshop scheduling")
                        return
                    workshopInterestOk = True
                    if workshopInterest.isdigit() and int(workshopInterest) <= len(workshopInterestOptions) and int(workshopInterest) > 0:
                        workshopInterest = workshopInterestOptions[int(workshopInterest) - 1]["name"]
                    elif workshopInterest.strip().lower() == "none":
                        workshopInterest = None
                    else:
                        workshopInterestOk = False
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return
        else:
            workshopInterest = template.get("workshopInterest")

        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        if not str(interaction.user.id) in memberTimeZones:
            timeZoneOutput = await self.changeTimeZone(interaction.user, isCommand=False)
            if not timeZoneOutput:
                await self.cancelCommand(dmChannel, "Workshop scheduling")
                return False


        # Workshop time
        eventTimes: tuple = await self.eventTime(interaction, dmChannel, "Workshop", ("Operation",), delta)

        # Workshop save template
        if template is None:
            embed = Embed(title="Do you wish to save this workshop as a template?", description="Enter `yes` or `y` if you want to save it.\nEnter anything else to not.", color=Color.gold())
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                templateSaveResponse = response.content.strip().lower()
                if templateSaveResponse == "cancel":
                    await self.cancelCommand(dmChannel, "Workshop scheduling")
                    return
                saveTemplate = templateSaveResponse in ("yes", "y")
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
            if saveTemplate:
                embed = Embed(title=SCHEDULE_EVENT_TEMPLATE_SAVE_NAME_QUESTION, description="Enter `none` to make it the same as the title.", color=Color.gold())
                embed.set_footer(text=SCHEDULE_CANCEL)
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                    templateName = response.content.strip()
                    if templateName.lower() == "cancel":
                        await self.cancelCommand(dmChannel, "Workshop scheduling")
                        return
                    elif templateName.lower() == "none":
                        templateName = title
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return
                newTemplate = {
                    "name": templateName,
                    "title": title,
                    "description": description,
                    "externalURL": externalURL,
                    "reservableRoles": reservableRoles,
                    "maxPlayers": maxPlayers,
                    "map": eventMap,
                    "duration": f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}",
                    "workshopInterest": workshopInterest
                }
                with open(WORKSHOP_TEMPLATES_FILE) as f:
                    workshopTemplates = json.load(f)
                workshopTemplates.append(newTemplate)
                with open(WORKSHOP_TEMPLATES_FILE, "w") as f:
                    json.dump(workshopTemplates, f, indent=4)
                embed = Embed(title=f"✅ Template saved as `{templateName}`!", color=Color.green())
                await dmChannel.send(embed=embed)
            else:
                embed = Embed(title="❌ Template not saved!", color=Color.red())
                await dmChannel.send(embed=embed)

        # Workshop finalizing
        try:
            if os.path.exists(EVENTS_FILE):
                with open(EVENTS_FILE) as f:
                    events = json.load(f)
            else:
                events = []
            newEvent = {
                "authorId": authorId,
                "title": title,
                "description": description,
                "externalURL": externalURL,
                "reservableRoles": reservableRoles,
                "maxPlayers": maxPlayers,
                "map": eventMap,
                "time": eventTimes[0].strftime(TIME_FORMAT),
                "endTime": eventTimes[1].strftime(TIME_FORMAT),
                "duration": f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}",
                "messageId": None,
                "accepted": [],
                "declined": [],
                "declinedForTiming": [],
                "tentative": [],
                "workshopInterest": workshopInterest,
                "type": "Workshop"  # Operation, Workshop, Event
            }
            events.append(newEvent)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            log.exception(e)
            newEvent = None

        embed = Embed(title="✅ Workshop created!", color=Color.green())
        await dmChannel.send(embed=embed)
        log.info(f"{interaction.user.display_name} ({interaction.user}) created the workshop: {title}!")

        await self.updateSchedule()

        if newEvent is not None:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            await interaction.followup.send(RESPONSE_EVENT_DONE.format(newEvent["title"], GUILD_ID, SCHEDULE, events[-1]["messageId"]))

            if workshopInterest is not None:
                with open(WORKSHOP_INTEREST_FILE) as f:
                    workshopInterestItem = [{"name": name, "wsInterest": wsInterest} for name, wsInterest in json.load(f).items() if name == workshopInterest][0]
                guild = self.bot.get_guild(GUILD_ID)
                message = ""
                for memberId in workshopInterestItem["wsInterest"]["members"]:
                    message += f"{member.mention} " if (member := guild.get_member(memberId)) is not None else ""
                if message != "":
                    await guild.get_channel(ARMA_DISCUSSION).send(f"{message}\nA {workshopInterestItem['wsInterest']['title']} workshop is up on <#{SCHEDULE}> - which you are interested in.\nIf you're no longer interested, please remove yourself from the list in <#{WORKSHOP_INTEREST}>!")

    @app_commands.command(name="event")
    @app_commands.guilds(GUILD)
    async def scheduleEvent(self, interaction: discord.Interaction) -> None:
        """ Create an event to add to the schedule.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        await interaction.response.send_message(RESPONSE_EVENT_PROGRESS.format("event"))
        log.info(f"{interaction.user.display_name} ({interaction.user}) is creating an event...")

        authorId = interaction.user.id

        # Event title
        embed = Embed(title=SCHEDULE_EVENT_TITLE.format("event"), color=Color.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        try:
            msg = await interaction.user.send(embed=embed)
        except Exception as e:
            log.exception(f"{interaction.user} | {e}")
            return
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
            title = response.content.strip()
            if title.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Event scheduling")
                return
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        # Event description
        embed = Embed(title=SCHEDULE_EVENT_DESCRIPTION_QUESTION, color=Color.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_THIRTY_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
            description = response.content.strip()
            if description.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Event scheduling")
                return
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        # Event URL
        embed = Embed(title=SCHEDULE_EVENT_URL_TITLE, description=SCHEDULE_EVENT_URL_DESCRIPTION, color=Color.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
            externalURL = response.content.strip()
            if externalURL.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Event scheduling")
                return
            elif externalURL.lower() == "none" or (len(externalURL) == 4 and "n" in externalURL.lower()):
                externalURL = None
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        # Event reservable roles
        embed = Embed(title=SCHEDULE_EVENT_RESERVABLE, description=SCHEDULE_EVENT_RESERVABLE_DIALOG, color=Color.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
            reservables = response.content.strip()
            if reservables.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Event scheduling")
                return
            reservableRolesNo = reservables.lower() in ("none", "n")
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        if not reservableRolesNo:
            try:
                reservableRoles = {role.strip(): None for role in reservables.split("\n") if len(role.strip()) > 0}
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        else:
            reservableRoles = None

        # Event map
        mapOK = False
        color=Color.gold()
        while not mapOK:
            embed = Embed(title=SCHEDULE_EVENT_MAP_PROMPT, description=SCHEDULE_NUMBER_FROM_TO_OR_NONE.format(1, len(MAPS)), color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color=Color.red()
            embed.add_field(name="Map", value="\n".join(f"**{idx}.** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                eventMap = response.content.strip()
                if eventMap.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Event scheduling")
                    return
                mapOK = True
                if eventMap.isdigit() and int(eventMap) <= len(MAPS) and int(eventMap) > 0:
                    eventMap = MAPS[int(eventMap) - 1]
                elif eventMap.strip().lower() == "none":
                    eventMap = None
                else:
                    mapOK = False
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

        # Event attendance
        attendanceOk = False
        color = Color.gold()
        while not attendanceOk:
            embed = Embed(title=SCHEDULE_EVENT_MAX_PLAYERS, description=SCHEDULE_EVENT_MAX_PLAYERS_DESCRIPTION, color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                maxPlayers = response.content.strip().lower()
                attendanceOk = True
                if maxPlayers == "cancel":
                    await self.cancelCommand(dmChannel, "Operation scheduling")
                    return
                elif maxPlayers == "none" or maxPlayers.isdigit() and int(maxPlayers) == 0:
                    maxPlayers = None
                elif maxPlayers == "anonymous":
                    maxPlayers = 0
                elif maxPlayers == "hidden":
                    maxPlayers = -1
                elif maxPlayers.isdigit() and int(maxPlayers) <= MAX_SERVER_ATTENDANCE:
                    maxPlayers = int(maxPlayers)
                elif maxPlayers.isdigit() and int(maxPlayers) > MAX_SERVER_ATTENDANCE:
                    maxPlayers = None
                else:
                    attendanceOk = False
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

        # Event duration
        color = Color.gold()
        duration = "INVALID INPUT"
        while not re.match(SCHEDULE_EVENT_DURATION_REGEX, duration):
            embed = Embed(title=SCHEDULE_EVENT_DURATION_QUESTION.format("event"), description=SCHEDULE_EVENT_DURATION_PROMPT, color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                duration = response.content.strip().lower()
                if duration == "cancel":
                    await self.cancelCommand(dmChannel, "Event scheduling")
                    return
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

        hours = int(duration.split("h")[0].strip()) if "h" in duration else 0
        minutes = int(duration.split("h")[-1].replace("m", "").strip()) if duration.strip()[-1] != "h" else 0
        delta = timedelta(hours=hours, minutes=minutes)

        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        if str(interaction.user.id) in memberTimeZones:
            try:
                timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
            except pytz.exceptions.UnknownTimeZoneError:
                timeZone = UTC
        else:
            timeZoneOutput = await self.changeTimeZone(interaction.user, isCommand=False)
            if not timeZoneOutput:
                await self.cancelCommand(dmChannel, "Event editing")
                return False
            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)

        # Event time
        timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
        startTimeOk = False
        while not startTimeOk:
            isFormatCorrect = False
            color = Color.gold()
            while not isFormatCorrect:
                embed = Embed(title=SCHEDULE_EVENT_TIME.format("event"), description=SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(timeZone.zone), color=color)
                utcNow = datetime.utcnow()
                nextHalfHour = utcNow + (datetime.min - utcNow) % timedelta(minutes=30)
                embed.add_field(name="Example", value=UTC.localize(nextHalfHour).astimezone(timeZone).strftime(TIME_FORMAT))
                embed.set_footer(text=SCHEDULE_CANCEL)
                color = Color.red()
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                    startTime = response.content.strip()
                    if startTime.lower() == "cancel":
                        await self.cancelCommand(dmChannel, "Event scheduling")
                        return
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return
                try:
                    startTime = datetimeParse(startTime)
                    isFormatCorrect = True
                except ValueError:
                    isFormatCorrect = False
            startTime = timeZone.localize(startTime).astimezone(UTC)
            if startTime < UTC.localize(utcNow):
                if (delta := UTC.localize(utcNow) - startTime) > timedelta(hours=1) and delta < timedelta(days=1):
                    newStartTime = startTime + timedelta(days=1)
                    embed = Embed(title=SCHEDULE_EVENT_TIME_TOMORROW, description=SCHEDULE_EVENT_TIME_TOMORROW_PREVIEW.format(utils.format_dt(startTime, style="F"), utils.format_dt(newStartTime, style="F")), color=Color.orange())
                    await dmChannel.send(embed=embed)
                    startTime = newStartTime
                    startTimeOk = True
                else:
                    embed = Embed(title=SCHEDULE_EVENT_TIME_PAST_QUESTION, description=SCHEDULE_EVENT_TIME_PAST_PROMPT, color=Color.orange())
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    await dmChannel.send(embed=embed)
                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, author=interaction.user, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                        keepStartTime = response.content.strip()
                        if keepStartTime.lower() == "cancel":
                            await self.cancelCommand(dmChannel, "Event scheduling")
                            return
                    except asyncio.TimeoutError:
                        await dmChannel.send(embed=TIMEOUT_EMBED)
                        return False
                    if keepStartTime.lower() in ("yes", "y"):
                        startTimeOk = True
            else:
                startTimeOk = True
        endTime = startTime + delta

        # Event finalizing
        try:
            if os.path.exists(EVENTS_FILE):
                with open(EVENTS_FILE) as f:
                    events = json.load(f)
            else:
                events = []
            newEvent = {
                "authorId": authorId,
                "title": title,
                "description": description,
                "externalURL": externalURL,
                "reservableRoles": reservableRoles,
                "maxPlayers": maxPlayers,
                "map": eventMap,
                "time": startTime.strftime(TIME_FORMAT),
                "endTime": endTime.strftime(TIME_FORMAT),
                "duration": f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}",
                "messageId": None,
                "accepted": [],
                "declined": [],
                "declinedForTiming": [],
                "tentative": [],
                "type": "Event"  # Operation, Workshop, Event
            }
            events.append(newEvent)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            log.exception(e)
            newEvent = None

        embed = Embed(title="✅ Event created!", color=Color.green())
        await dmChannel.send(embed=embed)
        log.info(f"{interaction.user.display_name} ({interaction.user}) created the event: {title}!")

        await self.updateSchedule()

        if newEvent is not None:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            await interaction.followup.send(RESPONSE_EVENT_DONE.format(newEvent["title"], GUILD_ID, SCHEDULE, events[-1]["messageId"]))

    @app_commands.command(name="timestamp")
    @app_commands.guilds(GUILD)
    @app_commands.describe(time="Your local time", format = "Returns soley the specified format")
    @app_commands.choices(format = [app_commands.Choice(name=f"[{style}] {description}", value=style) for style, description in TIMESTAMP_STYLES.items()])
    async def timestamp(self, interaction: discord.Interaction, time: str, format: app_commands.Choice[str] = "None") -> None:
        """ Convert your local time to a dynamic Discord timestamp.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        time (str): Inputted time to be converted.
        format (app_commands.Choice[str]): An optional specific format - if not specified then all formats will be displayed.

        Returns:
        None.
        """
        await interaction.response.defer()

        # Get user time zone
        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        if not str(interaction.user.id) in memberTimeZones:
            timeZoneOutput = await self.changeTimeZone(interaction.user, isCommand=False)
            if not timeZoneOutput:
                await self.cancelCommand(interaction.user.dm_channel, "Timestamp creation")
                await interaction.edit_original_message(embed=Embed(title="❌ Timestamp creation canceled", description="You must provide a time zone in your DMs!", color=Color.red()))
                return
            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)

        # Get the inputted time
        try:
            time = datetimeParse(time)
        except ValueError:
            await interaction.edit_original_message(embed=Embed(title="❌ Invalid time", description="Provide a valid time!", color=Color.red()))
            return

        # Output timestamp
        timeZone = pytz.timezone(memberTimeZones[str(interaction.user.id)])
        time = timeZone.localize(time).astimezone(UTC)
        embed = Embed(color=Color.green())
        embed.set_footer(text=f"Local time: {time.strftime(TIME_FORMAT)}\nTime zone: {memberTimeZones[str(interaction.user.id)]}")
        if format == "None":  # All formats
            timestamps = [utils.format_dt(time, style=timestampStyle[0]) for timestampStyle in TIMESTAMP_STYLES.items()]
            embed.add_field(name="Timestamp", value="\n".join(timestamps), inline=True)
            embed.add_field(name="Copy this", value="\n".join([f"`{stamp}`" for stamp in timestamps]), inline=True)
            embed.add_field(name="Description", value="\n".join([f"`{timestampStyle[1]}`" for timestampStyle in TIMESTAMP_STYLES.items()]), inline=True)
        else:  # One specific format
            timestamp = utils.format_dt(time, style=format.value)
            embed.add_field(name="Timestamp", value=timestamp, inline=True)
            embed.add_field(name="Copy this", value=f"`{timestamp}`", inline=True)

        await interaction.edit_original_message(embed=embed)

    @app_commands.command(name="changetimezone")
    @app_commands.guilds(GUILD)
    async def timeZone(self, interaction: discord.Interaction) -> bool:
        """ Change your time zone preferences for your next scheduled event. """
        await interaction.response.send_message("Changing time zone preferences...")
        timeZoneOutput = await self.changeTimeZone(interaction.user, isCommand=True)
        if not timeZoneOutput:
            await self.cancelCommand(interaction.user, "Time zone preferences")

    async def changeTimeZone(self, author: discord.Member, isCommand: bool = True) -> bool:
        """ Changing a personal time zone.

        Parameters:
        author (discord.Member): The command author.
        isCommand (bool): If the command calling comes from the actual slash command.

        Returns:
        bool: If function executed successfully.
        """
        log.info(f"{author.display_name} ({author}) is updating their time zone preferences...")

        if not os.path.exists(MEMBER_TIME_ZONES_FILE):
            with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                json.dump({}, f, indent=4)

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

                if timezoneOk:
                    with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                        json.dump(memberTimeZones, f, indent=4)
                    embed = Embed(title=f"✅ Time zone preferences changed!", description=f"Updated to `{timeZone.zone}`!" if isInputNotNone else "Preference removed!", color=Color.green())
                    await dmChannel.send(embed=embed)
                    return True

            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False


class ScheduleButtons(discord.ui.Button):
    def __init__(self, instance, message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.message = message

    async def callback(self, interaction: discord.Interaction):
        await self.instance.buttonHandling(self.message, self, interaction)

    async def on_timeout(self):
        self.disabled = True


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Schedule(bot))
