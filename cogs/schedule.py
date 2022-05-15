import os
import re
import json
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
from dateutil.parser import parse as datetimeParse
import pytz

from discord import Embed, Colour
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_permission
from discord_slash.model import SlashCommandPermissionType

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *

EVENT_TIME_FORMAT = "%Y-%m-%d %I:%M %p"
TIMEOUT_EMBED = Embed(title=ERROR_TIMEOUT, color=Colour.red())
EVENTS_FILE = "data/events.json"
MEMBER_TIME_ZONES_FILE = "data/memberTimeZones.json"
EVENTS_HISTORY_FILE = "data/eventsHistory.json"
WORKSHOP_TEMPLATES_FILE = "data/workshopTemplates.json"
WORKSHOP_TEMPLATES_DELETED_FILE = "data/workshopDeletedTemplates.json"
WORKSHOP_INTEREST_FILE = "data/workshopInterest.json"

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

class Schedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if cogsReady["schedule"]:
            return
        log.debug(LOG_COG_READY.format("Schedule"), flush=True)
        cogsReady["schedule"] = True

        if not os.path.exists(EVENTS_HISTORY_FILE):
            with open(EVENTS_HISTORY_FILE, "w") as f:
                json.dump([], f, indent=4)

        if not os.path.exists(WORKSHOP_TEMPLATES_FILE):
            with open(WORKSHOP_TEMPLATES_FILE, "w") as f:
                json.dump([], f, indent=4)

        if not os.path.exists(WORKSHOP_TEMPLATES_DELETED_FILE):
            with open(WORKSHOP_TEMPLATES_DELETED_FILE, "w") as f:
                json.dump([], f, indent=4)

        await self.updateSchedule()
        try:
            self.autoDeleteEvents.start()
        except Exception:
            log.warning(LOG_COULDNT_START.format("autoDeleteEvents scheduler"))
        try:
            self.checkAcceptedReminder.start()
        except Exception:
            log.warning(LOG_COULDNT_START.format("checkAcceptedReminder scheduler"))

    async def saveEventToHistory(self, event, autoDeleted=False):
        guild = self.bot.get_guild(SERVER)
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
    async def autoDeleteEvents(self):
        while not self.bot.ready:
            await asyncio.sleep(1)
        log.debug(LOG_CHECKING.format("to auto delete events"))
        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            utcNow = UTC.localize(datetime.utcnow())
            deletedEvents = []
            for event in events:
                endTime = UTC.localize(datetime.strptime(event["endTime"], EVENT_TIME_FORMAT))
                if utcNow > endTime + timedelta(minutes=69):
                    log.debug(f"Auto deleting: {event['title']}.")
                    deletedEvents.append(event)
                    eventMessage = await self.bot.get_channel(SCHEDULE).fetch_message(event["messageId"])
                    await eventMessage.delete()
                    # author = self.bot.get_guild(SERVER).get_member(event["authorId"])
                    # await self.bot.get_channel(ARMA_DISCUSSION).send(f"{author.mention} You silly goose, you forgot to delete your operation. I'm not your mother, but this time I will do it for you")
                    if event["maxPlayers"] != 0:
                        await self.saveEventToHistory(event, autoDeleted=True)
            if len(deletedEvents) == 0:
                log.debug("No events were auto deleted!")
            for event in deletedEvents:
                events.remove(event)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            print(e)

    @tasks.loop(minutes=10)
    async def checkAcceptedReminder(self):
        while not self.bot.ready:
            await asyncio.sleep(1)
        guild = self.bot.get_guild(SERVER)
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
                startTime = UTC.localize(datetime.strptime(event["time"], EVENT_TIME_FORMAT))
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
                        log.debug(f"Pinging members in accepted not in VC: {[member.display_name for member in acceptedMembersNotOnline]}...")
                        await channel.send(" ".join(member.mention for member in acceptedMembersNotOnline) + SCHEDULE_REMINDER_VOICE.format(COMMAND, DEPLOYED, event["type"].lower(), SCHEDULE))
                    if len(onlineMembersNotAccepted) > 0:
                        log.debug(f"Pinging members in VC not in accepted: {[member.display_name for member in onlineMembersNotAccepted]}...")
                        await channel.send(" ".join(member.mention for member in onlineMembersNotAccepted) + SCHEDULE_REMINDER_INGAME.format(SCHEDULE))
        except Exception as e:
            print(e)

    @cog_ext.cog_slash(name="refreshschedule",
                        description=REFRESH_SCHEDULE_COMMAND_DESCRIPTION,
                        guild_ids=[SERVER],
                        permissions={
                            SERVER: [
                                create_permission(EVERYONE, SlashCommandPermissionType.ROLE, False),
                                create_permission(UNIT_STAFF, SlashCommandPermissionType.ROLE, True),
                                create_permission(SERVER_HAMSTER, SlashCommandPermissionType.ROLE, True),
                                create_permission(CURATOR, SlashCommandPermissionType.ROLE, True)
                            ]
                        })
    async def refreshSchedule(self, ctx: SlashContext):
        await ctx.send(RESPONSE_REFRESHING.format(SCHEDULE))
        log.info(f"{ctx.author.display_name} ({ctx.author.name}#{ctx.author.discriminator}) is refreshing the schedule...")
        await self.updateSchedule()

    async def updateSchedule(self):
        self.lastUpdate = datetime.utcnow()
        channel = self.bot.get_channel(SCHEDULE)
        await channel.purge(limit=None, check=lambda m: m.author.id in FRIENDLY_SNEKS)

        await channel.send(SCHEDULE_INTRO_MESSAGE.format(", ".join([f"**{channel.guild.get_member(name).display_name}**" for name in DEVELOPERS if channel.guild.get_member(name) is not None])))

        if os.path.exists(EVENTS_FILE):
            try:
                with open(EVENTS_FILE) as f:
                    events = json.load(f)
                if len(events) == 0:
                    await channel.send(SCHEDULE_EMPTY_1)
                    await channel.send(SCHEDULE_EMPTY_2)
                for event in sorted(events, key=lambda e: datetime.strptime(e["time"], EVENT_TIME_FORMAT), reverse=True):
                    embed = self.getEventEmbed(event)
                    msg = await channel.send(embed=embed)
                    if event["reservableRoles"] is not None:
                        emojis = ("✅", "⏱", "❌", "❓", "👤", "✏️", "🗑")
                    else:
                        emojis = ("✅", "⏱", "❌", "❓", "✏️", "🗑")
                    for emoji in emojis:
                        await msg.add_reaction(emoji)
                    event["messageId"] = msg.id
                with open(EVENTS_FILE, "w") as f:
                    json.dump(events, f, indent=4)
            except Exception as e:
                print(e)
        else:
            with open(EVENTS_FILE, "w") as f:
                json.dump([], f, indent=4)
        if not os.path.exists(MEMBER_TIME_ZONES_FILE):
            with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                json.dump({}, f, indent=4)

    def getEventEmbed(self, event):
        guild = self.bot.get_guild(SERVER)

        colors = {
            "Operation": Colour.green(),
            "Workshop": Colour.blue(),
            "Event": Colour.gold()
        }
        embed = Embed(title=event["title"], description=event["description"], color=colors[event.get("type", "Operation")])

        if event["reservableRoles"] is not None:
            embed.add_field(name="\u200B", value="\u200B", inline=False)
            embed.add_field(name=f"Reservable Roles ({len([role for role, memberId in event['reservableRoles'].items() if memberId is not None])}/{len(event['reservableRoles'])}) 👤", value="\n".join(f"{roleName} - {('*' + member.display_name + '*' if (member := guild.get_member(memberId)) is not None else '**VACANT**') if memberId is not None else '**VACANT**'}" for roleName, memberId in event["reservableRoles"].items()), inline=False)
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        embed.add_field(name="Time", value=f"<t:{round(UTC.localize(datetime.strptime(event['time'], EVENT_TIME_FORMAT)).timestamp())}:F> - <t:{round(UTC.localize(datetime.strptime(event['endTime'], EVENT_TIME_FORMAT)).timestamp())}:t>", inline=False)
        embed.add_field(name="Duration", value=event["duration"], inline=False)
        embed.add_field(name="Map", value="Unspecified" if event["map"] is None else event["map"], inline=False)
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
        embed.timestamp = UTC.localize(datetime.strptime(event["time"], EVENT_TIME_FORMAT))

        return embed

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id != SCHEDULE:
            return
        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)

            if any(event["messageId"] == payload.message_id for event in events) and self.bot.ready and not payload.member.bot:
                scheduleNeedsUpdate = True
                removeReaction = True
                event = [event for event in events if event["messageId"] == payload.message_id][0]
                if "declinedForTiming" not in event:
                    event["declinedForTiming"] = []
                eventMessage = await self.bot.get_channel(SCHEDULE).fetch_message(event["messageId"])
                if payload.emoji.name == "✅":
                    if payload.member.id in event["declined"]:
                        event["declined"].remove(payload.member.id)
                    if payload.member.id in event["declinedForTiming"]:
                        event["declinedForTiming"].remove(payload.member.id)
                    if payload.member.id in event["tentative"]:
                        event["tentative"].remove(payload.member.id)
                    if payload.member.id not in event["accepted"]:
                        event["accepted"].append(payload.member.id)
                elif payload.emoji.name == "❌":
                    if payload.member.id in event["accepted"]:
                        event["accepted"].remove(payload.member.id)
                    if payload.member.id in event["declinedForTiming"]:
                        event["declinedForTiming"].remove(payload.member.id)
                    if payload.member.id in event["tentative"]:
                        event["tentative"].remove(payload.member.id)
                    if payload.member.id not in event["declined"]:
                        event["declined"].append(payload.member.id)
                    if event["reservableRoles"] is not None:
                        for roleName in event["reservableRoles"]:
                            if event["reservableRoles"][roleName] == payload.member.id:
                                event["reservableRoles"][roleName] = None
                elif payload.emoji.name == "⏱":
                    if payload.member.id in event["accepted"]:
                        event["accepted"].remove(payload.member.id)
                    if payload.member.id in event["tentative"]:
                        event["tentative"].remove(payload.member.id)
                    if payload.member.id in event["declined"]:
                        event["declined"].remove(payload.member.id)
                    if payload.member.id not in event["declinedForTiming"]:
                        event["declinedForTiming"].append(payload.member.id)
                    if event["reservableRoles"] is not None:
                        for roleName in event["reservableRoles"]:
                            if event["reservableRoles"][roleName] == payload.member.id:
                                event["reservableRoles"][roleName] = None
                elif payload.emoji.name == "❓":
                    if payload.member.id in event["accepted"]:
                        event["accepted"].remove(payload.member.id)
                    if payload.member.id in event["declined"]:
                        event["declined"].remove(payload.member.id)
                    if payload.member.id in event["declinedForTiming"]:
                        event["declinedForTiming"].remove(payload.member.id)
                    if payload.member.id not in event["tentative"]:
                        event["tentative"].append(payload.member.id)
                    if event["reservableRoles"] is not None:
                        for roleName in event["reservableRoles"]:
                            if event["reservableRoles"][roleName] == payload.member.id:
                                event["reservableRoles"][roleName] = None
                elif payload.emoji.name == "👤":
                    await self.reserveRole(payload.member, event)
                elif payload.emoji.name == "✏️":
                    if payload.member.id == event["authorId"] or any(role.id == UNIT_STAFF for role in payload.member.roles):
                        reorderEvents = await self.editEvent(payload.member, event, isTemplateEdit=False)
                        if reorderEvents:
                            with open(EVENTS_FILE, "w") as f:
                                json.dump(events, f, indent=4)
                            await self.updateSchedule()
                            return
                    else:
                        scheduleNeedsUpdate = False
                elif payload.emoji.name == "🗑":
                    if payload.member.id == event["authorId"] or any(role.id == UNIT_STAFF for role in payload.member.roles):
                        eventDeleted = await self.deleteEvent(payload.member, eventMessage, event)
                        if eventDeleted:
                            events.remove(event)
                            removeReaction = False
                    scheduleNeedsUpdate = False
                else:
                    scheduleNeedsUpdate = False
                if removeReaction:
                    try:
                        await eventMessage.remove_reaction(payload.emoji, payload.member)
                    except Exception:
                        pass
                if scheduleNeedsUpdate:
                    try:
                        embed = self.getEventEmbed(event)
                        await eventMessage.edit(embed=embed)
                    except Exception:
                        pass

            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            print(e)

    async def cancelCommand(self, channel, abortText:str) -> None:
        """
            Sends an abort response to the user.

            Parameters:
            channel: The users DM channel where the message is sent.
            abortText (str): The embed title - what is aborted.

            Returns:
            None
        """
        await channel.send(embed=Embed(title=ABORT_CANCELED.format(abortText), color=Colour.red()))

    async def reserveRole(self, member, event) -> None:
        """
            Reserving a single role on an event.

            Parameters:
            isTemplateEdit (bool): If the event is a template.

            Returns:
            None
        """
        reservationTime = datetime.utcnow()
        guild = self.bot.get_guild(SERVER)

        if member.id in event["declined"]:
            event["declined"].remove(member.id)
        if member.id in event["declinedForTiming"]:
            event["declinedForTiming"].remove(member.id)
        if member.id in event["tentative"]:
            event["tentative"].remove(member.id)
        if member.id not in event["accepted"]:
            event["accepted"].append(member.id)

        if event["maxPlayers"] is not None and event["accepted"].index(member.id) >= event["maxPlayers"]:
            embed = Embed(title="❌ Sorry, seems like there's no space left in the :b:op!", color=Colour.red())
            try:
                await member.send(embed=embed)
            except Exception as e:
                print(member, e)
            return

        vacantRoles = [roleName for roleName, memberId in event["reservableRoles"].items() if memberId is None or guild.get_member(memberId) is None]
        currentRole = [roleName for roleName, memberId in event["reservableRoles"].items() if memberId == member.id][0] if member.id in event["reservableRoles"].values() else None

        reserveOk = False
        color = Colour.gold()
        while not reserveOk:
            embed = Embed(title="Which role would you like to reserve?", description="Enter a number from the list.\nEnter `none` un-reserve any role you have occupied.", color=color)
            embed.add_field(name="Your current role", value=currentRole if currentRole is not None else "None", inline=False)
            embed.add_field(name="Vacant roles", value="\n".join(f"**{idx}** {roleName}" for idx, roleName in enumerate(vacantRoles, 1)) if len(vacantRoles) > 0 else "None", inline=False)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Colour.red()

            try:
                msg = await member.send(embed=embed)
            except Exception as e:
                print(member, e)
                return
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
                    return
                else:
                    reserveOk = False
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

            if reserveOk:
                if reservedRole is not None:
                    if event["reservableRoles"] is not None:
                        for roleName in event["reservableRoles"]:
                            if event["reservableRoles"][roleName] == member.id:
                                event["reservableRoles"][roleName] = None
                        if event["reservableRoles"][reservedRole] is None or guild.get_member(event["reservableRoles"][reservedRole]) is None:
                            event["reservableRoles"][reservedRole] = member.id
                else:
                    if event["reservableRoles"] is not None:
                        for roleName in event["reservableRoles"]:
                            if event["reservableRoles"][roleName] == member.id:
                                event["reservableRoles"][roleName] = None

                if reservationTime > self.lastUpdate:
                    embed = Embed(title=CHECK_COMPLETED.format("Role reservation"), color=Colour.green())
                    await dmChannel.send(embed=embed)
                else:
                    embed = Embed(title="❌ Schedule was updated while you were reserving a role. Try again!", color=Colour.red())
                    await dmChannel.send(embed=embed)
                    log.debug(LOG_SCHEDULE_UPDATE_ERROR.format(member.display_name, member.name, member.discriminator, "reserving a role"))

    async def editEvent(self, author, event, isTemplateEdit: bool = False) -> bool:
        editingTime = datetime.utcnow()
        editOk = False
        color = Colour.gold()
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
                log.info(f"{author.display_name} ({author.name}#{author.discriminator}) is editing the event: {event['title']}")
                embed.insert_field_at(0, name="**0** Type", value=f"```txt\n{event['type']}\n```", inline=False)
                embed.add_field(name="**7** Time", value=f"<t:{round(UTC.localize(datetime.strptime(event['time'], EVENT_TIME_FORMAT)).timestamp())}:F>", inline=False)
                embed.add_field(name="**8** Duration", value=f"```txt\n{event['duration']}\n```", inline=False)
                choiceNumbers:list = [str(x) for x in range(9)]
            else:
                embed.insert_field_at(0, name="**0** Template Name", value=f"```txt\n{event['name']}\n```", inline=False)
                embed.add_field(name="**7** Duration", value=f"```txt\n{event['duration']}\n```", inline=False)
                choiceNumbers:list = [str(x) for x in range(8)]
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Colour.red()

            try:
                msg = await author.send(embed=embed)
            except Exception as e:
                print(author, e)
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
            """
                Editing the duration of an event or template.

                Parameters:
                isTemplateEdit (bool): If the event is a template.

                Returns:
                bool: If function executed successfully.
            """
            color = Colour.gold()
            duration = "INVALID INPUT"
            while not re.match(SCHEDULE_EVENT_DURATION_REGEX, duration):
                embed = Embed(title=SCHEDULE_EVENT_DURATION_QUESTION.format("event"), description=SCHEDULE_EVENT_DURATION_PROMPT, colour=color)
                embed.set_footer(text=SCHEDULE_CANCEL)
                color = Colour.red()
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
                startTime = UTC.localize(datetime.strptime(event["time"], EVENT_TIME_FORMAT))
                delta = timedelta(hours=hours, minutes=minutes)
                endTime = startTime + delta
                event["endTime"] = endTime.strftime(EVENT_TIME_FORMAT)
            return True

        match choice:
            case "0":
                if not isTemplateEdit:
                    eventTypeNum = None
                    color = Colour.gold()
                    while eventTypeNum not in ("1", "2", "3"):
                        embed = Embed(title=":pencil2: What is the type of your event?", description=SCHEDULE_NUMBER_FROM_TO.format(1, 3), color=color)
                        embed.add_field(name="Type", value="**1** 🟩 Operation\n**2** 🟦 Workshop\n**3** 🟨 Event")
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        color = Colour.red()
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
                    embed = Embed(title=SCHEDULE_EVENT_TEMPLATE_SAVE_NAME_QUESTION, color=Colour.gold())
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
                embed = Embed(title=SCHEDULE_EVENT_TITLE.format(event.get("type", "operation").lower()), color=Colour.gold())
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
                embed = Embed(title=SCHEDULE_EVENT_DESCRIPTION_QUESTION, description=SCHEDULE_EVENT_DESCRIPTION.format(event["description"]), color=Colour.gold())
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
                embed = Embed(title=SCHEDULE_EVENT_URL_TITLE, description=SCHEDULE_EVENT_URL_DESCRIPTION, color=Colour.gold())
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
                embed = Embed(title=SCHEDULE_EVENT_RESERVABLE, description=SCHEDULE_EVENT_RESERVABLE_DIALOG + "\n(Editing the name of a role will make it vacant, but roles which keep their exact names will keep their reservations).", color=Colour.gold())
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
                color = Colour.gold()
                while not mapOK:
                    embed = Embed(title=SCHEDULE_EVENT_MAP_PROMPT, description=SCHEDULE_NUMBER_FROM_TO_OR_NONE.format(1, len(MAPS)), color=color)
                    color = Colour.red()
                    embed.add_field(name="Map", value="\n".join(f"**{idx}** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
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
                color = Colour.gold()
                while not attendanceOk:
                    embed = Embed(title=SCHEDULE_EVENT_MAX_PLAYERS, description=SCHEDULE_EVENT_MAX_PLAYERS_DESCRIPTION, color=color)
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    color = Colour.red()
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
                        color = Colour.gold()
                        while not isFormatCorrect:
                            embed = Embed(title=SCHEDULE_EVENT_TIME.format("event"), description=SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(timeZone.zone), color=color)
                            embed.add_field(name="Current Value", value=UTC.localize(datetime.strptime(event["time"], EVENT_TIME_FORMAT)).astimezone(timeZone).strftime(EVENT_TIME_FORMAT))
                            embed.set_footer(text=SCHEDULE_CANCEL)
                            color = Colour.red()
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
                                embed = Embed(title=SCHEDULE_EVENT_TIME_TOMORROW, description=SCHEDULE_EVENT_TIME_TOMORROW_PREVIEW.format(round(startTime.timestamp()), round(newStartTime.timestamp())), color=Colour.orange())
                                await dmChannel.send(embed=embed)
                                startTime = newStartTime
                                startTimeOk = True
                            else:
                                embed = Embed(title=SCHEDULE_EVENT_TIME_PAST_QUESTION, description=SCHEDULE_EVENT_TIME_PAST_PROMPT, color=Colour.orange())
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
                    event["time"] = startTime.strftime(EVENT_TIME_FORMAT)
                    event["endTime"] = endTime.strftime(EVENT_TIME_FORMAT)
                    reorderEvents = True
                    guild = self.bot.get_guild(SERVER)
                    embed = Embed(title=SCHEDULE_EVENT_START_TIME_CHANGE_TITLE.format(event["title"]), description=SCHEDULE_EVENT_START_TIME_CHANGE_DESCRIPTION.format(round(UTC.localize(datetime.strptime(oldStartTime, EVENT_TIME_FORMAT)).timestamp()), round(UTC.localize(datetime.strptime(event["time"], EVENT_TIME_FORMAT)).timestamp())), color=Colour.orange())
                    for memberId in event["accepted"] + event.get("declinedForTiming", []) + event["tentative"]:
                        member = guild.get_member(memberId)
                        if member is not None:
                            try:
                                await member.send(embed=embed)
                            except Exception as e:
                                print(member, e)
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
                embed = Embed(title=CHECK_EDITED.format(event["type"]), color=Colour.green())
                await dmChannel.send(embed=embed)
                log.info(f"{author.display_name} ({author.name}#{author.discriminator}) edited the event: {event['title']}.")
                return reorderEvents
            else:
                embed = Embed(title="❌ Schedule was updated while you were editing your operation. Try again!", color=Colour.red())
                await dmChannel.send(embed=embed)
                log.info(LOG_SCHEDULE_UPDATE_ERROR.format(author.display_name, author.name, author.discriminator, "editing an event"))
                return False
        else:  # Template
            embed = Embed(title=CHECK_EDITED.format("Template"), color=Colour.green())
            await dmChannel.send(embed=embed)
            log.warning(f"{author.display_name} ({author.name}#{author.discriminator}) edited the template: {event['name']}!")

    async def deleteEvent(self, author, message, event) -> bool:
        try:
            msg = await author.send(embed=Embed(title=SCHEDULE_EVENT_CONFIRM_DELETE.format(f"{event['type'].lower()}: `{event['title']}`"), color=Colour.orange()))
        except Exception as e:
            print(author, e)
            return False
        await msg.add_reaction("🗑")
        try:
            await self.bot.wait_for("reaction_add", timeout=TIME_ONE_MIN, check=lambda reaction, user, author=author: reaction.emoji == "🗑" and user == author)
        except asyncio.TimeoutError:
            await author.send(embed=TIMEOUT_EMBED)
            return False
        await message.delete()
        try:
            embed = Embed(title=CHECK_DELETED.format(event["type"]), color=Colour.green())
            await author.send(embed=embed)

            utcNow = UTC.localize(datetime.utcnow())
            startTime = UTC.localize(datetime.strptime(event["time"], EVENT_TIME_FORMAT))
            if event["maxPlayers"] != 0 and utcNow > startTime + timedelta(minutes=30):
                await self.saveEventToHistory(event)
            else:
                guild = self.bot.get_guild(SERVER)
                for memberId in event["accepted"] + event.get("declinedForTiming", []) + event["tentative"]:
                    member = guild.get_member(memberId)
                    if member is not None:
                        embed = Embed(title=SCHEDULE_EVENT_DELETED_TITLE.format(event.get("type", "Operation"), event["title"]), description=SCHEDULE_EVENT_DELETED_DESCRIPTION.format(event.get("type", "Operation").lower(), round(UTC.localize(datetime.strptime(event["time"], EVENT_TIME_FORMAT)).timestamp())), color=Colour.red())
                        try:
                            await member.send(embed=embed)
                        except Exception as e:
                            print(member, e)
        except Exception as e:
            print(e)
        return True

    @cog_ext.cog_slash(name="bop", description=SCHEDULE_COMMAND_DESCRIPTION.format("an operation"), guild_ids=[SERVER])
    async def bop(self, ctx: SlashContext):
        await self.scheduleOperation(ctx)

    @cog_ext.cog_slash(name="operation", description=SCHEDULE_COMMAND_DESCRIPTION.format("an operation"), guild_ids=[SERVER])
    async def operation(self, ctx: SlashContext):
        await self.scheduleOperation(ctx)

    async def scheduleOperation(self, ctx) -> None:
        """
            Scheduling an operation.

            Parameters:
            ctx: Context.

            Returns:
            None
        """
        await ctx.send(RESPONSE_EVENT_PROGRESS.format(":b:op."))
        log.info(LOG_CREATING_EVENT.format(ctx.author.display_name, ctx.author.name, ctx.author.discriminator, "an operation"))

        utcNow = UTC.localize(datetime.utcnow())
        authorId = ctx.author.id

        embed = Embed(title=SCHEDULE_EVENT_TITLE.format("operation"), description="Remeber, operation names should start with the word `Operation`\nE.g. Operation Red Tide.", color=Colour.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        try:
            msg = await ctx.author.send(embed=embed)
        except Exception as e:
            print(ctx.author, e)
            return
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            title = response.content.strip()
            if title.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Operation scheduling")
                return
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        embed = Embed(title=SCHEDULE_EVENT_DESCRIPTION_QUESTION, color=Colour.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_THIRTY_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            description = response.content.strip()
            if description.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Operation scheduling")
                return
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        embed = Embed(title=SCHEDULE_EVENT_URL_TITLE, description=SCHEDULE_EVENT_URL_DESCRIPTION, color=Colour.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            externalURL = response.content.strip()
            if externalURL.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Operation scheduling")
                return
            if externalURL.lower() == "none" or (len(externalURL) == 4 and "n" in externalURL.lower()):
                externalURL = None
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        embed = Embed(title=SCHEDULE_EVENT_RESERVABLE, description=SCHEDULE_EVENT_RESERVABLE_DIALOG, color=Colour.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        mapOK = False
        color = Colour.gold()
        while not mapOK:
            embed = Embed(title=SCHEDULE_EVENT_MAP_PROMPT, description=SCHEDULE_NUMBER_FROM_TO_OR_NONE.format(1, len(MAPS)), color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Colour.red()
            embed.add_field(name="Map", value="\n".join(f"**{idx}** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        attendanceOk = False
        color = Colour.gold()
        while not attendanceOk:
            embed = Embed(title=SCHEDULE_EVENT_MAX_PLAYERS, description=SCHEDULE_EVENT_MAX_PLAYERS_DESCRIPTION, color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Colour.red()
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        color = Colour.gold()
        duration = "INVALID INPUT"
        while not re.match(SCHEDULE_EVENT_DURATION_REGEX, duration):
            embed = Embed(title=SCHEDULE_EVENT_DURATION_QUESTION.format("operation"), description=SCHEDULE_EVENT_DURATION_PROMPT, color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        if str(ctx.author.id) in memberTimeZones:
            try:
                timeZone = pytz.timezone(memberTimeZones[str(ctx.author.id)])
            except pytz.exceptions.UnknownTimeZoneError:
                timeZone = UTC
        else:
            timeZoneOutput = await self.changeTimeZone(ctx.author, isCommand=False)
            if not timeZoneOutput:
                await self.cancelCommand(dmChannel, "Event editing")
                return False
            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)

        timeZone = pytz.timezone(memberTimeZones[str(ctx.author.id)])
        eventCollision = True
        while eventCollision:
            eventCollision = False
            startTimeOk = False
            while not startTimeOk:
                isFormatCorrect = False
                color = Colour.gold()
                while not isFormatCorrect:
                    embed = Embed(title=SCHEDULE_EVENT_TIME.format("operation"), description=SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(timeZone.zone), color=color)
                    utcNow = datetime.utcnow()
                    nextHalfHour = utcNow + (datetime.min - utcNow) % timedelta(minutes=30)
                    embed.add_field(name="Example", value=UTC.localize(nextHalfHour).astimezone(timeZone).strftime(EVENT_TIME_FORMAT))
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    color = Colour.red()
                    await dmChannel.send(embed=embed)
                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                        startTime = response.content.strip()
                        if startTime.lower() == "cancel":
                            await self.cancelCommand(dmChannel, "Operation scheduling")
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
                        embed = Embed(title=SCHEDULE_EVENT_TIME_TOMORROW, description=SCHEDULE_EVENT_TIME_TOMORROW_PREVIEW.format(round(startTime.timestamp()), round(newStartTime.timestamp())), color=Colour.orange())
                        await dmChannel.send(embed=embed)
                        startTime = newStartTime
                        startTimeOk = True
                    else:
                        embed = Embed(title=SCHEDULE_EVENT_TIME_PAST_QUESTION, description=SCHEDULE_EVENT_TIME_PAST_PROMPT, color=Colour.orange())
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        await dmChannel.send(embed=embed)
                        try:
                            response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, author=ctx.author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                            keepStartTime = response.content.strip().lower()
                            if keepStartTime == "cancel":
                                await self.cancelCommand(dmChannel, "Operation scheduling")
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
                    if event.get("type", "Operation") == "Event":
                        continue
                    eventStartTime = UTC.localize(datetime.strptime(event["time"], EVENT_TIME_FORMAT))
                    eventEndTime = UTC.localize(datetime.strptime(event["endTime"], EVENT_TIME_FORMAT))
                    if (eventStartTime <= startTime < eventEndTime) or (eventStartTime <= endTime < eventEndTime) or (startTime <= eventStartTime < endTime):
                        eventCollision = True
                        embed = Embed(title=SCHEDULE_EVENT_ERROR_COLLISION.format(event["title"]), description=SCHEDULE_EVENT_ERROR_DESCRIPTION, colour=Colour.red())
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        await dmChannel.send(embed=embed)
                    elif eventEndTime < startTime and eventEndTime + timedelta(hours=1) > startTime:
                        eventCollision = True
                        embed = Embed(title=SCHEDULE_EVENT_ERROR_PADDING_EARLY.format(event["title"]), description=SCHEDULE_EVENT_ERROR_DESCRIPTION, colour=Colour.red())
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        await dmChannel.send(embed=embed)
                    elif endTime < eventStartTime and endTime + timedelta(hours=1) > eventStartTime:
                        eventCollision = True
                        embed = Embed(title=SCHEDULE_EVENT_ERROR_PADDING_LATE.format(event["title"]), description=SCHEDULE_EVENT_ERROR_DESCRIPTION, colour=Colour.red())
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        await dmChannel.send(embed=embed)

                    if eventCollision:
                        try:
                            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                            collisionResponse = response.content.strip().lower()
                            if collisionResponse == "cancel":
                                await self.cancelCommand(dmChannel, "Operation scheduling")
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
                "time": startTime.strftime(EVENT_TIME_FORMAT),
                "endTime": endTime.strftime(EVENT_TIME_FORMAT),
                "duration": f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}",
                "messageId": None,
                "accepted": [],
                "declined": [],
                "tentative": [],
                "type": "Operation"  # Operation, Workshop, Event
            }
            events.append(newEvent)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            print(e)
            newEvent = None

        embed = Embed(title=CHECK_CREATED.format("Operation"), color=Colour.green())
        await dmChannel.send(embed=embed)
        log.info(LOG_CREATED_EVENT.format(ctx.author.display_name, ctx.author.name, ctx.author.discriminator, f"the operation: {title}"))

        await self.updateSchedule()

        if newEvent is not None:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            await ctx.send(RESPONSE_EVENT_DONE.format(":b:op", newEvent["title"], SERVER, SCHEDULE, events[-1]["messageId"]))

    @cog_ext.cog_slash(name="ws", description=SCHEDULE_COMMAND_DESCRIPTION.format("a workshop"), guild_ids=[SERVER])
    async def ws(self, ctx: SlashContext):
        await self.scheduleWorkshop(ctx)

    @cog_ext.cog_slash(name="workshop", description=SCHEDULE_COMMAND_DESCRIPTION.format("a workshop"), guild_ids=[SERVER])
    async def workshop(self, ctx: SlashContext):
        await self.scheduleWorkshop(ctx)

    async def scheduleWorkshop(self, ctx) -> None:
        """
            Scheduling a workshop.

            Parameters:
            ctx: Context.

            Returns:
            None
        """
        await ctx.send(RESPONSE_EVENT_PROGRESS.format("workshop"))
        log.info(LOG_CREATING_EVENT.format(ctx.author.display_name, ctx.author.name, ctx.author.discriminator, "a workshop"))

        utcNow = UTC.localize(datetime.utcnow())
        authorId = ctx.author.id

        templateActionRepeat: bool = True
        color = Colour.gold()
        while templateActionRepeat:
            with open(WORKSHOP_TEMPLATES_FILE) as f:
                workshopTemplates = json.load(f)
            embed = Embed(title=":clipboard: Templates", description="Enter a template number.\nEnter `none` to make a workshop from scratch.\n\nEdit template: `edit` + template number. E.g. `edit 2`.\nDelete template: `delete` + template number. E.g. `delete 4`. **IRREVERSIBLE!**", color=color)
            embed.add_field(name="Templates", value="\n".join(f"**{idx}** {template['name']}" for idx, template in enumerate(workshopTemplates, 1)) if len(workshopTemplates) > 0 else "-")
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Colour.red()
            try:
                msg = await ctx.author.send(embed=embed)
            except Exception as e:
                print(ctx.author, e)
                return
            dmChannel = msg.channel

            try:
                response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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
                                msg = await dmChannel.send(embed=Embed(title=SCHEDULE_EVENT_CONFIRM_DELETE.format(f"template: `{workshopTemplate['name']}`"), color=Colour.orange()))
                            except Exception as e:
                                print(ctx.author, e)
                                return
                            await msg.add_reaction("🗑")
                            try:
                                await self.bot.wait_for("reaction_add", timeout=TIME_ONE_MIN, check=lambda reaction, user, author=ctx.author: reaction.emoji == "🗑" and user == author)
                            except asyncio.TimeoutError:
                                await ctx.author.send(embed=TIMEOUT_EMBED)
                                return
                            log.warning(f"{ctx.author.display_name} ({ctx.author.name}#{ctx.author.discriminator}) deleted the workshop template: {workshopTemplate['name']}!")

                            with open(WORKSHOP_TEMPLATES_DELETED_FILE) as f:
                                workshopTempaltesDeleted = json.load(f)
                            workshopTempaltesDeleted.append(workshopTemplates[int(templateAction.split(" ")[-1]) - 1])
                            with open(WORKSHOP_TEMPLATES_DELETED_FILE, "w") as f:
                                json.dump(workshopTempaltesDeleted, f, indent=4)

                            workshopTemplates.pop(int(templateAction.split(" ")[-1]) - 1)
                            with open(WORKSHOP_TEMPLATES_FILE, "w") as f:
                                json.dump(workshopTemplates, f, indent=4)
                            await dmChannel.send(embed=Embed(title=CHECK_DELETED.format("Template"), color=Colour.green()))
                            return

                    elif templateAction.lower().startswith("edit"):
                        templateNumber = templateAction.split(" ")[-1]
                        if templateNumber.isdigit() and int(templateNumber) <= len(workshopTemplates) and int(templateNumber) > 0:
                            workshopTemplate = workshopTemplates[int(templateNumber) - 1]
                            log.info(f"{ctx.author.display_name} ({ctx.author.name}#{ctx.author.discriminator}) is editing the workshop template: {workshopTemplate['name']}...")
                            await self.editEvent(ctx.author, workshopTemplate, isTemplateEdit=True)

                            workshopTemplates[int(templateNumber) - 1] = workshopTemplate
                            with open(WORKSHOP_TEMPLATES_FILE, "w") as f:
                                json.dump(workshopTemplates, f, indent=4)
                            return

                    else: # Select template
                        if templateAction.isdigit() and int(templateAction) <= len(workshopTemplates) and int(templateAction) > 0:
                            template = workshopTemplates[int(templateAction) - 1]
                            templateActionRepeat = False

            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

        if template is None:
            embed = Embed(title=SCHEDULE_EVENT_TITLE.format("workshop"), color=Colour.gold())
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                title = response.content.strip()
                if title.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Workshop scheduling")
                    return
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        else:
            title = template["title"]

        if template is None:
            embed = Embed(title=SCHEDULE_EVENT_DESCRIPTION_QUESTION, color=Colour.gold())
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_THIRTY_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                description = response.content.strip()
                if description.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Workshop scheduling")
                    return
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        else:
            description = template["description"]

        if template is None:
            embed = Embed(title=SCHEDULE_EVENT_URL_TITLE, description=SCHEDULE_EVENT_URL_DESCRIPTION, color=Colour.gold())
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        if template is None:
            embed = Embed(title=SCHEDULE_EVENT_RESERVABLE, description=SCHEDULE_EVENT_RESERVABLE_DIALOG, color=Colour.gold())
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        if template is None:
            mapOk = False
            color=Colour.gold()
            while not mapOk:
                embed = Embed(title=SCHEDULE_EVENT_MAP_PROMPT, description=SCHEDULE_NUMBER_FROM_TO_OR_NONE.format(1, len(MAPS)), color=color)
                color=Colour.red()
                embed.add_field(name="Map", value="\n".join(f"**{idx}** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
                embed.set_footer(text=SCHEDULE_CANCEL)
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        if template is None:
            attendanceOk = False
            color = Colour.gold()
            while not attendanceOk:
                embed = Embed(title=SCHEDULE_EVENT_MAX_PLAYERS, description=SCHEDULE_EVENT_MAX_PLAYERS_DESCRIPTION, color=color)
                embed.set_footer(text=SCHEDULE_CANCEL)
                color = Colour.red()
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        if template is None:
            color = Colour.gold()
            duration = "INVALID INPUT"
            while not re.match(SCHEDULE_EVENT_DURATION_REGEX, duration):
                embed = Embed(title=SCHEDULE_EVENT_DURATION_QUESTION.format("workshop"), description=SCHEDULE_EVENT_DURATION_PROMPT, colour=color)
                embed.set_footer(text=SCHEDULE_CANCEL)
                color=Colour.red()
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        if template is None:
            workshopInterestOk = False
            color = Colour.gold()
            while not workshopInterestOk:
                with open(WORKSHOP_INTEREST_FILE) as f:
                    workshopInterestOptions = [{"name": name, "title": wsInterest["title"]} for name, wsInterest in json.load(f).items()]
                embed = Embed(title=":link: Which workshop waiting list is your workshop linked to?", description=SCHEDULE_NUMBER_FROM_TO_OR_NONE.format(1, len(workshopInterestOptions)), color=color)
                embed.add_field(name="Workshop Lists", value="\n".join(f"**{idx}** {wsInterest['title']}" for idx, wsInterest in enumerate(workshopInterestOptions, 1)))
                embed.set_footer(text=SCHEDULE_CANCEL)
                color = Colour.red()
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        if str(ctx.author.id) in memberTimeZones:
            try:
                timeZone = pytz.timezone(memberTimeZones[str(ctx.author.id)])
            except pytz.exceptions.UnknownTimeZoneError:
                timeZone = UTC
        else:
            timeZoneOutput = await self.changeTimeZone(ctx.author, isCommand=False)
            if not timeZoneOutput:
                await self.cancelCommand(dmChannel, "Workshop scheduling")
                return False
        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        timeZone = pytz.timezone(memberTimeZones[str(ctx.author.id)])
        eventCollision = True
        while eventCollision:
            eventCollision = False

            startTimeOk = False
            while not startTimeOk:
                isFormatCorrect = False
                color = Colour.gold()
                while not isFormatCorrect:
                    embed = Embed(title=SCHEDULE_EVENT_TIME.format("workshop"), description=SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(timeZone.zone), color=color)
                    utcNow = datetime.utcnow()
                    nextHalfHour = utcNow + (datetime.min - utcNow) % timedelta(minutes=30)
                    embed.add_field(name="Example", value=UTC.localize(nextHalfHour).astimezone(timeZone).strftime(EVENT_TIME_FORMAT))
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    color = Colour.red()
                    await dmChannel.send(embed=embed)
                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                        startTime = response.content.strip()
                        if startTime.lower() == "cancel":
                            await self.cancelCommand(dmChannel, "Workshop scheduling")
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
                        embed = Embed(title=SCHEDULE_EVENT_TIME_TOMORROW, description=SCHEDULE_EVENT_TIME_TOMORROW_PREVIEW.format(round(startTime.timestamp()), round(newStartTime.timestamp())), color=Colour.orange())
                        await dmChannel.send(embed=embed)
                        startTime = newStartTime
                        startTimeOk = True
                    else:
                        embed = Embed(title=SCHEDULE_EVENT_TIME_PAST_QUESTION, description=SCHEDULE_EVENT_TIME_PAST_PROMPT, color=Colour.orange())
                        embed.set_footer(text=SCHEDULE_CANCEL)
                        await dmChannel.send(embed=embed)
                        try:
                            response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, author=ctx.author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                            keepStartTime = response.content.strip().lower()
                            if keepStartTime == "cancel":
                                await self.cancelCommand(dmChannel, "Workshop scheduling")
                                return
                        except asyncio.TimeoutError:
                            await dmChannel.send(embed=TIMEOUT_EMBED)
                            return
                        if keepStartTime in ("yes", "y"):
                            startTimeOk = True
                else:
                    startTimeOk = True
            endTime = startTime + delta

            with open(EVENTS_FILE) as f:
                events = json.load(f)

            for event in events:
                if event.get("type", "Operation") != "Operation":
                    continue
                eventStartTime = UTC.localize(datetime.strptime(event["time"], EVENT_TIME_FORMAT))
                eventEndTime = UTC.localize(datetime.strptime(event["endTime"], EVENT_TIME_FORMAT))
                if (eventStartTime <= startTime < eventEndTime) or (eventStartTime <= endTime < eventEndTime) or (startTime <= eventStartTime < endTime):
                    eventCollision = True
                    embed = Embed(title=SCHEDULE_EVENT_ERROR_COLLISION.format(event["title"]), description=SCHEDULE_EVENT_ERROR_DESCRIPTION, colour=Colour.red())
                    await dmChannel.send(embed=embed)
                    break
                elif eventEndTime < startTime and eventEndTime + timedelta(hours=1) > startTime:
                    eventCollision = True
                    embed = Embed(title=SCHEDULE_EVENT_ERROR_PADDING_EARLY.format(event["title"]), description=SCHEDULE_EVENT_ERROR_DESCRIPTION, colour=Colour.red())
                    await dmChannel.send(embed=embed)
                    break
                elif endTime < eventStartTime and endTime + timedelta(hours=1) > eventStartTime:
                    eventCollision = True
                    embed = Embed(title=SCHEDULE_EVENT_ERROR_PADDING_LATE.format(event["title"]), description=SCHEDULE_EVENT_ERROR_DESCRIPTION, colour=Colour.red())
                    await dmChannel.send(embed=embed)
                    break

        if template is None:
            embed = Embed(title="Do you wish to save this workshop as a template?", description="Enter `yes` or `y` if you want to save it.\nEnter anything else to not.", color=Colour.gold())
            embed.set_footer(text=SCHEDULE_CANCEL)
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                templateSaveResponse = response.content.strip().lower()
                if templateSaveResponse == "cancel":
                    await self.cancelCommand(dmChannel, "Workshop scheduling")
                    return
                saveTemplate = templateSaveResponse in ("yes", "y")
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
            if saveTemplate:
                embed = Embed(title=SCHEDULE_EVENT_TEMPLATE_SAVE_NAME_QUESTION, description="Enter `none` to make it the same as the title.", color=Colour.gold())
                embed.set_footer(text=SCHEDULE_CANCEL)
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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
                embed = Embed(title=SCHEDULE_TEMPLATE_SAVED.format(templateName), color=Colour.green())
                await dmChannel.send(embed=embed)
            else:
                embed = Embed(title=SCHEDULE_TEMPLATE_DISCARD, color=Colour.red())
                await dmChannel.send(embed=embed)

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
                "time": startTime.strftime(EVENT_TIME_FORMAT),
                "endTime": endTime.strftime(EVENT_TIME_FORMAT),
                "duration": f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}",
                "messageId": None,
                "accepted": [],
                "declined": [],
                "tentative": [],
                "workshopInterest": workshopInterest,
                "type": "Workshop"  # Operation, Workshop, Event
            }
            events.append(newEvent)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            print(e)
            newEvent = None

        embed = Embed(title=CHECK_CREATED.format("Workshop"), color=Colour.green())
        await dmChannel.send(embed=embed)
        log.info(LOG_CREATED_EVENT.format(ctx.author.display_name, ctx.author.name, ctx.author.discriminator, f"the workshop: {title}"))

        await self.updateSchedule()

        if newEvent is not None:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            await ctx.send(RESPONSE_EVENT_DONE.format("workshop", newEvent["title"], SERVER, SCHEDULE, events[-1]["messageId"]))

            if workshopInterest is not None:
                with open(WORKSHOP_INTEREST_FILE) as f:
                    workshopInterestItem = [{"name": name, "wsInterest": wsInterest} for name, wsInterest in json.load(f).items() if name == workshopInterest][0]
                guild = self.bot.get_guild(SERVER)
                message = ""
                for memberId in workshopInterestItem["wsInterest"]["members"]:
                    message += f"{member.mention} " if (member := guild.get_member(memberId)) is not None else ""
                if message != "":
                    await guild.get_channel(ARMA_DISCUSSION).send(WORKSHOPINTEREST_PING.format(message, workshopInterestItem['wsInterest']['title'], SCHEDULE, WORKSHOP_INTEREST))

    @cog_ext.cog_slash(name="event", description=SCHEDULE_COMMAND_DESCRIPTION.format("an event"), guild_ids=[SERVER])
    async def event(self, ctx: SlashContext):
        await self.scheduleEvent(ctx)

    async def scheduleEvent(self, ctx):
        await ctx.send(RESPONSE_EVENT_PROGRESS.format("event"))
        log.info(LOG_CREATING_EVENT.format(ctx.author.display_name, ctx.author.name, ctx.author.discriminator, "an event"))
        authorId = ctx.author.id
        embed = Embed(title=SCHEDULE_EVENT_TITLE.format("event"), color=Colour.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        try:
            msg = await ctx.author.send(embed=embed)
        except Exception as e:
            print(ctx.author, e)
            return
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            title = response.content.strip()
            if title.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Event scheduling")
                return
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        embed = Embed(title=SCHEDULE_EVENT_DESCRIPTION_QUESTION, color=Colour.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_THIRTY_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            description = response.content.strip()
            if description.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Event scheduling")
                return
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        embed = Embed(title=SCHEDULE_EVENT_URL_TITLE, description=SCHEDULE_EVENT_URL_DESCRIPTION, color=Colour.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            externalURL = response.content.strip()
            if externalURL.lower() == "cancel":
                await self.cancelCommand(dmChannel, "Event scheduling")
                return
            elif externalURL.lower() == "none" or (len(externalURL) == 4 and "n" in externalURL.lower()):
                externalURL = None
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return

        embed = Embed(title=SCHEDULE_EVENT_RESERVABLE, description=SCHEDULE_EVENT_RESERVABLE_DIALOG, color=Colour.gold())
        embed.set_footer(text=SCHEDULE_CANCEL)
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        mapOK = False
        color=Colour.gold()
        while not mapOK:
            embed = Embed(title=SCHEDULE_EVENT_MAP_PROMPT, description=SCHEDULE_NUMBER_FROM_TO_OR_NONE.format(1, len(MAPS)), color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color=Colour.red()
            embed.add_field(name="Map", value="\n".join(f"**{idx}** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        attendanceOk = False
        color = Colour.gold()
        while not attendanceOk:
            embed = Embed(title=SCHEDULE_EVENT_MAX_PLAYERS, description=SCHEDULE_EVENT_MAX_PLAYERS_DESCRIPTION, color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Colour.red()
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        color = Colour.gold()
        duration = "INVALID INPUT"
        while not re.match(SCHEDULE_EVENT_DURATION_REGEX, duration):
            embed = Embed(title=SCHEDULE_EVENT_DURATION_QUESTION.format("event"), description=SCHEDULE_EVENT_DURATION_PROMPT, color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Colour.red()
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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

        if str(ctx.author.id) in memberTimeZones:
            try:
                timeZone = pytz.timezone(memberTimeZones[str(ctx.author.id)])
            except pytz.exceptions.UnknownTimeZoneError:
                timeZone = UTC
        else:
            timeZoneOutput = await self.changeTimeZone(ctx.author, isCommand=False)
            if not timeZoneOutput:
                await self.cancelCommand(dmChannel, "Event editing")
                return False
            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)

        timeZone = pytz.timezone(memberTimeZones[str(ctx.author.id)])
        startTimeOk = False
        while not startTimeOk:
            isFormatCorrect = False
            color = Colour.gold()
            while not isFormatCorrect:
                embed = Embed(title=SCHEDULE_EVENT_TIME.format("event"), description=SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(timeZone.zone), color=color)
                utcNow = datetime.utcnow()
                nextHalfHour = utcNow + (datetime.min - utcNow) % timedelta(minutes=30)
                embed.add_field(name="Example", value=UTC.localize(nextHalfHour).astimezone(timeZone).strftime(EVENT_TIME_FORMAT))
                embed.set_footer(text=SCHEDULE_CANCEL)
                color = Colour.red()
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
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
                    embed = Embed(title=SCHEDULE_EVENT_TIME_TOMORROW, description=SCHEDULE_EVENT_TIME_TOMORROW_PREVIEW.format(round(startTime.timestamp()), round(newStartTime.timestamp())), color=Colour.orange())
                    await dmChannel.send(embed=embed)
                    startTime = newStartTime
                    startTimeOk = True
                else:
                    embed = Embed(title=SCHEDULE_EVENT_TIME_PAST_QUESTION, description=SCHEDULE_EVENT_TIME_PAST_PROMPT, color=Colour.orange())
                    embed.set_footer(text=SCHEDULE_CANCEL)
                    await dmChannel.send(embed=embed)
                    try:
                        response = await self.bot.wait_for("message", timeout=TIME_ONE_MIN, check=lambda msg, author=ctx.author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
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
                "time": startTime.strftime(EVENT_TIME_FORMAT),
                "endTime": endTime.strftime(EVENT_TIME_FORMAT),
                "duration": f"{(str(hours) + 'h')*(hours != 0)}{' '*(hours != 0 and minutes !=0)}{(str(minutes) + 'm')*(minutes != 0)}",
                "messageId": None,
                "accepted": [],
                "declined": [],
                "tentative": [],
                "type": "Event"  # Operation, Workshop, Event
            }
            events.append(newEvent)
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        except Exception as e:
            print(e)
            newEvent = None

        embed = Embed(title=CHECK_CREATED.format("Event"), color=Colour.green())
        await dmChannel.send(embed=embed)
        log.info(LOG_CREATED_EVENT.format(ctx.author.display_name, ctx.author.name, ctx.author.discriminator, f"the event: {title}"))

        await self.updateSchedule()

        if newEvent is not None:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            await ctx.send(RESPONSE_EVENT_DONE.format("event", newEvent["title"], SERVER, SCHEDULE, events[-1]["messageId"]))

    @cog_ext.cog_slash(name="changetimezone", description=CHANGE_TIME_ZONE_COMMAND_DESCRIPTION, guild_ids=[SERVER])
    async def timeZone(self, ctx: SlashContext) -> None:
        await ctx.send(RESPONSE_TIME_ZONE)
        timeZoneOutput = await self.changeTimeZone(ctx.author, isCommand=True)
        if not timeZoneOutput:
            await self.cancelCommand(ctx.author.dm_channel, "Time zone preferences")

    async def changeTimeZone(self, author, isCommand:bool) -> bool:
        """
            Changing a personal time zone.

            Parameters:
            author: The command author.

            Returns:
            bool: If function executed successfully.
        """
        log.info(f"{author.display_name} ({author.name}#{author.discriminator}) is updating their time zone preferences...")

        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        timezoneOk = False
        color = Colour.gold()
        while not timezoneOk:
            embed = Embed(title=":clock1: What's your preferred time zone?", description=(SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(memberTimeZones[str(author.id)]) if str(author.id) in memberTimeZones else "You don't have a preferred time zone set.") + "\n\nEnter a number from the list below.\nEnter any time zone name from the column \"**TZ DATABASE NAME**\" in this [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)." + "\nEnter `none` to erase current preferences." * isCommand, color=color)
            embed.add_field(name="Popular Time Zones", value="\n".join(f"**{idx}** {tz}" for idx, tz in enumerate(TIME_ZONES, 1)))
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Colour.red()
            try:
                msg = await author.send(embed=embed)
            except Exception as e:
                print(author, e)
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
                    embed = Embed(title=f"✅ Time zone preferences changed{f' to `{timeZone.zone}`' if isInputNotNone else ''}!", color=Colour.green())
                    await dmChannel.send(embed=embed)
                    return True

            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False

def setup(bot):
    bot.add_cog(Schedule(bot))
