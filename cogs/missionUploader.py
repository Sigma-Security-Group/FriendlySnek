import os
import re
import json
import asyncio
from datetime import datetime
from dateutil.parser import parse as datetimeParse
import pytz
from ftplib import FTP

import discord
from discord import Embed
from discord import Colour
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_permission
from discord_slash.utils.manage_components import create_button, create_actionrow
from discord_slash.model import ButtonStyle, SlashCommandPermissionType

from constants import *

from __main__ import log, cogsReady, DEBUG, HOLD_UPDATE_FILE
if DEBUG:
    from constants.debug import *
import secret

TIMEOUT_EMBED = Embed(title="Time ran out. Try again. :anguished: ", color=Colour.red())
MISSIONS_UPLOADED_FILE = "data/missionsUploaded.log"
UPLOAD_TIME_FORMAT = "%Y-%m-%d %I:%M %p"
FTP_MISSIONS_DIR = "/144.48.106.194_2316/mpmissions"

class MissionUploader(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        log.debug("MissionUploader Cog is ready", flush=True)
        cogsReady["missionUploader"] = True
    
    async def checkAttachments(self, dmChannel, author, attachments):
        with FTP() as ftp:
            ftp.connect(host=secret.ftpHost, port=secret.ftpPort)
            ftp.login(user=secret.ftpUsername, passwd=secret.ftpPassword)
            ftp.cwd(FTP_MISSIONS_DIR)
            missionFilesOnServer = ftp.nlst()
        attachmentOk = False
        if len(attachments) == 0:
            embed = Embed(title="❌ You didn't upload any file. Please upload the mission file", color=Colour.red())
            await dmChannel.send(embed=embed)
        elif len(attachments) > 1:
            embed = Embed(title="❌ You supplied too many files. Plese upload only one file", color=Colour.red())
            await dmChannel.send(embed=embed)
        else:
            attachment = attachments[0]
            if not attachment.filename.endswith(".pbo"):
                embed = Embed(title="❌ This is not a pbo file. Please upload a pbo file", color=Colour.red())
                await dmChannel.send(embed=embed)
            elif attachment.filename in missionFilesOnServer:
                embed = Embed(title="❌ This file already exists. Please rename the file and reupload it", color=Colour.red())
                await dmChannel.send(embed=embed)
            else:
                attachmentOk = True
        return attachmentOk
    
    @cog_ext.cog_slash(name="uploadmission",
                       description="Upload a mission pbo file to the server.",
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
    async def uploadMission(self, ctx: SlashContext):
        if os.path.exists(HOLD_UPDATE_FILE):
            await ctx.send("Mission Upload comming soon")
            return
        await ctx.send("Upload mission file in DMs")
        
        embed = Embed(title="Upload the mission file you want to put on the server.", color=Colour.gold())
        msg = await ctx.author.send(embed=embed)
        dmChannel = msg.channel
        try:
            response = await self.bot.wait_for("message", timeout=120, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
            attachments = response.attachments
            attachmentOk = await self.checkAttachments(dmChannel, ctx.author, attachments)
        except asyncio.TimeoutError:
            await dmChannel.send(embed=TIMEOUT_EMBED)
            return
        while not attachmentOk:
            try:
                response = await self.bot.wait_for("message", timeout=120, check=lambda msg, ctx=ctx, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == ctx.author)
                attachments = response.attachments
                attachmentOk = await self.checkAttachments(dmChannel, ctx.author, attachments)
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return
        attachment = attachments[0]
        
        embed = Embed(title="Uploading mission file...", color=Colour.green())
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
        utcTime = datetime.utcnow().strftime(UPLOAD_TIME_FORMAT)
        member = f"{ctx.author.display_name}({ctx.author.name}#{ctx.author.discriminator})"
        memberId = ctx.author.id
        
        with open(MISSIONS_UPLOADED_FILE, "a") as f:
            f.write(f"\nFilename: {filename}\nUTC Time: {utcTime}\nMember: {member}\nMember ID: {memberId}\n")
        
        botLogChannel = self.bot.get_channel(BOT)
        embed = Embed(title="Mission file uploaded", color=Colour.blue())
        embed.add_field(name="Filename", value=filename)
        embed.add_field(name="UTC Time", value=utcTime)
        embed.add_field(name="Member", value=member)
        embed.add_field(name="Member ID", value=memberId)
        await botLogChannel.send(embed=embed)
        
        embed = Embed(title="Mission file uploaded", color=Colour.green())
        await dmChannel.send(embed=embed)

def setup(bot):
    bot.add_cog(MissionUploader(bot))