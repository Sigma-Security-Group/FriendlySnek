import secret, os, random, json, re
import asyncpraw, requests, pytz  # type: ignore

from datetime import datetime, timezone, timedelta
from dateutil.parser import parse as datetimeParse  # type: ignore
from bs4 import BeautifulSoup as BS  # type: ignore
from .workshopInterest import WORKSHOP_INTEREST_LIST  # type: ignore

from discord import Embed, Color
from discord.ext import commands, tasks  # type: ignore

from constants import *
from __main__ import log, cogsReady
if secret.DEBUG:
    from constants.debug import *


MOD_IDS = [1673456286, 623475643, 2041057379, 463939057, 773131200, 773125288, 884966711, 2174495332, 1376867375, 2522638637, 2459780823, 751965892, 2904714255, 1726184748, 2372036642, 2791403093, 2242548109, 450814997, 837729515, 897295039, 2447965207, 1643720957, 1375890861, 583496184, 583544987, 2264863911, 1638341685, 686802825, 2467590475, 333310405, 2811760677, 1284600102, 1224892496, 2941986336, 1745501605, 1291778160, 1883956552, 2020940806, 1188303655, 2140288272, 1858075458, 1858070328, 1808238502, 1862208264, 929396506, 1845100804, 930903722, 2814015609, 2801060088, 2585749287, 1770265310, 1423583812, 1397683809, 843425103, 843593391, 843632231, 843577117, 2466229756, 2013446344, 2264836821, 699630614, 1187306764, 2892020195, 1623498241, 2266710560, 2397371875, 2397360831, 2397376046, 2377329491, 1703187116, 1926513010, 1963617777, 1251859358, 1779063631, 2018593688]  # Just take it from the modpack HTML, ez clap (Updated: 17th March 2023)


