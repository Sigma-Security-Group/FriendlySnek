from logger import Logger
log = Logger()

import os
# Define whether to use Sigma server or APS (debug) server
DEBUG = os.path.exists("DEBUG")
# DEBUG = True  # always use debug server during development

import asyncio

# Set appropriate event loop policy to avoid runtime errors on windows
import platform
if platform.system() == 'Windows':
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import json
import pytz
from glob import glob
from datetime import datetime
# from apscheduler.schedulers.asyncio import AsyncIOScheduler

import discord
from discord.ext import commands, tasks
from discord_slash import SlashCommand

from constants import *
if DEBUG:
    from constants.debug import *
from messageAnalysis import runMessageAnalysis
import secret

COMMAND_PREFIX = "-"
COGS = [os.path.basename(path)[:-3] for path in glob("cogs/*.py")]
cogsReady = {cog: False for cog in COGS}

intents = discord.Intents.all()
bot = commands.Bot(COMMAND_PREFIX, intents=intents)
bot.ready = False
slash = SlashCommand(bot, override_type=True, sync_commands=True, sync_on_cog_reload=True)
for cog in COGS:
    bot.load_extension(f"cogs.{cog}")

MESSAGES_FILE = "data/messagesLog.json"
FULL_ACTIVITY_FILE = "data/fullActivityLog.json"
ACTIVITY_FILE = "data/activityLog.json"
MEMBERS_FILE = "data/members.json"

UTC = pytz.utc

newcomers = set()

# @tasks.loop(minutes=10)
# async def logActivity():
#     while not bot.ready:
#         await asyncio.sleep(1)
#     log.debug("Logging discord activity")
#     now = UTC.localize(datetime.utcnow()).strftime("%Y-%m-%d %I:%M %p")

#     with open(MESSAGES_FILE) as f:
#         messages = json.load(f)
#     with open(MESSAGES_FILE, "w") as f:
#         json.dump([], f, indent=4)

#     with open(FULL_ACTIVITY_FILE) as f:
#         fullActivity = json.load(f)
#     guild = bot.get_guild(SERVER)
#     online = [(member.id, member.display_name, any(role.id == UNIT_STAFF for role in member.roles)) for member in guild.members if member.status != discord.Status.offline]
#     inVoiceChannel = [{"channelId": channel.id, "channelName": channel.name, "members": [(member.id, member.display_name) for member in channel.members]} for channel in guild.voice_channels]
#     fullActivity[now] = {"messages": messages, "online": online, "inVoiceChannel": inVoiceChannel}
#     with open(FULL_ACTIVITY_FILE, "w") as f:
#         json.dump(fullActivity, f, indent=4)

#     with open(MEMBERS_FILE) as f:
#         members = json.load(f)
#     members.update({str(member.id): member.display_name for member in guild.members})
#     with open(MEMBERS_FILE, "w") as f:
#         json.dump(members, f, indent=4)

#     with open(ACTIVITY_FILE) as f:
#         activity = json.load(f)
#     online = len([member for member in guild.members if member.status != discord.Status.offline])
#     staffOnline = len([member for member in guild.members if member.status != discord.Status.offline and any(role.id == UNIT_STAFF for role in member.roles)])
#     messagesPerChannel = {}
#     for message in messages:
#         if message["channelName"] not in messagesPerChannel:
#             messagesPerChannel[message["channelName"]] = 0
#         messagesPerChannel[message["channelName"]] += 1
#     voiceChannels = {
#         "Bar and Mess Hall": len([member for channel in guild.voice_channels for member in channel.members if channel.id in (THE_BAR, MESS_HALL)]),
#         "Game Rooms": len([member for channel in guild.voice_channels for member in channel.members if channel.id in (GAME_ROOM_ONE, GAME_ROOM_TWO, GAME_ROOM_THREE)]),
#         "Command": len([member for channel in guild.voice_channels for member in channel.members if channel.id == COMMAND]),
#         "Deployed": len([member for channel in guild.voice_channels for member in channel.members if channel.id == DEPLOYED])
#     }
#     activity[now] = {"online": online, "staffOnline": staffOnline, "messages": messagesPerChannel, "voiceChannels": voiceChannels}
#     with open(ACTIVITY_FILE, "w") as f:
#         json.dump(activity, f, indent=4)

# activityMonitorScheduler = AsyncIOScheduler()
# activityMonitorScheduler.add_job(logActivity, "interval", minutes=10)

