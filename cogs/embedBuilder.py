import discord
import re

from datetime import datetime
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
    @discord.app_commands.describe(channel = "Target channel for later sending embed.")
    async def buildEmbed(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        """Builds embeds.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        channel (discord.TextChannel): Target textchannel to send embed.

        Returns:
        None.
        """
        log.info(f"{interaction.user.display_name} ({interaction.user}) is building an embed.")

        # Send preview embed (empty)
        view = BuilderView()
        items = [
            BuilderButton(self, None, row=0, label="Title", style=discord.ButtonStyle.secondary, custom_id="builder_button_title"),
            BuilderButton(self, None, row=0, label="Description", style=discord.ButtonStyle.secondary, custom_id="builder_button_description"),
            BuilderButton(self, None, row=0, label="URL", style=discord.ButtonStyle.secondary, custom_id="builder_button_url", disabled=True),
            BuilderButton(self, None, row=0, label="Timestamp", style=discord.ButtonStyle.secondary, custom_id="builder_button_timestamp", disabled=True),
            BuilderButton(self, None, row=0, label="Color", style=discord.ButtonStyle.secondary, custom_id="builder_button_color", disabled=True),

            BuilderButton(self, None, row=1, label="Thumbnail", style=discord.ButtonStyle.secondary, custom_id="builder_button_thumbnail"),
            BuilderButton(self, None, row=1, label="Image", style=discord.ButtonStyle.secondary, custom_id="builder_button_image"),

            BuilderButton(self, None, row=1, label="Author", style=discord.ButtonStyle.secondary, custom_id="builder_button_author"),
            BuilderButton(self, None, row=1, label="Footer", style=discord.ButtonStyle.secondary, custom_id="builder_button_footer"),
        ]
        for item in items:
            view.add_item(item)

        await interaction.response.send_message("Embed builder!", view=view)


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


    async def buttonHandling(self, message: discord.Message | None, button: discord.ui.Button, interaction: discord.Interaction, authorId: int | None) -> None:
        """Handling all embedbuilder button interactions.

        Parameters:
        message (discord.Message | None): If the message is provided, it's used along with some specific button action.
        button (discord.ui.Button): The Discord button.
        interaction (discord.Interaction): The Discord interaction.
        authorId (int | None): ID of user who executed the command.

        Returns:
        None.
        """
        if not isinstance(interaction.user, discord.Member):
            log.exception("ButtonHandling: user not discord.Member")
            return

        if interaction.message is None:
            log.exception("ButtonHandling: interaction.message is None")
            return


        name = button.custom_id[len("builder_button_"):]
        modal = BuilderModal(self, f"Set embed {name.lower()}", f"builder_modal_{name.lower()}", interaction.message, button.view)
        modalConfig = {
            "style": discord.TextStyle.short,
            "placeholder": None,
            "default": None,
            "maxLength": None,
            "customitems": []
        }

        # Configure field specific values
        embed = None
        if len(interaction.message.embeds) > 0:
            embed = interaction.message.embeds[0]

        match name.lower():
            case "title":
                modalConfig["maxLength"] = 256
                if embed:
                    modalConfig["default"] = embed.title
            case "description":
                modalConfig["style"] = discord.TextStyle.long
                modalConfig["maxLength"] = 4000
                if embed:
                    modalConfig["default"] = embed.description
            case "timestamp":
                if embed and embed.timestamp:
                    modalConfig["default"] = datetime.strftime(embed.timestamp, "%Y-%m-%d %H:%M:%S")
            case "color":
                modalConfig["placeholder"] = "#HEX or RGB"
                if embed and embed.color:
                    modalConfig["default"] = "#" + hex(embed.color.value).lstrip("0x").upper().zfill(6)

            case "url":
                modalConfig["placeholder"] = "https://www.gnu.org"
                if embed:
                    modalConfig["default"] = embed.url

            case "thumbnail":
                modalConfig["placeholder"] = "https://www.gnu.org/graphics/gnu-head.jpg"
                if embed and embed.thumbnail:
                    modalConfig["default"] = embed.thumbnail.url
            case "image":
                modalConfig["placeholder"] = "https://www.gnu.org/graphics/gnu-head.jpg"
                if embed and embed.image:
                    modalConfig["default"] = embed.image.url

            case "author":
                modalConfig["customitems"] = [
                    discord.ui.TextInput(label="Author Name", default=embed.author.name if embed and embed.author and embed.author.name else None, required=False, max_length=256),
                    discord.ui.TextInput(label="Author URL", default=embed.author.url if embed and embed.author and embed.author.url else None, required=False),
                    discord.ui.TextInput(label="Author Icon URL", default=embed.author.icon_url if embed and embed.author and embed.author.icon_url else None, required=False)
                ]
            case "footer":
                modalConfig["customitems"] = [
                    discord.ui.TextInput(label="Footer Text", default=embed.footer.text if embed and embed.footer and embed.footer.text else None, required=False, max_length=2048),
                    discord.ui.TextInput(label="Footer Icon URL", default=embed.footer.icon_url if embed and embed.footer and embed.footer.icon_url else None, required=False)
                ]


        if len(modalConfig["customitems"]) == 0:
            modal.add_item(discord.ui.TextInput(label=name, style=modalConfig["style"], placeholder=modalConfig["placeholder"], default=modalConfig["default"], required=False, max_length=modalConfig["maxLength"]))
        else:
            for item in modalConfig["customitems"]:
                modal.add_item(item)
        await interaction.response.send_modal(modal)


    async def modalHandling(self, modal: discord.ui.Modal, interaction: discord.Interaction, message: discord.Message, view: discord.ui.View | None) -> None:
        if not isinstance(interaction.user, discord.Member):
            log.exception("ButtonHandling modalHandling: interaction.user is not discord.Member")
            return

        value: str = modal.children[0].value.strip()

        stderr = None
        embed = Embed()
        if len(message.embeds) > 0:
            embed = message.embeds[0]

        # Values depend on (any) key to be filled
        dependencies = {
            "title": ("URL", "Timestamp", "Color"),
            "description": ("URL", "Timestamp", "Color")
        }

        name = modal.custom_id[len("builder_modal_"):]
        match name:
            case "title":
                embed.title = value
                if (not embed.description):
                    for item in view.children:
                        for dependency in dependencies["title"]:
                            if isinstance(item, discord.ui.Button) and item.label == dependency:
                                item.disabled = (not value)
            case "description":
                embed.description = value
                if (not embed.title):
                    for item in view.children:
                        for dependency in dependencies["description"]:
                            if isinstance(item, discord.ui.Button) and item.disabled == (not not value) and item.label == dependency:
                                item.disabled = (not value)
            case "timestamp":
                try:
                    embed.timestamp = datetimeParse(value)
                except Exception:
                    stderr = "Invalid timestamp format."
            case "color":
                pattern1 = re.compile(r"#?[a-zA-Z0-9]{6}")
                pattern2 = re.compile(r"(\d{1,3}(?:,| |, ))(\d{1,3}(?:,| |, ))(\d{1,3})")

                # Hex
                if re.match(pattern1, value):
                    embed.color = int(value.lstrip("#"), 16)

                # RGB
                elif re.match(pattern2, value):
                    rgb = re.findall(pattern2, value)[0]
                    embed.color = discord.Color.from_rgb(int(rgb[0].rstrip(" ").rstrip(",")), int(rgb[1].rstrip(" ").rstrip(",")), int(rgb[2].rstrip(" ").rstrip(",")))

            case "url":
                if not embed.title:
                    stderr = "Embed title must be set."
                elif not value.startswith("http"):
                    stderr = "URL must be HTTP or HTTPS."
                else:
                    embed.url = value

            case "thumbnail":
                embed.set_thumbnail(url=value)
            case "image":
                embed.set_image(url=value)

            case "author":
                embed.set_author(name=modal.children[0].value.strip(), url=modal.children[1].value.strip(), icon_url=modal.children[2].value.strip())
            case "footer":
                embed.set_footer(text=modal.children[0].value.strip(), icon_url=modal.children[1].value.strip())

        if stderr:
            await interaction.response.send_message(stderr, ephemeral=True, delete_after=15.0)
            return

        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            await interaction.response.send_message(str(e), ephemeral=True, delete_after=15.0)


# ===== <Views and Buttons> =====

class BuilderView(discord.ui.View):
    """Handling all builder views."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = None

class BuilderButton(discord.ui.Button):
    """Handling all builder buttons."""
    def __init__(self, instance, message: discord.Message | None, authorId: int | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.message = message
        self.authorId = authorId

    async def callback(self, interaction: discord.Interaction):
        await self.instance.buttonHandling(self.message, self, interaction, self.authorId)

#class BuilderSelect(discord.ui.Select):
#    """Handling all builder dropdowns."""
#    def __init__(self, instance, eventMsg: discord.Message, placeholder: str, minValues: int, maxValues: int, customId: str, row: int, options: list[discord.SelectOption], disabled: bool = False, eventMsgView: discord.ui.View | None = None, *args, **kwargs):
#        super().__init__(placeholder=placeholder, min_values=minValues, max_values=maxValues, custom_id=customId, row=row, options=options, disabled=disabled, *args, **kwargs)
#        self.eventMsg = eventMsg
#        self.instance = instance
#        self.eventMsgView = eventMsgView

#    async def callback(self, interaction: discord.Interaction) -> None:
#        await self.instance.selectHandling(self, interaction, self.eventMsg, self.eventMsgView)

class BuilderModal(discord.ui.Modal):
    """Handling all builder modals."""
    def __init__(self, instance, title: str, customId: str, message: discord.Message, view: discord.ui.View | None = None) -> None:
        super().__init__(title=title, custom_id=customId)
        self.instance = instance
        self.message = message
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        # try:
        await self.instance.modalHandling(self, interaction, self.message, self.view)
        # except Exception as e:
        #     log.exception(f"Modal Handling Failed\n{e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        # await interaction.response.send_message("Something went wrong. cope.", ephemeral=True)
        log.exception(error)

# ===== </Views and Buttons> =====



async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmbedBuilder(bot))
