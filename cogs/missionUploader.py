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


MISSIONS_UPLOADED_FILE = "data/missionsUploaded.log"
TIMEOUT_EMBED = Embed(title=ERROR_TIMEOUT, color=Color.red())
UTC = pytz.utc

SERVERS = [
    {
        "Name": "SSG - Operations Server",
        "Directory": "/euc-ogs7.armahosts.com_2482/mpmissions",
        "Host": "euc-ogs7.armahosts.com",
        "Port": 8822
    },
    {
        "Name": "SSG - Training & Testing Server",
        "Directory": "/euc-ogs11.armahosts.com_2492/mpmissions",
        "Host": "euc-ogs11.armahosts.com",
        "Port": 8821
    }
]

class MissionUploader(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("MissionUploader"), flush=True)
        cogsReady["missionUploader"] = True

    async def cancelCommand(self, channel: discord.DMChannel, abortText:str) -> None:
        """ Sends an abort response to the user.

        Parameters:
        channel (discord.DMChannel): The users DM channel where the message is sent.
        abortText (str): The embed title - what is aborted.

        Returns:
        None.
        """
        await channel.send(embed=Embed(title=f"❌ {abortText} canceled!", color=Color.red()))

    async def checkAttachments(self, server: dict, dmChannel: discord.DMChannel, attachments: list[discord.Attachment]) -> bool:
        """ Checks a users' message attachemnts if it complies with the set boundries.

        Parameters:
        dmChannel (discord.DMChannel): The DMChannel the user reponse is from.
        attachments (list[discord.Attachment]): A list of attachments from the user response.

        Returns:
        bool.
        """
        try:
            with FTP() as ftp:
                ftp.connect(host=server["Host"], port=server["Port"])
                ftp.login(user=secret.FTP_USERNAME, passwd=secret.FTP_PASSWORD)
                ftp.cwd(server["Directory"])
                missionFilesOnServer = ftp.nlst()
        except Exception as e:
            log.exception(e)
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
        """ Upload a mission PBO file to the server.

        Parameters:
        interaction (discord.Interaction): The Discor interaction.

        Returns:
        None.
        """
        await interaction.response.send_message("Upload mission file in DMs...")
        log.info(f"{interaction.user.display_name} ({interaction.user}) is uploading a mission file...")

        # Server
        serverSelectOk = False
        color = Color.gold()
        while not serverSelectOk:
            embed = Embed(title="Which server would you like to upload to?", description="\n".join([f"{index}. {server['Name']}" for index, server in enumerate(SERVERS, 1)]), color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            msg = await interaction.user.send(embed=embed)
            dmChannel = msg.channel
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                serverNumber = response.content.strip().lower()
                if serverNumber == "cancel":
                    await self.cancelCommand(dmChannel, "Mission uploading")
                    return
                elif serverNumber in [str(idx[0]) for idx in enumerate(SERVERS, 1)]:
                    serverSelectOk = True
                    server = SERVERS[int(serverNumber) - 1]
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

        # Mission file
        color = Color.gold()
        attachmentOk = False
        while not attachmentOk:
            embed = Embed(title="Upload the mission file you want to put on the server.", color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            msg = await interaction.user.send(embed=embed)
            dmChannel = msg.channel
            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                file = response.content.strip().lower()
                if file.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Mission uploading")
                    return
                attachments = response.attachments
                attachmentOk = await self.checkAttachments(server, dmChannel, attachments)
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        attachment = attachments[0]

        # Uploading
        await dmChannel.send(embed=Embed(title="Uploading mission file...", color=Color.green()))

        with open(f"tmp/{attachment.filename}", "wb") as f:
            await attachment.save(f)

        with FTP() as ftp:
            ftp.connect(host=server["Host"], port=server["Port"])
            ftp.login(user=secret.FTP_USERNAME, passwd=secret.FTP_PASSWORD)
            ftp.cwd(server["Directory"])
            if not DEBUG:
                with open(f"tmp/{attachment.filename}", "rb") as f:
                    ftp.storbinary(f"STOR {attachment.filename}", f)

        filename = attachment.filename
        utcTime = UTC.localize(datetime.utcnow())
        member = f"{interaction.user.display_name} ({interaction.user})"

        with open(MISSIONS_UPLOADED_FILE, "a") as f:
            f.write(f"\nFilename: {filename}\nUTC Time: {utcTime.strftime(TIME_FORMAT)}\nMember: {member}\nMember ID: {interaction.user.id}\n")

        embed = Embed(title="Uploaded mission file", color=Color.blue())
        embed.add_field(name="Filename", value=f"`{filename}`")
        embed.add_field(name="Server", value=f"`{server['Name']}`")
        embed.add_field(name="Time", value=utils.format_dt(pytz.timezone("UTC").localize(datetime.utcnow()).astimezone(UTC), style="F"))
        embed.add_field(name="Member", value=interaction.user.mention)
        embed.set_footer(text=f"Member ID: {interaction.user.id}")

        await self.bot.get_channel(BOT).send(embed=embed)  # Send the log message in the BOT channel

        log.info(f"{interaction.user.display_name} ({interaction.user}) uploaded the mission file {filename}!")
        if not DEBUG:
            embed = Embed(title="✅ Mission file uploaded", color=Color.green())
        if DEBUG:
            embed = Embed(title="Mission file uploaded", description="Actually... The file did not actually upload hehe.\nBot has debug mode enabled!", color=Color.orange())
        await dmChannel.send(embed=embed)

    @uploadMission.error
    async def onUploadMissionError(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """ uploadMission errors - dedicated for the discord.app_commands.errors.MissingAnyRole error.

        Parameters:
        interaction (discord.Interaction): The Discor interaction.
        error (app_commands.AppCommandError): The end user error.

        Returns:
        None.
        """
        if type(error) == discord.app_commands.errors.MissingAnyRole:
            guild = self.bot.get_guild(GUILD_ID)
            embed = Embed(title="❌ Missing permissions", description=f"You do not have the permissions to upload a mission file!\nThe permitted roles are: {', '.join([guild.get_role(role).name for role in (UNIT_STAFF, SERVER_HAMSTER, MISSION_BUILDER, CURATOR)])}.", color=Color.red())
            await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MissionUploader(bot))
