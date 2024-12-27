import discord, logging
import requests  # type: ignore

from discord.ext import commands  # type: ignore

from secret import DEBUG
from constants import *
if DEBUG:
    from constants.debug import *

URL = "https://icanhazdadjoke.com/"
HEADERS = {"Accept": "application/json"}

log = logging.getLogger(__name__)

class Jokes(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Jokes"))
        self.bot.cogsReady["jokes"] = True

    @discord.app_commands.command(name="dadjoke")
    @discord.app_commands.guilds(GUILD)
    async def dadjoke(self, interaction: discord.Interaction) -> None:
        """Receive a hilarious dad joke."""
        response = requests.get(url=URL, headers=HEADERS)
        data = response.json()
        await interaction.response.send_message(data["joke"])

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Jokes(bot))
