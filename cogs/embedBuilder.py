import discord
import pytz  # type: ignore

from datetime import datetime, timedelta, timezone
from dateutil.parser import parse as datetimeParse  # type: ignore

from discord import Embed, Color
from discord.ext import commands # type: ignore

from secret import DEBUG
from constants import *
from __main__ import log, cogsReady
if DEBUG:
    from constants.debug import *



class EmbedBuilder(commands.Cog):
    """Embed Builder Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("EmbedBuilder"), flush=True)
        cogsReady["embedBuilder"] = True


# ===== <Build Embed> =====

    @discord.app_commands.command(name="build-embed")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_STAFF_LIMIT)
    async def buildEmbed(self, interaction: discord.Interaction) -> None:
        """Builds embeds.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        log.info(f"{interaction.user.display_name} ({interaction.user}) is building an embed.")
        # Send preview embed (empty)
        # View has buttons
            # Title
                # Modal short
            # Description
                # Modal short
            # URL
                # Modal short
            # Author name
                # Modal short
            # Author iconurl
                # Modal short
            # Author url
                # Modal short
            # thumbnail
                # Modal short
            # Image
                # Modal short
            # Footer text
                # Modal short
            # Footer iconurl
                # Modal short
            # Timestamp
                # Modal short (check datetime.datetime)
            # Color
                # Modal short (check integer, hex string, array rgb values)


            # Add Field
                # Extra message with view
                    # Name
                    # Value
                    # Inline
            # Remove Field


    @buildEmbed.error
    async def onBuildEmbedError(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        """buildEmbed errors - dedicated for the discord.app_commands.errors.MissingAnyRole error.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        error (discord.app_commands.AppCommandError): The end user error.

        Returns:
        None.
        """
        if type(error) == discord.app_commands.errors.MissingAnyRole:
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("onBuildEmbedError: guild is None")
                return

            embed = Embed(title="❌ Missing permissions", description=f"You do not have the permissions to build embeds!\nThe permitted roles are: {', '.join([guild.get_role(role).name for role in CMD_STAFF_LIMIT])}.", color=Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=15.0)

# ===== </Build Embed> =====


# ===== <Views and Buttons> =====

class ScheduleView(discord.ui.View):
    """Handling all schedule views."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = None

class ScheduleButton(discord.ui.Button):
    """Handling all schedule buttons."""
    def __init__(self, instance, message: discord.Message | None, authorId: int | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.message = message
        self.authorId = authorId

    async def callback(self, interaction: discord.Interaction):
        await self.instance.buttonHandling(self.message, self, interaction, self.authorId)

class ScheduleSelect(discord.ui.Select):
    """Handling all schedule dropdowns."""
    def __init__(self, instance, eventMsg: discord.Message, placeholder: str, minValues: int, maxValues: int, customId: str, row: int, options: list[discord.SelectOption], disabled: bool = False, eventMsgView: discord.ui.View | None = None, *args, **kwargs):
        super().__init__(placeholder=placeholder, min_values=minValues, max_values=maxValues, custom_id=customId, row=row, options=options, disabled=disabled, *args, **kwargs)
        self.eventMsg = eventMsg
        self.instance = instance
        self.eventMsgView = eventMsgView

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.instance.selectHandling(self, interaction, self.eventMsg, self.eventMsgView)

class ScheduleModal(discord.ui.Modal):
    """Handling all schedule modals."""
    def __init__(self, instance, title: str, customId: str, eventMsg: discord.Message, view: discord.ui.View | None = None) -> None:
        super().__init__(title=title, custom_id=customId)
        self.instance = instance
        self.eventMsg = eventMsg
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        # try:
        await self.instance.modalHandling(self, interaction, self.eventMsg, self.view)
        # except Exception as e:
        #     log.exception(f"Modal Handling Failed\n{e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        # await interaction.response.send_message("Something went wrong. cope.", ephemeral=True)
        log.exception(error)

# ===== </Views and Buttons> =====



async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmbedBuilder(bot))
