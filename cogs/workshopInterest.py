import os
import json

from discord import Embed
from discord.ext import commands

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *

WORKSHOP_INTEREST_FILE = "data/workshopInterest.json"

class WorkshopInterest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        log.debug("WorkshopInterest Cog is ready", flush=True)
        cogsReady["workshopInterest"] = True

        if not os.path.exists(WORKSHOP_INTEREST_FILE):
            workshopInterest = {}
            for name, title, description in (
                ("Newcomer", "Newcomer", ""),
                ("Rotary Wing", "Rotary Wing 🚁", "Learn to fly helicopters and provide with transport and close air support."),
                ("Fixed Wing", "Fixed Wing ✈️", "Learn the dynamics of using fixed wing and fighter jet aircraft."),
                ("JTAC", "JTAC 📡", ""),
                ("Medic", "Medic 💉", ""),
                ("Heavy Weapons", "Heavy Weapons 💣", "Learn how to efficiently operate as a machine gun crew, use grenade launchers, and shoot cretins out of shitboxes (AT & AA)."),
                ("Marksman", "Marksman 🎯", "Learn how to shoot big bullet far."),
                ("Breacher", "Breacher 🚪", ""),
                ("Mechanised", "Mechanised 🛡️​", "A short course on driving, gunning, and commanding a 6.21 million dollar reason the heavy weapons guy is useless."),
                ("RPV-SO", "RPV-SO 🛩️​", ""),
                ("Team Leading", "Team Leading", "")
            ):
                workshopInterest[name] = {"title": title, "description": description, "members": [], "messageId": None}
            with open(WORKSHOP_INTEREST_FILE, "w") as f:
                json.dump(workshopInterest, f, indent=4)
        await self.updateChannel()

    def getWorkshopEmbed(self, workshop):
        guild = self.bot.get_guild(SERVER)
        description = workshop.get("description")
        if description is not None:
            embed = Embed(title=workshop["title"], description=description)
        else:
            embed = Embed(title=workshop["title"])
        interestedList = "\n".join(member.display_name for memberId in workshop["members"] if (member := guild.get_member(memberId)) is not None)
        if interestedList == "":
            interestedList = "-"
        embed.add_field(name="Interested People", value=interestedList)
        return embed

    async def updateChannel(self):
        channel = self.bot.get_channel(WORKSHOP_INTEREST)
        await channel.purge(limit=None, check=lambda m: m.author.id in (FRIENDLY_SNEK, FRIENDLY_SNEK_DEV))

        await channel.send("Welcome to the workshop interest channel. Here you can show interest for different workshops.")

        with open(WORKSHOP_INTEREST_FILE) as f:
            workshopInterest = json.load(f)
        for workshop in workshopInterest.values():
            embed = self.getWorkshopEmbed(workshop)
            msg = await channel.send(embed=embed)
            workshop["messageId"] = msg.id
            for emoji in ("✅", "❌"):
                await msg.add_reaction(emoji)
        with open(WORKSHOP_INTEREST_FILE, "w") as f:
            json.dump(workshopInterest, f, indent=4)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id != WORKSHOP_INTEREST:
            return
        try:
            with open(WORKSHOP_INTEREST_FILE) as f:
                workshopInterest = json.load(f)

            if any(workshop["messageId"] == payload.message_id for workshop in workshopInterest.values()) and self.bot.ready and not payload.member.bot:
                channelNeedsUpdate = True
                workshop = [workshop for workshop in workshopInterest.values() if workshop["messageId"] == payload.message_id][0]
                workshopMessage = await self.bot.get_channel(WORKSHOP_INTEREST).fetch_message(workshop["messageId"])
                if payload.emoji.name == "✅":
                    if payload.member.id not in workshop["members"]:
                        workshop["members"].append(payload.member.id)
                elif payload.emoji.name == "❌":
                    if payload.member.id in workshop["members"]:
                        workshop["members"].remove(payload.member.id)
                else:
                    channelNeedsUpdate = False

                try:
                    await workshopMessage.remove_reaction(payload.emoji, payload.member)
                except Exception:
                    pass

                if channelNeedsUpdate:
                    try:
                        embed = self.getWorkshopEmbed(workshop)
                        await workshopMessage.edit(embed=embed)
                    except Exception:
                        pass

            with open(WORKSHOP_INTEREST_FILE, "w") as f:
                json.dump(workshopInterest, f, indent=4)
        except Exception as e:
            print(e)

def setup(bot):
    bot.add_cog(WorkshopInterest(bot))
