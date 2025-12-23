import os, contextlib, secret, discord, logging
import paramiko, pytz  # type: ignore

from datetime import datetime, timezone
from discord.ext import commands  # type: ignore

from utils import Utils
from constants import *
if secret.DEBUG:
    from constants.debug import *

MISSIONS_UPLOADED_FILE = "data/missionsUploaded.log"
UTC = pytz.utc

log = logging.getLogger("FriendlySnek")

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
        log.debug(LOG_COG_READY.format("MissionUploader"))
        self.bot.cogsReady["missionUploader"] = True

    @discord.app_commands.command(name="uploadmission")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.describe(
        missionfile="Missionfile to upload. Naming: 'YYYY_MM_DD_Operation_Name_V1.Map.pbo'",
        server="Which server to upload to?"
    )
    @discord.app_commands.choices(server = [discord.app_commands.Choice(name=srv["name"], value=host) for host, srv in secret.SFTP.items()])
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_UPLOADMISSION)
    async def uploadMission(self, interaction: discord.Interaction, missionfile: discord.Attachment, server: discord.app_commands.Choice[str]) -> None:
        """Upload a mission PBO file to the server."""

        log.debug(f"{interaction.user.id} [{interaction.user.display_name}] Is uploading a mission file")

        # Only allow .pbo files
        if not missionfile.filename.endswith(".pbo"):
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid file type", description="This is not a PBO file. Please upload a PBO file!", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
            return

        # Cap file size to ~25 MB
        if missionfile.size > 26_250_000:
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid filesize", description="Max allowed filesize is 25 MB!", color=discord.Color.red()), ephemeral=True, delete_after=30.0)
            return

        await interaction.response.send_message(embed=discord.Embed(title="Uploading mission file...", description="Standby, this can take a minute...", color=discord.Color.green()))

        sftp = None
        timeout = 10 # seconds
        try:
            transport = paramiko.Transport((server.value, secret.SFTP[server.value]["port"]))
            transport.sock.settimeout(timeout)
            transport.connect(
                username=secret.SFTP[server.value]["username"],
                password=secret.SFTP[server.value]["password"]
            )
            sftp = paramiko.SFTPClient.from_transport(transport)
            if sftp is None:
                raise Exception("missionUploader uploadMission: sftp is None after connection")

            # Change remote directory if defined
            if secret.SFTP[server.value]["directory"]:
                sftp.chdir(secret.SFTP[server.value]["directory"])

            missionFilesOnServer = [attr.filename for attr in sftp.listdir_attr()]
            if missionfile.filename in missionFilesOnServer:
                await interaction.edit_original_response(embed=discord.Embed(
                    title="❌ Invalid filename",
                    description=f"This file already exists. Please rename the file and reupload it!\nFilename: `{missionfile.filename}`",
                    color=discord.Color.red()
                ))
                return

            # Save file locally
            filepath = f"tmp/missionUpload/{missionfile.filename}"
            with open(filepath, "wb") as f:
                await missionfile.save(f)

            if not secret.DEBUG:
                try:
                    # Upload file
                    sftp.put(filepath, missionfile.filename)
                except Exception:
                    log.exception(f"{interaction.user.id} [{interaction.user.display_name}] Failed to put mission file on server")

        except Exception as e:
            log.exception(f"{interaction.user.id} [{interaction.user.display_name}] Failed to upload mission file")
            await interaction.edit_original_response(embed=discord.Embed(
                title="❌ Connection error",
                description=f"There was an error connecting to the server. Please try again later!\n```\n{e}\n```",
                color=discord.Color.red()
            ))
            return

        finally:
            with contextlib.suppress(Exception):
                if sftp is not None:
                    sftp.close()
                if "transport" in locals():
                    transport.close()


        # Cleanup
        try:
            os.remove(f"tmp/missionUpload/{missionfile.filename}")
        except Exception as e:
            log.exception("MissionUploader uploadMission: Failed to delete mission file after upload")

        # Log the upload
        with open(MISSIONS_UPLOADED_FILE, "a") as f:
            f.write(f"\nFilename: {missionfile.filename}\n"
                f"Server: {secret.SFTP[server.value]['name']}\n"
                f"UTC Time: {datetime.now(timezone.utc).strftime(TIME_FORMAT)}\n"
                f"Member: {interaction.user.display_name} ({interaction.user})\n"
                f"Member ID: {interaction.user.id}\n"
            )

        if secret.DISCORD_LOGGING.get("upload_mission_file", False):
            embed = discord.Embed(title="Uploaded mission file" + (" (Debug)" if secret.DEBUG else ""), color=discord.Color.blue())
            embed.add_field(name="Filename", value=f"`{missionfile.filename}`")
            embed.add_field(name="Size", value=f"`{convertBytes(missionfile.size)}`")
            embed.add_field(name="Server", value=f"`{secret.SFTP[server.value]['name']}`")
            embed.add_field(name="Time", value=discord.utils.format_dt(datetime.now(timezone.utc), style="F"))
            embed.add_field(name="Member", value=interaction.user.mention)
            embed.set_footer(text=f"Member ID: {interaction.user.id}")

            # Send the log message in the Audit Logs channel
            channelAuditLogs = self.bot.get_channel(AUDIT_LOGS)
            if not isinstance(channelAuditLogs, discord.TextChannel):
                log.exception("MissionUploader uploadMission: channelAuditLogs not discord.TextChannel")
                return

            await channelAuditLogs.send(embed=embed)

        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Uploaded the mission file '{missionfile.filename}'" + (" (DEBUG)"*secret.DEBUG))
        await interaction.edit_original_response(content=f"Mission file successfully uploaded: `{missionfile.filename}`" + (" (DEBUG)"*secret.DEBUG), embed=None)


async def setup(bot: commands.Bot) -> None:
    MissionUploader.uploadMission.error(Utils.onSlashError)
    await bot.add_cog(MissionUploader(bot))
