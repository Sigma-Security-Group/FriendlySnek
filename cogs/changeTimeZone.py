import json
import pytz
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from constants import *
from __main__ import log, DEBUG
if DEBUG:
    from constants.debug import *

TIMEOUT_EMBED = discord.Embed(title=ERROR_TIMEOUT, color=discord.Color.red())

class ChangeTimeZone(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cancelCommand(self, user, abortText:str) -> None:
        """
            Sends an abort response to the user.

            Parameters:
            user: The users DM channel where the message is sent.
            abortText (str): The embed title - what is aborted.

            Returns:
            None
        """
        await user.send(embed=discord.Embed(title=ABORT_CANCELED.format(abortText), color=discord.Color.red()))

    @app_commands.command(name="changetimezone")
    @app_commands.guilds(GUILD)
    async def timeZone(self, interaction: discord.Interaction) -> bool:
        """ Change your time zone preferences for your next scheduled event. """
        await interaction.response.send_message("Changing time zone preferences...")
        timeZoneOutput = await self.changeTimeZone(interaction, isCommand=True)
        if not timeZoneOutput:
            await self.cancelCommand(interaction.user, "Time zone preferences")

    async def changeTimeZone(self, interaction: discord.Interaction, isCommand: bool = True) -> bool:
        """
            Changing a personal time zone.

            Parameters:
            author: The command author.
            isCommand (bool): If the command calling comes from the actual slash command.

            Returns:
            bool: If function executed successfully.
        """
        log.info(f"{interaction.user.display_name} ({interaction.user.name}#{interaction.user.discriminator}) is updating their time zone preferences...")

        with open(MEMBER_TIME_ZONES_FILE) as f:
            memberTimeZones = json.load(f)

        timezoneOk = False
        color = discord.Color.gold()
        while not timezoneOk:
            embed = discord.Embed(title=":clock1: What's your preferred time zone?", description=(SCHEDULE_EVENT_SELECTED_TIME_ZONE.format(memberTimeZones[str(interaction.user.id)]) if str(interaction.user.id) in memberTimeZones else "You don't have a preferred time zone set.") + "\n\nEnter a number from the list below.\nEnter any time zone name from the column \"**TZ DATABASE NAME**\" in this [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)." + "\nEnter `none` to erase current preferences." * isCommand, color=color)
            embed.add_field(name="Popular Time Zones", value="\n".join(f"**{idx}** {tz}" for idx, tz in enumerate(TIME_ZONES, 1)))
            embed.set_footer(text="Enter `cancel` to abort this command.")
            color = discord.Color.red()
            try:
                msg = await interaction.user.send(embed=embed)
            except Exception as e:
                print(interaction.user, e)
                return False
            dmChannel = msg.channel
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                timeZone = response.content.strip()
                with open(MEMBER_TIME_ZONES_FILE) as f:
                    memberTimeZones = json.load(f)
                isInputNotNone = True
                if timeZone.lower() == "cancel":
                    return False
                elif timeZone.isdigit() and int(timeZone) <= len(TIME_ZONES) and int(timeZone) > 0:
                    timeZone = pytz.timezone(list(TIME_ZONES.values())[int(timeZone) - 1])
                    memberTimeZones[str(interaction.user.id)] = timeZone.zone
                    timezoneOk = True
                else:
                    try:
                        timeZone = pytz.timezone(timeZone)
                        memberTimeZones[str(interaction.user.id)] = timeZone.zone
                        timezoneOk = True
                    except pytz.exceptions.UnknownTimeZoneError:
                        if str(interaction.user.id) in memberTimeZones:
                            del memberTimeZones[str(interaction.user.id)]
                        if timeZone.lower() == "none" and isCommand:
                            isInputNotNone = False
                            timezoneOk = True

                if timezoneOk:
                    with open(MEMBER_TIME_ZONES_FILE, "w") as f:
                        json.dump(memberTimeZones, f, indent=4)
                    embed = discord.Embed(title=f"✅ Time zone preferences changed{f' to `{timeZone.zone}`' if isInputNotNone else ''}!", color=discord.Color.green())
                    await dmChannel.send(embed=embed)
                    return True

            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return False

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ChangeTimeZone(bot))
