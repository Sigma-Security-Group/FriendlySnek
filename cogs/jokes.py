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

    # @app_commands.command(name="boop")
    # @app_commands.guilds(GUILD)
    # async def boop(self, interaction: discord.Interaction) -> None:
    #     """Boop."""
    #     response = choice([
    #         "My nose is itchy now, thanks.",
    #         "Stop it, you're gonna make me blush.",
    #         "Please stop, I'm ticklish.",
    #         "I hope you didn't catch my virus there.",
    #         "Beep",
    #         "Boop",
    #         "Boopity boop",
    #         "Boop boop boop",
    #         "*Sneezes*",
    #         "Ok, shutting down now."
    #     ])
    #     await interaction.response.send_message(response)
    #     if response == "Ok, shutting down now.":
    #         await sleep(5)
    #         await interaction.followup.send("Just kidding, I'm back. :snake:")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Jokes(bot))
