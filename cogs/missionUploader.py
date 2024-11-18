import os
import contextlib
import secret
import discord
import pysftp, pytz  # type: ignore

from datetime import datetime, timezone
from discord.ext import commands  # type: ignore

from logger import Logger
from constants import *
from __main__ import cogsReady
if secret.DEBUG:
    from constants.debug import *


MISSIONS_UPLOADED_FILE = "data/missionsUploaded.log"
UTC = pytz.utc

SERVERS = [
    {
        "Name": "SSG - Operations Server",
        "Directory": "148.251.192.96_2322/mpmissions",
        "Host": "148.251.192.96",
        "Port": 8822
    },
    {
        "Name": "SSG - Event Server",
        "Directory": "38.133.154.95_2322/mpmissions",
        "Host": "38.133.154.95",
        "Port": 8822
    }
]

def convertBytes(size: int):
    for unit in ["bytes", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f'{size:.1f} {unit}'
        size /= 1024.0

class MissionUploader(commands.Cog):
    """Mission uploader cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        Logger.debug(LOG_COG_READY.format("MissionUploader"), flush=True)
        cogsReady["missionUploader"] = True

    @discord.app_commands.command(name="uploadmission")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.describe(
        missionfile="Missionfile to upload. Naming: 'YYYY_MM_DD_Operation_Name.Map.pbo'",
        server="Which server to upload to?"
    )
    @discord.app_commands.choices(server = [discord.app_commands.Choice(name=srv["Name"], value=srv["Host"]) for srv in SERVERS])
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_UPLOADMISSION)
    async def uploadMission(self, interaction: discord.Interaction, missionfile: discord.Attachment, server: discord.app_commands.Choice[str]) -> None:
        """Upload a mission PBO file to the server."""

        # await interaction.response.send_message("Mission uploading is temporarily disabled. Please contact Unit Staff or Server Hampters for assistance.", ephemeral=True, delete_after=30.0)
        # Logger.debug(f"{interaction.user.display_name} ({interaction.user}) attempted to upload a mission file while upload was disabled.")
        # return

        Logger.debug(f"{interaction.user.display_name} ({interaction.user}) is uploading a mission file...")

        # Only allow .pbo files
        if not missionfile.filename.endswith(".pbo"):
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid file type", description="This is not a PBO file. Please upload a PBO file!", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
            return

        # Cap file size to ~25 MB
        if missionfile.size > 26_250_000:
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid filesize", description="Max allowed filesize is 25 MB!", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
            return

        await interaction.response.send_message(embed=discord.Embed(title="Uploading mission file...", description="Standby, this can take a minute...", color=discord.Color.green()))
        serverDict = [srv for srv in SERVERS if srv["Host"] == server.value][0]
        sftp = None
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None

        try:
            with pysftp.Connection(serverDict["Host"], port=serverDict["Port"], username=secret.SFTP[serverDict["Host"]]["username"], password=secret.SFTP[serverDict["Host"]]["password"], cnopts=cnopts, default_path=serverDict["Directory"]) as sftp:
                missionFilesOnServer = [file.filename for file in sftp.listdir_attr()]
                if missionfile.filename in missionFilesOnServer:
                    await interaction.edit_original_response(embed=discord.Embed(title="❌ Invalid filename", description=f"This file already exists. Please rename the file and reupload it!\nFilename: `{missionfile.filename}`", color=discord.Color.red()))
                    return

                # Saving file locally
                with open(f"tmp/missionUpload/{missionfile.filename}", "wb") as f:
                    await missionfile.save(f)

                if not secret.DEBUG:
                    try:
                        # Upload file from tmp
                        with open(f"tmp/missionUpload/{missionfile.filename}", "rb") as f:
                            sftp.put(f"tmp/missionUpload/{missionfile.filename}")
                    except Exception as e:
                        Logger.exception(f"{interaction.user} | {e}")
        except Exception as e:
            Logger.exception(f"{interaction.user} | {e}")
            await interaction.response.send_message(embed=discord.Embed(title="❌ Connection error", description="There was an error connecting to the server. Please try again later!", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
            return

        finally:
            with contextlib.suppress(Exception):
                if sftp is not None:
                    sftp.close()

        try:
            os.remove(f"tmp/missionUpload/{missionfile.filename}")
        except Exception as e:
            Logger.exception("missionUploader uploadMission: Could not delete mission file after upload.")

        with open(MISSIONS_UPLOADED_FILE, "a") as f:
            f.write(f"\nFilename: {missionfile.filename}\n"
                f"Server: {serverDict['Name']}\n"
                f"UTC Time: {datetime.now(timezone.utc).strftime(TIME_FORMAT)}\n"
                f"Member: {interaction.user.display_name} ({interaction.user})\n"
                f"Member ID: {interaction.user.id}\n"
            )

        if secret.DISCORD_LOGGING.get("upload_mission_file", False):
            embed = discord.Embed(title="Uploaded mission file" + (" (Debug)" if secret.DEBUG else ""), color=discord.Color.blue())
            embed.add_field(name="Filename", value=f"`{missionfile.filename}`")
            embed.add_field(name="Size", value=f"`{convertBytes(missionfile.size)}`")
            embed.add_field(name="Server", value=f"`{serverDict['Name']}`")
            embed.add_field(name="Time", value=discord.utils.format_dt(datetime.now(timezone.utc), style="F"))
            embed.add_field(name="Member", value=interaction.user.mention)
            embed.set_footer(text=f"Member ID: {interaction.user.id}")

            # Send the log message in the Audit Logs channel
            channelAuditLogs = self.bot.get_channel(AUDIT_LOGS)
            if not isinstance(channelAuditLogs, discord.TextChannel):
                Logger.exception("UploadMission: channelAuditLogs is not discord.TextChannel")
                return

            await channelAuditLogs.send(embed=embed)

        Logger.info(f"{interaction.user.display_name} ({interaction.user}) uploaded the mission file: {missionfile.filename}!")
        await interaction.edit_original_response(content=f"Mission file successfully uploaded: `{missionfile.filename}`" + (" (DEBUG)"*secret.DEBUG), embed=None)


    @uploadMission.error
    async def onUploadMissionError(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        """uploadMission errors - dedicated for the discord.app_commands.errors.MissingAnyRole error."""
        if type(error) == discord.app_commands.errors.MissingAnyRole:
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                Logger.exception("onUploadMissionError: guild is None")
                return

            embed = discord.Embed(title="❌ Missing permissions", description=f"You do not have the permissions to upload a mission file!\nThe permitted roles are: {', '.join([role.name for allowedRole in CMD_LIMIT_UPLOADMISSION if (role := guild.get_role(allowedRole)) is not None])}.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)
            return
        Logger.exception(error)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MissionUploader(bot))