class BotTasks(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("BotTasks"), flush=True)
        cogsReady["bottasks"] = True

        if not self.checkModUpdates.is_running():
            self.checkModUpdates.start()

        if not self.oneHourTasks.is_running():
            self.oneHourTasks.start()

        if not self.fiveMinTasks.is_running():
            self.fiveMinTasks.start()


    @tasks.loop(minutes=30.0)
    async def checkModUpdates(self) -> None:
        """Checks mod updates, pings hampters if detected."""
        output = []
        for modID in MOD_IDS:
            # Fetch mod
            response = requests.get(url=CHANGELOG_URL.format(modID))

            # Parse HTML
            soup = BS(response.text, "html.parser")

            # Mod Title
            name = soup.find("div", class_="workshopItemTitle")
            if name is None:
                continue
            name = name.string

            # Find latest update
            update = soup.find("div", class_="detailBox workshopAnnouncement noFooter")


            # Loop paragraphs in latest update
            for paragraph in update.descendants:
                stripTxt = str(paragraph).strip()
                if not stripTxt:  # Ignore empty shit
                    continue

                # Find update time
                elif stripTxt.startswith("Update: "):
                    date = stripTxt
                    break  # dw bout shit after this


            # Parse time to datetime
            dateTimeParse = datetimeParse(date[len("Update: "):].replace("@ ", ""))

            # Convert it into UTC (shitty arbitrary code)
            utcTime = pytz.UTC.localize(dateTimeParse + timedelta(hours=7))  # Change this if output time is wrong: will cause double ping

            # Current time
            now = pytz.UTC.localize(datetime.utcnow())

            # Check if update is new
            if utcTime > (now - timedelta(minutes=29.0, seconds=59.0)):  # Relative time checking
                log.debug(f"Arma mod update: {name}")
                output.append({
                    "modID": modID,
                    "name": name,
                    "datetime": utcTime
                })


        if len(output) > 0:
            # Create message
            guild = self.bot.get_guild(GUILD_ID)
            if guild is None:
                log.exception("checkModUpdates: guild is None")
                return

            changelog = await guild.fetch_channel(CHANGELOG)
            if not isinstance(changelog, discord.channel.TextChannel):
                log.exception("checkModUpdates: changelog channel is not discord.channel.TextChannel")
                return

            hampter = guild.get_role(SERVER_HAMSTER)
            if hampter is None:
                log.exception("checkModUpdates: Hampter role is None")
                return

            # Each mod update will be sent in a separate message
            msgContent: str | None = hampter.mention + (f" ({len(output)})" if len(output) > 1 else "") + "\n\n"  # Ping for first message
            for mod in output:
                await changelog.send(msgContent, embed=Embed(title=mod["name"], url=CHANGELOG_URL.format(mod['modID']), timestamp=mod["datetime"], color=Color.dark_blue()))
                msgContent = None  # Only 1 ping



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
        async for submission in submissions:  # Check the latest submission [break]
            subCreated = datetime.fromtimestamp(submission.created_utc).replace(tzinfo=timezone.utc)  # Latest post timestamp
            break

        if datetime.now().replace(tzinfo=timezone.utc) < (subCreated + timedelta(weeks=1.0, minutes=30.0)):  # Dont post if now is less than ~1 week than last post
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
            log.warning("No Recruiting flair found!")

        # Submission details
        propagandaPath = r"constants/SSG_Propaganda"
        post = {
            "Title": "[A3][18+][Recruiting][Worldwide] | Casual-Attendance, PMC Themed Unit | Sigma Security Group is now Recruiting!",
            "FlairID": flairID,
            "Description": """About Us:

- **Flexibility**: Sigma has no formal sign-up process, no commitments, and offers instruction on request. Certification in specialty roles is available and run by professionals in the field.

- **Activity**: We regularly host quality operations, and aim to provide content with a rich story and balanced flow/combat in order to keep our players interested.

- **Professionalism**: Operations are cooperative Zeus curated events, built and run by dedicated community members. Roleplay is encouraged, tactics are refined, and immersion is achieved.

- **Immersion**: Mods we use on the server are focused on expanding the default feature set and enhancing immersion. Our entire mod collection is found on the Arma 3 Steam Workshop.

Requirements:

- **Respect**: We are looking to play with respectful, patient members who we can trust and have a laugh with.

- **Community**: We don't want strangers, we ask members to be social and contribute in their own way. Community management roles are on a volunteer basis.

- **Maturity**: Players must be easy going, know when to be serious, and be willing to learn and improve alongside their fellow Operators. You must be at least age 18+ to join.

- **Communication**: Members must have a functioning microphone and use it during all operations.

Join Us:

- Would you like to know more? Join the **[Discord Server](https://discord.gg/KtcVtfjAYj)** for more information."""
        }

        """ submit_image disabled temp cuz devs haven't released new version which fixes image_path error """
        # Send submission with random image
        submission = await sub.submit_image(title=post["Title"], image_path=f"{propagandaPath}/{random.choice(os.listdir(propagandaPath))}", flair_id=post["FlairID"])
        await submission.reply(post["Description"])

        log.info("Reddit recruitment posted!")

        armaDisc = self.bot.get_channel(ARMA_DISCUSSION)
        if not isinstance(armaDisc, discord.channel.TextChannel):
            log.exception("checkModUpdates: Arma Discussion channel is not discord.channel.TextChannel")
            return

        await armaDisc.send(f"Reddit recruitment post published, go upvote it!\nhttps://www.reddit.com{submission.permalink}")

    def getPingString(self, rawRole: int | tuple) -> str | None:
        """Generate a ping string from role id(s).

        Parameters:
        rawRole (int | tuple): One role id or tuple with role ids.

        Returns:
        str | None: str with pings or None if failed.
        """
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Bottasks getSmePing: guild is None")
            return None

        if isinstance(rawRole, int):
            role = guild.get_role(rawRole)
            if role is None:
                log.exception("Bottasks smeReminder: role is None")
                return None
            return role.mention

        roles = [guild.get_role(roleId) for roleId in rawRole]
        if None in roles:
            log.exception(f"Bottasks getSmePing: roleId {roles[roles.index(None)]} returns None")
            return None
        return " ".join([role.mention for role in roles])  # type: ignore

    async def smeReminder(self) -> None:
        """Reminds SMEs if they haven't hosten in the required time."""
        utcNow = datetime.utcnow()

        if utcNow.day != 1 or utcNow.hour != 0:  # Only execute function on 1st day of month around midnight UTC
            return

        with open(EVENTS_HISTORY_FILE) as f:
            eventsHistory = json.load(f)
        with open(EVENTS_FILE) as f:
            events = json.load(f)

        smeCorner = self.bot.get_channel(SME_CORNER)
        if not isinstance(smeCorner, discord.TextChannel):
            log.exception("Bottasks smeReminder: smeCorner is not discord.TextChannel")
            return

        pingEmbed = Embed(
            title="Workshop Reminder",
            color=Color.orange()
        )

        workshopsInTimeFrame = []
        for wsName, wsDetails in WORKSHOP_INTEREST_LIST.items():
            wsScheduled = False
            # Check for scheduled events
            for event in events:
                if "workshopInterest" in event and event["workshopInterest"] == wsName:
                    wsScheduled = True
                    workshopsInTimeFrame.append(wsName)
                    break

            if wsScheduled is True:
                continue

            # Check for past events
            for event in eventsHistory[::-1]:  # Newest to oldest
                if "workshopInterest" in event and event["workshopInterest"] == wsName:

                    # Send reminder if latest workshop was scheduled more than 60 days ago
                    if datetime.strptime(event["time"], TIME_FORMAT) < (datetime.now() - timedelta(days=60)):
                        eventScheduled = pytz.utc.localize(datetime.strptime(event['time'], TIME_FORMAT))
                        pingEmbed.description = f"Last `{wsName}` event you had (`{event['title']}`) was at {discord.utils.format_dt(eventScheduled, style='F')} ({discord.utils.format_dt(eventScheduled, style='R')}).\nPlease host at least every 2 months to give everyone a chance to cert!"
                        await smeCorner.send(self.getPingString(wsDetails["role"]), embed=pingEmbed)
                    else:
                        workshopsInTimeFrame.append(wsName)
                    break

            else:  # No workshop found
                pingEmbed.description = f"Last `{wsName}` event you had couldn't be found in my logs.\nPlease host at least every 2 months to give everyone a chance to cert!"
                await smeCorner.send(self.getPingString(wsDetails["role"]), embed=pingEmbed)

        if len(workshopsInTimeFrame) > 0:
            await smeCorner.send(":clap: Good job for keeping up the hosting " + ", ".join([f"`{wsName}`" for wsName in workshopsInTimeFrame]) + "! :clap:")

    @tasks.loop(hours=1.0)
    async def oneHourTasks(self) -> None:
        await self.redditRecruitmentPosts()
        await self.smeReminder()



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
                log.warning("bottasks fiveMinTasks: guild is None")
                return

            # User
            member = guild.get_member(details["userID"])

            if details["type"] == "newcomer":
                removalList.append(time)

                if member is None:
                    log.debug("Newcomer is no longer in the server")
                    continue

                if len(member.roles) > 2:
                    log.debug(f"Newcomer already verified: {member}")
                    continue

                channelWelcome = guild.get_channel(WELCOME)
                if not isinstance(channelWelcome, discord.TextChannel):
                    log.warning("bottasks fiveMinTasks: welcomeChannel is not TextChannel")
                    return


                roleUnitStaff = guild.get_role(UNIT_STAFF)
                roleAdvisor = guild.get_role(ADVISOR)
                if roleUnitStaff is None or roleAdvisor is None:
                    log.warning("bottasks fiveMinTasks: roleUnitStaff or roleAdvisor is None")
                    return

                hasUserPinged = len([
                    message async for message
                    in channelWelcome.history(limit=100)
                    if message.author.id == member.id and (str(roleUnitStaff.id) in message.content or str(roleAdvisor.id) in message.content)
                ]) > 0

                if hasUserPinged is True:
                    continue

                await channelWelcome.send(f"{member.mention} Don't forget to ping @​{roleUnitStaff.name} and @​{roleAdvisor.name} when you are ready!")
                continue


            ## REMINDERS

            if member is None:
                log.warning("bottasks fiveMinTasks: user is None")
                removalList.append(time)
                continue

            # Channel
            channel = self.bot.get_channel(details["channelID"])
            if channel is None or not isinstance(channel, discord.TextChannel):
                log.warning("bottasks fiveMinTasks: channel not TextChannel")
                removalList.append(time)
                continue

            # Embed
            setTime = datetime.fromtimestamp(details["setTime"])
            embed = Embed(title="Reminder", description=details["message"], timestamp=setTime, color=Color.dark_blue())
            embed.set_footer(text="Set")

            # Repeat
            if details["repeat"] is True:
                embed.set_author(name="Repeated reminder")
                embed.set_footer(text="Next reminder")
                embed.timestamp = datetime.fromtimestamp(float(time)) + timedelta(seconds=details["timedeltaSeconds"])
                updateTimeList.append(time)

            # Send msg
            pings = re.findall(r"<@&\d+>|<@!?\d+>", details["message"])
            await channel.send(member.mention + (" | " * (len(pings) > 0)) + " ".join(pings), embed=embed)
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



