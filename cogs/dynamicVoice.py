import discord
from discord.ext import commands  # type: ignore

from logger import Logger
from secret import DEBUG
from constants import *
from __main__ import cogsReady
if DEBUG:
    from constants.debug import *

class DynamicVoice(commands.Cog):
    """Dynamic Voice Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        Logger.debug(LOG_COG_READY.format("DynamicVoice"), flush=True)
        cogsReady["dynamicVoice"] = True


    @discord.app_commands.command(name="voicelimit")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.describe(newlimit="New user limit for the channel; between 0-99.")
    async def voicelimit(self, interaction: discord.Interaction, newlimit: int) -> None:
        """Changes your active dynamic voice channel's user limit.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        newlimit (int): New voice channel user limit.

        Returns:
        None.
        """
        if not isinstance(interaction.user, discord.Member) or not interaction.user.voice or not interaction.user.voice.channel or not interaction.user.voice.channel.name.startswith("Room #"):
            await interaction.response.send_message(f"You must be in a dynamic channel. Create one by joining <#{CREATE_CHANNEL}>", ephemeral=True, delete_after=15.0)
            return

        if newlimit < 0 or newlimit > 99:
            await interaction.response.send_message("New limit must be greater than 0 and less than 99!", ephemeral=True, delete_after=15.0)
            return

        Logger.debug(f"{interaction.user.display_name} ({interaction.user}) changed the limit from '{interaction.user.voice.channel.user_limit}' to '{newlimit}'")
        await interaction.user.voice.channel.edit(user_limit=newlimit)
        await interaction.response.send_message(f"Changed <#{interaction.user.voice.channel.id}> user limit to `{newlimit}`", ephemeral=True, delete_after=15.0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DynamicVoice(bot))
