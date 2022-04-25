from logger import Logger
log = Logger()

import os
# Define whether to use Sigma server or APS (debug) server
DEBUG = os.path.exists("DEBUG")
# DEBUG = True  # always use debug server during development

import asyncio

# Set appropriate event loop policy to avoid runtime errors on windows
import platform
if platform.system() == "Windows":
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytz
from glob import glob
# from apscheduler.schedulers.asyncio import AsyncIOScheduler

import discord
from discord.ext import commands
from discord_slash import SlashCommand

from constants import *
if DEBUG:
    from constants.debug import *
from messageAnalysis import runMessageAnalysis
import secret

if not os.path.exists("./data"):
    os.mkdir("data")

COGS = [os.path.basename(path)[:-3] for path in glob("cogs/*.py")]
cogsReady = {cog: False for cog in COGS}

intents = discord.Intents.all()
bot = commands.Bot(COMMAND_PREFIX, intents=intents)
bot.ready = False
slash = SlashCommand(bot, override_type=True, sync_commands=True, sync_on_cog_reload=True)
for cog in COGS:
    bot.load_extension(f"cogs.{cog}")

UTC = pytz.utc
newcomers = set()

@bot.event
async def on_ready():
    # if bot.ready:
    #     return
    while not all(cogsReady.values()):
        await asyncio.sleep(1)
    bot.ready = True
    log.info(LOG_BOT_READY)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="you"))  # 🐍

@bot.event
async def on_message(message):
    # Ignore messages from itself
    if message.author.id == FRIENDLY_SNEK:
        return
    if DEBUG and message.author.id in FRIENDLY_SNEKS:
        return

    # Ignore messages that were not sent on the correct server
    if message.guild is None or message.guild.id != SERVER:
        # log.warning("Wrong server")
        return

    # Execute commands
    if message.content.startswith(COMMAND_PREFIX) or message.content.startswith("/"):
        log.debug(f"{message.author.display_name} ({message.author.name}#{message.author.discriminator}) > {message.content}")
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
    await asyncio.sleep(24 * 60 * 60)  # Seconds
    if member.id not in newcomers:
        log.debug(f"Newcomer is no longer in the server {member.display_name} ({member.name}#{member.discriminator})")
        return
    currentMembers = await guild.fetch_members().flatten()
    if member in currentMembers:
        updatedMember = await guild.fetch_member(member.id)
        if len(updatedMember.roles) < 2:
            unitStaffRole = guild.get_role(UNIT_STAFF)
            log.debug(f"Sending ping reminder to {updatedMember.display_name} ({updatedMember.name}#{updatedMember.discriminator})")
            await bot.get_channel(WELCOME).send(f"{updatedMember.mention} Don't forget to ping {unitStaffRole.name} when you are ready.")
        else:
            log.debug(f"Newcomer is no longer in need of an interview {updatedMember.display_name} ({updatedMember.name}#{updatedMember.discriminator})")
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
    log.exception(LOG_ERROR)

@bot.event
async def on_command_error(ctx, error):
    log.error(error)

@bot.command(hidden=True, help="Reload bot (Dev only)")
async def reload(ctx):
    if ctx.author.id != ADRIAN and ctx.author.id != FROGGI:
        return
    for cog in COGS:
        bot.reload_extension(f"cogs.{cog}")
    await ctx.send(MAIN_RELOAD_RESPONSE)

if __name__ == "__main__":
    try:
        bot.run(secret.tokenDev if DEBUG else secret.token)
        log.info(LOG_BOT_STOPPED)
    except Exception:
        log.exception(LOG_ERROR)
