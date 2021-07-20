import discord
from discord.ext import commands

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *

EVENT_TIME_FORMAT = "%Y-%m-%d %I:%M %p"

class Schedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        log.debug("Schedule Cog is ready", flush=True)
        cogsReady["schedule"] = True

def setup(bot):
    bot.add_cog(Schedule(bot))