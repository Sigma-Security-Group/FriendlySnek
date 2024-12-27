import re, math, discord, collections.abc

from discord.ext import commands  # type: ignore

from logger import Logger
from secret import DEBUG
from constants import *
if DEBUG:
    from constants.debug import *

CUSTOMID_PERSISTENT_BUTTON_REGEX = r"buttonrole_persistent_(?P<whitelistid>\d+)_(?P<roleid>\d+)"
CUSTOMID_PERSISTENT_BUTTON_FORMAT = "buttonrole_persistent_{}_{}"

@discord.app_commands.guilds(GUILD)
class ButtonRoles(commands.GroupCog, group_name="button-role"):
    """Workshop Interest Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        Logger.debug(LOG_COG_READY.format("ButtonRoles"), flush=True)
        self.bot.cogsReady["buttonRoles"] = True


    @discord.app_commands.command(name="create")
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_STAFF)
    @discord.app_commands.describe(
        target_channel = "Where the message will be sent.",
        role1 = "A role for users to toggle.",
        role2 = "A role for users to toggle.",
        role3 = "A role for users to toggle.",
        role4 = "A role for users to toggle.",
        role5 = "A role for users to toggle.",
        role6 = "A role for users to toggle.",
        role7 = "A role for users to toggle.",
        role8 = "A role for users to toggle.",
        role9 = "A role for users to toggle.",
        role10 = "A role for users to toggle.",
        whitelist_role = "What role is allowed to press the buttons (e.g. Members).",
        message_content = "What the message content will display.",
    )
    async def buttonRoleCreate(self, interaction: discord.Interaction, target_channel: discord.TextChannel, role1: discord.Role, role2: discord.Role = None, role3: discord.Role = None, role4: discord.Role = None, role5: discord.Role = None, role6: discord.Role = None, role7: discord.Role = None, role8: discord.Role = None, role9: discord.Role = None, role10: discord.Role = None, whitelist_role: discord.Role = None, message_content: str = "**Click any button to recieve that role!**\n*This only works if you have passed the welcome interview!*") -> None:
        """Create a Button Role message.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        target_channel (discord.TextChannel): Channel to send the output message.
        role1 (discord.Role): Mandatory toggleable role.
        role2 (discord.Role | None): Optional toggleable role.
        role3 (discord.Role | None): Optional toggleable role.
        role4 (discord.Role | None): Optional toggleable role.
        role5 (discord.Role | None): Optional toggleable role.
        role6 (discord.Role | None): Optional toggleable role.
        role7 (discord.Role | None): Optional toggleable role.
        role8 (discord.Role | None): Optional toggleable role.
        role9 (discord.Role | None): Optional toggleable role.
        role10 (discord.Role | None): Optional toggleable role.
        whitelist_role (discord.Role | None): Optional whitelisted role for interacting with any button.
        message_content (str): Optional custom output message content.

        Returns:
        None.
        """
        view = ButtonRolesPersistentView(whitelistRole=whitelist_role)
        permittedRoles = ButtonRoles.permittedAssignableRoles(target_channel.guild.roles)

        for role in (role1, role2, role3, role4, role5, role6, role7, role8, role9, role10):
            # Ignore role that aren't filled
            if not role:
                continue

            # Remove duplicates
            roleCustomId = CUSTOMID_PERSISTENT_BUTTON_FORMAT.format((whitelist_role.id if whitelist_role else 0), role.id)
            if roleCustomId in [item.custom_id for item in view.children]:
                continue

            # Only allow permitted roles
            if role not in permittedRoles:
                continue

            # Add persistent button
            view.add_item(
                ButtonRolesPersistentButton(
                    custom_id=roleCustomId,
                    label=role.name,
                    style=discord.ButtonStyle.primary
                )
            )

        # All roles were ignored
        if not view.children:
            embed = discord.Embed(title="❌ Invalid roles", description="The role(s) you have entered are not permitted to be attached!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=15.0)
            return

        # Send feedback
        Logger.info(f"{interaction.user.id} [{interaction.user.display_name}] Created a button-role message")
        msg = await target_channel.send(message_content, view=view)
        await interaction.response.send_message(f"Button Role message created! {msg.jump_url}", ephemeral=True, delete_after=30.0)


    @staticmethod
    async def toggleRole(interaction: discord.Interaction, roleId: int) -> None:
        """Toggles role for member.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        roleId (int): Role id to toggle on user.

        Returns:
        None.
        """
        guild = interaction.guild
        if not isinstance(guild, discord.Guild):
            Logger.exception("ButtonRoles toggleRole: guild not discord.Guild")
            return

        role = guild.get_role(roleId)
        if not isinstance(role, discord.Role):
            Logger.exception("ButtonRoles toggleRole: role not discord.Role")
            embed = discord.Embed(title="❌ Invalid role", description="Role does not exist. Please contact Unit Staff!", color=discord.Color.red())
            await interaction.response.send_message(content=interaction.user.mention, embed=embed, ephemeral=True, delete_after=15.0)
            return

        # Toggle role
        checkRoleInRoles = role in interaction.user.roles
        if checkRoleInRoles:
            await interaction.user.remove_roles(role, reason="Button Role interaction [Remove].")
        else:
            await interaction.user.add_roles(role, reason="Button Role interaction [Add].")

        # Send feedback
        embed = discord.Embed(description=("Removed" if checkRoleInRoles else "Added") + f" {role.mention}", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=15.0)


    @discord.app_commands.command(name="edit")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_STAFF)
    @discord.app_commands.describe(message_channel = "What channel the existing message is in.", message_id = "What message id the existing message has.")
    async def buttonRoleEdit(self, interaction: discord.Interaction, message_channel: discord.TextChannel, message_id: str) -> None:
        """Edit a Button Role message.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        message_channel (discord.TextChannel): The target message's channel.
        message_id (str): Target message id.

        Returns:
        None.
        """
        # Invalid TextChannel / message.id combo
        try:
            message = await message_channel.fetch_message(int(message_id))
        except Exception:
            embed = discord.Embed(title="❌ Invalid data", description=f"Message with id `{message_id}` could not be found in channel {message_channel.mention}!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=15.0)
            return

        guild = interaction.guild
        if not isinstance(guild, discord.Guild):
            Logger.exception("ButtonRoles buttonRoleEdit: guild not discord.Guild")
            return

        # Automatically update message buttons
        view = discord.ui.View.from_message(message, timeout=None)
        isUpdateView = False
        for item in view.children:
            whitelistId, roleId = item.custom_id.split("_")[-2:]
            role = guild.get_role(int(roleId))

            # Role no longer exist; remove button
            if not isinstance(role, discord.Role):
                isUpdateView = True
                view.remove_item(item)
                continue


            # Role name updated
            if item.label != role.name:
                isUpdateView = True
                item.label = role.name
                continue

        if isUpdateView:
            await message.edit(view=view)


        # Prompt user with editing alternatives
        embed = discord.Embed(title=f"Edit button role message", url=message.jump_url, description="Choose wheter to add or remove a role from the target button role message.\nYou can have up to 25 roles.", color=discord.Color.gold())
        view = ButtonRolesView()
        buttons = (
            ButtonRolesButton(msgChannel=message_channel, buttonRoleMsgId=message.id, custom_id="buttonrole_edit_add", label="Add", style=discord.ButtonStyle.success),
            ButtonRolesButton(msgChannel=message_channel, buttonRoleMsgId=message.id, custom_id="buttonrole_edit_remove", label="Remove", style=discord.ButtonStyle.danger)
        )
        for button in buttons:
            view.add_item(button)

        Logger.info(f"{interaction.user.id} [{interaction.user.display_name}] Edits a button-role message '{message_id}'")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=300.0)


    @staticmethod
    def generateSelectMenu(msgChannel: discord.TextChannel, buttonRoleMsgId: int, whitelistRoleId: int, iterable: collections.abc.Iterable[discord.SelectOption], placeholder: str, customId: str) -> collections.abc.Generator:
        """Generates multiple select menus.

        Parameters:
        buttonRoleMsgId (int): Button role message id, passed to Select class.
        whitelistRoleId (int): Whitelist role id, passed to Select class.
        iterable (collections.abc.Iterable[discord.SelectOption]): SelectOptions for the select menu.
        placeholder (str): Select menu placeholder.
        customId (str): Select menu custom id.

        Returns:
        collections.abc.Generator: Iterable containing select menus.
        """
        # Chunk all roles into select menus with max 25 options each
        # Max 4 select menus allowed (cope and seethe)
        for i in range(min(math.ceil(len(iterable) / 25), 4)):
            yield ButtonRolesSelect(msgChannel=msgChannel, buttonRoleMsgId=buttonRoleMsgId, whitelistRoleId=whitelistRoleId, placeholder=placeholder, minValues=1, maxValues=1, customId=f"{customId}_REMOVE{i}", row=i, options=iterable[:25])
            iterable = iterable[25:]


    @staticmethod
    def permittedAssignableRoles(guildRoles: collections.abc.Sequence[discord.Role], blacklist: list[discord.Role] = []) -> list[discord.Role]:
        """Generate allowed roles for snek to assign.

        Parameters:
        guildRoles (collections.abc.Sequence[discord.Role]): All guild roles to choose from.
        blacklist (list[discord.Role]): Roles that must not be included in the returned result.

        Returns:
        list[discord.Role]: List of all permitted assignable roles.
        """
        return [guildRole for guildRole in guildRoles if (guildRole not in blacklist and not guildRole.is_default() and guildRole.is_assignable())]


    @staticmethod
    async def buttonHandling(interaction: discord.Interaction, button: discord.ui.Button, msgChannel: discord.TextChannel, buttonRoleMsgId: int) -> None:
        """Handling button interactions.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        button (discord.ui.Button): Button instance.
        buttonRoleMsgId (int): Button-Role message id.

        Returns:
        None.
        """
        guild = interaction.guild
        if not isinstance(guild, discord.Guild):
            Logger.exception("ButtonRoles buttonHandling: guild not discord.Guild")
            return

        buttonRoleMsg = await msgChannel.fetch_message(buttonRoleMsgId)

        # Fetch active roles from message
        activeRoleIds = []
        whitelistRoleId = 0
        for item in discord.ui.View.from_message(buttonRoleMsg, timeout=None).children:
            whitelistRoleId, activeRoleIdRaw = item.custom_id.split("_")[-2:]
            activeRoleIds.append(int(activeRoleIdRaw))

        view = discord.ui.View()
        currentRoles = [guild.get_role(msgRoleId) for msgRoleId in activeRoleIds]

        # Button specific actions
        match button.custom_id:
            case "buttonrole_edit_add":
                addableRoles = ButtonRoles.permittedAssignableRoles(guild.roles, blacklist=currentRoles)
                if not addableRoles:
                    embed = discord.Embed(title="❌ No roles available", description="Cannot find any roles to add, that isn't already attached to the message.", color=discord.Color.red())
                    await interaction.response.send_message(interaction.user.mention, embed=embed, ephemeral=True, delete_after=15.0)
                    return

                options = [discord.SelectOption(label=addableRole.name, value=addableRole.id) for addableRole in addableRoles]
                for item in ButtonRoles.generateSelectMenu(msgChannel=msgChannel, buttonRoleMsgId=buttonRoleMsgId, whitelistRoleId=whitelistRoleId, iterable=options, placeholder="Select a role to add.", customId="buttonrole_select_add"):
                    view.add_item(item)

                embed = discord.Embed(title="Select role", description="Select a role from the dropdown, to add it from the button roles.", color=discord.Color.gold())


            case "buttonrole_edit_remove":
                if not currentRoles:
                    embed = discord.Embed(title="❌ No roles available", description="Cannot find any roles attached to the message.", color=discord.Color.red())
                    await interaction.response.send_message(interaction.user.mention, embed=embed, ephemeral=True, delete_after=15.0)
                    return

                options = [discord.SelectOption(label=currentRole.name, value=currentRole.id) for currentRole in currentRoles]
                for item in ButtonRoles.generateSelectMenu(msgChannel=msgChannel, buttonRoleMsgId=buttonRoleMsgId, whitelistRoleId=whitelistRoleId, iterable=options, placeholder="Select a role to remove.", customId="buttonrole_select_remove"):
                    view.add_item(item)

                embed = discord.Embed(title="Select role", description="Select a role from the dropdown, to remove it from the button roles.", color=discord.Color.gold())


        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=300.0)


    @staticmethod
    async def selectHandling(interaction: discord.Interaction, select: discord.ui.Select, msgChannel: discord.TextChannel, buttonRoleMsgId: int, whitelistRoleId: int) -> None:
        """Handling select menu interactions.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        select (discord.ui.Select): Select instance.
        buttonRoleMsgId (int): Button-Role message id.
        whitelistRoleId (int): Whitelist role id.

        Returns:
        None.
        """
        infoLabel = select.custom_id.split("_REMOVE")[0]
        roleIdSelected = int(select.values[0])

        buttonRoleMsg = await msgChannel.fetch_message(buttonRoleMsgId)

        match infoLabel:
            case "buttonrole_select_add":
                guild = interaction.guild
                if not isinstance(guild, discord.Guild):
                    Logger.exception("ButtonRoles selectHandling: guild not discord.Guild")
                    return

                roleSelected = guild.get_role(roleIdSelected)
                if not isinstance(roleSelected, discord.Role):
                    Logger.exception("ButtonRoles selectHandling: roleSelected not discord.Role")
                    return

                view = discord.ui.View.from_message(buttonRoleMsg, timeout=None)
                newButtonCustomId = CUSTOMID_PERSISTENT_BUTTON_FORMAT.format(whitelistRoleId, roleIdSelected)

                # Check for existing role
                for item in view.children:
                    if item.custom_id == newButtonCustomId:
                        embed = discord.Embed(title="❌ Role exists", description=f"{roleSelected.mention} has already been added to the button role message!", color=discord.Color.red())
                        await interaction.response.edit_message(embed=embed, view=None)
                        return

                # Role limitation
                if len(view.children) == 25:
                    embed = discord.Embed(title="❌ Role limit reached", description="You may not add more than 25 roles to one button role message.", color=discord.Color.red())
                    await interaction.response.edit_message(embed=embed, view=None)
                    return

                # Add button & send feedback
                view.add_item(
                    ButtonRolesPersistentButton(
                        custom_id=newButtonCustomId,
                        label=roleSelected.name,
                        style=discord.ButtonStyle.primary
                    )
                )

                await buttonRoleMsg.edit(view=view)
                embed = discord.Embed(title="✅ Role added", description=f"{roleSelected.mention} has been added from the button role message!", color=discord.Color.green())
                await interaction.response.edit_message(embed=embed, view=None)


            case "buttonrole_select_remove":
                view = discord.ui.View.from_message(buttonRoleMsg, timeout=None)
                for item in view.children:
                    match = re.match(CUSTOMID_PERSISTENT_BUTTON_REGEX, item.custom_id)
                    roleIdMatched = int(match["roleid"])
                    if roleIdSelected == roleIdMatched:
                        view.remove_item(item)
                        await buttonRoleMsg.edit(view=view)

                        roleMention = ""
                        try:
                            roleMention = interaction.guild.get_role(roleIdSelected).mention
                        except Exception:
                            pass

                        embed = discord.Embed(title="✅ Role removed", description=(roleMention if roleMention else "Role") + " has been removed from the button role message!", color=discord.Color.green())
                        await interaction.response.edit_message(embed=embed, view=None)
                        return

                embed = discord.Embed(title="❌ Role not found", description="Selected role could not be found attached to the message.", color=discord.Color.red())
                await interaction.response.edit_message(embed=embed, view=None)



# ===== <Views and Buttons> =====

class ButtonRolesPersistentView(discord.ui.View):
    """Handling all schedule persistent views."""
    def __init__(self, whitelistRole = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = None
        self.whitelistRole = whitelistRole


class ButtonRolesPersistentButton(discord.ui.DynamicItem[discord.ui.Button], template=CUSTOMID_PERSISTENT_BUTTON_REGEX):
    """Handling all button roles persistent buttons."""
    def __init__(self, custom_id:str = "", roleId: int = None, whitelistId: int = None, *args, **kwargs):
        super().__init__(discord.ui.Button(custom_id=custom_id, *args, **kwargs))
        self.roleId = roleId
        self.whitelistId = whitelistId

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        whitelistId = int(match["whitelistid"])
        roleId = int(match["roleid"])
        return cls(item.custom_id, whitelistId=whitelistId, roleId=roleId)

    async def callback(self, interaction: discord.Interaction):
        if self.whitelistId:
            guild = interaction.guild
            if not isinstance(guild, discord.Guild):
                Logger.exception("ButtonRolesPersistentButton callback: guild not discord.Guild")
                return

            whitelistRole = guild.get_role(self.whitelistId)
            if not isinstance(whitelistRole, discord.Role):
                Logger.exception("ButtonRolesPersistentButton callback: whitelistRole not discord.Role")
                return

            if whitelistRole not in interaction.user.roles:
                embed = discord.Embed(title="❌ Invalid role", description=f"You do not have the role: {whitelistRole.mention}", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=15.0)
                return

        await ButtonRoles.toggleRole(interaction, self.roleId)


class ButtonRolesView(discord.ui.View):
    """Handling schedule views."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = None


