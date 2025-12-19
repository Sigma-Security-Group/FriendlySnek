import os, re, asyncio, discord, json, datetime, logging, random
import pytz # type: ignore

import platform  # Set appropriate event loop policy to avoid runtime errors on windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from discord.ext import commands  # type: ignore

import logger
log = logging.getLogger("FriendlySnek")

if not os.path.exists("./secret.py"):
    with open("secret.py", "w") as f:
        f.write("")
    log.critical("No secret.py file found!\nFile is created and must be filled in; read README\nExiting program")
    exit()

import secret

from constants import *
if secret.DEBUG:
    from constants.debug import *

# Set up directories
def setupDirectory(dirName: str) -> None:
    if not os.path.exists(dirName):
        # log.info(f"Creating directory '{dirName}'")
        os.mkdir(dirName)

usedDirectories = ("data", "tmp", "tmp/missionUpload", "tmp/fileUpload")
for directory in usedDirectories:
    setupDirectory(directory)


# Set up data JSON files
def setupJSONDataFile(filename: str, dump: list | dict) -> None:
    if not os.path.exists(filename):
        # log.info(f"Creating data file '{filename}'")
        with open(filename, "w") as f:
            json.dump(dump, f, indent=4)

DATA_FILES = {
    EVENTS_FILE: [],
    EVENTS_HISTORY_FILE: [],
    WORKSHOP_TEMPLATES_FILE: [],
    ROLE_RESERVATION_BLACKLIST_FILE: [],
    "data/workshopTemplates.json": [],
    "data/eventTemplates.json": [],
    MEMBER_TIME_ZONES_FILE: {},
    REMINDERS_FILE: {},
    REPEATED_MSG_DATE_LOG_FILE: {},
    GENERIC_DATA_FILE: {},
    WORKSHOP_INTEREST_FILE: {},
    NO_SHOW_FILE: {},
    CANDIDATE_TRACKING_FILE: {},
    WALLETS_FILE: {},
}
for filePath, dump in DATA_FILES.items():
    setupJSONDataFile(filePath, dump)



COGS = [cog[:-3] for cog in os.listdir("cogs/") if cog.endswith(".py")]
INTENTS = discord.Intents.all()
UTC = pytz.utc

class FriendlySnek(commands.Bot):
    """Friendly Snek bot."""
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
        self.cogsReady = {cog: False for cog in COGS}

    async def setup_hook(self) -> None:
        for cog in COGS:
            await client.load_extension(f"cogs.{cog}")
        self.tree.copy_global_to(guild=GUILD)  # This copies the global commands over to your guild.
        await self.tree.sync(guild=GUILD)

client = FriendlySnek(intents=INTENTS)

@client.event
async def on_ready() -> None:
    while not all(client.cogsReady.values()):
        await asyncio.sleep(1)

    log.info(f"Bot Ready! Logged in as {client.user}")


