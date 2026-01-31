from collections.abc import AsyncIterator
import secret, os, random, json, re, aiohttp, discord, logging, asyncio
import asyncpraw, pytz  # type: ignore

from typing import Tuple
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta  # type: ignore
from bs4 import BeautifulSoup as BS  # type: ignore
from .workshopInterest import WORKSHOP_INTEREST_LIST, WorkshopInterest  # type: ignore
from .spreadsheet import Spreadsheet

from discord.ext import commands, tasks  # type: ignore

from constants import *
if secret.DEBUG:
    from constants.debug import *

log = logging.getLogger("FriendlySnek")
lock = asyncio.Lock()

def chunkList(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

class BotTasks(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("BotTasks"))
        self.bot.cogsReady["botTasks"] = True

        if not self.oneHourTasks.is_running():
            self.oneHourTasks.start()

        if not self.fiveMinTasks.is_running():
            self.fiveMinTasks.start()


    @staticmethod
    @commands.Cog.listener()
    async def on_member_join(member: discord.Member) -> None:
        """On member join client event.

        Parameters:
        member (discord.Member): The Discord member.

        Returns:
        None.
        """
        guild = member.guild
        if guild.id != GUILD_ID:
            return

        # Log in Audit Logs
        if secret.DISCORD_LOGGING.get("user_join", False):
            channelAuditLogs = member.guild.get_channel(AUDIT_LOGS)
            if not isinstance(channelAuditLogs, discord.TextChannel):
                log.exception("BotTasks on_member_join: channelAuditLogs not discord.TextChannel")
            else:
                memberJoined = discord.utils.format_dt(member.created_at, style="F") if member.created_at else "Unknown"
                embed = discord.Embed(description=f"{member.mention} {member.name}\n**Account Created**\n{memberJoined}", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
                embed.set_author(name="Member Joined", icon_url=member.display_avatar)
                embed.set_footer(text=f"Member ID: {member.id}")
                embed.set_thumbnail(url=member.display_avatar)
                await channelAuditLogs.send(embed=embed)

        # Add to spreadsheet
        Spreadsheet.memberJoin(member)

        #if Member account was created less than 45 days ago, alert unit staff and assign only suspicious account role
        if (datetime.now(timezone.utc) - member.created_at) < timedelta(days=45):
            channelStaffChat = guild.get_channel(STAFF_CHAT)
            if not isinstance(channelStaffChat, discord.TextChannel):
                log.exception("BotTasks on_member_join: channelStaffChat not discord.TextChannel")
                return
            roleUnitStaff = guild.get_role(UNIT_STAFF)
            if roleUnitStaff is None:
                log.exception("Bottasks on_member_join: roleUnitStaff is None")
                return

            createTimeFormat = member.created_at.strftime(TIME_FORMAT)
            log.info(f"BotTasks on_member_join: Suspicious Account detected {member.id} ({member.display_name}). Account Created: {createTimeFormat}")

            embed = discord.Embed(
                title="Suspicious Account Detected",
                description=f"{member.mention} {member.name}\n**Account Created**\n{discord.utils.format_dt(member.created_at, style='F')} ({discord.utils.format_dt(member.created_at, style='R')})",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=f"Member ID: {member.id}")
            embed.set_thumbnail(url=member.display_avatar)
            await channelStaffChat.send(f"{roleUnitStaff.mention}", embed=embed)

            rolesToRemove = [role for role in member.roles if not role.is_default()]
            try:
                if rolesToRemove:
                    await member.remove_roles(*rolesToRemove, reason="Suspicious Account")
            except Exception:
                if any(not role.is_default() for role in member.roles):
                    log.warning(f"BotTasks on_member_join: failed to remove roles from suspicious member '{member.id}' ({member.display_name})")

            roleSuspiciousAccount = guild.get_role(SUSPICIOUS_ACCOUNT)
            if roleSuspiciousAccount is None:
                log.exception("Bottasks on_member_join: roleSuspiciousAccount is None")
                return

            try:
                await member.add_roles(roleSuspiciousAccount, reason="Suspicious Account")
                susText = guild.get_channel(SUS_TEXT)
                if not isinstance(susText, discord.TextChannel):
                    log.exception("BotTasks on_member_join: susText is not discord.TextChannel")
                    return
                await susText.send(f"{member.mention}, your account is marked as suspicious due to being newly created. Please follow the instructions in the pinned message to resolve this.")
                return
            except Exception:
                log.warning(f"BotTasks on_member_join: failed to add suspicious role to member '{member.id}' ({member.display_name})")


        # Add prospect role
        roleProspect = guild.get_role(PROSPECT)
        if not isinstance(roleProspect, discord.Role):
            log.exception("BotTasks on_member_join: roleProspect is not discord.Role")
            return

        try:
            await member.add_roles(roleProspect, reason="Joined guild")
        except discord.HTTPException:
            log.warning(f"BotTasks on_member_join: failed to add prospect role to member '{member.id}'")


        # Send welcome message
        channelWelcome = member.guild.get_channel(WELCOME)
        if not isinstance(channelWelcome, discord.TextChannel):
            log.exception("BotTasks on_member_join: channelWelcome not discord.TextChannel")
            return
        embed = discord.Embed(title=f"Welcome, {member.display_name}!", description=f"Your view of the Discord server is limited. Please check <#{RULES_AND_EXPECTATIONS}> and <#{SERVER_INFO}>. Dont forget to ping @​Recruitment Team when you are ready for a brief 5 minute onboarding interview.", color=discord.Color.green())
        await channelWelcome.send(member.mention, embed=embed)


        # Add newcomer reminder
        remindTime = datetime.now() + timedelta(days=1)
        with open(REMINDERS_FILE) as f:
            reminders = json.load(f)

        for reminder in reminders.items():
            if reminder[1]["type"] == "newcomer" and reminder[1]["userID"] == member.id:
                return

        reminders[datetime.timestamp(remindTime)] = {
            "type": "newcomer",
            "userID": member.id
        }
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=4)



    @staticmethod
    async def fetchWebsiteText(modIds: list[int]) -> AsyncIterator[Tuple[int, str]]:
        MAX_INVALID_FETCHES = 3
        invalidFetches = 0
        iterMods = [(modID, CHANGELOG_URL.format(modID)) for modID in modIds]
        random.shuffle(iterMods)  # Shuffle mod list to reduce chance of rate limiting / bot detection

        funCooldownValue = lambda start, stop: start + random.random() * (stop - start) # Cooldown between start and stop seconds

        cookies = {"steamCountry": "FR%7C4219667261a70fcd1f30065fd4923490"}

        async with aiohttp.ClientSession() as session:
            for i, mod in enumerate(iterMods):
                modID, url = mod
                if invalidFetches >= MAX_INVALID_FETCHES:
                    log.warning("BotTasks checkModUpdates: invalidFetches limit reached, breaking loop")
                    break

                # Longer cooldown every 9 fetches
                # Steam returns HTTP 429 on the 40th request
                if i % 9 == 0 and i != 0:
                    async with lock:
                        await asyncio.sleep(funCooldownValue(15, 34))

                # Each fetch cooldown
                async with lock:
                    await asyncio.sleep(funCooldownValue(5.1, 10.9)) # Arbitrary Cooldown, sleep between 5.1 and 10.9 seconds

                async with session.get(url, cookies=cookies) as response:
                    if response.status != 200:
                        invalidFetches += 1
                        log.warning(f"BotTasks fetchWebsiteText: response.status is not 200 ({response.status}) '{url}' ({i+1}/{len(iterMods)})")
                        async with lock:
                            await asyncio.sleep(funCooldownValue(30, 60))  # Rate limit, sleep for longer
                        continue
                    yield (modID, await response.text())


    @staticmethod
    def parseModUpdateDate(modupdateTime: str) -> datetime:
        """Parse mod update time from string to datetime.

        Parameters:
        modupdateTime (str): The mod update time string, either one of these formats:
        'Update: 1 Jan @ 06:00am'
        'Update: 1 Jan, 2026 @ 06:00pm'

        Returns:
        datetime: The parsed datetime.

        Raises:
        ValueError: If the date format is unrecognized.
        """
        formats = [
            ("Update: %d %b, %Y @ %I:%M%p", True),   # with year
            ("Update: %d %b @ %I:%M%p", False),      # without year
        ]

        for fmt, has_year in formats:
            try:
                dt = datetime.strptime(modupdateTime, fmt)
                if not has_year:
                    dt = dt.replace(year=datetime.now().year)
                return dt
            except ValueError:
                pass

        raise ValueError(f"Unrecognized date format: {modupdateTime}")


    async def checkModUpdates(self) -> None:
        """Checks mod updates, pings hampters if detected."""
        CHECK_MOD_UPDATE_INTERVAL = 8.0  # hours

        output = []
        with open(GENERIC_DATA_FILE) as f:
            genericData = json.load(f)
            if "modpackIds" not in genericData:
                log.exception("BotTasks checkModUpdates: modpackIds not in genericData")
                return

            if "jcaCounter" not in genericData:
                genericData["jcaCounter"] = 0

        jcaModUpdateFound = False

        async for modID, website in BotTasks.fetchWebsiteText(genericData["modpackIds"]):
            modUpdateDate = ""
            # Fetch mod & parse HTML
            soup = BS(website, "html.parser")

            # Mod Title
            name = soup.find("div", class_="workshopItemTitle")
            if name is None:
                continue
            name = name.string

            # Find latest update
            update = soup.find("div", class_="detailBox workshopAnnouncement noFooter changeLogCtn")
            if update is None:
                log.exception("BotTasks checkModUpdates: update is None")
                return

            # Loop paragraphs in latest update
            for paragraph in update.descendants:
                stripTxt = str(paragraph).strip()
                if not stripTxt:  # Ignore empty shit
                    continue

                # Find update time
                elif stripTxt.startswith("Update: "):
                    modUpdateDate = stripTxt
                    break  # dw bout shit after this

            # Parse time to datetime
            try:
                modDateParsed = BotTasks.parseModUpdateDate(modUpdateDate)
            except Exception as e:
                log.exception(f"BotTasks checkModUpdates: Error parsing mod update date: {e}")
                continue

            # Convert it into UTC (shitty arbitrary code)
            modDateUTC = pytz.UTC.localize(modDateParsed + timedelta(hours=7))  # Change this if output time is wrong: will cause double ping

            # Current time
            now = datetime.now(timezone.utc)

            # Check if update is new
            if modDateUTC < now + timedelta(minutes=5.0) and modDateUTC > now - timedelta(hours=7, minutes=59.0):  # Relative time checking
                log.debug(f"BotTasks checkModUpdates: Arma mod update '{name}' - '{modDateUTC}'")
                output.append({
                    "modID": modID,
                    "name": name,
                    "datetime": modDateUTC
                })

                # JCA counter
                if modID in (3333302397, 3337555434):
                    genericData["jcaCounter"] += 1
                    jcaModUpdateFound = True


        with open(GENERIC_DATA_FILE, "w") as f:
            json.dump(genericData, f, indent=4)

        if len(output) > 0:
            # Create message
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("BotTasks checkModUpdates: guild is None")
                return

            channelChangelog = await guild.fetch_channel(CHANGELOG)
            if not isinstance(channelChangelog, discord.TextChannel):
                log.exception("BotTasks checkModUpdates: channelChangelog not discord.TextChannel")
                return

            roleHampter = guild.get_role(SERVER_HAMSTER)
            if roleHampter is None:
                log.exception("BotTasks checkModUpdates: roleHampter is None")
                return

            roleGuinea = guild.get_role(GUINEA_PIG)
            if roleGuinea is None:
                log.exception("BotTasks checkModUpdates: roleGuinea is None")
                return

            # Each mod update will be sent in a separate message
            msgContent: str | None = roleHampter.mention + " " + roleGuinea.mention + (f" ({len(output)})" if len(output) > 1 else "") + "\n"  # Ping for first message
            if jcaModUpdateFound:
                msgContent += f"The Holy JCA Developer; wisdom tally: {genericData['jcaCounter']}"

            for mod in output:
                await channelChangelog.send(msgContent, embed=discord.Embed(title=mod["name"], url=CHANGELOG_URL.format(mod['modID']), timestamp=mod["datetime"], color=discord.Color.dark_blue()))
                msgContent = None  # Only 1 ping


        # Update next execution time
        nextTime = (datetime.now(timezone.utc) + timedelta(hours=CHECK_MOD_UPDATE_INTERVAL))
        nextTime = nextTime.replace(microsecond=0)
        nextTime = datetime.timestamp(nextTime)

        with open(REPEATED_MSG_DATE_LOG_FILE) as f:
            msgDateLog = json.load(f)

        msgDateLog["modUpdates"] = nextTime
        with open(REPEATED_MSG_DATE_LOG_FILE, "w") as f:
            json.dump(msgDateLog, f, indent=4)



    async def redditRecruitmentPosts(self) -> None:
        """ Posts Reddit recruitment posts once a week."""
        username = "SigmaSecurityGroup"
        reddit = asyncpraw.Reddit(
            client_id=secret.REDDIT["client_id"],
            client_secret=secret.REDDIT["client_secret"],
            password=secret.REDDIT["password"],
            user_agent=f"Sigma Security Group by /u/{username}",
            username=username,
        )

        account = await reddit.redditor(username)  # Fetch our account
        submissions = account.submissions.new(limit=1)  # Get account submissions sorted by latest
        subCreated = None
        async for submission in submissions:  # Check the latest submission [break]
            subCreated = datetime.fromtimestamp(submission.created_utc, timezone.utc)  # Latest post timestamp
            break

        if subCreated is None:
            subCreated = datetime.fromtimestamp(0, timezone.utc)

        if datetime.now(timezone.utc) < (subCreated + timedelta(weeks=1.0, minutes=30.0)):  # Dont post if now is less than ~1 week than last post
            return

        # 1 week has passed, post new
        sub = await reddit.subreddit("FindAUnit")

        # Find Recruiting flair UUID
        flairID = None
        async for flair in sub.flair.link_templates.user_selectable():
            if flair["flair_text"] == "Recruiting":
                flairID = flair["flair_template_id"]
                break
        else:
            log.warning("BotTasks redditRecruitmentPosts: No recruiting flair found")

        # Submission details
        propagandaPath = r"constants/SSG_Propaganda"
        post = {
            "Title": "[A3][Recruiting][Worldwide] | Casual-Attendance, PMC Themed Unit | Sigma Security Group is now Recruiting!",
            "FlairID": flairID,
            "Description": """About Us:

- **Flexibility**: Sigma has no formal sign-up process, no commitments, and offers instruction on request. Certification in specialty roles is available and run by professionals in the field.

- **Activity**: We regularly host quality operations, and aim to provide content with a rich story and balanced flow/combat in order to keep our players interested.

- **Professionalism**: Operations are cooperative Zeus curated events, built and run by dedicated community members. Roleplay is encouraged, tactics are refined, and immersion is achieved.

- **Immersion**: Mods we use on the server are focused on expanding the default feature set and enhancing immersion. Our entire mod collection is found on the Arma 3 Steam Workshop.

Requirements:

- **Respect**: We are looking to play with respectful, patient members who we can trust and have a laugh with.

- **Community**: We don't want strangers, we ask members to be social and contribute in their own way. Community management roles are on a volunteer basis.

- **Maturity**: Players must be easy going, know when to be serious, and be willing to learn and improve alongside their fellow Operators. You must be at least age 16 to join.

- **Communication**: Members must have a functioning microphone and use it during all operations.

Join Us:

- Would you like to know more? Join the **[Discord Server](https://discord.gg/KtcVtfjAYj)** for more information."""
        }

        """ submit_image disabled temp cuz devs haven't released new version which fixes image_path error """
        # Send submission with random image
        submission = await sub.submit_image(title=post["Title"], image_path=f"{propagandaPath}/{random.choice(os.listdir(propagandaPath))}", flair_id=post["FlairID"])
        await submission.reply(post["Description"])

        log.info("BotTasks redditRecruitmentPosts: Reddit recruitment posted")

        channelArmaDiscussion = self.bot.get_channel(ARMA_DISCUSSION)
        if not isinstance(channelArmaDiscussion, discord.TextChannel):
            log.exception("BotTasks redditRecruitmentPosts: channelArmaDiscussion not discord.TextChannel")
            return

        await channelArmaDiscussion.send(f"Reddit recruitment post published, go upvote it!\nhttps://www.reddit.com{submission.permalink}")

    def getPingString(self, rawRole: int | tuple) -> str | None:
        """Generate a ping string from role id(s).

        Parameters:
        rawRole (int | tuple): One role id or tuple with role ids.

        Returns:
        str | None: str with pings or None if failed.
        """
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Bottasks getPingString: guild is None")
            return None

        if isinstance(rawRole, int):
            role = guild.get_role(rawRole)
            if role is None:
                log.exception("Bottasks getPingString: role is None")
                return None
            return role.mention

        roles = [guild.get_role(roleId) for roleId in rawRole]
        if None in roles:
            log.exception(f"Bottasks getPingString: roleId {roles[roles.index(None)]} returns None")
            return None
        return " ".join([role.mention for role in roles])  # type: ignore

    async def smeReminder(self) -> None:
        """Pings SME role if workshops haven't been hosted in required time."""

        with open(EVENTS_HISTORY_FILE) as f:
            eventsHistory = json.load(f)
        with open(EVENTS_FILE) as f:
            events = json.load(f)

        smeCorner = self.bot.get_channel(SME_CORNER)
        if not isinstance(smeCorner, discord.TextChannel):
            log.exception("Bottasks smeReminder: smeCorner not discord.TextChannel")
            return

        pingEmbed = discord.Embed(color=discord.Color.orange())

        with open(WORKSHOP_INTEREST_FILE) as f:
            wsIntFile: dict = json.load(f)
        wsHostDone = []
        wsHostFailed = []
        for wsName, wsDetails in WORKSHOP_INTEREST_LIST.items():
            wsScheduled = False
            # Check for scheduled events
            for event in events:
                if "workshopInterest" in event and event["workshopInterest"] == wsName:
                    wsScheduled = True
                    wsHostDone.append(wsName)
                    break

            if wsScheduled:
                continue

            pingEmbed.title = f"Workshop Reminder [{wsName}]"
            pingEmbed.description = f"\n\nInterested people signed up on workshop-interest: {len(wsIntFile.get(wsName, {'members': []}).get('members', []))}"

            # Check for past events
            for event in eventsHistory[::-1]:  # Newest to oldest
                if "workshopInterest" in event and event["workshopInterest"] == wsName:

                    # Send reminder if latest workshop was scheduled more than 60 days ago
                    if datetime.strptime(event["time"], TIME_FORMAT) < (datetime.now() - timedelta(days=60)):
                        eventScheduled = pytz.utc.localize(datetime.strptime(event['time'], TIME_FORMAT))
                        pingEmbed.description = f"Last `{wsName}` event you had (`{event['title']}`) was at {discord.utils.format_dt(eventScheduled, style='F')} ({discord.utils.format_dt(eventScheduled, style='R')}).\nPlease host at least every 2 months to give everyone a chance to cert!" + pingEmbed.description
                        await smeCorner.send(self.getPingString(wsDetails["role"]), embed=pingEmbed)
                    else:
                        wsHostDone.append(wsName)
                    break

            else:  # No workshop found
                pingEmbed.description = f"Last `{wsName}` event you had couldn't be found in my logs.\nPlease host at least every 2 months to give everyone a chance to cert!" + pingEmbed.description
                await smeCorner.send(self.getPingString(wsDetails["role"]), embed=pingEmbed)


            wsHostFailed.append(wsName)

        if len(wsHostFailed) > 0:
            log.debug(f"Bottasks smeReminder: SME reminder failed to host: {', '.join(wsHostFailed)}")

        if len(wsHostDone) > 0:
            log.debug(f"Bottasks smeReminder: SME reminder succeeded in hosting: {', '.join(wsHostDone)}")
            await smeCorner.send(":clap: Good job for keeping up the hosting " + ", ".join([f"`{wsName}`" for wsName in wsHostDone]) + "! :clap:")


        # Update next execution time
        with open(REPEATED_MSG_DATE_LOG_FILE) as f:
            msgDateLog = json.load(f)

        # Get datetime for next time in 6 months
        nextTime = Reminders.getFirstDayNextMonth()

        msgDateLog["smeReminder"] = datetime.timestamp(nextTime)
        with open(REPEATED_MSG_DATE_LOG_FILE, "w") as f:
            json.dump(msgDateLog, f, indent=4)

        log.info("Bottasks smeReminder: SME reminder sent & updated time")

    @staticmethod
    async def clearBumps(guild: discord.Guild) -> None:
        """ Clears daily /bump limit for users."""
        CLEAR_BUMP_TIMES_INTERVAL = 24.0 # hours

        with open(REPEATED_MSG_DATE_LOG_FILE) as f:
            msgDateLog = json.load(f)

        # Calculate next execution time (next day at midnight UTC)
        nextTime = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=CLEAR_BUMP_TIMES_INTERVAL)
        sendBumpResetMessage = False

        try:
            # Reset all wallet bump counts
            with open(WALLETS_FILE, "r", encoding="utf-8") as f:
                wallets = json.load(f)

            for walletData in wallets.values():
                if not sendBumpResetMessage and walletData.get("timesBumped", 0) > 0:
                    sendBumpResetMessage = True
                walletData["timesBumped"] = 0

            with open(WALLETS_FILE, "w", encoding="utf-8") as f:
                json.dump(wallets, f, indent=4)

            # Update next execution time
            msgDateLog["clearBumpTimes"] = datetime.timestamp(nextTime)
            with open(REPEATED_MSG_DATE_LOG_FILE, "w") as f:
                json.dump(msgDateLog, f, indent=4)

            log.debug("Bottasks oneHourTasks: cleared timesBumped in all wallets")
        except Exception as e:
            log.warning(f"Bottasks oneHourTasks: failed to clear timesBumped in wallets: {e}")

        if not sendBumpResetMessage:
            return

        casinoChannel = guild.get_channel(CASINO)
        if not isinstance(casinoChannel, discord.TextChannel):
            log.exception("Bottasks oneHourTasks: casinoChannel not discord.TextChannel")
            return

        # Send bump reset message
        try:
            embed = discord.Embed(
                title="Bump Bonuses Reset!",
                description=f"All bumps have been reset. Everyone is now eligible for their `{MAX_BUMPS}` daily bump bonuses again!\n\nAs a reminder, you can bump the server using the `/bump` command to earn SnekCoins!",
                color=discord.Color.green()
            )
            await casinoChannel.send(embed=embed)
        except Exception:
            log.warning("Bottasks oneHourTasks: failed to send bump reset message")


    @staticmethod
    async def smeBigBrother(guild: discord.Guild, manuallyExecuted: bool) -> None:
        """Summarize each SMEs activity last 6 months for Unit Staff."""
        channelStaffChat = guild.get_channel(STAFF_CHAT)
        if channelStaffChat is None:
            log.exception("Bottasks smeBigBrother: channelStaffChat is None")
            return

        with open(EVENTS_HISTORY_FILE) as f:
            eventsHistory = json.load(f)

        searchTime = datetime.now(timezone.utc) - timedelta(weeks=26.0)  # Last 6 months
        eventsHistorySorted = sorted(eventsHistory, key=lambda event: event["time"], reverse=True)
        bigBrotherWatchList = {}

        # Iterate all SME roles
        for wsName, wsDetails in WORKSHOP_INTEREST_LIST.items():
            # Skip all non SME specific role (e.g. newcomer ws)
            if wsDetails["role"] not in SME_ROLES:
                continue

            roleSme = guild.get_role(wsDetails["role"])
            if roleSme is None:
                log.exception(f"Bottasks smeBigBrother: roleSme is None, id='{wsDetails['role']}'.")
                continue

            # Iterate SME holders
            for memberSme in roleSme.members:
                # Search in old
                isWsFound = False
                for event in eventsHistorySorted:  # Newest to oldest
                    eventScheduled = pytz.utc.localize(datetime.strptime(event["time"], TIME_FORMAT))
                    if "workshopInterest" in event and event["workshopInterest"] == wsName and event["authorId"] == memberSme.id and eventScheduled > searchTime:
                        isWsFound = True
                        eventScheduledFormat = discord.utils.format_dt(eventScheduled, style="R")
                        if memberSme.display_name not in bigBrotherWatchList:
                            bigBrotherWatchList[memberSme.display_name] = {roleSme.mention: {"count": 1, "time": eventScheduledFormat}}
                        elif roleSme.mention not in bigBrotherWatchList[memberSme.display_name]:
                            bigBrotherWatchList[memberSme.display_name][roleSme.mention] = {"count": 1, "time": eventScheduledFormat}
                        else:
                            bigBrotherWatchList[memberSme.display_name][roleSme.mention]["count"] += 1


                if not isWsFound:  # No workshop found
                    if memberSme.display_name not in bigBrotherWatchList:
                        bigBrotherWatchList[memberSme.display_name] = {roleSme.mention: {"count": 0, "time": None}}
                    else:
                        bigBrotherWatchList[memberSme.display_name][roleSme.mention] = {"count": 0, "time": None}


        embedsToSend = []
        for person, personDetails in bigBrotherWatchList.items():
            embedDescription = "\n".join([smeRoleMention + ("not hosting in the past 6 months!"*(statistics["count"] == 0)) + (f"hosted {statistics['time']} - host count ({statistics['count']})"*(statistics["count"] != 0)) for smeRoleMention, statistics in personDetails.items()])
            embedsToSend.append(discord.Embed(title=person, color=discord.Color.gold(), description=embedDescription))

        embedTitle = f"SME Activity Report [{('Manual'*manuallyExecuted) + ('Automatic'*(not manuallyExecuted))}]"
        embedDescription = "Here comes an activity report on all individual SMEs"
        if not manuallyExecuted:
            embedDescription += ", reoccuring every 6 months"
        embedDescription += ".\nThis displays one embed for each SME; each row for each SME tag - last hosted workshop and total count."

        if len(embedsToSend) == 0:
            log.warning("Bottasks smeBigBrother: no embeds sent")
            await channelStaffChat.send(discord.Embed(title=embedTitle, color=discord.Color.red(), description="Nothing to send. Contact Snek Lords."))
            return

        embedsToSend.insert(0, discord.Embed(title=embedTitle, color=discord.Color.green(), description=embedDescription))
        for embedChunk in chunkList(embedsToSend, 10):
            log.info("Bottasks smeBigBrother: sending chunk")
            await channelStaffChat.send(embeds=embedChunk)


        # Update next execution time
        with open(REPEATED_MSG_DATE_LOG_FILE) as f:
            msgDateLog = json.load(f)

        # Get datetime for next time in 6 months
        nextTime = Reminders.getFirstDayNextMonth()
        for _ in range(5):
            nextTime = Reminders.getFirstDayNextMonth(nextTime)

        msgDateLog["smeBigBrother"] = datetime.timestamp(nextTime)
        with open(REPEATED_MSG_DATE_LOG_FILE, "w") as f:
            json.dump(msgDateLog, f, indent=4)


    @staticmethod
    async def workshopInterestWipe(guild: discord.Guild) -> None:
        """Wipe workshop interest lists every year."""
        log.info("BotTasks workshopInterestWipe: wiping workshop interest lists")

        # Update next execution time
        with open(REPEATED_MSG_DATE_LOG_FILE) as f:
            msgDateLog = json.load(f)

        # Get datetime for next time in 1 year
        nextTime = Reminders.getFirstDayNextMonth()
        for _ in range(11):
            nextTime = Reminders.getFirstDayNextMonth(nextTime)

        msgDateLog["workshopInterestWipe"] = datetime.timestamp(nextTime)
        with open(REPEATED_MSG_DATE_LOG_FILE, "w") as f:
            json.dump(msgDateLog, f, indent=4)

        # Wipe workshop interest lists
        channelWorkshopInterest = guild.get_channel(WORKSHOP_INTEREST)
        if not isinstance(channelWorkshopInterest, discord.TextChannel):
            log.exception("BotTasks workshopInterestWipe: channelWorkshopInterest not discord.TextChannel")
            return

        with open(WORKSHOP_INTEREST_FILE) as f:
            wsIntFile = json.load(f)

        for wsName in WORKSHOP_INTEREST_LIST.keys():
            wsIntFile[wsName]["members"] = []
        with open(WORKSHOP_INTEREST_FILE, "w") as f:
            json.dump(wsIntFile, f, indent=4)

        # Update embeds
        for wsName in WORKSHOP_INTEREST_LIST.keys():
            try:
                wsIntEmbed = await channelWorkshopInterest.fetch_message(wsIntFile[wsName].get("messageId", 0))
            except Exception:
                log.warning(f"BotTasks workshopInterestWipe: failed to fetch wsIntEmbed '{wsName}' with id '{wsIntFile[wsName].get('messageId', 0)}'")
                continue

            if not isinstance(wsIntEmbed, discord.Message):
                log.warning("BotTasks workshopInterestWipe: wsIntEmbed not discord.Message")
                continue

            try:
                await wsIntEmbed.edit(embed=WorkshopInterest.getWorkshopEmbed(guild, wsName))
            except Exception:
                log.warning(f"BotTasks workshopInterestWipe: failed to edit wsIntEmbed '{wsName}'")

        # Announce wipe in announcements
        channelAnnouncements = guild.get_channel(ANNOUNCEMENTS)
        if not isinstance(channelAnnouncements, discord.abc.GuildChannel):
            log.exception("BotTasks workshopInterestWipe: channelAnnouncements not discord.GuildChannel")
            return

        await channelAnnouncements.send("@everyone", embed=discord.Embed(title="🧻 Workshop Interest Wipe 🧻", description="Happy new years!\nAll workshop interest lists have been wiped. Please re-sign up for any workshops you are interested in.\n\nThis ensures that inactive members are purged off the lists.", color=discord.Color.orange()), allowed_mentions=discord.AllowedMentions.all())


    @tasks.loop(hours=1.0)
    async def oneHourTasks(self) -> None:
        # redditRecruitmentPosts
        if secret.REDDIT_ACTIVE:
            try:
                await self.redditRecruitmentPosts()
            except Exception:
                log.exception(f"Bottasks oneHourTasks: Reddit recruitment posts")

        # smeReminder
        with open(REPEATED_MSG_DATE_LOG_FILE) as f:
            msgDateLog = json.load(f)

        if secret.SME_REMINDER_ACTIVE and ("smeReminder" not in msgDateLog or (datetime.fromtimestamp(msgDateLog["smeReminder"], tz=pytz.utc) < datetime.now(timezone.utc))):
            try:
                await self.smeReminder()
            except Exception:
                log.exception(f"Bottasks oneHourTasks: SME reminder")

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Bottasks oneHourTasks: guild is None")
            return

        # smeBigBrother
        if secret.SME_BIG_BROTHER and ("smeBigBrother" not in msgDateLog or (datetime.fromtimestamp(msgDateLog["smeBigBrother"], tz=pytz.utc) < datetime.now(timezone.utc))):
            try:
                await BotTasks.smeBigBrother(guild, False)
            except Exception:
                log.exception(f"Bottasks oneHourTasks: SME big brother")

        # workshopInterestWipe
        if secret.WORKSHOP_INTEREST_WIPE and "workshopInterestWipe" not in msgDateLog:
            log.info("Bottasks oneHourTasks: workshopInterestWipe not in msgDateLog - set timestamp to 1 Jan next year")
            msgDateLog["workshopInterestWipe"] = datetime(datetime.now(timezone.utc).year+1, 1, 1, 12, 0, 0, 0, tzinfo=pytz.utc).timestamp()
            with open(REPEATED_MSG_DATE_LOG_FILE, "w") as f:
                json.dump(msgDateLog, f, indent=4)
        elif secret.WORKSHOP_INTEREST_WIPE and (datetime.fromtimestamp(msgDateLog["workshopInterestWipe"], tz=pytz.utc) < datetime.now(timezone.utc)):
            try:
                await BotTasks.workshopInterestWipe(guild)
            except Exception:
                log.exception(f"Bottasks oneHourTasks: workshopInterestWipe")

        # checkModUpdates
        if secret.MOD_UPDATE_ACTIVE and ("modUpdates" not in msgDateLog or (datetime.fromtimestamp(msgDateLog["modUpdates"], tz=pytz.utc) < datetime.now(timezone.utc))):
            try:
                await self.checkModUpdates()
            except Exception:
                log.exception(f"Bottasks oneHourTasks: checkModUpdates")

        # clear timesBumped in all wallets
        if secret.CLEAR_BUMP_ACTIVE and ("clearBumpTimes" not in msgDateLog or (datetime.fromtimestamp(msgDateLog["clearBumpTimes"], tz=pytz.utc) < datetime.now(timezone.utc))):
            try:
                await BotTasks.clearBumps(guild)
            except Exception:
                log.exception(f"Bottasks oneHourTasks: clear wallet bumps")


    @tasks.loop(minutes=5)
    async def fiveMinTasks(self) -> None:
        with open(REMINDERS_FILE) as f:
            reminders = json.load(f)

        removalList = []
        updateTimeList = []
        for time, details in reminders.items():
            reminderTime = datetime.fromtimestamp(float(time))
            if reminderTime > datetime.now():
                continue

            ## NEWCOMERS

            # Guild
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("Bottasks fiveMinTasks: guild is None")
                return

            # User
            member = guild.get_member(details["userID"])

            if details["type"] == "newcomer":
                removalList.append(time)

                if member is None:
                    log.debug("Bottasks fiveMinTasks: Newcomer is no longer in the server")
                    continue

                if len(member.roles) > 2:
                    log.debug(f"Bottasks fiveMinTasks: Newcomer already verified '{member}'")
                    continue

                channelWelcome = guild.get_channel(WELCOME)
                if not isinstance(channelWelcome, discord.TextChannel):
                    log.exception("Bottasks fiveMinTasks: channelWelcome not TextChannel")
                    return


                roleRecruitmentTeam = guild.get_role(RECRUITMENT_TEAM)
                if roleRecruitmentTeam is None:
                    log.exception("Bottasks fiveMinTasks: roleRecruitmentTeam is None")
                    return

                hasUserPinged = len([
                    message async for message
                    in channelWelcome.history(limit=100)
                    if message.author.id == member.id and roleRecruitmentTeam in message.role_mentions
                ]) > 0

                if hasUserPinged:
                    continue

                await channelWelcome.send(f"{member.mention} Don't forget to ping @​{roleRecruitmentTeam.name} when you are ready!")
                continue


            ## REMINDERS

            if member is None:
                log.warning("Bottasks fiveMinTasks: member is None")
                removalList.append(time)
                continue

            # Channel
            channel = self.bot.get_channel(details["channelID"])
            if channel is None or not isinstance(channel, discord.TextChannel):
                log.warning("Bottasks fiveMinTasks: channel not TextChannel")
                removalList.append(time)
                continue

            # Embed
            setTime = datetime.fromtimestamp(details["setTime"])
            embed = discord.Embed(title="Reminder", description=details["message"], timestamp=setTime, color=discord.Color.dark_blue())
            embed.set_footer(text="Set")

            # Repeat
            if details["repeat"]:
                embed.set_author(name="Repeated reminder")
                embed.set_footer(text="Next reminder")
                embed.timestamp = datetime.fromtimestamp(float(time)) + timedelta(seconds=details["timedeltaSeconds"])
                updateTimeList.append(time)

            # Link button
            view = discord.ui.View()
            if details["messageID"]:
                view.add_item(discord.ui.Button(
                    label="Go to original message",
                    style=discord.ButtonStyle.link,
                    url=f"https://discord.com/channels/{GUILD_ID}/{details['channelID']}/{details['messageID']}"
                ))

            # Send msg
            pings = re.findall(r"<@&\d+>|<@!?\d+>", details["message"])
            await channel.send(member.mention + (" | " * (len(pings) > 0)) + " ".join(pings), embed=embed, view=view)
            removalList.append(time)


        for updateTime in updateTimeList:
            reminderTime = datetime.fromtimestamp(float(updateTime))
            reminders[updateTime]["setTime"] = datetime.now().timestamp()
            reminders[datetime.timestamp(reminderTime + timedelta(seconds=reminders[updateTime]["timedeltaSeconds"]))] = reminders[updateTime]

        # Update file
        for removal in removalList:
            del reminders[removal]

        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=4)


