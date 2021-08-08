import re
import asyncio
from datetime import datetime
from discord import Embed
from discord import Colour
from discord.ext.commands import Cog
from discord.ext.commands import command

from lib.logger import log
from lib.db import db

EVENT_TIME_FORMAT = "%Y-%m-%d %I:%M %p"

class Schedule(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = {}
    
    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogsReady.readyUp("schedule")
            log.debug("Schedule cog ready")
    
    async def updateSchedule(self):
        channel = self.bot.channels.schedule
        await channel.purge(limit=None)
        self.events = {}
        
        events = db.records("SELECT eventId, eventTitle, eventDescription, externalUrl, minPlayers, maxPlayers, isNsfw, eventTime, eventDuration, authorId FROM schedule")
        for eventId, eventTitle, eventDescription, externalUrl, minPlayers, maxPlayers, isNsfw, eventTime, eventDuration, authorId in sorted(events, key=lambda x: datetime.strptime(x[7], EVENT_TIME_FORMAT), reverse=True):
            embed = self.getEventEmbed(eventId, eventTitle, eventDescription, externalUrl, minPlayers, maxPlayers, isNsfw, eventTime, eventDuration, authorId)
            msg = await channel.send(embed=embed)
            author = channel.guild.get_member(authorId)
            self.events[msg.id] = (eventId, msg, author)
        
        for _, msg, _ in self.events.values():
            for emoji in ("✅", "❌", "❓", "✏️", "🗑"):
                await msg.add_reaction(emoji)
    
    def getEventEmbed(self, eventId, eventTitle, eventDescription, externalUrl, minPlayers, maxPlayers, isNsfw, eventTime, eventDuration, authorId):
        channel = self.bot.channels.schedule
        
        embed = Embed(title=eventTitle, description=eventDescription)
            
        embed.add_field(name="External URL", value=externalUrl, inline=False)
        embed.add_field(name="Time", value=eventTime, inline=False)
        embed.add_field(name="Duration", value=eventDuration, inline=False)
        embed.add_field(name="Players", value=f"{minPlayers}{('-' + str(maxPlayers)) * (maxPlayers > minPlayers)}", inline=False)
        embed.add_field(name="NSFW", value=("No", "Yes")[isNsfw], inline=False)
        
        players = db.records("SELECT userId, scheduledStatus, lastUpdated FROM scheduledPeople WHERE eventId = ?", eventId)
        accepted = []
        standby = []
        declined = []
        tentative = []
        for userId, scheduledStatus, _ in sorted(players, key=lambda x: x[2]):
            name = channel.guild.get_member(userId).display_name
            if scheduledStatus == "Accepted":
                if len(accepted) < maxPlayers:
                    accepted.append(name)
                else:
                    standby.append(name)
            elif scheduledStatus == "Declined":
                declined.append(name)
            else:
                tentative.append(name)
        embed.add_field(name=f"Accepted ({len(accepted)}/{maxPlayers})", value="\n".join(name for name in accepted) if len(accepted) > 0 else "-")
        embed.add_field(name=f"Declined ({len(declined)})", value="\n".join(name for name in declined) if len(declined) > 0 else "-")
        embed.add_field(name=f"Tentative ({len(tentative)})", value="\n".join(name for name in tentative) if len(tentative) > 0 else "-")
        if len(standby) > 0:
            embed.add_field(name=f"Standby ({len(standby)})", value="\n".join(name for name in standby) if len(tentative) > 0 else "-", inline=False)
        
        author = channel.guild.get_member(authorId)
        embed.set_footer(text=author.display_name)
        embed.timestamp = datetime.strptime(eventTime, EVENT_TIME_FORMAT)
        
        return embed
    
    @Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.message_id in self.events and self.bot.ready and not payload.member.bot:
            scheduleNeedsUpdate = True
            removeReaction = True
            if payload.emoji.name == "✅":
                self.setScheduledStatus(self.events[payload.message_id][0], payload.member.id, "Accepted")
            elif payload.emoji.name == "❌":
                self.setScheduledStatus(self.events[payload.message_id][0], payload.member.id, "Declined")
            elif payload.emoji.name == "❓":
                self.setScheduledStatus(self.events[payload.message_id][0], payload.member.id, "Tentative")
            elif payload.emoji.name == "✏️":
                if payload.member.id == self.events[payload.message_id][2].id or any(role.name in ("Staff", "Admin") for role in payload.member.roles):
                    await self.editEvent(self.events[payload.message_id][1].id)
            elif payload.emoji.name == "🗑":
                if payload.member.id == self.events[payload.message_id][2].id or any(role.name in ("Staff", "Admin") for role in payload.member.roles):
                    await self.deleteEvent(self.events[payload.message_id][1].id)
                    removeReaction = False
                scheduleNeedsUpdate = False
            else:
                scheduleNeedsUpdate = False
            if removeReaction:
                await self.events[payload.message_id][1].remove_reaction(payload.emoji, payload.member)
            if scheduleNeedsUpdate:
                eventId, message, _ = self.events[payload.message_id]
                event = db.record("SELECT eventId, eventTitle, eventDescription, externalUrl, minPlayers, maxPlayers, isNsfw, eventTime, eventDuration, authorId FROM schedule WHERE eventId = ?", eventId)
                embed = self.getEventEmbed(*event)
                await message.edit(embed=embed)
                # await self.updateSchedule()
    
    def setScheduledStatus(self, eventId, userId, scheduledStatus):
        lastUpdated = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        field = db.field("SELECT id FROM scheduledPeople WHERE eventId = ? AND userId = ?", eventId, userId)
        if field is None:
            db.execute("INSERT INTO scheduledPeople (eventId, userId, scheduledStatus, lastUpdated) VALUES (?, ?, ?, ?)", eventId, userId, scheduledStatus, lastUpdated)
        else:
            db.execute("UPDATE scheduledPeople SET scheduledStatus = ?, lastUpdated = ? WHERE id = ?", scheduledStatus, lastUpdated, field)
    
    async def editEvent(self, messageId):
        eventId, message, author = self.events[messageId]
        
        event = db.record("SELECT eventTitle, eventDescription, externalUrl, minPlayers, maxPlayers, isNsfw, eventTime, eventDuration FROM schedule WHERE eventId = ?", eventId)
        eventTitle, eventDescription, externalUrl, minPlayers, maxPlayers, isNsfw, eventTime, eventDuration = event
        
        embed = Embed(title="Enter the number of the event attribute you want to modify.")
        embed.add_field(name="1-Title", value=f"```{eventTitle}```", inline=False)
        embed.add_field(name="2-Description", value=f"```{eventDescription}```", inline=False)
        embed.add_field(name="3-External URL", value=f"```{externalUrl}```", inline=False)
        embed.add_field(name="4-Number of Players", value=f"```{str(minPlayers) + ('-' + str(maxPlayers)) * (maxPlayers > minPlayers)}```", inline=False)
        embed.add_field(name="5-NSFW", value=f"```{('No', 'Yes')[isNsfw]}```", inline=False)
        embed.add_field(name="6-Event Date and Time", value=f"```{eventTime}```", inline=False)
        embed.add_field(name="7-Event Duration", value=f"```{eventDuration}```", inline=False)
        embed.set_footer(text="To stop editing, just wait a minute until the event editing times out")
        msg = await author.send(embed=embed)
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
            choice = response.content
        except asyncio.TimeoutError:
            return
        while choice not in ("1", "2", "3", "4", "5", "6", "7"):
            embed = Embed(title="❌ Wrong input", colour=Colour.red(), description="Enter the number of an attribute")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                choice = response.content
            except asyncio.TimeoutError:
                return
        
        if choice == "1":
            embed = Embed(title="What is the scenario title?")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                title = response.content
            except asyncio.TimeoutError:
                return
            db.execute("UPDATE schedule SET eventTitle = ? WHERE eventId = ?", title, eventId)
        
        elif choice == "2":
            embed = Embed(title="What is the scenario description?")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                description = response.content
            except asyncio.TimeoutError:
                return
            db.execute("UPDATE schedule SET eventDescription = ? WHERE eventId = ?", description, eventId)
        
        elif choice == "3":
            embed = Embed(title="Any external URL?", description="Enter none or a URL")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                externalUrl = response.content
            except asyncio.TimeoutError:
                return
            if externalUrl == "none":
                externalUrl = None
            db.execute("UPDATE schedule SET externalUrl = ? WHERE eventId = ?", externalUrl, eventId)
        
        elif choice == "4":
            embed = Embed(title="How many players can play?", description="Enter one number (between 1 and 50 included) or two numbers separated by a dash (-).\ne.g. 5\ne.g. 2-6")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                numPlayersStr = response.content.strip()
            except asyncio.TimeoutError:
                return
            while not re.match(r"^([1-9]\d*)?\d(-([1-9]\d*)?\d)?$", numPlayersStr):
                embed = Embed(title="❌ Wrong format", colour=Colour.red(), description="Enter one number (between 1 and 50 included) or two numbers separated by a dash (-).\ne.g. 5\ne.g. 2-6")
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    numPlayersStr = response.content.strip()
                except asyncio.TimeoutError:
                    return
            minPlayers = min(map(int, numPlayersStr.split("-")))
            maxPlayers = max(map(int, numPlayersStr.split("-")))
            db.execute("UPDATE schedule SET minPlayers = ?, maxPlayers = ? WHERE eventId = ?", minPlayers, maxPlayers, eventId)
        
        elif choice == "5":
            embed = Embed(title="Does the scenario have NSFW elements?", description="Enter yes, no, y or n")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                nsfwStr = response.content.strip().lower()
            except asyncio.TimeoutError:
                return
            while nsfwStr not in ("yes", "no", "y", "n"):
                embed = Embed(title="❌ Wrong format", colour=Colour.red(), description="Enter yes, no, y or n")
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    nsfwStr = response.content.strip().lower()
                except asyncio.TimeoutError:
                    return
            isNsfw = nsfwStr in ("yes", "y")
            db.execute("UPDATE schedule SET isNsfw = ? WHERE eventId = ?", isNsfw, eventId)
        
        elif choice == "6":
            now = datetime.utcnow().strftime(EVENT_TIME_FORMAT)
            embed = Embed(title="When will the scenario take place?", description=f"Enter UTC time and date in the following format:\nYYYY-MM-DD hh:mm AM/PM\n\ne.g. {now}")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                eventTimeStr = response.content.strip()
            except asyncio.TimeoutError:
                return
            try:
                _ = datetime.strptime(eventTimeStr, EVENT_TIME_FORMAT)
                formatOK = True
            except ValueError:
                formatOK = False
                
            while not formatOK:
                embed = Embed(title="❌ Wrong format", colour=Colour.red(), description=f"Enter UTC time and date in the following format:\nYYYY-MM-DD hh:mm AM/PM\n\ne.g. {now}")
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    eventTimeStr = response.content.strip()
                except asyncio.TimeoutError:
                    return
                try:
                    _ = datetime.strptime(eventTimeStr, EVENT_TIME_FORMAT)
                    formatOK = True
                except ValueError:
                    formatOK = False
            db.execute("UPDATE schedule SET eventTime = ? WHERE eventId = ?", eventTimeStr, eventId)
        
        elif choice == "7":
            embed = Embed(title="How long is the scenario expected to last?", description="e.g. 2h\ne.g. 2h 30m\ne.g. 3h 30m")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                durationStr = response.content.strip()
            except asyncio.TimeoutError:
                return
            while not re.match(r"^(([1-9]\d*)?\dh(\s([1-5])?\dm)?)|(([1-5])?\dm)$", durationStr):
                embed = Embed(title="❌ Wrong format", colour=Colour.red(), description="e.g. 2h\ne.g. 2h 30m\ne.g. 4h 30m")
                await dmChannel.send(embed=embed)
                try:
                    response = await self.bot.wait_for("message", timeout=600, check=lambda msg, author=author, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                    durationStr = response.content.strip()
                except asyncio.TimeoutError:
                    return
            db.execute("UPDATE schedule SET eventDuration = ? WHERE eventId = ?", durationStr, eventId)
        
        event = db.record("SELECT eventId, eventTitle, eventDescription, externalUrl, minPlayers, maxPlayers, isNsfw, eventTime, eventDuration, authorId FROM schedule WHERE eventId = ?", eventId)
        embed = self.getEventEmbed(*event)
        await message.edit(embed=embed)
        
        embed = Embed(title="✅ Event edited", colour=Colour.green())
        await dmChannel.send(embed=embed)

    async def deleteEvent(self, messageId):
        eventId, message, author = self.events[messageId]
        msg = await author.send("Are you sure you want to delete this event?")
        await msg.add_reaction("🗑")
        try:
            _ = await self.bot.wait_for("reaction_add", timeout=60, check=lambda reaction, user, author=author: reaction.emoji == "🗑" and user == author)
        except asyncio.TimeoutError:
            await author.send("Confirmation timed out.")
            return
        db.execute("DELETE FROM schedule WHERE eventId = ?", eventId)
        db.execute("DELETE FROM scheduledPeople WHERE eventId = ?", eventId)
        await message.delete()
        del self.events[messageId]
        await author.send("Event deleted.")
    
    @command(name="event", aliases=["schedule", "sched"], brief="Schedule Event (Keeper)", help="Add an event to the schedule (definitely didn't copy the idea from the SSG bot :thinking:). Only keepers and staff can use this command.")
    async def scheduleEvent(self, ctx):
        if not any(role.name in ("Keeper", "Staff", "Admin") for role in ctx.author.roles):
            return
        if ctx.channel not in (self.bot.channels.general, self.bot.channels.bot_testing):
            return
        await ctx.message.delete()
        
        embed = Embed(title="What is the scenario title?")
        msg = await ctx.author.send(embed=embed)
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            title = response.content
        except asyncio.TimeoutError:
            return
        
        embed = Embed(title="What is the scenario description?")
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            description = response.content
        except asyncio.TimeoutError:
            return
        
        embed = Embed(title="Any external URL?", description="Enter none or a URL")
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            externalUrl = response.content
        except asyncio.TimeoutError:
            return
        if externalUrl == "none":
            externalUrl = None
        
        embed = Embed(title="How many players can play?", description="Enter one number (between 1 and 50 included) or two numbers separated by a dash (-).\ne.g. 5\ne.g. 2-6")
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            numPlayersStr = response.content.strip()
        except asyncio.TimeoutError:
            return
        while not re.match(r"^([1-9]\d*)?\d(-([1-9]\d*)?\d)?$", numPlayersStr):
            embed = Embed(title="❌ Wrong format", colour=Colour.red(), description="Enter one number (between 1 and 50 included) or two numbers separated by a dash (-).\ne.g. 5\ne.g. 2-6")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                numPlayersStr = response.content.strip()
            except asyncio.TimeoutError:
                return
        minPlayers = min(map(int, numPlayersStr.split("-")))
        maxPlayers = max(map(int, numPlayersStr.split("-")))
        
        embed = Embed(title="Does the scenario have NSFW elements?", description="Enter yes, no, y or n")
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            nsfwStr = response.content.strip().lower()
        except asyncio.TimeoutError:
            return
        while nsfwStr not in ("yes", "no", "y", "n"):
            embed = Embed(title="❌ Wrong format", colour=Colour.red(), description="Enter yes, no, y or n")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                nsfwStr = response.content.strip().lower()
            except asyncio.TimeoutError:
                return
        isNsfw = nsfwStr in ("yes", "y")
        
        now = datetime.utcnow().strftime(EVENT_TIME_FORMAT)
        embed = Embed(title="When will the scenario take place?", description=f"Enter UTC time and date in the following format:\nYYYY-MM-DD hh:mm AM/PM\n\ne.g. {now}")
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            eventTimeStr = response.content.strip()
        except asyncio.TimeoutError:
            return
        try:
            _ = datetime.strptime(eventTimeStr, EVENT_TIME_FORMAT)
            formatOK = True
        except ValueError:
            formatOK = False
            
        while not formatOK:
            embed = Embed(title="❌ Wrong format", colour=Colour.red(), description=f"Enter UTC time and date in the following format:\nYYYY-MM-DD hh:mm AM/PM\n\ne.g. {now}")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                eventTimeStr = response.content.strip()
            except asyncio.TimeoutError:
                return
            try:
                _ = datetime.strptime(eventTimeStr, EVENT_TIME_FORMAT)
                formatOK = True
            except ValueError:
                formatOK = False
        
        embed = Embed(title="How long is the scenario expected to last?", description="e.g. 2h\ne.g. 2h 30m\ne.g. 3h 30m")
        await dmChannel.send(embed=embed)
        try:
            response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            durationStr = response.content.strip()
        except asyncio.TimeoutError:
            return
        while not re.match(r"^(([1-9]\d*)?\dh(\s([1-5])?\dm)?)|(([1-5])?\dm)$", durationStr):
            embed = Embed(title="❌ Wrong format", colour=Colour.red(), description="e.g. 2h\ne.g. 2h 30m\ne.g. 4h 30m")
            await dmChannel.send(embed=embed)
            try:
                response = await self.bot.wait_for("message", timeout=600, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                durationStr = response.content.strip()
            except asyncio.TimeoutError:
                return
        
        log.debug(f"Event created by {ctx.author}")
        db.execute("INSERT INTO schedule (eventTitle, eventDescription, externalUrl, minPlayers, maxPlayers, isNsfw, eventTime, eventDuration, authorId) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", title, description, externalUrl, minPlayers, maxPlayers, isNsfw, eventTimeStr, durationStr, ctx.author.id)
        
        embed = Embed(title="✅ Event created", colour=Colour.green())
        await dmChannel.send(embed=embed)
        
        await self.updateSchedule()

def setup(bot):
    bot.add_cog(Schedule(bot))