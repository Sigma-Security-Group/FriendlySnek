import discord, logging
from discord.ext import commands  # type: ignore
from itertools import count, filterfalse

import secret
from constants import *
if secret.DEBUG:
    from constants.debug import *

log = logging.getLogger("FriendlySnek")

@discord.app_commands.guilds(GUILD)
class DynamicVoice(commands.GroupCog, name="voice"):
    """Dynamic Voice Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("DynamicVoice"))
        self.bot.cogsReady["dynamicVoice"] = True


    @staticmethod
    @commands.Cog.listener()
    async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        """On member voiceState change."""
        if not ((before.channel and before.channel.guild.id == GUILD_ID) or (after.channel and after.channel.guild.id == GUILD_ID)):
            return

        # User joined create channel vc; create new vc
        if after.channel and after.channel.id == CREATE_CHANNEL:
            guild = member.guild
            customChannelsCategory = discord.utils.get(guild.categories, id=CUSTOM_CHANNELS)
            if customChannelsCategory is None:
                log.exception("DynamicVoice on_voice_state_update: customChannelsCategory is None")
                return

            voiceNums = []
            # Iterate all dynamic "Room" channels, extract digit(s)
            for customVoice in customChannelsCategory.voice_channels:
                if customVoice.name.startswith("Room #"):
                    voiceNums.append(int("".join(c for c in customVoice.name[len("Room #"):] if c.isdigit())))

            newVoiceName = f"Room #{next(filterfalse(set(voiceNums).__contains__, count(1)))}"
            if member.voice and member.voice.channel:
                newVoiceChannel = await guild.create_voice_channel(newVoiceName, reason="User created new dynamic voice channel.", category=customChannelsCategory)
                await member.move_to(newVoiceChannel, reason="User created new dynamic voice channel.")


        if before.channel and before.channel.id != CREATE_CHANNEL and before.channel.category and before.channel.category.id == CUSTOM_CHANNELS and len(before.channel.members) == 0:
            try:
                await before.channel.delete(reason="No users left in dynamic voice channel.")
            except Exception:
                log.warning(f"DynamicVoice on_voice_state_update: failed to delete dynamic voice channel: '{before.channel.name}' ({member.id})")


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

        oldLimit = interaction.user.voice.channel.user_limit
        log.debug(f"{interaction.user.id} [{interaction.user.display_name}] Changed the dynamic voice limit from '{oldLimit}' to '{new_limit}'")
        await interaction.user.voice.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(f"Changed {interaction.user.voice.channel.mention} user limit to `{new_limit}`", ephemeral=True, delete_after=15.0)

        if secret.DISCORD_LOGGING.get("voice_dynamic_limit", False):
            if not isinstance(interaction.guild, discord.Guild):
                log.exception("DynamicVoice limit: interaction.guild not discord.Guild")
                return
            channelAuditLogs = interaction.guild.get_channel(AUDIT_LOGS)
            if not isinstance(channelAuditLogs, discord.TextChannel):
                log.exception("DynamicVoice limit: channelAuditLogs not discord.TextChannel")
                return

            embed = discord.Embed(title="Dynamic Voice Channel Limit", description=f"Channel: {interaction.user.voice.channel.name}\nOld limit: `{oldLimit}`\nNew limit: `{new_limit}`", color=discord.Color.blue())
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar)
            embed.set_footer(text=f"Member ID: {interaction.user.id} | Channel ID: {interaction.user.voice.channel.id}")
            await channelAuditLogs.send(embed=embed)


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
        log.debug(f"{interaction.user.id} [{interaction.user.display_name}] Changed the dynamic voice name from '{oldName}' to '{new_name}'")
        await interaction.user.voice.channel.edit(name=new_name)
        await interaction.response.send_message(f"Changed voice channel name from `{oldName}` to `{new_name}`", ephemeral=True, delete_after=15.0)

        if secret.DISCORD_LOGGING.get("voice_dynamic_name", False):
            if not isinstance(interaction.guild, discord.Guild):
                log.exception("DynamicVoice name: interaction.guild not discord.Guild")
                return
            channelAuditLogs = interaction.guild.get_channel(AUDIT_LOGS)
            if not isinstance(channelAuditLogs, discord.TextChannel):
                log.exception("DynamicVoice name: channelAuditLogs not discord.TextChannel")
                return

            embed = discord.Embed(title="Dynamic Voice Channel Name", description=f"Old channel name: `{oldName}`\nNew channel name: `{new_name}`", color=discord.Color.blue())
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar)
            embed.set_footer(text=f"Member ID: {interaction.user.id} | Channel ID: {interaction.user.voice.channel.id}")
            await channelAuditLogs.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DynamicVoice(bot))
