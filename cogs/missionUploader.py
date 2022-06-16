import asyncio
import pytz
import secret
from datetime import datetime
import pysftp

from discord import app_commands, Embed, Color, utils
from discord.ext import commands

from constants import *
from __main__ import log, cogsReady
if secret.DEBUG:
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
        "Port": 8822
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
            embed = Embed(title="Which server would you like to upload to?", description="\n".join([f"{index}. {server['Name']}" for index, server in enumerate(SERVERS, start=1)]), color=color)
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
                elif serverNumber in [str(index[0]) for index in enumerate(SERVERS, start=1)]:
                    serverSelectOk = True
                    server = SERVERS[int(serverNumber) - 1]
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

        # Mission file
        color = Color.gold()
        attachmentOk = False
        while not attachmentOk:
            embed = Embed(title="Upload mission file", description="Please rename your mission file according to the naming convention, to make it easier for everyone!\n`YYYY-MM-DD-Operation-Name.Map.pbo`\nE.g. `2022-06-17-Operation-Honda-Civic.Altis.pbo`", color=color)
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
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

            sftp = None
            try:
                attachments = response.attachments
                if len(attachments) == 0:
                    embed = Embed(title="❌ You didn't upload a file. Please upload the mission file!", color=Color.red())
                    await dmChannel.send(embed=embed)
                    continue
                elif len(attachments) > 1:
                    embed = Embed(title="❌ You supplied too many files. Plese only upload one file!", color=Color.red())
                    await dmChannel.send(embed=embed)
                    continue

                attachment = attachments[0]
                if len(attachments) == 1 and not attachment.filename.endswith(".pbo"):
                    embed = Embed(title="❌ This is not a PBO file. Please upload a PBO file!", color=Color.red())
                    await dmChannel.send(embed=embed)
                    continue

                cnopts = pysftp.CnOpts()
                cnopts.hostkeys = None
                with pysftp.Connection(server["Host"], port=server["Port"], username=secret.FTP_USERNAME, password=secret.FTP_PASSWORD, cnopts=cnopts, default_path=server["Directory"]) as sftp:
                    missionFilesOnServer = [file.filename for file in sftp.listdir_attr()]

                    if len(attachments) == 1 and attachment.filename in missionFilesOnServer:
                        embed = Embed(title="❌ This file already exists. Please rename the file and reupload it!", color=Color.red())
                        await dmChannel.send(embed=embed)
                        continue

                    else:
                        attachmentOk = True

                    # Uploading
                    await dmChannel.send(embed=Embed(title="Uploading mission file...", description="Standby, this can take a minute...", color=Color.green()))

                    # Saving file locally
                    attachment = attachments[0]
                    filename = attachment.filename
                    with open(f"tmp/{filename}", "wb") as f:
                        await attachment.save(f)

                    if not secret.DEBUG:
                        try:
                            # Upload file from tmp
                            with open(f"tmp/{filename}", "rb") as f:
                                sftp.put(f"tmp/{filename}")
                        except Exception as e:
                            log.exception(f"{interaction.user} | {e}")

            except Exception as e:
                log.exception(f"{interaction.user} | {e}")
            finally:
                if sftp is not None:
                    sftp.close()


        utcTime = UTC.localize(datetime.utcnow())
        member = f"{interaction.user.display_name} ({interaction.user})"

        with open(MISSIONS_UPLOADED_FILE, "a") as f:
            f.write(f"\nFilename: {filename}\nServer: {server['Name']}\nUTC Time: {utcTime.strftime(TIME_FORMAT)}\nMember: {member}\nMember ID: {interaction.user.id}\n")

        embed = Embed(title="Uploaded mission file" + (" (Debug)" if secret.DEBUG else ""), color=Color.blue())
        embed.add_field(name="Filename", value=f"`{filename}`")
        embed.add_field(name="Server", value=f"`{server['Name']}`")
        embed.add_field(name="Time", value=utils.format_dt(pytz.timezone("UTC").localize(datetime.utcnow()).astimezone(UTC), style="F"))
        embed.add_field(name="Member", value=interaction.user.mention)
        embed.set_footer(text=f"Member ID: {interaction.user.id}")

        await self.bot.get_channel(BOT).send(embed=embed)  # Send the log message in the BOT channel

        log.info(f"{interaction.user.display_name} ({interaction.user}) uploaded the mission file {filename}!")
        if not secret.DEBUG:
            embed = Embed(title="✅ Mission file uploaded", color=Color.green())
        else:
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
