from logger import Logger
log = Logger()

import secret
import pytz
import asyncio
import os
DEBUG = os.path.exists("DEBUG")  # Define whether to use the Sigma or BTR (debug) server
# DEBUG = True  # always use debug server during development

import platform  # Set appropriate event loop policy to avoid runtime errors on windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# from typing import Optional
import discord
# from discord import app_commands
from discord.ext import commands

from constants import *
if DEBUG:
    from constants.debug import *

if not os.path.exists("./data"):
    os.mkdir("data")

COGS = [cog[:-3] for cog in os.listdir("cogs/") if cog.endswith(".py")]
cogsReady = {cog: False for cog in COGS}

INTENTS = discord.Intents.all()
UTC = pytz.utc
newcomers = set()

class FriendlySnek(commands.Bot):
    def __init__(self, *, intents: discord.Intents, applicationID: int):
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents, application_id=applicationID, activity=discord.Activity(type=discord.ActivityType.watching, name="you"), status="online")  # 🐍
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.

        #self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        self.tree.copy_global_to(guild=GUILD)  # This copies the global commands over to your guild.
        for cog in COGS:
            await client.load_extension(f"cogs.{cog}")
        await self.tree.sync(guild=GUILD)

# In order to use a basic synchronization of the app commands in the setup_hook,
# you have to replace the 0 with your bot's application_id that you find in the developer portal.
client = FriendlySnek(intents=INTENTS, applicationID=FRIENDLY_SNEK_DEV_FROGGI)
client.ready = False

@client.event
async def on_ready():
    while not all(cogsReady.values()):
        await asyncio.sleep(1)
    client.ready = True
    log.info(f"Bot Ready! Logged in as {client.user}.")


@client.event
async def on_message(message):
    return
    # # Ignore messages from itself
    # if message.author.id == FRIENDLY_SNEK:
    #     return
    # if DEBUG and message.author.id in FRIENDLY_SNEKS:
    #     return

    # # Ignore messages that were not sent on the correct server
    # if message.guild is None or message.guild.id != SERVER:
    #     return

    # # Execute commands
    # if message.content.startswith(COMMAND_PREFIX):
    #     log.debug(f"{message.author.display_name} ({message.author.name}#{message.author.d iscriminator}) > {message.content}")
    #     await bot.process_commands(message)

    # # Unmark newcomer pinging unit staff as needing a reminder to ping unit staff
    # if message.author.id in newcomers:
    #     unitStaffRole = message.guild.get_role(UNIT_STAFF)
    #     if unitStaffRole in message.role_mentions:
    #         newcomers.remove(message.author.id)

    # # Run message content analysis
    # #await runMessageAnalysis(bot, message)


@client.event
async def on_member_join(member):
    guild = member.guild
    if guild.id != GUILD_ID:
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
            await client.get_channel(WELCOME).send(f"{updatedMember.mention} Don't forget to ping {unitStaffRole.name} when you are ready.")
        else:
            log.debug(f"Newcomer is no longer in need of an interview {updatedMember.display_name} ({updatedMember.name}#{updatedMember.discriminator})")
    else:
        log.debug(f"Newcomer is no longer in the server {member.display_name}({member.name}#{member.discriminator})")
    if member.id in newcomers:
        newcomers.remove(member.id)

@client.event
async def on_member_leave(member):
    if member.id in newcomers:
        newcomers.remove(member.id)
        log.debug(f"Newcomer left {member.display_name}({member.name}#{member.discriminator})")

@client.event
async def on_error(event, *args, **kwargs):  # Do we need these parameters?
    log.exception(LOG_ERROR)

@client.event
async def on_command_error(ctx, error):
    log.error(error)

#@client.command(hidden=True, help="Reload cogs (Dev only)")
#async def reload(ctx):
#    if ctx.author.id not in DEVELOPERS:
#        return
#    for cog in cogs:
#        client.reload_extension(f"cogs.{cog}")
#    await ctx.send("Cogs reloaded!")


# @client.tree.command()
# async def hello(interaction: discord.Interaction):
#     """Says hello!"""
#     await interaction.response.send_message(f"Hi, {interaction.user.mention}")


# @client.tree.command()
# @app_commands.describe(
#     first_value="The first value you want to add something to",
#     second_value="The value you want to add to the first value",
# )
# async def add(interaction: discord.Interaction, first_value: int, second_value: int):
#     """Adds two numbers together."""
#     await interaction.response.send_message(f"{first_value} + {second_value} = {first_value + second_value}")


# The rename decorator allows us to change the display of the parameter on Discord.
# In this example, even though we use `text_to_send` in the code, the client will use `text` instead.
# Note that other decorators will still refer to it as `text_to_send` in the code.
# @client.tree.command()
# @app_commands.rename(text_to_send="text")
# @app_commands.describe(text_to_send="Text to send in the current channel")
# async def send(interaction: discord.Interaction, text_to_send: str):
#     """Sends the text into the current channel."""
#     await interaction.response.send_message(text_to_send)


# To make an argument optional, you can either give it a supported default argument
# or you can mark it as Optional from the typing standard library. This example does both.
# @client.tree.command()
# @app_commands.describe(member="The member you want to get the joined date from; defaults to the user who uses the command")
# async def joined(interaction: discord.Interaction, member: Optional[discord.Member] = None):
#     """Says when a member joined."""
#     # If no member is explicitly provided then we use the command user here
#     member = member or interaction.user

#     # The format_dt function formats the date time into a human readable representation in the official client
#     await interaction.response.send_message(f"{member} joined {discord.utils.format_dt(member.joined_at)}")


# A Context Menu command is an app command that can be run on a member or on a message by
# accessing a menu within the client, usually via right clicking.
# It always takes an interaction as its first parameter and a Member or Message as its second parameter.

# This context menu command only works on members
# @client.tree.context_menu(name="Show Join Date")
# async def show_join_date(interaction: discord.Interaction, member: discord.Member):
#     # The format_dt function formats the date time into a human readable representation in the official client
#     await interaction.response.send_message(f"{member} joined at {discord.utils.format_dt(member.joined_at)}")


# This context menu command only works on messages
# @client.tree.context_menu(name="Report to Moderators")
# async def report_message(interaction: discord.Interaction, message: discord.Message):
#     # We're sending this response message with ephemeral=True, so only the command executor can see it
#     await interaction.response.send_message(
#         f"Thanks for reporting this message by {message.author.mention} to our moderators.", ephemeral=True
#     )

#     # Handle report by sending it into a log channel
#     log_channel = interaction.guild.get_channel(0)  # replace with your channel id

#     embed = discord.Embed(title="Reported Message")
#     if message.content:
#         embed.description = message.content

#     embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
#     embed.timestamp = message.created_at

#     url_view = discord.ui.View()
#     url_view.add_item(discord.ui.Button(label="Go to Message", style=discord.ButtonStyle.url, url=message.jump_url))

#     await log_channel.send(embed=embed, view=url_view)


if __name__ == "__main__":
    try:
        client.run(secret.tokenDev if DEBUG else secret.token)
        log.info("Bot stopped!")
    except Exception:
        log.exception("An error occured!")
