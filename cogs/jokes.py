from discord.ext import commands
from discord_slash import cog_ext, SlashContext
import requests

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *

URL = "https://icanhazdadjoke.com/"
headers = {"Accept": "application/json"}

class Jokes(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Jokes"), flush=True)
        cogsReady["jokes"] = True

    @cog_ext.cog_slash(name="dadjoke", guild_ids=[SERVER], description=DADJOKE_COMMAND_DESCRIPTION)
    async def dadjoke(self, ctx: SlashContext) -> None:
        r = requests.get(url=URL, headers=headers)
        data = r.json()
        await ctx.send(data["joke"])

def setup(bot) -> None:
    bot.add_cog(Jokes(bot))
