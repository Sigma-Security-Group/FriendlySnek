import os, json, re, discord, logging

from discord.ext import commands  # type: ignore

from cogs.staff import Staff
from secret import DEBUG
from constants import *
if DEBUG:
    from constants.debug import *

# Maybe move this to constants.py
WORKSHOP_INTEREST_LIST: dict[str, dict[str, str | int | tuple]] = {
    "Naval": {
        "emoji": "⚓",
        "role": SME_NAVAL,
        "description": "\"But tbh the naval sme tag was mostly a joke\" - Police"
    },
    "Artillery": {
        "emoji": "💥",
        "role": SME_ARTILLERY,
        "description": "Learn to drop big shells on targets far away."
    },
    "Mechanised": {
        "emoji": "🛡️",
        "role": SME_MECHANISED,
        "description": "A short course on driving, gunning, and commanding a 6.21 million dollar reason the heavy weapons guy is useless."
    },
    "UAV": {
        "emoji": "🛩️",
        "role": SME_UAV,
        "description": "Operators of Unmanned Air Vehicles (UAVs) remotely control drones used for ISR and light CAS."
    },
    "Rotary Wing": {
        "emoji": "🚁",
        "role": SME_RW_PILOT,
        "description": "Learn to fly helicopters and provide transport and close air support."
    },
    "Fixed Wing": {
        "emoji": "✈️",
        "role": SME_FW_PILOT,
        "description": "Learn how to fly high-speed fighter jets, and obliderate the enemy! 💥"
    },
    "JTAC": {
        "emoji": "📡",
        "role": SME_JTAC,
        "description": "Learn how to direct close air support."
    },
    "Medic": {
        "emoji": "💉",
        "role": SME_MEDIC,
        "description": "Learn how to administer combat aid to wounded personnel in a timely and effective manner."
    },
    "Marksman": {
        "emoji": "🎯",
        "role": SME_MARKSMAN,
        "description": "Learn how to shoot big bullet far."
    },
    "Heavy Weapons": {
        "emoji": "💣",
        "role": SME_HEAVY_WEAPONS,
        "description": "Learn how to efficiently operate as a machine gun crew, use grenade launchers, and shoot cretins out of shitboxes (AT & AA)."
    },
    "Leadership": {
        "emoji": "🫀",  # Anatomical heart
        "role": (UNIT_STAFF, ADVISOR, STRATEGIST),
        "description": "Learn how to lead a team, squad or platoon in Sigma Security Group."
    },
    "Rifleman": {
        "emoji": "🔫",
        "role": (UNIT_STAFF, ADVISOR, STRATEGIST, OPERATOR),
        "description": "Become a more educated rifleman - a complementary newcomer workshop."
    },
    "Newcomer": {
        "emoji": "🐣",
        "role": (UNIT_STAFF, ADVISOR, OPERATOR, STRATEGIST),
        "description": "Learn what you need to know before attending an operation in Sigma Security Group."
    },
}

log = logging.getLogger("FriendlySnek")

