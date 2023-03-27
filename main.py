import os, re, pytz, asyncio, discord

from logger import Logger
log = Logger()

import platform  # Set appropriate event loop policy to avoid runtime errors on windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from discord import Embed, Color
from discord.ext import commands  # type: ignore

if not os.path.exists("./secret.py"):
    log.info("Creating a secret.py file!")
    with open("secret.py", "w") as f:
        f.write(  # Write secret.py template
            """TOKEN = ""
TOKEN_DEV = ""
DEBUG = True

SFTP = {
    "username": "",
    "password": ""
}

REDDIT = {
    "client_id": "",
    "client_secret": "",
    "password": ""
}"""
        )
    exit()

import secret

from constants import *
if secret.DEBUG:
    from constants.debug import *

if not os.path.exists("./data"):
    log.info("Creating a data directory!")
    os.mkdir("data")

if not os.path.exists("./tmp"):  # Mission missionUploader stuff- TODO maybe create it if it's needed?
    log.info("Creating a tmp directory!")
    os.mkdir("tmp")

COGS = [cog[:-3] for cog in os.listdir("cogs/") if cog.endswith(".py")]
cogsReady = {cog: False for cog in COGS}

INTENTS = discord.Intents.all()
UTC = pytz.utc
newcomers: set[int] = set()

class FriendlySnek(commands.Bot):
    def __init__(self, *, intents: discord.Intents) -> None:
        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=intents,
            activity=discord.Activity(  # 🐍
                type=discord.ActivityType.watching,
                name="you"
            ),
            status="online"
        )

    async def setup_hook(self) -> None:
        for cog in COGS:
            await client.load_extension(f"cogs.{cog}")
        self.tree.copy_global_to(guild=GUILD)  # This copies the global commands over to your guild.
        await self.tree.sync(guild=GUILD)

client = FriendlySnek(intents=INTENTS)
client.ready = False

@client.event
async def on_ready() -> None:
    while not all(cogsReady.values()):
        await asyncio.sleep(1)
    client.ready = True
    log.info(f"Bot Ready! Logged in as {client.user}.")

@client.event
async def on_message(message: discord.Message) -> None:
    """ On message client event.

    Parameters:
    message (discord.Message): The Discord message.

    Returns:
    None.
    """
    if message.author.id == FRIENDLY_SNEK:  # Ignore messages from itself
        return
    if secret.DEBUG and message.author.id in FRIENDLY_SNEKS:  # Ignore messages from other Friendly Sneks if DEBUG mode
        return

    if message.guild is None or message.guild.id != GUILD_ID:  # Ignore messages that were not sent on the correct server
        return

    # Execute commands
    if message.content.startswith(COMMAND_PREFIX):
        log.debug(f"{message.author.display_name} ({message.author}) > {message.content}")
        message.content = message.content.lower()
        await client.process_commands(message)

    # Unmark newcomer pinging Unit Staff or Advisor as needing a reminder to ping Unit Staff or Advisor
    if message.author.id in newcomers:
        if message.guild.get_role(UNIT_STAFF) in message.role_mentions or message.guild.get_role(ADVISOR) in message.role_mentions:
            newcomers.remove(message.author.id)

    # Run message content analysis
    await analyzeChannel(client, message, COMBAT_FOOTAGE, "video")
    await analyzeChannel(client, message, PROPAGANDA, "image")