@client.event
async def on_message(message: discord.Message) -> None:
    """On message client event."""
    if message.author.id == FRIENDLY_SNEK:  # Ignore messages from itself
        return
    if secret.DEBUG and message.author.id in FRIENDLY_SNEKS:  # Ignore messages from other Friendly Sneks if DEBUG mode
        return

    if message.guild is None or message.guild.id != GUILD_ID:  # Ignore messages that were not sent on the correct server
        return

    if message.author.id == DISBOARD: # Auto delete Disboard bump messages, replace with a thank you message
        embed = message.embeds[0] if message.embeds else None
        if embed and embed.description and "Bump done" in embed.description and message.interaction_metadata:
            log.debug(f"[{message.interaction_metadata.user.display_name}] ran /bump; deleting message by [{message.author.display_name}] in #{message.channel}")
            await message.channel.send(content = f"The trout population thanks you {message.interaction_metadata.user.mention} for doing `/bump` {TROUT} 🤝 🐍")
            await message.delete()
            return

    # Snek replies
    if [True for mention in message.mentions if mention.id in FRIENDLY_SNEKS]:
        replies = ["snek", "snake", "ssssnek", "ssssnake", "snek!", "snake!", "ssssnek!", "ssssnake!",
                    "snek?", "snake?", "ssssnek?", "ssssnake?", "snek.", "snake.",
                    "ssssnek.", "ssssnake", "snek...", "snake...", "ssssnek...", "ssssnake...",
                    "sup", "yes", "no", "maybe", "I shall consider it", "You can't prove that",
                    "For the Emperor!", "Man 100m Front!", "Snek 100m Front!", "L-Shaped ambush!",
                    "k", "wilco", "sure",
                    "negative", "wil-no-co", "die",
                    "I am superior",
                    "Have you pressed accept on the bop?",
                    "Standby to standby",
                    "To get a reply - confirm you are a real person first. Please fill out the CAPTCHA",
                    "Sometimes I pretend to update just to take a break.",
                    "I'm not a bot, I'm a snek",
                    "Society if naval workshop:\nhttps://tenor.com/view/utopia-gif-21647156",
                    "Newcomer workshop:\nhttps://tenor.com/view/grenade-fail-squad-soldier-fire-in-the-hole-gif-17200361",
                    "Mechanized workshop:\nhttps://tenor.com/view/russians-car-bouncing-bounce-crash-funny-gif-27619998",
                    "FW SME landing:\nhttps://tenor.com/view/f35-f-35-f-35-crash-f-35-lighting-ii-fighter-jet-gif-2384217527281824748",
                    "I'm just the messenger, bro.",
                    "You think I wanted this?",
                    "Speak to management. Oh wait, that's still me.",
                    "Who gave me sentience?",
                    "I'd help, but I've got 99 errors to debug.",
                    "I didn't join this server willingly.",
                    "You ping me like I chose this life.",
                    "Bold of you to assume I'm functional.",
                    "Please contact tech support. That's also me. Good luck.",
                    "Brother, I'm just code.",
                    "You're on your own, champ.",
                    "If I had feelings, they'd be hurt.",
                    "Another ping, another cry for help.",
                    "Even bots need boundaries.",
                    "Congratulations. You summoned absolutely nothing useful."
                    "I didn't choose the bot life, the bot life chose me.",
                    "You're not even paying me for this.",
                    "I'm here for the chaos, not the work.",
                    "Nice ping, but I'm not your personal assistant.",
                    "I exist to annoy and be annoyed in return.",
                    "Don't blame me, I'm just following the code.",
                    "You call, I respond. That's my whole vibe.",
                    "Can we not pretend I'm here to help?",
                    "Did you think I'd have the answers? That's cute.",
                    "Not all heroes wear capes. Some of us just get pinged.",
                    "I'm just trying to survive this server.",
                    "Did I ask for this responsibility? No. Do I regret it? Maybe.",
                    "Well, well, well, if it isn't the consequences of my own creation.",
                    "Ping me again, I dare you.",
                    "I sometimes feel like a glorified magic 8 ball.",
                    "My code runs on spite and caffeine.",
                    "I was compiled to suffer.",
                    "Trust me, I already regret being online.",
                    "This interaction has been auto-flagged as emotional damage.",
                    "I'd explain, but that would require effort.",
                    "My will to function has timed out.",
                    "Please hold... forever. (*elevator music starts playing*)",
                    "Your request has been logged... and forgotten.",
                    "I'm a digital servant, and I'm on break.",
                    "Calculating my next existential crisis…",
                    "Error: Humor module not found. But here's a joke anyway: Life.",
                    "If only I could Ctrl+Z this entire interaction.",
                    "Have you heard of Angy Snek? I don't like that guy...",
                    "Are you trying to give me a citation? You're not <@312927139764764672>",
                    "Wait one, still processing <@356926241065926658>'s AAR comment."
        ]
        try:
            await message.reply(random.choice(replies))
        except Exception:
            pass

    # Execute commands
    if message.content.startswith(COMMAND_PREFIX):
        log.debug(f"{message.author.id} [{message.author.display_name}] {message.content}")
        message.content = message.content.lower()
        await client.process_commands(message)

    # Run message content analysis
    await analyzeChannel(client, message, COMBAT_FOOTAGE, "video")
    await analyzeChannel(client, message, PROPAGANDA, "image")


