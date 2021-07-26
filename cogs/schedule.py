import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext

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
    
    @cog_ext.cog_slash(name="schedule", guild_ids=[SERVER])
    async def schedule(self, ctx: SlashContext):
        await ctx.send("Schedule")

def setup(bot):
    bot.add_cog(Schedule(bot))