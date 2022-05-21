from secret import DEBUG

from discord import app_commands
from discord.ext import commands

from constants import *
from __main__ import log, cogsReady, client, COGS
if DEBUG:
    from constants.debug import *


class Reload(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Reload"), flush=True)
        cogsReady["reload"] = True

    @app_commands.command(name="reload")
    @app_commands.guilds(GUILD)
    async def reload(self, interaction: discord.Interaction) -> bool:
        """ Reload bot cogs. """
        if interaction.user.id not in DEVELOPERS:
            return
        for cog in COGS:
            await client.reload_extension(f"cogs.{cog}")
        await interaction.response.send_message("Cogs reloaded!")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reload(bot))