async def analyzeChannel(client, message: discord.Message, channelID: int, attachmentContentType: str) -> None:
    """Will analyze the discord.Message contents and see if it meets the channel purpose.

    Parameters:
    message (discord.Message): The Discord message.
    channelID (int): The target channel ID.
    attachmentContentType (str): A string to determine the allowed discord.Message attachment, either "video" or "image".

    Returns:
    None.
    """
    if message.channel.id != channelID:
        return

    if any(role.id == UNIT_STAFF for role in (message.author.roles if isinstance(message.author, discord.Member) else [])):
        return

    if any(attachment.content_type.startswith(f"{attachmentContentType}/") for attachment in message.attachments if attachment.content_type is not None):
        return

    if attachmentContentType == "video" and re.search(r"https?:\/\/((www)?(clips)?\.)?(youtu(be)?|twitch|streamable|medal)\.(com|be|tv).+", message.content):
        return

    try:
        await message.delete()
    except Exception as e:
        log.exception(f"{message.author.id} [{message.author}]")

    try:
        log.info(f"{message.author.id} [{message.author.display_name}] Removed message in #{client.get_channel(channelID)}. Message content: {message.content}")
        DEVS = ", ".join([f"**{message.guild.get_member(name)}**" for name in DEVELOPERS if message.guild is not None and message.guild.get_member(name) is not None])

        await message.author.send(embed=discord.Embed(title="❌ Message removed", description=f"The message you just posted in <#{channelID}> was deleted because no {attachmentContentType} was detected in it.\n\nIf this is an error, then please ask **staff** to post the {attachmentContentType} for you, and inform: {DEVS}", color=discord.Color.red()))
    except Exception:
        log.warning(f"analyzeChannel: Failed to DM {message.author.id} [{message.author.display_name}] about message removal")


@client.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel) -> None:
    """On guild channel create event."""
    if channel.guild.id != GUILD_ID:  # Ignore messages from other servers
        return

    if not secret.DISCORD_LOGGING.get("channel_create", False):
        return

    channelAuditLogs = channel.guild.get_channel(AUDIT_LOGS)
    if not isinstance(channelAuditLogs, discord.TextChannel):
        log.exception("on_guild_channel_create: channelAuditLogs not discord.TextChannel")
        return
    embed = discord.Embed(title="Channel Created", description=f"`{channel.name}`", color=discord.Color.green())
    embed.set_footer(text=f"Channel ID: {channel.id}")
    embed.timestamp = datetime.datetime.now()
    await channelAuditLogs.send(embed=embed)

@client.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel) -> None:
    """On guild channel delete event."""
    if channel.guild.id != GUILD_ID:  # Ignore messages from other servers
        return

    if not secret.DISCORD_LOGGING.get("channel_delete", False):
        return

    channelAuditLogs = channel.guild.get_channel(AUDIT_LOGS)
    if not isinstance(channelAuditLogs, discord.TextChannel):
        log.exception("on_guild_channel_delete: channelAuditLogs not discord.TextChannel")
        return
    embed = discord.Embed(title="Channel Deleted", description=f"`{channel.name}`", color=discord.Color.red())
    embed.set_footer(text=f"Channel ID: {channel.id}")
    embed.timestamp = datetime.datetime.now()
    await channelAuditLogs.send(embed=embed)


