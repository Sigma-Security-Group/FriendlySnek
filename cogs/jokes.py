from secret import DEBUG
import requests

from discord import app_commands
from discord.ext import commands  # type: ignore

from constants import *
from __main__ import log, cogsReady
if DEBUG:
    from constants.debug import *


URL = "https://icanhazdadjoke.com/"
HEADERS = {"Accept": "application/json"}

class Jokes(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Jokes"), flush=True)
        cogsReady["jokes"] = True

    @app_commands.command(name="dadjoke")
    @app_commands.guilds(GUILD)
    async def dadjoke(self, interaction: discord.Interaction) -> None:
        """ Receive a hilarious dad joke.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        response = requests.get(url=URL, headers=HEADERS)
        data = response.json()
        await interaction.response.send_message(data["joke"])

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Jokes(bot))