class WorkshopInterest(commands.Cog):
    """Workshop Interest Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("WorkshopInterest"))
        self.bot.cogsReady["workshopInterest"] = True

        isUpdateChannel = False

        if not os.path.exists(WORKSHOP_INTEREST_FILE):
            isUpdateChannel = True
            workshopInterest = {}
            for name in WORKSHOP_INTEREST_LIST.keys():
                workshopInterest[name] = {
                    "members": [],
                    "messageId": 0
                }
            with open(WORKSHOP_INTEREST_FILE, "w") as f:
                json.dump(workshopInterest, f, indent=4)

        else:
            with open(WORKSHOP_INTEREST_FILE) as f:
                wsIntFile = json.load(f)

            # Mismatch in file/dict
            mismatches = set(WORKSHOP_INTEREST_LIST) - set(wsIntFile)
            if mismatches:
                isUpdateChannel = True
                for mismatch in mismatches:
                    wsIntFile[mismatch] = {
                        "members": [],
                        "messageId": 0
                    }
                with open(WORKSHOP_INTEREST_FILE, "w") as f:
                    json.dump(wsIntFile, f, indent=4)


        if isUpdateChannel:
            await self.updateChannel()


    async def updateChannel(self) -> None:
        """Updates the interest channel with all messages.

        Parameters:
        None.

        Returns:
        None.
        """
        log.info("WSINT updateChannel: updating workshop interest channel")
        wsIntChannel = self.bot.get_channel(WORKSHOP_INTEREST)
        if not isinstance(wsIntChannel, discord.TextChannel):
            log.exception("WSINT updateChannel: wsIntChannel not discord.TextChannel")
            return

        await wsIntChannel.purge(limit=None, check=lambda message: message.author.id in FRIENDLY_SNEKS)

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("WSINT updateChannel: guild is None")
            return

        with open(WORKSHOP_INTEREST_FILE) as f:
            wsIntFile = json.load(f)

        for workshopName in WORKSHOP_INTEREST_LIST.keys():
            # Fetch embed
            embed = self.getWorkshopEmbed(guild, workshopName)

            # Do button stuff
            view = discord.ui.View(timeout=None)
            buttons = (
                WorkshopInterestButton(custom_id="workshopinterest_add", row=0, label="Interested", style=discord.ButtonStyle.success),
                WorkshopInterestButton(custom_id="workshopinterest_remove", row=0, label="Not Interested", style=discord.ButtonStyle.danger)
            )
            for button in buttons:
                view.add_item(item=button)

            msg = await wsIntChannel.send(embed=embed, view=view)

            # Set embed messageId - used for removing people once workshop is done
            wsIntFile[workshopName]["messageId"] = msg.id

        with open(WORKSHOP_INTEREST_FILE, "w", encoding="utf-8") as f:
            json.dump(wsIntFile, f, indent=4)


    @staticmethod
    def getWorkshopEmbed(guild: discord.Guild, workshopName: str) -> discord.Embed:
        """Generates an embed from the given workshop.

        Parameters:
        guild (discord.Guild): The target guild.
        workshopName (str): The workshop name.

        Returns:
        discord.Embed: The generated embed.
        """
        embed = discord.Embed(title=f"{WORKSHOP_INTEREST_LIST[workshopName]['emoji']} {workshopName}", description=WORKSHOP_INTEREST_LIST[workshopName]["description"], color=discord.Color.dark_blue())

        with open(WORKSHOP_INTEREST_FILE) as f:
            workshopInterest = json.load(f)
            removedMember = False

        # Get the interested member's name. If they aren't found, remove them
        interestedMembers = ""
        membersCleaned = []
        for memberID in workshopInterest[workshopName]["members"]:
            member = guild.get_member(memberID)
            if member is not None:
                membersCleaned.append(memberID)
                interestedMembers += member.display_name + "\n"
            else:
                removedMember = True

        if removedMember:
            workshopInterest[workshopName]["members"] = membersCleaned
            with open(WORKSHOP_INTEREST_FILE, "w", encoding="utf-8") as f:
                json.dump(workshopInterest, f, indent=4)

        if interestedMembers == "":
            interestedMembers = "-"
            lenInterested = 0
        else:
            lenInterested = len(interestedMembers.strip().split('\n'))

        embed.add_field(name=f"Interested People ({lenInterested})", value=interestedMembers)
        # 1 discord.Role as SME
        if (wsRole := WORKSHOP_INTEREST_LIST[workshopName]["role"]) and isinstance(wsRole, int):
            wsIntRole = guild.get_role(wsRole)
            if wsIntRole is None:
                raise ValueError("WSINT getWorkshopEmbed: wsIntRole is None")

            smes = [sme.display_name for sme in wsIntRole.members]
            if smes:
                embed.set_footer(text=f"SME{'s' * (len(smes) > 1)}: {', '.join(smes)}")

            else:  # No SME
                embed.set_footer(text=f"No SMEs")

        # >1 discord.Role as SME
        elif isinstance(wsRole, tuple):
            smeroles = [sme.name for role in wsRole if (sme := guild.get_role(role)) is not None]
            embed.set_footer(text=f"SME roles: {', '.join(smeroles)}")

        return embed


    @commands.command(name="clean-specific-workshop-interest-list")
    @commands.has_any_role(*CMD_LIMIT_CLEANWSINTEREST)
    async def cleanSpecificWorkshopInterestList(self, ctx: commands.Context, worskhopListName: str = commands.parameter(description="Name of targeted workshop"), member: str = commands.parameter(default="", description="Optional target member")) -> None:
        """Clear specific workshop interest list, no confirmation. Can remove specific member if supplied."""
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("WSINT cleanSpecificWorkshopInterestList: ctx.guild not discord.Guild")
            return

        channelWSINT = self.bot.get_channel(WORKSHOP_INTEREST)
        if not isinstance(channelWSINT, discord.TextChannel):
            log.exception("WSINT cleanSpecificWorkshopInterestList: channelWSINT not discord.TextChannel")
            return


        with open(WORKSHOP_INTEREST_FILE) as f:
                workshopInterest = json.load(f)

        # Find workshop
        for workshop in WORKSHOP_INTEREST_LIST.keys():
            if worskhopListName.lower() == workshop.lower():

                # If specific member specified
                if member:
                    targetMember = Staff._getMember(member, ctx.guild)
                    if targetMember is None:
                        await ctx.send(f"No member found for search term: `{member}`")
                        return

                    for signupMember in workshopInterest[workshop]["members"]:
                        if signupMember == targetMember.id:
                            workshopInterest[workshop]["members"].remove(targetMember.id)

                            with open(WORKSHOP_INTEREST_FILE, "w") as f:
                                json.dump(workshopInterest, f, indent=4)

                            msg = await channelWSINT.fetch_message(workshopInterest[workshop]["messageId"])
                            try:
                                await msg.edit(embed=self.getWorkshopEmbed(ctx.guild, workshop))
                            except Exception as e:
                                log.exception(f"{ctx.author.id} [{ctx.author.display_name}]")

                            await ctx.send(embed=discord.Embed(title="✅ Removed user", description=f"Removed user {targetMember.mention} (`{targetMember.id}`) from the workshop `{workshop}` interest list.", color=discord.Color.green()))
                            return
                    else:
                        await ctx.send(embed=discord.Embed(title="❌ Invalid member", description=f"Could not find member {targetMember.mention} (`{targetMember.id}`) in the workshop interest list.", color=discord.Color.red()))
                        return

                # Clean whole workshop
                else:
                    workshopInterest[workshop]["members"] = []
                    with open(WORKSHOP_INTEREST_FILE, "w") as f:
                        json.dump(workshopInterest, f, indent=4)

                    msg = await channelWSINT.fetch_message(workshopInterest[workshop]["messageId"])
                    try:
                        await msg.edit(embed=self.getWorkshopEmbed(ctx.guild, workshop))
                    except Exception as e:
                        log.exception(f"{ctx.author.id} [{ctx.author.display_name}]")
                    await ctx.send(embed=discord.Embed(title="✅ Cleared workshop list!", description=f"Cleared workshop list '{workshop}'.", color=discord.Color.green()))
                    return

        # Invalid workshop
        await ctx.send(embed=discord.Embed(title="❌ Invalid workshop name", description=f"Could not find workshop '{worskhopListName}'.", color=discord.Color.red()))


class WorkshopInterestButton(discord.ui.DynamicItem[discord.ui.Button], template=r"workshopinterest_(?P<action>add|remove)"):
    """Handling all workshop interest buttons."""
    def __init__(self, custom_id="", *args, **kwargs):
        super().__init__(discord.ui.Button(custom_id=custom_id, *args, **kwargs))

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        return cls(item.custom_id)

    async def callback(self, interaction: discord.Interaction):
        try:
            with open(WORKSHOP_INTEREST_FILE) as f:
                workshopInterest = json.load(f)

            if interaction.message is None:
                log.exception("WSINT updateInterestList: interaction.message is None")
                return

            wsTitle = interaction.message.embeds[0].title
            if wsTitle is None:
                log.exception("WSINT updateInterestList: wsTitle is None")
                return

            # Brute force emoji removal, produces title
            for i in range(len(wsTitle)):
                if wsTitle[i:] in WORKSHOP_INTEREST_LIST:
                    wsTitle = wsTitle[i:]
                    break
            wsMembers = workshopInterest[wsTitle]["members"]

            if interaction.data["custom_id"] == "workshopinterest_add":
                if interaction.user.id not in wsMembers:
                    wsMembers.append(interaction.user.id)  # Add member to WS
                else:
                    await interaction.response.send_message("You are already interested!", ephemeral=True)
                    return

            elif interaction.data["custom_id"] == "workshopinterest_remove":
                if interaction.user.id in wsMembers:
                    wsMembers.remove(interaction.user.id)  # Remove member from WS
                else:
                    await interaction.response.send_message("You are already not interested!", ephemeral=True)
                    return

            with open(WORKSHOP_INTEREST_FILE, "w") as f:
                json.dump(workshopInterest, f, indent=4)

            if interaction.guild is None:
                log.exception("WSINT updateInterestList: interaction.guild is None")
                return
            try:
                await interaction.response.edit_message(embed=WorkshopInterest.getWorkshopEmbed(interaction.guild, wsTitle))
            except Exception as e:
                log.exception(f"{interaction.user.id} [{interaction.user.display_name}]")

        except Exception as e:
            log.exception(f"{interaction.user.id} [{interaction.user.display_name}]")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WorkshopInterest(bot))
    bot.add_dynamic_items(WorkshopInterestButton)
