from logger import Logger
log = Logger()

import os
# Define whether to use Sigma server or APS (debug) server
DEBUG = os.path.exists("DEBUG")
DEBUG = True  # always use debug server during development

import asyncio

# Set appropriate event loop policy to avoid runtime errors on windows
import platform
if platform.system() == 'Windows':
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pickle
from glob import glob
import discord
from discord.ext import commands

from constants import *
if DEBUG:
    from contants.debug import *
from messageAnalysis import runMessageAnalysis

COMMAND_PREFIX = "-"
COGS = [os.path.basename(path)[:-3] for path in glob("cogs/*.py")]
cogsReady = {cog: False for cog in COGS}

intents = discord.Intents.all()
bot = commands.Bot(COMMAND_PREFIX, intents=intents)
for cog in COGS:
    bot.load_extension(f"cogs.{cog}")

@bot.event
async def on_ready():
    while not all(cogsReady.values()):
        await asyncio.sleep(1)
    log.info("Bot Ready")

@bot.event
async def on_message(message):
    # Ignore messages from itself
    if message.author.id == FRIENDLY_SNEK:
        return
    
    # Ignore messages that were not sent on the correct server
    if message.guild is None or message.guild.id != SERVER:
        log.warning("Wrong server")
        return
    
    # Execute commands
    if message.content.startswith(COMMAND_PREFIX):
        log.debug(f"{message.author.display_name}({message.author.name}#{message.author.discriminator}) > {message.content}")
        await bot.process_commands(message)
    
    await runMessageAnalysis(bot, message)

@bot.event
async def on_member_join(member):
    guild = member.guild
    if guild.id != SERVER:
        log.debug("Member joined on another server")
        return
    log.debug("Member joined")
    await asyncio.sleep(5 * 60)  # seconds
    currentMembers = await guild.fetch_members()
    if member in currentMembers:
        updatedMember = await guild.fetch_member(member.id)
        if len(updatedMember.roles) < 2:
            bot.get_channel(WELCOME)

@bot.event
async def on_error(event, *args, **kwargs):
    log.exception("An error occured")

@bot.event
async def on_command_error(ctx, error):
    log.error(error)

if __name__ == "__main__":
    defaultData = {"scheduleEvents": {}}
    if os.path.exists("data.pkl"):
        try:
            with open("data.pkl", "rb") as f:
                data = pickle.load(f)
        except Exception:
            data = defaultData
    else:
        data = defaultData
    
    with open(("tokenDev" if os.path.exists("tokenDev") else "token") if DEBUG else "token") as f:
        token = f.read().strip()
    try:
        bot.data = data
        bot.run(token)
        log.info("Bot Stopped")
    except Exception:
        log.exception("An error occured")
    finally:
        with open("data.pkl", "wb") as f:
            pickle.dump(data, f)