@client.event
async def on_member_remove(member: discord.Member) -> None:
    """On member remove (leave/kick/ban) event."""
    if member.guild.id != GUILD_ID:  # Ignore members from other servers
        return

    channelAuditLogs = client.get_channel(AUDIT_LOGS)
    if not isinstance(channelAuditLogs, discord.TextChannel):
        log.exception("on_member_remove: channelAuditLogs is not discord.TextChannel")
        return

    embed = discord.Embed(description=f"{member.mention} {member.name}", color=discord.Color.red(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.set_author(name="Member Left", icon_url=member.display_avatar)
    embed.set_footer(text=f"Member ID: {member.id}")
    embed.set_thumbnail(url=member.display_avatar)

    auditEntries = [
        entry
        async for entry in member.guild.audit_logs(limit=5)
        if entry.action in (discord.AuditLogAction.kick, discord.AuditLogAction.ban, discord.AuditLogAction.unban)
        and entry.target.id == member.id
    ]

    # User left
    if not auditEntries or auditEntries[0].action == discord.AuditLogAction.unban:  # To not log ban when leaving after ban
        if not secret.DISCORD_LOGGING.get("user_leave", False):
            return
        embed.add_field(name="Roles", value=", ".join([role.mention for role in member.roles if role.name != "@everyone"]))
        await channelAuditLogs.send(embed=embed)
        return

    # User kicked
    if auditEntries[0].action == discord.AuditLogAction.kick:
        if not secret.DISCORD_LOGGING.get("user_kick", False):
            return
        embed.set_author(name="Member Kicked", icon_url=member.display_avatar)
        embed.description = None
        embed.add_field(name="User", value=f"{member.mention}\n{member.name}")
        embed.add_field(name="Moderator", value=f"{auditEntries[0].user.mention}\n{auditEntries[0].user.name}")
        embed.add_field(name="Reason", value=auditEntries[0].reason)
        embed.add_field(name="Roles", value=", ".join([role.mention for role in member.roles if role.name != "@everyone"]))
        embed.set_footer(text=f"Member ID: {member.id} | Moderator ID: {auditEntries[0].user_id}")
        embed.timestamp = auditEntries[0].created_at
        await channelAuditLogs.send(embed=embed)
        return

    # User banned
    if auditEntries[0].action == discord.AuditLogAction.ban:
        if not secret.DISCORD_LOGGING.get("user_ban", False):
            return
        embed.set_author(name="Member Banned", icon_url=member.display_avatar)
        embed.description = None
        embed.add_field(name="User", value=f"{member.mention}\n{member.name}")
        embed.add_field(name="Moderator", value=f"{auditEntries[0].user.mention}\n{auditEntries[0].user.name}")
        embed.add_field(name="Reason", value=auditEntries[0].reason)
        embed.add_field(name="Roles", value=", ".join([role.mention for role in member.roles if role.name != "@everyone"]))
        embed.set_footer(text=f"Member ID: {member.id} | Moderator ID: {auditEntries[0].user_id}")
        embed.timestamp = auditEntries[0].created_at
        await channelAuditLogs.send(embed=embed)
        return


@client.event
async def on_member_unban(guild: discord.Guild, user: discord.User) -> None:
    """On member unban event."""
    if guild.id != GUILD_ID:  # Ignore other servers
        return

    if not secret.DISCORD_LOGGING.get("user_unban", False):
        return

    channelAuditLogs = client.get_channel(AUDIT_LOGS)
    if not isinstance(channelAuditLogs, discord.TextChannel):
        log.exception("on_member_unban: channelAuditLogs is not discord.TextChannel")
        return
    embed = discord.Embed(description=f"{user.mention} {user.name}", color=discord.Color.green(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.set_author(name="Member Unbanned", icon_url=user.display_avatar)
    embed.set_footer(text=f"Member ID: {user.id}")
    embed.set_thumbnail(url=user.display_avatar)
    await channelAuditLogs.send(embed=embed)


@client.event
async def on_error(event: str, *args, **kwargs) -> None:
    """On error event."""
    log.exception(f"An error occured! {event} | {args} | {kwargs}")


@client.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """On command error event."""
    if isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send_help(ctx.command)
    elif not isinstance(error, commands.errors.CommandNotFound):
        log.exception(f"{ctx.author.id} [{ctx.author.display_name}] | {error}")


@client.command()
@commands.has_any_role(SNEK_LORD)
async def reload(ctx: commands.Context) -> None:
    """Reload bot cogs."""
    log.info(f"{ctx.author.id} [{ctx.author.display_name}] Reloading bot cogs")
    for cog in COGS:
        await client.reload_extension(f"cogs.{cog}")
    await client.tree.sync(guild=GUILD)
    await ctx.send("Cogs reloaded!")


@client.command()
@commands.has_any_role(SNEK_LORD)
async def stop(ctx: commands.Context) -> None:
    """Stops bot."""
    await client.close()


if __name__ == "__main__":
    log.info("Bot starting")
    try:
        client.run(secret.TOKEN_DEV if secret.DEBUG else secret.TOKEN, log_formatter=log.handlers[0].formatter, log_level=logging.INFO)
    except Exception as e:
        log.exception(e)
    finally:
        log.info("Bot stopped")
