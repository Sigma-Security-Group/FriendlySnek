import secret, asyncio
import pysftp, pytz  # type: ignore

from datetime import datetime
from discord import Embed, Color
from discord.ext import commands  # type: ignore

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
        "Directory": "euc-ogs7.armahosts.com_2482/mpmissions",
        "Host": "euc-ogs7.armahosts.com",
        "Port": 8822
    }
]
server = SERVERS[0]

class MissionUploader(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("MissionUploader"), flush=True)
        cogsReady["missionUploader"] = True

    @discord.app_commands.command(name="uploadmission")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(UNIT_STAFF, SERVER_HAMSTER, MISSION_BUILDER, CURATOR)
    async def uploadMission(self, interaction: discord.Interaction) -> None:
        """ Upload a mission PBO file to the server.

        Parameters:
        interaction (discord.Interaction): The Discor interaction.

        Returns:
        None.
        """
        await interaction.response.send_message("Upload mission file in DMs...")
        log.debug(f"{interaction.user.display_name} ({interaction.user}) is uploading a mission file...")

        # Mission file
        color = Color.gold()
        attachmentOk = False
        while not attachmentOk:
            embed = Embed(title="Upload mission file", description="Please rename your mission file according to the naming convention, to make it easier for everyone!\n`YYYY_MM_DD_Operation_Name.Map.pbo`\nE.g. `2022_06_17_Operation_Honda_Civic.Altis.pbo`", color=color)
            embed.set_footer(text=SCHEDULE_CANCEL)
            color = Color.red()
            msg = await interaction.user.send(embed=embed)
            dmChannel = msg.channel

            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, interaction=interaction, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == interaction.user)
                file = response.content.strip().lower()
                if file.lower() == "cancel":
                    await dmChannel.send(embed=Embed(title=f"❌ Mission uploading canceled!", color=Color.red()))
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
                with pysftp.Connection(server["Host"], port=server["Port"], username=secret.SFTP["username"], password=secret.SFTP["password"], cnopts=cnopts, default_path=server["Directory"]) as sftp:
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
        embed.add_field(name="Time", value=discord.utils.format_dt(pytz.timezone("UTC").localize(datetime.utcnow()).astimezone(UTC), style="F"))
        embed.add_field(name="Member", value=interaction.user.mention)
        embed.set_footer(text=f"Member ID: {interaction.user.id}")

        # Send the log message in the Bot channel
        botChannel = self.bot.get_channel(BOT)
        if not isinstance(botChannel, discord.channel.TextChannel):
            log.exception("UploadMission: botChanel is not discord.channel.TextChannel")
            return

        await botChannel.send(embed=embed)

        log.info(f"{interaction.user.display_name} ({interaction.user}) uploaded the mission file: {filename}!")
        if not secret.DEBUG:
            embed = Embed(title="✅ Mission file uploaded", color=Color.green())
        else:
            embed = Embed(title="Mission file uploaded", description="Actually... The file did not actually upload hehe.\nBot has debug mode enabled!", color=Color.orange())
        await dmChannel.send(embed=embed)

    @uploadMission.error
    async def onUploadMissionError(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        """ uploadMission errors - dedicated for the discord.app_commands.errors.MissingAnyRole error.

        Parameters:
        interaction (discord.Interaction): The Discor interaction.
        error (discord.app_commands.AppCommandError): The end user error.

        Returns:
        None.
        """
        if type(error) == discord.app_commands.errors.MissingAnyRole:
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("onUploadMissionError: guild is None")
                return

            embed = Embed(title="❌ Missing permissions", description=f"You do not have the permissions to upload a mission file!\nThe permitted roles are: {', '.join([role.name for allowedRole in (UNIT_STAFF, SERVER_HAMSTER, MISSION_BUILDER, CURATOR) if (role := guild.get_role(allowedRole)) is not None])}.", color=Color.red())
            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MissionUploader(bot))