@bot.event
async def on_ready():
    # if bot.ready:
    #     return
    while not all(cogsReady.values()):
        await asyncio.sleep(1)
    bot.ready = True
    log.info("Bot Ready")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="you"))  # 🐍
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, "w") as f:
            json.dump([], f, indent=4)
    if not os.path.exists(FULL_ACTIVITY_FILE):
        with open(FULL_ACTIVITY_FILE, "w") as f:
            json.dump({}, f, indent=4)
    if not os.path.exists(MEMBERS_FILE):
        with open(MEMBERS_FILE, "w") as f:
            json.dump({}, f, indent=4)
    if not os.path.exists(ACTIVITY_FILE):
        with open(FULL_ACTIVITY_FILE) as f:
            fullActivity = json.load(f)
        activity = {}
        for t, act in fullActivity.items():
            online = len([member for member in act["online"]])
            staffOnline = len([member for member in act["online"] if member[2]])
            messagesPerChannel = {}
            for message in act["messages"]:
                if message["channelName"] not in messagesPerChannel:
                    messagesPerChannel[message["channelName"]] = 0
                messagesPerChannel[message["channelName"]] += 1
            voiceChannels = {
                "Bar and Mess Hall": len([member for channel in act["inVoiceChannel"] for member in channel["members"] if channel["channelId"] in (THE_BAR, MESS_HALL)]),
                "Game Rooms": len([member for channel in act["inVoiceChannel"] for member in channel["members"] if channel["channelId"] in (GAME_ROOM_ONE, GAME_ROOM_TWO, GAME_ROOM_THREE)]),
                "Command": len([member for channel in act["inVoiceChannel"] for member in channel["members"] if channel["channelId"] == COMMAND]),
                "Deployed": len([member for channel in act["inVoiceChannel"] for member in channel["members"] if channel["channelId"] == DEPLOYED])
            }
            activity[t] = {"online": online, "staffOnline": staffOnline, "messages": messagesPerChannel, "voiceChannels": voiceChannels}
        with open(ACTIVITY_FILE, "w") as f:
            json.dump(activity, f, indent=4)
    # if not activityMonitorScheduler.running:
    #     activityMonitorScheduler.start()
    # try:
    #     logActivity.start()
    # except:
    #     log.warning("Couldn't start logActivity scheduler")

@bot.event
async def on_message(message):
    # Ignore messages from itself
    if message.author.id == FRIENDLY_SNEK:
        return
    if DEBUG and message.author.id == FRIENDLY_SNEK_DEV:
        return

    # Ignore messages that were not sent on the correct server
    if message.guild is None or message.guild.id != SERVER:
        # log.warning("Wrong server")
        return

    if not message.author.bot:
        with open(MESSAGES_FILE) as f:
            messages = json.load(f)
        messages.append({"authorId": message.author.id, "authorName": message.author.display_name, "channelId": message.channel.id, "channelName": message.channel.name})
        with open(MESSAGES_FILE, "w") as f:
            json.dump(messages, f, indent=4)

    # Execute commands
    if message.content.startswith(COMMAND_PREFIX) or message.content.startswith("/"):
        log.debug(f"{message.author.display_name}({message.author.name}#{message.author.discriminator}) > {message.content}")
        await bot.process_commands(message)

    # Unmark newcomer pinging unit staff as needing a reminder to ping unit staff
    if message.author.id in newcomers:
        unitStaffRole = message.guild.get_role(UNIT_STAFF)
        if unitStaffRole in message.role_mentions:
            newcomers.remove(message.author.id)

    # Run message content analysis
    await runMessageAnalysis(bot, message)

@bot.event
async def on_member_join(member):
    guild = member.guild
    if guild.id != SERVER:
        # log.debug("Member joined on another server")
        return
    newcomers.add(member.id)
    log.debug("Member joined")
    await asyncio.sleep(24 * 60 * 60)  # seconds
    if member.id not in newcomers:
        log.debug(f"Newcomer is no longer in the server {member.display_name}({member.name}#{member.discriminator})")
        return
    currentMembers = await guild.fetch_members().flatten()
    if member in currentMembers:
        updatedMember = await guild.fetch_member(member.id)
        if len(updatedMember.roles) < 2:
            unitStaffRole = guild.get_role(UNIT_STAFF)
            log.debug(f"Sending ping reminder to {updatedMember.display_name}({updatedMember.name}#{updatedMember.discriminator})")
            await bot.get_channel(WELCOME).send(f"{updatedMember.mention} Don't forget to ping {unitStaffRole.name} when you are ready.")
        else:
            log.debug(f"Newcomer is no longer in need of an interview {updatedMember.display_name}({updatedMember.name}#{updatedMember.discriminator})")
    else:
        log.debug(f"Newcomer is no longer in the server {member.display_name}({member.name}#{member.discriminator})")
    if member.id in newcomers:
        newcomers.remove(member.id)

@bot.event
async def on_member_leave(member):
    if member.id in newcomers:
        newcomers.remove(member.id)
        log.debug(f"Newcomer left {member.display_name}({member.name}#{member.discriminator})")

@bot.event
async def on_error(event, *args, **kwargs):
    log.exception("An error occured")

@bot.event
async def on_command_error(ctx, error):
    log.error(error)

@bot.command(hidden=True, help="Reload bot (Dev only)")
async def reload(ctx):
    if ctx.author.id != ADRIAN:
        return
    for cog in COGS:
        bot.reload_extension(f"cogs.{cog}")
    await ctx.send("Reloaded")

if __name__ == "__main__":
    try:
        bot.run(secret.tokenDev if DEBUG else secret.token)
        log.info("Bot stopped")
    except Exception:
        log.exception("An error occured")