@discord.app_commands.guilds(GUILD)
class Reminders(commands.GroupCog, name="reminder"):
    """Reminders Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @staticmethod
    def getFirstDayNextMonth(startDate: datetime | None = None) -> datetime:
        if startDate is None:
            startDate = datetime.now(timezone.utc)
        return (startDate.replace(day=1) + timedelta(days=32)).replace(day=1, hour=12, minute=0, second=0, microsecond=0)

    @staticmethod
    def getFutureDate(datetimeDict: dict[str, int | None]) -> datetime:
        """Create future datetime from time period values.

        Parameters:
        datetimeDict (dict[str, int | None]): Keys as time period [year/day/minute] (month is optional), values as None or stringed number.

        Returns:
        datetime: The future date.
        """
        futureDate = now = datetime.now()
        yearsToAdd = datetimeDict.get("years") or 0
        monthsToAdd = datetimeDict.get("months") or 0
        if yearsToAdd or monthsToAdd:
            futureDate = futureDate + relativedelta(years=yearsToAdd, months=monthsToAdd)

        formatTime = lambda t: 0.0 if t is None else t
        futureDate += timedelta(
            weeks = formatTime(datetimeDict["weeks"]),
            days = formatTime(datetimeDict["days"]),
            hours = formatTime(datetimeDict["hours"]),
            minutes = formatTime(datetimeDict["minutes"]),
            seconds = formatTime(datetimeDict["seconds"])
        )
        return futureDate

    @staticmethod
    def filterMatches(matches) -> dict[str, int | None]:
        """Merges multiple time dicts into one, by finding biggest values & adds recurring ones.

        Parameters:
        matches (): List of re.Match.

        Returns:
        dict[str, int | None]: The one dict.
        """
        totalValues: dict[str, int | None] = {}
        for match in matches:
            for key, value in match.groupdict().items():
                if key not in totalValues or totalValues[key] is None:
                    totalValues[key] = None if value is None else int(value)
                elif isinstance(totalValues[key], int) and value is not None:
                    totalValues[key] += int(value)
        return totalValues

    def parseRelativeTime(self, time: str) -> datetime | None:
        """Parses raw str relative time into datetime object.

        Parameters:
        time (str): Unparsed relative time.

        Returns:
        datetime | None: DT object if time could be parsed, or None if unparsable.
        """
        timeStrip = time.strip()
        shortTimeRegex = r"(?P<years>\d+(?=y))?(?P<weeks>\d+(?=w))?(?P<days>\d+(?=d))?(?P<hours>\d+(?=h))?(?P<minutes>\d+(?=m))?(?P<seconds>\d+(?=s))?"
        timeDict = self.filterMatches(re.finditer(shortTimeRegex, timeStrip, re.I))

        timeFound = lambda times: len([value for value in times.values() if value is not None]) > 0

        # Short version of relative time inputted (e.g. "1y9m11wd99h111m999s")
        if timeFound(timeDict):
            return self.getFutureDate(timeDict)

        # Long version of relative time inputted (e.g. "99 minutes")
        longTimeRegex = r"(?P<years>\d+(?=\s?years?))?(?P<months>\d+(?=\s?months?))?(?P<weeks>\d+(?=\s?weeks?))?(?P<days>\d+(?=\s?days?))?(?P<hours>\d+(?=\s?hours?))?(?P<minutes>\d+(?=\s?minutes?))?(?P<seconds>\d+(?=\s?seconds?))?"
        timeDict = self.filterMatches(re.finditer(longTimeRegex, timeStrip, re.I))
        if timeFound(timeDict):
            return self.getFutureDate(timeDict)

        # timeFound is False on both accounts
        return None


    @discord.app_commands.command(name="set")
    @discord.app_commands.describe(
        when = "When to be reminded of something.",
        text = "What to be reminded of.",
        repeat = "If the reminder repeats."
    )
    async def reminderSet(self, interaction: discord.Interaction, when: str, text: str | None = None, repeat: bool | None = None) -> None:
        """Sets a reminder to remind you of something at a specific time."""
        if when.strip() == "":
            await interaction.response.send_message(embed=discord.Embed(title="❌ Input e.g. 'in 5 minutes' or '1 hour'.", color=discord.Color.red()), ephemeral=True, delete_after=10.0)
            return

        reminderTime = self.parseRelativeTime(when)
        if reminderTime is None:
            await interaction.response.send_message(embed=discord.Embed(title="❌ Could not parse the given time.", color=discord.Color.red()), ephemeral=True, delete_after=10.0)
            return

        if repeat and ((reminderTime - datetime.now()) < timedelta(minutes=1)):
            await interaction.response.send_message(embed=discord.Embed(title="❌ I will not spam-remind you.", color=discord.Color.red()), ephemeral=True, delete_after=10.0)
            return

        if interaction.channel is None:
            log.exception("BotTasks reminderSet: interaction.channel is None")
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid channel.", color=discord.Color.red()), ephemeral=True, delete_after=10.0)
            return

        with open(REMINDERS_FILE) as f:
            reminders = json.load(f)

        reminders[datetime.timestamp(reminderTime)] = {
            "type": "reminder",
            "userID": interaction.user.id,
            "channelID": interaction.channel.id,
            "messageID": None,
            "message": text or "",
            "setTime": datetime.timestamp(datetime.now()),
            "timedeltaSeconds": (reminderTime - datetime.now()).total_seconds(),
            "repeat": repeat or False
        }

        embedDescription = "I will remind you " + discord.utils.format_dt(reminderTime, style="R") + (f"\n{text}" if text else "")
        embed=discord.Embed(description=embedDescription, color=discord.Color.green())
        embed.set_author(name=interaction.user, icon_url=interaction.user.display_avatar)

        await interaction.response.send_message(embed=embed)
        messageInteraction = await interaction.original_response()
        reminders[datetime.timestamp(reminderTime)]["messageID"] = messageInteraction.id
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=4)

    @discord.app_commands.command(name="list")
    async def reminderList(self, interaction: discord.Interaction) -> None:
        """Shows the currently running reminders."""
        with open(REMINDERS_FILE) as f:
            reminders = json.load(f)

        embed = discord.Embed(title="Reminders", color=discord.Color.dark_blue())

        desc = ""
        reminderCount = 0
        for reminderTime, reminderDetails in reminders.items():
            if reminderDetails["userID"] == interaction.user.id:
                desc += discord.utils.format_dt(datetime.fromtimestamp(float(reminderTime), tz=pytz.utc)) + ":\n"
                desc += reminderDetails["message"] + "\n\n"
                reminderCount += 1
        embed.description = desc[:DISCORD_LIMITS["message_embed"]["embed_description"]]
        embed.set_footer(text=f"{reminderCount} reminder{'s' * (reminderCount > 1)}")

        if reminderCount == 0:
            await interaction.response.send_message("No reminders currently active.", ephemeral=True, delete_after=10.0)
            return

        await interaction.response.send_message(embed=embed)


    @discord.app_commands.command(name="clear")
    async def reminderClear(self, interaction: discord.Interaction) -> None:
        """Clears all reminders you have set."""
        with open(REMINDERS_FILE) as f:
            reminders = json.load(f)

        # Find user reminders
        removeList = []
        for reminderTime, reminderDetails in reminders.items():
            if reminderDetails["userID"] == interaction.user.id:
                removeList.append(reminderTime)

        if len(removeList) == 0:
            await interaction.response.send_message("No reminders currently active.", ephemeral=True, delete_after=10.0)
            return

        # Remove reminders
        for remove in removeList:
            del reminders[remove]
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=4)

        await interaction.response.send_message(f"{len(removeList)} reminder{'s' * (len(removeList) > 1)} removed.")

    async def reminderDeleteAutocomplete(self, interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
        """Slash command autocomplete when removing reminders."""
        with open(REMINDERS_FILE) as f:
            reminders = json.load(f)

        # Find user reminders
        userReminders = []
        for reminderTime, reminderDetails in reminders.items():
            if reminderDetails["userID"] == interaction.user.id:
                userReminders.append({
                    "name": datetime.fromtimestamp(float(reminderTime), tz=pytz.utc).strftime("%Y-%m-%d %H:%M") + f": {reminderDetails['message'][:20]}",
                    "value": reminderTime
                })

        if len(userReminders) == 0:
            return [discord.app_commands.Choice(name="No reminders currently active.", value="-")]
        else:
            return [
                discord.app_commands.Choice(name=reminder["name"], value=reminder["value"])
                for reminder in userReminders if current.lower() in reminder["name"].lower()
            ][:DISCORD_LIMITS["interactions"]["autocomplete_choices"]]

    @discord.app_commands.command(name="delete")
    @discord.app_commands.autocomplete(reminder=reminderDeleteAutocomplete)
    async def reminderDelete(self, interaction: discord.Interaction, reminder: str) -> None:
        """Delete a reminder."""
        if reminder == "-":
            await interaction.response.send_message("No reminders currently active.", ephemeral=True, delete_after=10.0)
            return

        with open(REMINDERS_FILE) as f:
            reminders = json.load(f)

        embed = discord.Embed(
            title="Reminder Deleted",
            description=reminders[reminder]["message"],
            color=discord.Color.red(),
            timestamp=datetime.fromtimestamp(float(reminder), tz=pytz.utc)
        )
        embed.set_footer(text="Reminder set")

        # Remove requested reminder
        del reminders[reminder]
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=4)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotTasks(bot))
    await bot.add_cog(Reminders(bot))
