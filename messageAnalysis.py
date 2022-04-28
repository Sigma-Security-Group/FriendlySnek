import re
from discord import Embed, Colour
from constants import *
from __main__ import log, DEBUG

if DEBUG:
    from constants.debug import *

staffPings = {}

async def runMessageAnalysis(bot, message):
    # await staffPingAnalysis(bot, message)
    await analyzeChannel(bot, message, COMBAT_FOOTAGE, "video")
    await analyzeChannel(bot, message, PROPAGANDA, "image")

async def staffPingAnalysis(bot, message):
    staffRoles = STAFF_ROLES

    # Handle staff ping replies
    if message.reference is not None and message.reference.message_id in staffPings:
        unitStaffRole = message.guild.get_role(UNIT_STAFF)
        if unitStaffRole in message.author.roles:
            pingMessage, botMessage = staffPings[message.reference.message_id]
            log.debug(f"Staff replied to ping in message: {pingMessage.jump_url}")
            await botMessage.edit(content=f"{' '.join(role.mention for role in pingMessage.role_mentions if role.id in staffRoles)}: {pingMessage.jump_url}\nReplied by {message.author.display_name}: {message.jump_url}")
            del staffPings[message.reference.message_id]

    # Handle staff pings
    if any(role.id in staffRoles for role in message.role_mentions):
        log.debug(f"Staff Pinged\nMessage Link: {message.jump_url}\nMessage Author: {message.author.display_name}({message.author.name}#{message.author.discriminator})")
        botMessage = await bot.get_channel(STAFF_CHAT).send(f"{' '.join(role.mention for role in message.role_mentions if role.id in staffRoles)}: {message.jump_url}")
        staffPings[message.id] = (message, botMessage)

async def analyzeChannel(bot, message, channelID:int, attachmentContentType:str):
    if message.channel.id != channelID:
        return
    elif any(role.id == UNIT_STAFF for role in message.author.roles):
        return
    elif any(attachment.content_type.startswith(f"{attachmentContentType}/") for attachment in message.attachments):
        return
    elif attachmentContentType == "video" and re.search(VIDEO_URLS_REGEX, message.content):
        return
    try:
        await message.delete()
    except Exception:
        pass
    try:
        log.warning(f"Removing message in {bot.get_channel(channelID)} from {message.author}")
        devs = " and/or ".join([f"**{message.guild.get_member(name)}**" for name in DEVELOPERS if message.guild.get_member(name) is not None])
        await message.author.send(embed=Embed(title=ERROR_INVALID_MESSAGE, description=ANALYSIS_ILLEGAL_MESSAGE.format(channelID, attachmentContentType, devs), color=Colour.red()))
    except Exception as e:
        print(message.author, e)
    return