class Reminders(commands.GroupCog, name="reminder"):
    """Reminders Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @staticmethod
    def getFutureDate(datetimeDict: dict[str, int | None]) -> datetime:
        """Create future datetime from time period values.

        Parameters:
        datetimeDict (dict[str, int | None]): Keys as time period [year/day/minute] (month is optional), values as None or stringed number.

        Returns:
        datetime: The future date.
        """
        futureDate = now = datetime.now()
        if datetimeDict["years"] is not None:
            yearsToAdd = datetimeDict["years"]
            try:
                futureDate = datetime(now.year + yearsToAdd, now.month, now.day)
            except ValueError:
                futureDate = datetime(now.year + yearsToAdd, now.month + 1, 1)

            futureDate = futureDate.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

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
        if timeFound(timeDict) is True:
            return self.getFutureDate(timeDict)

        # Long version of relative time inputted (e.g. "99 minutes")
        longTimeRegex = r"(?P<years>\d+(?=\s?years?))?(?P<months>\d+(?=\s?months?))?(?P<weeks>\d+(?=\s?weeks?))?(?P<days>\d+(?=\s?days?))?(?P<hours>\d+(?=\s?hours?))?(?P<minutes>\d+(?=\s?minutes?))?(?P<seconds>\d+(?=\s?seconds?))?"
        timeDict = self.filterMatches(re.finditer(longTimeRegex, timeStrip, re.I))
        if timeFound(timeDict) is True:
            return self.getFutureDate(timeDict)

        # timeFound is False on both accounts
        return None


    @discord.app_commands.command(name="set")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.describe(
        when = "When to be reminded of something.",
        text = "What to be reminded of.",
        repeat = "If the reminder repeats."
    )
    async def reminderSet(self, interaction: discord.Interaction, when: str, text: str | None = None, repeat: bool | None = None) -> None:
        """Sets a reminder to remind you of something at a specific time."""
        if when.strip() == "":
            await interaction.response.send_message(embed=Embed(title="❌ Input e.g. 'in 5 minutes' or '1 hour'.", color=Color.red()), ephemeral=True, delete_after=10.0)
            return

        reminderTime = self.parseRelativeTime(when)
        if reminderTime is None:
            await interaction.response.send_message(embed=Embed(title="❌ Could not parse the given time.", color=Color.red()), ephemeral=True, delete_after=10.0)
            return

        if repeat is True and ((reminderTime - datetime.now()) < timedelta(minutes=1)):
            await interaction.response.send_message(embed=Embed(title="❌ I will not spam-remind you.", color=Color.red()), ephemeral=True, delete_after=10.0)
            return

        if interaction.channel is None:
            log.warning("bottasks reminderSet: interaction.channel is None")
            await interaction.response.send_message(embed=Embed(title="❌ Invalid channel.", color=Color.red()), ephemeral=True, delete_after=10.0)
            return

        with open(REMINDERS_FILE) as f:
            reminders = json.load(f)

        reminders[datetime.timestamp(reminderTime)] = {
            "type": "reminder",
            "userID": interaction.user.id,
            "channelID": interaction.channel.id,
            "message": text or "reminder",
            "setTime": datetime.timestamp(datetime.now()),
            "timedeltaSeconds": (reminderTime - datetime.now()).total_seconds(),
            "repeat": repeat or False
        }
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=4)

        embed=Embed(description=f"I will remind you {discord.utils.format_dt(reminderTime, style='R')}", color=Color.green())
        embed.set_author(name=interaction.user, icon_url=interaction.user.display_avatar)
        await interaction.response.send_message(embed=embed)


    @discord.app_commands.command(name="list")
    @discord.app_commands.guilds(GUILD)
    async def reminderList(self, interaction: discord.Interaction) -> None:
        """Shows the currently running reminders."""
        with open(REMINDERS_FILE) as f:
            reminders = json.load(f)

        embed = Embed(title="Reminders", color=Color.dark_blue())

        desc = ""
        reminderCount = 0
        for reminderTime, reminderDetails in reminders.items():
            if reminderDetails["userID"] == interaction.user.id:
                desc += discord.utils.format_dt(datetime.fromtimestamp(float(reminderTime), tz=pytz.utc)) + ":\n"
                desc += reminderDetails["message"] + "\n\n"
                reminderCount += 1
        embed.description = desc[:4096]
        embed.set_footer(text=f"{reminderCount} reminder{'s' * (reminderCount > 1)}")

        if reminderCount == 0:
            await interaction.response.send_message("No reminders currently active.", ephemeral=True, delete_after=10.0)
            return

        await interaction.response.send_message(embed=embed)


    @discord.app_commands.command(name="clear")
    @discord.app_commands.guilds(GUILD)
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
            ][:25]

    @discord.app_commands.command(name="delete")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.autocomplete(reminder=reminderDeleteAutocomplete)
    async def reminderDelete(self, interaction: discord.Interaction, reminder: str) -> None:
        """Delete a reminder."""
        if reminder == "-":
            await interaction.response.send_message("No reminders currently active.", ephemeral=True, delete_after=10.0)
            return

        with open(REMINDERS_FILE) as f:
            reminders = json.load(f)

        embed = Embed(
            title="Reminder Deleted",
            description=reminders[reminder]["message"],
            color=Color.red(),
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
