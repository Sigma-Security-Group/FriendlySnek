from constants import *

from __main__ import log, DEBUG

staffPings = {}

async def runMessageAnalysis(bot, message):
    pass
    # await staffPingAnalysis(bot, message)

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