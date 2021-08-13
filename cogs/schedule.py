import os
import re
import json
import asyncio
from datetime import datetime
from dateutil.parser import parse as datetimeParse
import pytz

import discord
from discord import Embed
from discord import Colour
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_permission
from discord_slash.utils.manage_components import create_button, create_actionrow
from discord_slash.model import ButtonStyle, SlashCommandPermissionType

from constants import *

from __main__ import log, cogsReady, DEBUG, HOLD_UPDATE_FILE
if DEBUG:
    from constants.debug import *

EVENT_TIME_FORMAT = "%Y-%m-%d %I:%M %p"
EVENTS_FILE = "data/events.json"
MEMBER_TIME_ZONES_FILE = "data/memberTimeZones.json"
TIMEOUT_EMBED = Embed(title="Time ran out. Try again. :anguished: ", color=Colour.red())

MAPS = [
    "Altis",
    "Anizay",
    "Chernarus",
    "Hellanmaa",
    "Hellanmaa Winter",
    "Kidal",
    "Kujari",
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
    "Zargabad",
    "Training Map",
    "Laghisola",
    "Uzbin Valley",
    "Isla Abramia",
    "Desert",
    "Colombia",
    "Panthera",
    "Panthera Winter",
    "Sugar Lake"
]

UTC = pytz.utc
TIME_ZONES = {
    "UTC": "UTC",
    "Pacific American Time (LA)": "America/Los_Angeles",
    "Eastern American Time (NY)": "America/New_York",
    "British Time (London)": "Europe/London",
    "Central European Time (Brussels)": "Europe/Brussels",
    "Eastern European Time (Sofia)": "Europe/Sofia",
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
        log.debug("Schedule Cog is ready", flush=True)
        cogsReady["schedule"] = True
        await self.updateSchedule()
    
    @cog_ext.cog_slash(name="refreshschedule",
                       description="Refresh the schedule. Use this command if an event was deleted without using the reactions.",
                       guild_ids=[SERVER],
                       permissions={
                           SERVER: [
                               create_permission(EVERYONE, SlashCommandPermissionType.ROLE, False),
                               create_permission(UNIT_STAFF, SlashCommandPermissionType.ROLE, True)
                           ]
                       })
    async def refreshSchedule(self, ctx: SlashContext):
        await ctx.send("Updating schedule")
        await self.updateSchedule()
    
    async def updateSchedule(self):
        if os.path.exists(HOLD_UPDATE_FILE):
            return
        self.lastUpdate = datetime.utcnow()
        channel = self.bot.get_channel(SCHEDULE)
        await channel.purge(limit=None, check=lambda m: m.author.id in (FRIENDLY_SNEK, FRIENDLY_SNEK_DEV))
        
        await channel.send(f"Welcome to the schedule channel. To schedule an event you can use the **`/schedule`** command and follow the instructions through DMs. If you haven't set a prefered time zone yet you will be promped to do so when you schedule an event. If you want to set, change or delete your time zone preference you can do so with the **`/changetimezone`** command.\n\nIf you have any features suggestions or encounter any bugs, please contact {channel.guild.get_member(ADRIAN).display_name}.")
        
        if os.path.exists(EVENTS_FILE):
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            for event in sorted(events, key=lambda e: datetime.strptime(e["time"], EVENT_TIME_FORMAT), reverse=True):
                embed = self.getEventEmbed(event)
                msg = await channel.send(embed=embed)
                for emoji in (f"<:Green:{GREEN}>", f"<:Red:{RED}>", f"<:Yellow:{YELLOW}>", "✏️", "🗑"):
                    await msg.add_reaction(emoji)
                event["messageId"] = msg.id
            with open(EVENTS_FILE, "w") as f:
                json.dump(events, f, indent=4)
        else:
            with open(EVENTS_FILE, "w") as f:
                json.dump([], f, indent=4)
        if not os.path.exists(MEMBER_TIME_ZONES_FILE):
            with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                json.dump({}, f, indent=4)
    
    def getEventEmbed(self, event):
        guild = self.bot.get_guild(SERVER)
        
        embed = Embed(title=event["title"], description=event["description"], color=Colour.green())

        embed.add_field(name="Time", value=f"Start: <t:{round(UTC.localize(datetime.strptime(event['time'], EVENT_TIME_FORMAT)).timestamp())}:F>\n Duration: {event['duration']}", inline=False)
        embed.add_field(name="Map", value="None" if event["map"] is None else event["map"], inline=False)
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        embed.add_field(name="External URL", value=event["externalURL"], inline=False)
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        
        acceptedIds = event["accepted"]
        standbyIds = []
        if event["maxPlayers"] is not None and len(acceptedIds) > event["maxPlayers"]:
            acceptedIds, standbyIds = acceptedIds[:event["maxPlayers"]], acceptedIds[event["maxPlayers"]:]
        declinedIds = event["declined"]
        tentativeIds = event["tentative"]
        
        accepted = [guild.get_member(memberId).display_name for memberId in acceptedIds]
        standby = [guild.get_member(memberId).display_name for memberId in standbyIds]
        declined = [guild.get_member(memberId).display_name for memberId in declinedIds]
        tentative = [guild.get_member(memberId).display_name for memberId in tentativeIds]
        
        embed.add_field(name=f"Accepted ({len(accepted)}/{event['maxPlayers']}) <:Green:{GREEN}>" if event["maxPlayers"] is not None else f"Accepted ({len(accepted)}) <:Green:{GREEN}>", value="\n".join(name for name in accepted) if len(accepted) > 0 else "-", inline=True)
        embed.add_field(name=f"Declined ({len(declined)}) <:Red:{RED}>", value="\n".join(name for name in declined) if len(declined) > 0 else "-", inline=True)
        embed.add_field(name=f"Tentative ({len(tentative)}) <:Yellow:{YELLOW}>", value="\n".join(name for name in tentative) if len(tentative) > 0 else "-", inline=True)
        if len(standby) > 0:
            embed.add_field(name=f"Standby ({len(standby)}) :clock:", value="\n".join(name for name in standby), inline=False)
        
        author = guild.get_member(event["authorId"])
        embed.set_footer(text=f"Created by {author.display_name}")
        embed.timestamp = UTC.localize(datetime.strptime(event["time"], EVENT_TIME_FORMAT))
        
        return embed
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        with open(EVENTS_FILE) as f:
            events = json.load(f)
        
        if any(event["messageId"] == payload.message_id for event in events) and self.bot.ready and not payload.member.bot:
            scheduleNeedsUpdate = True
            removeReaction = True
            event = [event for event in events if event["messageId"] == payload.message_id][0]
            eventMessage = await self.bot.get_channel(SCHEDULE).fetch_message(event["messageId"])
            if payload.emoji.id == GREEN:
                if payload.member.id in event["declined"]:
                    event["declined"].remove(payload.member.id)
                if payload.member.id in event["tentative"]:
                    event["tentative"].remove(payload.member.id)
                if payload.member.id not in event["accepted"]:
                    event["accepted"].append(payload.member.id)
            elif payload.emoji.id == RED:
                if payload.member.id in event["accepted"]:
                    event["accepted"].remove(payload.member.id)
                if payload.member.id in event["tentative"]:
                    event["tentative"].remove(payload.member.id)
                if payload.member.id not in event["declined"]:
                    event["declined"].append(payload.member.id)
            elif payload.emoji.id == YELLOW:
                if payload.member.id in event["accepted"]:
                    event["accepted"].remove(payload.member.id)
                if payload.member.id in event["declined"]:
                    event["declined"].remove(payload.member.id)
                if payload.member.id not in event["tentative"]:
                    event["tentative"].append(payload.member.id)
            elif payload.emoji.name == "✏️":
                if payload.member.id == event["authorId"] or any(role.id == UNIT_STAFF for role in payload.member.roles):
                    reorderEvents = await self.editEvent(payload.member, event)
                    if reorderEvents:
                        with open(EVENTS_FILE, "w") as f:
                            json.dump(events, f, indent=4)
                        await self.updateSchedule()
                        return
            elif payload.emoji.name == "🗑":
                if payload.member.id == event["authorId"] or any(role.id == UNIT_STAFF for role in payload.member.roles):
                    await self.deleteEvent(payload.member, eventMessage)
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
    
    async def editEvent(self, author, event):
        editingTime = datetime.utcnow()
        embed = Embed(title=":pencil2: What would you like to edit?", color=Colour.gold())
        embed.add_field(name="**1** Title", value=f"```{event['title']}```", inline=False)
        embed.add_field(name="**2** Description", value=f"```{event['description']}```", inline=False)
        embed.add_field(name="**3** External URL", value=f"```{event['externalURL']}```", inline=False)
        embed.add_field(name="**4** Map", value=f"```{event['map']}```", inline=False)
        embed.add_field(name="**5** Max Players", value=f"```{event['maxPlayers']}```", inline=False)
        embed.add_field(name="**6** Time", value=f"<t:{round(UTC.localize(datetime.strptime(event['time'], EVENT_TIME_FORMAT)).timestamp())}:F>", inline=False)
        embed.add_field(name="**7** Duration", value=f"```{event['duration']}```", inline=False)
        msg = await author.send(embed=embed)
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=120, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
            choice = response.content
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return False
        while choice not in ("1", "2", "3", "4", "5", "6", "7"):
            embed = Embed(title="❌ Wrong input", colour=Colour.red(), description="Enter the number of an attribute")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=120, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                choice = response.content
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False
        
        reorderEvents = False

        if choice == "1":
            embed = Embed(title=":pencil2: What is the title of your event?", color=Colour.gold())
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                title = response.content
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False
            event["title"] = title
            
        elif choice == "2":
            embed = Embed(title=":notepad_spiral: What is the event description?", color=Colour.gold())
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=1800, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                description = response.content
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False
            event["description"] = description
            
        elif choice == "3":
            embed = Embed(title=":notebook_with_decorative_cover: Enter none or a URL \n e.g. Signup sheet / Briefing / OPORD", color=Colour.gold())
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                externalURL = response.content
                if externalURL.strip().lower() == "none":
                    externalURL = None
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False
            event["externalURL"] = externalURL
            
        elif choice == "4":
            embed = Embed(title=":globe_with_meridians: Enter Your Map Number", color=Colour.gold(), description="Choose from the list below or enter none for no map")
            embed.add_field(name="Map", value="\n".join(f"**{idx}** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                eventMap = response.content
                if eventMap.isdigit() and int(eventMap) <= len(MAPS) and int(eventMap) > 0:
                    eventMap = MAPS[int(eventMap) - 1]
                else:
                    eventMap = None
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False
            event["map"] = eventMap
            
        elif choice == "5":
            embed = Embed(title=":family_man_boy_boy: What is the maximum number of attendees?", color=Colour.gold(), description="Enter none or a number above zero and not greater than 100")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                maxPlayers = response.content
                if maxPlayers.isdigit():
                    maxPlayers = int(maxPlayers)
                else:
                    maxPlayers = None
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False
            event["maxPlayers"] = maxPlayers
            
        elif choice == "6":
            with open(MEMBER_TIME_ZONES_FILE) as f:
                memberTimeZones = json.load(f)
            
            if str(author.id) in memberTimeZones:
                try:
                    timeZone = pytz.timezone(memberTimeZones[str(author.id)])
                except pytz.exceptions.UnknownTimeZoneError:
                    timeZone = UTC
            else:
                embed = Embed(title=":clock1: It appears that you haven't set your prefered time zone yet. What is your prefered time zone?", color=Colour.gold(), description="Enter `none`, a number from the list or any time zone name from the column 'TZ DATABASE NAME' in the following Wikipedia article (https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to make your choice. If you enter `none` or something invalid UTC will be assumed and you will be asked again the next time you schedule an event. You can change or delete your prefered time zone at any time with the `/changeTimeZone` command.")
                embed.add_field(name="Time Zone", value="\n".join(f"**{idx}** {tz}" for idx, tz in enumerate(TIME_ZONES, 1)))
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    timeZone = response.content
                    saveTimeZonepreference = True
                    if timeZone.isdigit() and int(timeZone) <= len(TIME_ZONES) and int(timeZone) > 0:
                        timeZone = pytz.timezone(list(TIME_ZONES.values())[int(timeZone) - 1])
                    else:
                        try:
                            timeZone = pytz.timezone(timeZone)
                        except pytz.exceptions.UnknownTimeZoneError:
                            timeZone = UTC
                            saveTimeZonepreference = False
                    if saveTimeZonepreference:
                        memberTimeZones[str(author.id)] = timeZone.zone
                        with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                            json.dump(memberTimeZones, f, indent=4)
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return False
            
            embed = Embed(title="What is the time of the event?", color=Colour.gold(), description=f"Your selected time zone is '{timeZone.zone}'\ne.g. 2021-08-08 9:30 PM")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                eventTime = response.content.strip()
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False
            try:
                eventTime = datetimeParse(eventTime)
                isFormatCorrect = True
            except ValueError:
                isFormatCorrect = False
            while not isFormatCorrect:
                embed = Embed(title="❌ Wrong format", colour=Colour.red(), description="e.g. 2021-08-08 9:30 PM")
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    eventTime = response.content.strip()
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return False
                try:
                    eventTime = datetimeParse(eventTime)
                    isFormatCorrect = True
                except ValueError:
                    isFormatCorrect = False
            eventTime = timeZone.localize(eventTime).astimezone(UTC).strftime(EVENT_TIME_FORMAT)
            event["time"] = eventTime
            reorderEvents = True
            
        elif choice == "7":
            embed = Embed(title="What is the duration of the event?", color=Colour.gold(), description="e.g. 2h\ne.g. 2h 30m\ne.g. 3h 30m")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                duration = response.content.strip()
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False
            while not re.match(r"^(([1-9]\d*)?\dh(\s?([1-5])?\dm)?)|(([1-5])?\dm)$", duration):
                embed = Embed(title="❌ Wrong format", colour=Colour.red(), description="e.g. 2h\ne.g. 2h 30m\ne.g. 4h 30m")
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    duration = response.content.strip()
                except asyncio.TimeoutError:
                    await dmChannel.send(embed=TIMEOUT_EMBED)
                    return False
            event["duration"] = duration
        
        if editingTime > self.lastUpdate:
            embed = Embed(title="✅ Event edited", color=Colour.green())
            await dmChannel.send(embed=embed)
            return reorderEvents
        else:
            embed = Embed(title="❌ Schedule was updated while you were editing your event. Try again.", color=Colour.red())
            await dmChannel.send(embed=embed)
            return False
    
    async def deleteEvent(self, author, message):
        msg = await author.send("Are you sure you want to delete this event?")
        await msg.add_reaction("🗑")
        try:
            _ = await self.bot.wait_for("reaction_add", timeout=60, check=lambda reaction, user, author=author: reaction.emoji == "🗑" and user == author)
        except asyncio.TimeoutError:
            await author.send(embed=TIMEOUT_EMBED)
            return
        await message.delete()
        embed = Embed(title="✅ Event deleted", color=Colour.green())
        await author.send(embed=embed)
    
    @cog_ext.cog_slash(name="schedule", description="Create an event to add to the schedule.", guild_ids=[SERVER])
    async def schedule(self, ctx: SlashContext):
        if os.path.exists(HOLD_UPDATE_FILE):
            await ctx.send("Schedule comming very soon")
            return
        await ctx.send("Scheduling event")
        
        authorId = ctx.author.id

        embed = Embed(title=":pencil2: What is the title of your event?", color=Colour.gold())
        msg = await ctx.author.send(embed=embed)
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            title = response.content
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        
        embed = Embed(title=":notepad_spiral: What is the event description?", color=Colour.gold())
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=1800, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            description = response.content
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        
        embed = Embed(title=":notebook_with_decorative_cover: Enter none or a URL \n e.g. Signup sheet / Briefing / OPORD", color=Colour.gold())
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            externalURL = response.content
            if externalURL.strip().lower() == "none":
                externalURL = None
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        
        embed = Embed(title=":globe_with_meridians: Enter Your Map Number", color=Colour.gold(), description="Choose from the list below or enter none for no map")
        embed.add_field(name="Map", value="\n".join(f"**{idx}** {mapName}" for idx, mapName in enumerate(MAPS, 1)))
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            eventMap = response.content
            if eventMap.isdigit() and int(eventMap) <= len(MAPS) and int(eventMap) > 0:
                eventMap = MAPS[int(eventMap) - 1]
            else:
                eventMap = None
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        
        embed = Embed(title=":family_man_boy_boy: What is the maximum number of attendees?", color=Colour.gold(), description="Enter none or a number above zero and not greater than 100")
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            maxPlayers = response.content
            if maxPlayers.isdigit():
                maxPlayers = int(maxPlayers)
            else:
                maxPlayers = None
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        
        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)
        
        if str(ctx.author.id) in memberTimeZones:
            try:
                timeZone = pytz.timezone(memberTimeZones[str(ctx.author.id)])
            except pytz.exceptions.UnknownTimeZoneError:
                timeZone = UTC
        else:
            embed = Embed(title=":clock1: It appears that you don't have a prefered time zone currently set. What is your prefered time zone?", color=Colour.gold(), description="Enter `none`, a number from the list or any time zone name from the column 'TZ DATABASE NAME' in the following Wikipedia article (https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to make your choice. If you enter `none` or something invalid UTC will be assumed and you will be asked again the next time you schedule an event. You can change or delete your prefered time zone at any time with the `/changetimezone` command.")
            embed.add_field(name="Time Zone", value="\n".join(f"**{idx}** {tz}" for idx, tz in enumerate(TIME_ZONES, 1)))
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                timeZone = response.content
                saveTimeZonepreference = True
                if timeZone.isdigit() and int(timeZone) <= len(TIME_ZONES) and int(timeZone) > 0:
                    timeZone = pytz.timezone(list(TIME_ZONES.values())[int(timeZone) - 1])
                else:
                    try:
                        timeZone = pytz.timezone(timeZone)
                    except pytz.exceptions.UnknownTimeZoneError:
                        timeZone = UTC
                        saveTimeZonepreference = False
                if saveTimeZonepreference:
                    memberTimeZones[str(ctx.author.id)] = timeZone.zone
                    with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                        json.dump(memberTimeZones, f, indent=4)
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        
        embed = Embed(title="What is the time of the event?", color=Colour.gold(), description=f"Your selected time zone is '{timeZone.zone}'\ne.g. 2021-08-08 9:30 PM")
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            eventTime = response.content.strip()
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        try:
            eventTime = datetimeParse(eventTime)
            isFormatCorrect = True
        except ValueError:
            isFormatCorrect = False
        while not isFormatCorrect:
            embed = Embed(title="❌ Wrong format", colour=Colour.red(), description="e.g. 2021-08-08 9:30 PM")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                eventTime = response.content.strip()
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
            try:
                eventTime = datetimeParse(eventTime)
                isFormatCorrect = True
            except ValueError:
                isFormatCorrect = False
        eventTime = timeZone.localize(eventTime).astimezone(UTC).strftime(EVENT_TIME_FORMAT)
        
        embed = Embed(title="What is the duration of the event?", color=Colour.gold(), description="e.g. 2h\ne.g. 2h 30m\ne.g. 3h 30m")
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            duration = response.content.strip()
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        while not re.match(r"^(([1-9]\d*)?\dh(\s?([1-5])?\dm)?)|(([1-5])?\dm)$", duration):
            embed = Embed(title="❌ Wrong format", colour=Colour.red(), description="e.g. 2h\ne.g. 2h 30m\ne.g. 4h 30m")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                duration = response.content.strip()
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        
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
            "maxPlayers": maxPlayers,
            "map": eventMap,
            "time": eventTime,
            "duration": duration,
            "messageId": None,
            "accepted": [],
            "declined": [],
            "tentative": []
        }
        events.append(newEvent)
        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)
        
        embed = Embed(title="✅ Event created", color=Colour.green())
        await dmChannel.send(embed=embed)
        
        await self.updateSchedule()
        
        await ctx.send("Event scheduled")
    
    @cog_ext.cog_slash(name="changetimezone", description="Change your time zone preferences for the next time you schedule an event.", guild_ids=[SERVER])
    async def changeTimeZone(self, ctx: SlashContext):
        await ctx.send("Changing Time Zone Preferences")
        
        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)
        
        embed = Embed(title=":clock1: What is your prefered time zone?", color=Colour.gold(), description=(f"Your current time zone preference is '{memberTimeZones[str(ctx.author.id)]}'." if str(ctx.author.id) in memberTimeZones else "You don't have a prefered time zone set.") + " Enter `none`, a number from the list or any time zone name from the column 'TZ DATABASE NAME' in the following Wikipedia article (https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to make your choice. If you enter `none` or something invalid your current preference will be deleted and you will be asked again the next time you schedule an event. You can change or delete your prefered time zone at any time with the `/changetimezone` command.")
        embed.add_field(name="Time Zone", value="\n".join(f"**{idx}** {tz}" for idx, tz in enumerate(TIME_ZONES, 1)))
        embed.set_footer(text="Enter `cancel` to keep your current preference")
        msg = await ctx.author.send(embed=embed)
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            timeZone = response.content
            if timeZone.strip().lower() == "cancel":
                return
            if timeZone.isdigit() and int(timeZone) <= len(TIME_ZONES) and int(timeZone) > 0:
                timeZone = pytz.timezone(list(TIME_ZONES.values())[int(timeZone) - 1])
                memberTimeZones[str(ctx.author.id)] = timeZone.zone
            else:
                try:
                    timeZone = pytz.timezone(timeZone)
                    memberTimeZones[str(ctx.author.id)] = timeZone.zone
                except pytz.exceptions.UnknownTimeZoneError:
                    if str(ctx.author.id) in memberTimeZones:
                        del memberTimeZones[str(ctx.author.id)]
            with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                json.dump(memberTimeZones, f, indent=4)
            embed = Embed(title="✅ Time zone preferences changed", color=Colour.green())
            await dmChannel.send(embed=embed)
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        

def setup(bot):
    bot.add_cog(Schedule(bot))