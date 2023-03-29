import secret, os, random
import asyncpraw, requests, pytz  # type: ignore

from datetime import datetime, timezone, timedelta
from dateutil.parser import parse as datetimeParse  # type: ignore
from bs4 import BeautifulSoup as BS  # type: ignore

from discord import utils
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

        if not self.redditRecruitmentPosts.is_running():
            self.redditRecruitmentPosts.start()


    @tasks.loop(minutes=30.0)
    async def checkModUpdates(self) -> None:
        try:
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

                    # Find update changelog
                    #elif stripTxt.startswith("<p id=\""):  # THE changelog, dw bout shit after it
                    #    chl = stripTxt
                    #    break


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

                message = hampter.mention + (f" ({len(output)})" if len(output) > 1 else "") + "\n\n"  # Ping for first message
                for mod in output:
                    # Title + Date
                    message += f"{mod['name']}\n"

                    # Timestamp
                    message += utils.format_dt(mod["datetime"], style="F") + "\n"

                    # Link
                    message += f"<{CHANGELOG_URL.format(mod['modID'])}>"

                    # Each new mod update will be sent in a separate message
                    await changelog.send(message)
                    message = ""

        except Exception as e:
            log.exception(e)


    @tasks.loop(hours=1.0)
    async def redditRecruitmentPosts(self) -> None:
        try:
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
        except Exception as e:
            log.exception(e)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotTasks(bot))