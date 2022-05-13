import asyncio
from datetime import datetime
import pytz
from ftplib import FTP

from discord import Embed, Colour
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_permission
from discord_slash.model import SlashCommandPermissionType

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *
import secret

TIMEOUT_EMBED = Embed(title=ERROR_TIMEOUT, color=Colour.red())
MISSIONS_UPLOADED_FILE = "data/missionsUploaded.log"
UPLOAD_TIME_FORMAT = "%Y-%m-%d %I:%M %p"
# FTP_MISSIONS_DIR = "/144.48.106.194_2316/mpmissions"  # Host Havoc
FTP_MISSIONS_DIR = "/euc-ogs7.armahosts.com_2482/mpmissions"  # Dwarf's server
#FTP_MISSIONS_DIR_TEST = "/euc-ogs11.armahosts.com_8821/mpmissions"  # Dwarf's server TEST

UTC = pytz.utc

class MissionUploader(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("MissionUploader"), flush=True)
        cogsReady["missionUploader"] = True

    async def checkAttachments(self, dmChannel, attachments):
        with FTP() as ftp:
            ftp.connect(host=secret.ftpHost, port=secret.ftpPort)
            ftp.login(user=secret.ftpUsername, passwd=secret.ftpPassword)
            ftp.cwd(FTP_MISSIONS_DIR)
            missionFilesOnServer = ftp.nlst()
        attachmentOk = False
        if len(attachments) == 0:
            embed = Embed(title=MISSION_UPLOAD_ERROR_NO_FILE, color=Colour.red())
            await dmChannel.send(embed=embed)
        elif len(attachments) > 1:
            embed = Embed(title=MISSION_UPLOAD_ERROR_TOO_MANY_FILES, color=Colour.red())
            await dmChannel.send(embed=embed)
        else:
            attachment = attachments[0]
            if not attachment.filename.endswith(".pbo"):
                embed = Embed(title=MISSION_UPLOAD_ERROR_NO_PBO, color=Colour.red())
                await dmChannel.send(embed=embed)
            elif attachment.filename in missionFilesOnServer:
                embed = Embed(title=MISSION_UPLOAD_ERROR_DUPLICATE, color=Colour.red())
                await dmChannel.send(embed=embed)
            else:
                attachmentOk = True
        return attachmentOk

    @cog_ext.cog_slash(name="uploadmission",
                       description=MISSION_UPLOAD_COMMAND_DESCRIPTION,
                       guild_ids=[SERVER],
                       permissions={
                           SERVER: [
                               create_permission(EVERYONE, SlashCommandPermissionType.ROLE, False),
                               create_permission(UNIT_STAFF, SlashCommandPermissionType.ROLE, True),
                               create_permission(SERVER_HAMSTER, SlashCommandPermissionType.ROLE, True),
                               create_permission(MISSION_BUILDER, SlashCommandPermissionType.ROLE, True),
                               create_permission(CURATOR, SlashCommandPermissionType.ROLE, True)
                           ]
                       })
    async def uploadMission(self, ctx: SlashContext) -> None:
        await ctx.send(MISSION_UPLOAD_RESPONSE)
        log.info(MISSION_UPLOAD_LOG_UPLOADING.format(ctx.author.display_name, ctx.author.name, ctx.author.discriminator))

        embed = Embed(title=MISSION_UPLOAD_PROMPT, color=Colour.gold())
        msg = await ctx.author.send(embed=embed)
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=120, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            attachments = response.attachments
            attachmentOk = await self.checkAttachments(dmChannel, attachments)
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        while not attachmentOk:
            try:
                response = await self.bot.wait_for("message", timeout=120, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                attachments = response.attachments
                attachmentOk = await self.checkAttachments(dmChannel, attachments)
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        attachment = attachments[0]

        embed = Embed(title=MISSION_UPLOAD_UPLOADING, color=Colour.green())
        await dmChannel.send(embed=embed)

        with open(f"tmp/{attachment.filename}", "wb") as f:
            await attachment.save(f)

        with FTP() as ftp:
            ftp.connect(host=secret.ftpHost, port=secret.ftpPort)
            ftp.login(user=secret.ftpUsername, passwd=secret.ftpPassword)
            ftp.cwd(FTP_MISSIONS_DIR)
            if not DEBUG:
                with open(f"tmp/{attachment.filename}", "rb") as f:
                    ftp.storbinary(f"STOR {attachment.filename}", f)

        filename = attachment.filename
        utcTime = UTC.localize(datetime.utcnow())
        member = f"{ctx.author.display_name}({ctx.author.name}#{ctx.author.discriminator})"
        memberId = ctx.author.id

        with open(MISSIONS_UPLOADED_FILE, "a") as f:
            f.write(f"\nFilename: {filename}\nUTC Time: {utcTime.strftime(UPLOAD_TIME_FORMAT)}\nMember: {member}\nMember ID: {memberId}\n")

        botLogChannel = self.bot.get_channel(BOT)
        embed = Embed(title=MISSION_UPLOAD_UPLOADED, color=Colour.blue())
        embed.add_field(name="Filename", value=filename)
        embed.add_field(name="Time", value=f"<t:{round(utcTime.timestamp())}:F>")
        embed.add_field(name="Member", value=member)
        embed.add_field(name="Member ID", value=memberId)
        await botLogChannel.send(embed=embed)

        log.info(MISSION_UPLOAD_LOG_UPLOADED.format(ctx.author.display_name, ctx.author.name, ctx.author.discriminator))
        embed = Embed(title=MISSION_UPLOAD_UPLOADED, color=Colour.green())
        await dmChannel.send(embed=embed)

def setup(bot) -> None:
    bot.add_cog(MissionUploader(bot))