class ButtonRolesButton(discord.ui.Button):
    """Handling button roles buttons."""
    def __init__(self, msgChannel: discord.TextChannel, buttonRoleMsgId: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.msgChannel = msgChannel
        self.buttonRoleMsgId = buttonRoleMsgId


    async def callback(self, interaction: discord.Interaction):
        await ButtonRoles.buttonHandling(interaction, self, self.msgChannel, self.buttonRoleMsgId)


class ButtonRolesSelect(discord.ui.Select):
    """Handling all button roles dropdowns."""
    def __init__(self, msgChannel: discord.TextChannel, buttonRoleMsgId: int, whitelistRoleId: int, placeholder: str, minValues: int, maxValues: int, customId: str, row: int, options: list[discord.SelectOption], disabled: bool = False, *args, **kwargs):
        super().__init__(placeholder=placeholder, min_values=minValues, max_values=maxValues, custom_id=customId, row=row, options=options, disabled=disabled, *args, **kwargs)
        self.msgChannel = msgChannel
        self.buttonRoleMsgId = buttonRoleMsgId
        self.whitelistRoleId = whitelistRoleId

    async def callback(self, interaction: discord.Interaction) -> None:
        await ButtonRoles.selectHandling(interaction, self, self.msgChannel, self.buttonRoleMsgId, self.whitelistRoleId)


# ===== </Views and Buttons> =====

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ButtonRoles(bot))
    bot.add_dynamic_items(ButtonRolesPersistentButton)
