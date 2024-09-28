import discord
from discord.ext import commands  # type: ignore

from logger import Logger
from secret import DEBUG
from constants import *
from __main__ import cogsReady
if DEBUG:
    from constants.debug import *


@discord.app_commands.guilds(GUILD)
class DynamicVoice(commands.GroupCog, name="voice"):
    """Dynamic Voice Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        Logger.debug(LOG_COG_READY.format("DynamicVoice"), flush=True)
        cogsReady["dynamicVoice"] = True


    @discord.app_commands.command(name="limit")
    @discord.app_commands.describe(new_limit="New user limit for the channel; between 0-99.")
    async def limit(self, interaction: discord.Interaction, new_limit: discord.app_commands.Range[int, 0, 99]) -> None:
        """Changes your active dynamic voice channel's user limit.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        new_limit (int): New voice channel user limit.

        Returns:
        None.
        """
        if not isinstance(interaction.user, discord.Member) or not interaction.user.voice or not interaction.user.voice.channel or not interaction.user.voice.channel.category or not interaction.user.voice.channel.category.id == CUSTOM_CHANNELS:
            await interaction.response.send_message(f"You must be in a dynamic channel. Create one by joining <#{CREATE_CHANNEL}>", ephemeral=True, delete_after=15.0)
            return

        if new_limit < 0 or new_limit > 99:
            await interaction.response.send_message("New limit must be greater than 0 and less than 99!", ephemeral=True, delete_after=15.0)
            return

        Logger.debug(f"{interaction.user.display_name} ({interaction.user}) changed the dynamic voice limit from '{interaction.user.voice.channel.user_limit}' to '{new_limit}'")
        await interaction.user.voice.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(f"Changed {interaction.user.voice.channel.mention} user limit to `{new_limit}`", ephemeral=True, delete_after=15.0)


    @discord.app_commands.command(name="name")
    @discord.app_commands.describe(new_name="New channel name; 1-100 characters.")
    async def name(self, interaction: discord.Interaction, new_name: discord.app_commands.Range[str, 1, 100]) -> None:
        """Changes your active dynamic voice channel's name.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        new_name (str): New voice channel name.

        Returns:
        None.
        """
        if not isinstance(interaction.user, discord.Member) or not interaction.user.voice or not interaction.user.voice.channel or not interaction.user.voice.channel.category or not interaction.user.voice.channel.category.id == CUSTOM_CHANNELS:
            await interaction.response.send_message(f"You must be in a dynamic channel. Create one by joining <#{CREATE_CHANNEL}>", ephemeral=True, delete_after=15.0)
            return

        if len(new_name) > 100:
            await interaction.response.send_message("New name must be greater than 0 and less than 99 characters!", ephemeral=True, delete_after=15.0)
            return

        oldName = interaction.user.voice.channel.name
        Logger.debug(f"{interaction.user.display_name} ({interaction.user}) changed the dynamic voice name from '{oldName}' to '{new_name}'")
        await interaction.user.voice.channel.edit(name=new_name)
        await interaction.response.send_message(f"Changed voice channel name from `{oldName}` to `{new_name}`", ephemeral=True, delete_after=15.0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DynamicVoice(bot))