async def analyzeChannel(client, message: discord.Message, channelID: int, attachmentContentType: str) -> None:
    """ Will analyze the discord.Message contents and see if it meets the channel purpose.

    Parameters:
    message (discord.Message): The Discord message.
    channelID (int): The target channel ID.
    attachmentContentType (str): A string to determine the allowed discord.Message attachment, either "video" or "image".

    Returns:
    None.
    """
    if message.channel.id != channelID:
        return
    elif any(role.id == UNIT_STAFF for role in (message.author.roles if isinstance(message.author, discord.Member) else [])):
        return
    elif any(attachment.content_type.startswith(f"{attachmentContentType}/") for attachment in message.attachments if attachment.content_type is not None):
        return
    elif attachmentContentType == "video" and re.search(r"https?:\/\/((www)?(clips)?\.)?(youtu(be)?|twitch|streamable)\.(com|be|tv).+", message.content):
        return

    try:
        await message.delete()
    except Exception as e:
        log.exception(f"{message.author} | {e}")

    try:
        log.info(f"Removed message in #{client.get_channel(channelID)} from {message.author.display_name} ({message.author}). Message content: {message.content}")
        DEVS = ", ".join([f"**{message.guild.get_member(name)}**" for name in DEVELOPERS if message.guild is not None and message.guild.get_member(name) is not None])

        await message.author.send(embed=Embed(title="❌ Message removed", description=f"The message you just posted in <#{channelID}> was deleted because no {attachmentContentType} was detected in it.\n\nIf this is an error, then please ask **staff** to post the {attachmentContentType} for you, and inform: {DEVS}", color=Color.red()))
    except Exception as e:
        log.exception(f"{message.author} | {e}")

@client.event
async def on_member_join(member: discord.Member) -> None:
    """ On member join client event.

    Parameters:
    member (discord.Member): The Discord member.

    Returns:
    None.
    """
    guild = member.guild
    if guild.id != GUILD_ID:
        return
    newcomers.add(member.id)
    log.debug(f"Newcomer joined the server: {member}")
    await asyncio.sleep(24 * 60 * 60)  # 24 hours in seconds
    if member.id not in newcomers:
        log.debug(f"Newcomer is no longer in the server: {member}")
        return

    if member in [member async for member in guild.fetch_members()]:
        updatedMember = await guild.fetch_member(member.id)
        if len(updatedMember.roles) <= 2:
            log.debug(f"Newcomer ping reminder: {updatedMember}")
            unitStaff = guild.get_role(UNIT_STAFF)
            advisor = guild.get_role(ADVISOR)
            await client.get_channel(WELCOME).send(f"{updatedMember.mention} Don't forget to ping{' @​' + unitStaff.name if unitStaff is not None else ''}{' and' if unitStaff and advisor else ''}{' @​' + advisor.name if advisor is not None else ''} when you are ready!")
        else:
            log.debug(f"Newcomer is no longer in need of an interview: {updatedMember.display_name} ({updatedMember})")
    else:
        log.debug(f"Newcomer is no longer in the server: {member}")
    if member.id in newcomers:
        newcomers.remove(member.id)

@client.event
async def on_member_leave(member: discord.Member) -> None:
    """ On member leave client event.

    Parameters:
    member (discord.Member): The Discord member.

    Returns:
    None.
    """
    if member.id in newcomers:
        newcomers.remove(member.id)
        log.debug(f"Newcomer left: {member.display_name} ({member})")

@client.event
async def on_error(event, *args, **kwargs) -> None:
    log.exception(f"An error occured! {event}")

@client.event
async def on_command_error(ctx: commands.Context, error: commands.errors) -> None:
    errorType = type(error)
    if errorType is commands.errors.MissingRequiredArgument:
        await ctx.send_help(ctx.command)
    elif not errorType is commands.CommandNotFound:
        log.exception(f"{ctx.author} | {error}")

def devCheck() -> commands.check:
    """ A permissions check for the reload command.

    Parameters:
    None.

    Returns:
    commands.check
    """
    def predict(ctx: commands.context) -> bool:
        return ctx.author.id in DEVELOPERS
    return commands.check(predict)

@client.command()
@devCheck()
async def reload(ctx: commands.context) -> None:
    """ Reload bot cogs - Devs only. """
    log.info(f"{ctx.author.display_name} ({ctx.author}) Reloading bot cogs...")
    if ctx.author.id not in DEVELOPERS:
        return
    for cog in COGS:
        await client.reload_extension(f"cogs.{cog}")
    await client.tree.sync(guild=GUILD)
    await ctx.send("Cogs reloaded!")

if secret.DEBUG:
    @client.command()
    @devCheck()
    async def stop(ctx: commands.context) -> None:
        """ Stops bot - Devs only. """
        await client.close()


if __name__ == "__main__":
    try:
        client.run(secret.TOKEN_DEV if secret.DEBUG else secret.TOKEN)
        log.info("Bot stopped!")
    except Exception as e:
        log.exception(e)
