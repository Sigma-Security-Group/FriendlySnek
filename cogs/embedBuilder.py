import discord, re, logging

from datetime import datetime
from dateutil.parser import parse as datetimeParse  # type: ignore

from discord.ext import commands # type: ignore

from utils import Utils
from secret import DEBUG
from constants import *
if DEBUG:
    from constants.debug import *

log = logging.getLogger("FriendlySnek")

class EmbedBuilder(commands.Cog):
    """Embed Builder Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("EmbedBuilder"))
        self.bot.cogsReady["embedBuilder"] = True


# ===== <Build Embed> =====

    @discord.app_commands.command(name="build-embed")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_STAFF)
    @discord.app_commands.describe(
        channel = "Target channel for later sending embed, or fetching message from.",
        messageid = "Optional discord message id for editing an embed.",
        attachment = "Optional attachment (file)."
    )
    async def buildEmbed(self, interaction: discord.Interaction, channel: discord.TextChannel | discord.Thread, messageid: str = "", attachment: discord.Attachment | None = None) -> None:
        """Builds embeds.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        channel (discord.TextChannel): Target textchannel to send embed.
        messageid (str, optional): Target message id for editing that message's first embed.

        Returns:
        None.
        """

        messageEdit = discord.utils.MISSING
        messageEditEmbed = discord.utils.MISSING
        if messageid:
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("EmbedBuilder buildEmbed: guild is None")
                return

            try:
                messageid = int(messageid)
                messageEdit = await channel.fetch_message(messageid)
            except Exception:
                embed = discord.Embed(title="❌ Invalid data", description=f"Message with id `{messageid}` could not be found in channel {channel.mention}!", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=15.0)
                return


            stderr = None
            if len(messageEdit.embeds) == 0:
                stderr = "Message does not have an embed!"

            elif messageEdit.author.id != self.bot.user.id:
                stderr = f"Message is not sent by me ({self.bot.user.mention})!"

            if stderr:
                embed = discord.Embed(title="❌ Invalid message", description=stderr, color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=15.0)
                return

            log.info(f"{interaction.user.id} [{interaction.user.display_name}] Is editing a message ({messageid}) embed")

            messageEditEmbed = messageEdit.embeds[0]

        else:
            log.info(f"{interaction.user.id} [{interaction.user.display_name}] Is building an embed")


        # Send preview embed (empty)
        view = BuilderView(channel.id, messageid)
        items = [
            BuilderButton(self, authorId=interaction.user.id, row=0, label="Title", style=discord.ButtonStyle.secondary, custom_id="builder_button_title"),
            BuilderButton(self, authorId=interaction.user.id, row=0, label="Description", style=discord.ButtonStyle.secondary, custom_id="builder_button_description"),
            BuilderButton(self, authorId=interaction.user.id, row=0, label="URL", style=discord.ButtonStyle.secondary, custom_id="builder_button_url", disabled=True),
            BuilderButton(self, authorId=interaction.user.id, row=0, label="Timestamp", style=discord.ButtonStyle.secondary, custom_id="builder_button_timestamp", disabled=True),
            BuilderButton(self, authorId=interaction.user.id, row=0, label="Color", style=discord.ButtonStyle.secondary, custom_id="builder_button_color", disabled=True),

            BuilderButton(self, authorId=interaction.user.id, row=1, label="Thumbnail", style=discord.ButtonStyle.secondary, custom_id="builder_button_thumbnail"),
            BuilderButton(self, authorId=interaction.user.id, row=1, label="Image", style=discord.ButtonStyle.secondary, custom_id="builder_button_image"),

            BuilderButton(self, authorId=interaction.user.id, row=1, label="Author", style=discord.ButtonStyle.secondary, custom_id="builder_button_author"),
            BuilderButton(self, authorId=interaction.user.id, row=1, label="Footer", style=discord.ButtonStyle.secondary, custom_id="builder_button_footer"),

            BuilderButton(self, authorId=interaction.user.id, row=2, label="Cancel", style=discord.ButtonStyle.danger, custom_id="builder_button_cancel"),
            BuilderButton(self, authorId=interaction.user.id, row=2, label="Submit", style=discord.ButtonStyle.primary, custom_id="builder_button_submit", disabled=(not attachment)),
        ]
        for item in items:
            view.add_item(item)

        if messageEditEmbed is not discord.utils.MISSING:
            EmbedBuilder.adaptViewAfterEmbed(view, EmbedBuilder.getDependencies(messageEditEmbed))

        attachment = await attachment.to_file() if attachment else discord.utils.MISSING

        await interaction.response.send_message(
            "Embed builder!",
            embed=messageEditEmbed,
            view=view,
            file=attachment
        )

        if not attachment and isinstance(messageEdit, discord.Message) and len(messageEdit.attachments):
            embed = discord.Embed(title="⚠️ Removing attachment", description="The target message (messageid) currently has an attachment.\nYou have not provided an attachment.\n**This means that on submit, the attachment will be removed!**", color=discord.Color.orange())
            await interaction.followup.send(interaction.user.mention, embed=embed, ephemeral=True)


# ===== </Build Embed> =====

    @staticmethod
    def getDependencies(embed: discord.Embed) -> dict:
        """Get dependency dict."""
        return {
            "title": {
                "dependent": ("URL", "Timestamp", "Color", "Submit"),
                "propertyValue": embed.title
            },
            "description": {
                "dependent": ("Timestamp", "Color", "Submit"),
                "propertyValue": embed.description
            },
            "thumbnail": {
                "dependent": ("Timestamp", "Color", "Submit"),
                "propertyValue": embed.thumbnail.url if embed.thumbnail else None
            },
            "image": {
                "dependent": ("Timestamp", "Color", "Submit"),
                "propertyValue": embed.image.url if embed.image else None
            },
            "author": {
                "dependent": ("Timestamp", "Color", "Submit"),
                "propertyValue": embed.author.name if embed.author else None
            },
            "footer": {
                "dependent": ("Timestamp", "Color", "Submit"),
                "propertyValue": embed.footer.text if embed.footer else None
            },
        }


    @staticmethod
    def unLockDependents(view: discord.ui.View, dependencies: dict, name: str, value: str) -> None:
        """(Un)locks view.button if other field that is a dependant is (in)active."""
        for item in view.children:
            # Skip if item is not dependent on the field identified by `name`
            if item.label not in dependencies.get(name, {}).get("dependent", ()):
                continue

            if value:
                item.disabled = False
                continue

            # If value is False, check if any other dependency keeps the button active
            item.disabled = True  # Assume disabled unless another dependency makes it active
            for key, dependency in dependencies.items():
                if key != name and item.label in dependency["dependent"]:
                    # If any other dependency has `propertyValue` True, keep the item enabled
                    if dependency["propertyValue"]:
                        item.disabled = False
                        break


    @staticmethod
    def adaptViewAfterEmbed(view: discord.ui.View, dependencies: dict) -> None:
        """Checks if all buttons in view are configured correctly, disabled or not depending on dependancies."""
        for key, val in dependencies.items():
            EmbedBuilder.unLockDependents(view, dependencies, key, val["propertyValue"])


# ===== <Views and Buttons> =====


class BuilderView(discord.ui.View):
    """Handling all builder views."""
    def __init__(self, targetChannel: int, messageId: int | None, *args, **kwargs):
        super().__init__(timeout=None, *args, **kwargs)
        self.targetChannel = targetChannel
        self.messageId = messageId


class BuilderButton(discord.ui.Button):
    """Handling all builder buttons."""
    def __init__(self, instance, authorId: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.authorId = authorId

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.authorId:
            await interaction.response.send_message(f"{interaction.user.mention} Only the one who executed the command may interact with the buttons!", ephemeral=True, delete_after=15.0)
            return

        if not isinstance(interaction.user, discord.Member):
            log.exception("EmbedBuilder buttonHandling: user not discord.Member")
            return

        if interaction.message is None:
            log.exception("EmbedBuilder buttonHandling: interaction.message is None")
            return


        name = interaction.data["custom_id"][len("builder_button_"):]
        modal = BuilderModal(f"Set embed {name.lower()}", f"builder_modal_{name.lower()}", interaction.message, self.view)
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

            case "cancel":
                await interaction.response.edit_message(
                    content=f"Cancelled command!",
                    embed=None,
                    attachments=[],
                    view=None
                )
                return
            case "submit":
                if not hasattr(self.view, "targetChannel"):
                    log.exception("EmbedBuilder buttonHandling: targetChannel not set in button.view")
                    return

                guild = interaction.guild
                if not guild:
                    log.exception("EmbedBuilder buttonHandling: guild is None")
                    return

                targetChannel = guild.get_channel_or_thread(self.view.targetChannel)
                if not targetChannel:
                    log.exception("EmbedBuilder buttonHandling: targetChannel is None")
                    return

                if hasattr(self.view, "messageId") and self.view.messageId:
                    try:
                        targetMessage = await targetChannel.fetch_message(self.view.messageId)
                    except Exception:
                        embed = discord.Embed(title="❌ Invalid messageid", description=f"Message with id `{self.view.messageId}` could not be found in channel `{targetChannel.mention}`!", color=discord.Color.red())
                        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=15.0)
                        return

                    log.info(f"{interaction.user.id} [{interaction.user.display_name}] Edited the embed on message '{self.view.messageId}' in '{targetChannel.name}' ({targetChannel.id})")
                    await targetMessage.edit(
                        embed=interaction.message.embeds[0] if len(interaction.message.embeds) > 0 else None,
                        attachments=([await interaction.message.attachments[0].to_file()]) if len(interaction.message.attachments) > 0 else []
                    )
                    await interaction.response.edit_message(
                        content=f"Message embed edited, {targetMessage.jump_url}!",
                        embed=None,
                        attachments=[],
                        view=None
                    )
                    return

                log.info(f"{interaction.user.id} [{interaction.user.display_name}] Built an embed and sent it to '{targetChannel.id}' [{targetChannel.name}]")
                await targetChannel.send(
                    embed=interaction.message.embeds[0] if len(interaction.message.embeds) > 0 else None,
                    file=(await interaction.message.attachments[0].to_file()) if len(interaction.message.attachments) > 0 else None
                )
                await interaction.response.edit_message(
                    content=f"Embed sent to {targetChannel.mention}!",
                    embed=None,
                    attachments=[],
                    view=None
                )
                return


        if len(modalConfig["customitems"]) == 0:
            modal.add_item(discord.ui.TextInput(label=name, style=modalConfig["style"], placeholder=modalConfig["placeholder"], default=modalConfig["default"], required=False, max_length=modalConfig["maxLength"]))
        else:
            for item in modalConfig["customitems"]:
                modal.add_item(item)
        await interaction.response.send_modal(modal)


class BuilderModal(discord.ui.Modal):
    """Handling all builder modals."""
    def __init__(self, title: str, customId: str, message: discord.Message, view: discord.ui.View | None = None) -> None:
        super().__init__(title=title, custom_id=customId)
        self.message = message
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            log.exception("BuilderModal on_submit: interaction.user not discord.Member")
            return

        value: str = self.children[0].value.strip()

        stderr = None
        embed = discord.Embed()
        if len(self.message.embeds) > 0:
            embed = self.message.embeds[0]

        # Values depend on (any) key to be filled
        dependencies = EmbedBuilder.getDependencies(embed)

        name = interaction.data["custom_id"][len("builder_modal_"):]
        match name:
            case "title":
                embed.title = value
                EmbedBuilder.unLockDependents(self.view, dependencies, name, value)
            case "description":
                embed.description = value
                EmbedBuilder.unLockDependents(self.view, dependencies, name, value)
            case "timestamp":
                try:
                    embed.timestamp = datetimeParse(value)
                except Exception:
                    stderr = "Invalid timestamp format."
            case "color":
                patternRGB = re.compile(r"(\d{1,3}(?:,| |, ))(\d{1,3}(?:,| |, ))(\d{1,3})")

                # Hex
                if re.match(r"^#?(?:[0-9a-fA-F]{3}){1,2}$", value):
                    try:
                        embed.color = int(value.lstrip("#"), 16)
                    except ValueError:
                        stderr = "Invalid color value."

                # RGB
                elif re.match(patternRGB, value):
                    rgb = re.findall(patternRGB, value)[0]
                    try:
                        embed.color = discord.Color.from_rgb(int(rgb[0].rstrip(" ").rstrip(",")), int(rgb[1].rstrip(" ").rstrip(",")), int(rgb[2].rstrip(" ").rstrip(",")))
                    except Exception:
                        stderr = "Invalid color value."

            case "url":
                if not re.match(r"^https?:\/\/.*", value):
                    stderr = "URL must be a valid HTTP or HTTP link."
                else:
                    embed.url = value

            case "thumbnail":
                if embed and not embed.title and not embed.description and not value and not embed.image and not embed.author and not embed.footer:
                    embed = None
                else:
                    embed.set_thumbnail(url=value)
                    EmbedBuilder.unLockDependents(self.view, dependencies, name, value)
            case "image":
                if embed and not embed.title and not embed.description and not embed.thumbnail and not value and not embed.author and not embed.footer:
                    embed = None
                else:
                    embed.set_image(url=value)
                    EmbedBuilder.unLockDependents(self.view, dependencies, name, value)

            case "author":
                authorName = self.children[0].value.strip()
                authorURL = self.children[1].value.strip()
                authorIconURL = self.children[2].value.strip()
                if not authorName and (authorURL or authorIconURL):
                    stderr = "Must set Author Name if using Author URL or Author Icon URL."
                elif embed and not embed.title and not embed.description and not embed.thumbnail and not embed.image and not authorName and not embed.footer:
                    embed = None
                else:
                    embed.set_author(name=authorName, url=authorURL, icon_url=authorIconURL)
                    EmbedBuilder.unLockDependents(self.view, dependencies, name, value)
            case "footer":
                footerText = self.children[0].value.strip()
                footerIconURL = self.children[1].value.strip()
                if not footerText and footerIconURL:
                    stderr = "Must set Footer Text if using Footer Icon URL."
                elif embed and not embed.title and not embed.description and not embed.thumbnail and not embed.image and not embed.author and not footerText:
                    embed = None
                else:
                    embed.set_footer(text=footerText, icon_url=footerIconURL)
                    EmbedBuilder.unLockDependents(self.view, dependencies, name, value)


        if stderr:
            await interaction.response.send_message(stderr, ephemeral=True, delete_after=15.0)
            return

        # Delete embed
        if not embed or (embed and not embed.title and not embed.description and not embed.thumbnail and not embed.image and not embed.author and not embed.footer):
            embed = None

        try:
            await interaction.response.edit_message(embed=embed, view=self.view)
        except Exception as e:
            await interaction.response.send_message(str(e), ephemeral=True, delete_after=15.0)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.exception(error)


# ===== </Views and Buttons> =====



async def setup(bot: commands.Bot) -> None:
    EmbedBuilder.buildEmbed.error(Utils.onSlashError)
    await bot.add_cog(EmbedBuilder(bot))
