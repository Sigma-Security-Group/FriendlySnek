import os
import re
import json
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
from dateutil.parser import parse as datetimeParse
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import discord
from discord import Embed
from discord import Colour
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_permission, create_multi_ids_permission
from discord_slash.utils.manage_components import create_button, create_actionrow
from discord_slash.model import ButtonStyle, SlashCommandPermissionType

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *
import anvilController

WORKSHOP_INTEREST_FILE = "data/workshopInterest.json"

class WorkshopInterest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        log.debug("WorkshopInterest Cog is ready", flush=True)
        cogsReady["workshopInterest"] = True
        
        if not DEBUG:  # TODO remove before launching on Sigma server
            return
        
        if not os.path.exists(WORKSHOP_INTEREST_FILE):
            with open(WORKSHOP_INTEREST_FILE, "w") as f:
                json.dump({}, f, indent=4)
        await self.updateChannel()
    
    def getWorkshopEmbed(self, workshop, interest):
        guild = self.bot.get_guild(SERVER)
        embed = Embed(title=workshop)
        interestedList = "\n".join(member.display_name for memberId in interested["members"] if (member := guild.get_member(memberId)) is not None)
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
        for workshop, interest in workshopInterest.items():
            embed = self.getWorkshopEmbed(workshop, interest)
            msg = await channel.send(embed=embed)
            interest["messageId"] = msg.id
        with open(WORKSHOP_INTEREST_FILE, "w") as f:
            json.dump(workshopInterest, f, indent=4)

def setup(bot):
    bot.add_cog(WorkshopInterest(bot))