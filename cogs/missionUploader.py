from secret import DEBUG
import asyncio
import pytz
import secret
from datetime import datetime
from ftplib import FTP

from discord import app_commands, Embed, Color, utils
from discord.ext import commands

from constants import *
from __main__ import log, cogsReady
if DEBUG:
    from constants.debug import *


TIMEOUT_EMBED = Embed(title=ERROR_TIMEOUT, color=Color.red())
MISSIONS_UPLOADED_FILE = "data/missionsUploaded.log"
# FTP_MISSIONS_DIR = "/144.48.106.194_2316/mpmissions"  # Host Havoc
#FTP_MISSIONS_DIR = "/euc-ogs7.armahosts.com_2482/mpmissions"  # Dwarf's server
FTP_MISSIONS_DIR = "/euc-ogs11.armahosts.com_2492/mpmissions"  # Dwarf's server TEST

UTC = pytz.utc

class MissionUploader(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("MissionUploader"), flush=True)
        cogsReady["missionUploader"] = True

    async def checkAttachments(self, dmChannel, attachments):
        """
            X.

            Parameters:
            dmChannel: X.
            attachments: X.

            Returns:
            None
        """
        with FTP() as ftp:
            ftp.connect(host=secret.FTP_HOST, port=secret.FTP_PORT)
            ftp.login(user=secret.FTP_USERNAME, passwd=secret.FTP_PASSWORD)
            ftp.cwd(FTP_MISSIONS_DIR)
            missionFilesOnServer = ftp.nlst()
        attachmentOk = False
        if len(attachments) == 0:
            embed = Embed(title="❌ You didn't upload a file. Please upload the mission file!", color=Color.red())
            await dmChannel.send(embed=embed)
        elif len(attachments) > 1:
            embed = Embed(title="❌ You supplied too many files. Plese only upload one file!", color=Color.red())
            await dmChannel.send(embed=embed)
        else:
            attachment = attachments[0]
            if not attachment.filename.endswith(".pbo"):
                embed = Embed(title="❌ This is not a PBO file. Please upload a PBO file!", color=Color.red())
                await dmChannel.send(embed=embed)
            elif attachment.filename in missionFilesOnServer:
                embed = Embed(title="❌ This file already exists. Please rename the file and reupload it!", color=Color.red())
                await dmChannel.send(embed=embed)
            else:
                attachmentOk = True
        return attachmentOk

    @app_commands.command(name="uploadmission")
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_any_role(UNIT_STAFF, SERVER_HAMSTER, MISSION_BUILDER, CURATOR)
    async def uploadMission(self, interaction: discord.Interaction) -> None:
        """ Upload a mission PBO file to the server. """
        await interaction.response.send_message("Upload mission file in DMs...")
        log.info(f"{interaction.user.display_name} ({interaction.user.name}#{interaction.user.discriminator}) is uploading a mission file...")

        embed = Embed(title="Upload the mission file you want to put on the server.", color=Color.gold())
        msg = await interaction.user.send(embed=embed)
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
            attachments = response.attachments
            attachmentOk = await self.checkAttachments(dmChannel, attachments)
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        while not attachmentOk:
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                attachments = response.attachments
                attachmentOk = await self.checkAttachments(dmChannel, attachments)
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        attachment = attachments[0]

        embed = Embed(title="Uploading mission file...", color=Color.green())
        await dmChannel.send(embed=embed)

        with open(f"tmp/{attachment.filename}", "wb") as f:
            await attachment.save(f)

        with FTP() as ftp:
            ftp.connect(host=secret.FTP_HOST, port=secret.FTP_PORT)
            ftp.login(user=secret.FTP_USERNAME, passwd=secret.FTP_PASSWORD)
            ftp.cwd(FTP_MISSIONS_DIR)
            DEBUG = False
            if not DEBUG:
                with open(f"tmp/{attachment.filename}", "rb") as f:
                    ftp.storbinary(f"STOR {attachment.filename}", f)

        filename = attachment.filename
        utcTime = UTC.localize(datetime.utcnow())
        member = f"{interaction.user.display_name} ({interaction.user.name}#{interaction.user.discriminator})"
        memberId = interaction.user.id

        with open(MISSIONS_UPLOADED_FILE, "a") as f:
            f.write(f"\nFilename: {filename}\nUTC Time: {utcTime.strftime(TIME_FORMAT)}\nMember: {member}\nMember ID: {memberId}\n")

        botLogChannel = self.bot.get_channel(BOT)
        embed = Embed(title="Mission file uploaded!", color=Color.blue())
        embed.add_field(name="Filename", value=filename)
        embed.add_field(name="Time", value=utils.format_dt(datetime.utcnow(), style="F"))
        embed.add_field(name="Member", value=member)
        embed.add_field(name="Member ID", value=memberId)
        await botLogChannel.send(embed=embed)

        log.info(f"{interaction.user.display_name} ({interaction.user.name}#{interaction.user.discriminator}) uploaded a mission file!")
        embed = Embed(title="Mission file uploaded!", color=Color.green())
        await dmChannel.send(embed=embed)

    @uploadMission.error
    async def onUploadMissionError(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if type(error) == discord.app_commands.errors.MissingAnyRole:
            guild = self.bot.get_guild(GUILD_ID)
            embed = Embed(title="❌ Missing permissions", description=f"You do not have the permissions to upload a mission file!\nThe permitted roles are: {', '.join([guild.get_role(role).name for role in (UNIT_STAFF, SERVER_HAMSTER, MISSION_BUILDER, CURATOR)])}.", color=Color.red())
            await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MissionUploader(bot))
