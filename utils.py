import discord, logging

log = logging.getLogger("FriendlySnek")

class Utils:
    @staticmethod
    async def onSlashError(instance, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        """Handles errors for slash commands.

        Parameters:
        instance: Cog instance.
        interaction (discord.Interaction): The Discord interaction.
        error (discord.app_commands.AppCommandError): The error that occurred.

        Returns:
        None.
        """
        if type(error) == discord.app_commands.errors.MissingAnyRole:
            guild = interaction.guild
            if guild is None:
                log.exception("Utils onSlashError: guild is None")
                return

            missingRolesList = []
            for missingRole in error.missing_roles:
                if isinstance(missingRole, int):
                    fetchedRole = guild.get_role(missingRole)
                    missingRolesList.append(f"`{missingRole}`" if fetchedRole is None else fetchedRole.mention)

                else:
                    missingRolesList.append(str(missingRole))

            embed = discord.Embed(title="❌ Missing permissions", description=f"You do not have the permissions to execute this command!\nThe permitted roles are: {', '.join(missingRolesList)}.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)
            return
        log.exception(error)
