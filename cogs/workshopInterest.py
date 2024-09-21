import os, json

from discord import Embed, Color
from discord.ext import commands  # type: ignore

from logger import Logger
from secret import DEBUG
from constants import *
from __main__ import cogsReady
if DEBUG:
    from constants.debug import *

# Maybe move this to constants.py
WORKSHOP_INTEREST_LIST: dict[str, dict[str, str | int | tuple]] = {
    "Naval": {
        "emoji": "⚓",
        "role": SME_NAVAL,
        "description": "\"I am naval SME\" - Police"
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
    "Newcomer": {
        "emoji": "🐣",
        "role": (UNIT_STAFF, ADVISOR, OPERATOR, STRATEGIST),
        "description": "Learn what you need to know before attending an operation in Sigma Security Group."
    },
    "Leadership": {
        "emoji": "🫀",  # Anatomical heart
        "role": (ADVISOR, STRATEGIST),
        "description": "Learn how to lead a team, squad or platoon in Sigma Security Group."
    }
}


class WorkshopInterest(commands.Cog):
    """Workshop Interest Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        Logger.debug(LOG_COG_READY.format("WorkshopInterest"), flush=True)
        cogsReady["workshopInterest"] = True

        if not os.path.exists(WORKSHOP_INTEREST_FILE):
            # JSON dump template
            workshopInterest = {}
            for name in WORKSHOP_INTEREST_LIST.keys():
                workshopInterest[name] = {
                    "members": [],
                    "messageId": 0
                }

            # Write to file
            with open(WORKSHOP_INTEREST_FILE, "w") as f:
                json.dump(workshopInterest, f, indent=4)

        await self.updateChannel()

    async def updateChannel(self) -> None:
        """Updates the interest channel with all messages.

        Parameters:
        None.

        Returns:
        None.
        """
        # TODO Goddamnit I hate this fucking resend shit. Please implement persistent views

        wsIntChannel = self.bot.get_channel(WORKSHOP_INTEREST)
        if not isinstance(wsIntChannel, discord.channel.TextChannel):
            Logger.exception("WSINT updateChannel: wsInt is not discord.channel.TextChannel")
            return

        await wsIntChannel.purge(limit=None, check=lambda message: message.author.id in FRIENDLY_SNEKS)

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            Logger.exception("WSINT updateChannel: guild is None")
            return

        with open(WORKSHOP_INTEREST_FILE) as f:
            wsIntFile = json.load(f)

        for workshopName in WORKSHOP_INTEREST_LIST.keys():
            # Fetch embed
            embed = self.getWorkshopEmbed(guild, workshopName)

            # Do button stuff
            row = discord.ui.View()
            row.timeout = None
            buttons = (
                WorkshopInterestButton(self, row=0, label="Interested", style=discord.ButtonStyle.success, custom_id="add"),
                WorkshopInterestButton(self, row=0, label="Not Interested", style=discord.ButtonStyle.danger, custom_id="remove")
            )
            for button in buttons:
                row.add_item(item=button)

            msg = await wsIntChannel.send(embed=embed, view=row)

            # Set embed messageId - used for removing people once workshop is done
            wsIntFile[workshopName]["messageId"] = msg.id

        with open(WORKSHOP_INTEREST_FILE, "w", encoding="utf-8") as f:
            json.dump(wsIntFile, f, indent=4)

    @staticmethod
    def getWorkshopEmbed(guild: discord.Guild, workshopName: str) -> Embed:
        """Generates an embed from the given workshop.

        Parameters:
        guild (discord.Guild): The target guild.
        workshopName (str): The workshop name.

        Returns:
        discord.Embed: The generated embed.
        """
        embed = Embed(title=f"{WORKSHOP_INTEREST_LIST[workshopName]['emoji']} {workshopName}", description=WORKSHOP_INTEREST_LIST[workshopName]["description"], color=Color.dark_blue())

        with open(WORKSHOP_INTEREST_FILE) as f:
            workshopInterest = json.load(f)
            removedMember = False

        # Get the interested member's name. If they aren't found, remove them
        interestedMembers = ""
        for memberID in workshopInterest[workshopName]["members"]:
            member = guild.get_member(memberID)
            if member is not None:
                interestedMembers += member.display_name + "\n"
            else:
                workshopInterest[workshopName]["members"].remove(memberID)
                removedMember = True

        if removedMember:
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

    async def updateInterestList(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """Handling all workshop interest button interactions.

        Parameters:
        button (discord.ui.Button): The Discord button.
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        try:
            with open(WORKSHOP_INTEREST_FILE) as f:
                workshopInterest = json.load(f)

            if interaction.message is None:
                Logger.exception("WSINT UpdateInterestList: interaction.message is None")
                return

            wsTitle = interaction.message.embeds[0].title
            if wsTitle is None:
                Logger.exception("WSINT UpdateInterestList: wsTitle is None")
                return

            # Brute force emoji removal, produces title
            for i in range(len(wsTitle)):
                if wsTitle[i:] in WORKSHOP_INTEREST_LIST:
                    wsTitle = wsTitle[i:]
                    break
            wsMembers = workshopInterest[wsTitle]["members"]

            if button.custom_id == "add":
                if interaction.user.id not in wsMembers:
                    wsMembers.append(interaction.user.id)  # Add member to WS
                else:
                    await interaction.response.send_message("You are already interested!", ephemeral=True)
                    return

            elif button.custom_id == "remove":
                if interaction.user.id in wsMembers:
                    wsMembers.remove(interaction.user.id)  # Remove member from WS
                else:
                    await interaction.response.send_message("You are already not interested!", ephemeral=True)
                    return

            with open(WORKSHOP_INTEREST_FILE, "w") as f:
                json.dump(workshopInterest, f, indent=4)

            if interaction.guild is None:
                Logger.exception("WSINT updateInterestList: interaction.guild is None")
                return
            try:
                await interaction.response.edit_message(embed=self.getWorkshopEmbed(interaction.guild, wsTitle))
            except Exception as e:
                Logger.exception(f"{interaction.user} | {e}")

        except Exception as e:
            Logger.exception(f"{interaction.user} | {e}")


    @commands.command(name="clean-specific-workshop-interest-list")
    @commands.has_any_role(*CMD_CLEANWSINTEREST_LIMIT)
    async def cleanSpecificWorkshopInterestList(self, ctx: commands.Context, *, worskhopListName: str) -> None:
        """Clear specific workshop interest list, no confirmation."""
        with open(WORKSHOP_INTEREST_FILE) as f:
                workshopInterest = json.load(f)

        for workshop in WORKSHOP_INTEREST_LIST.keys():
            if worskhopListName.lower() == workshop.lower():
                workshopInterest[workshop]["members"] = []
                with open(WORKSHOP_INTEREST_FILE, "w") as f:
                    json.dump(workshopInterest, f, indent=4)

                guild = self.bot.get_guild(GUILD_ID)
                if guild is None:
                    Logger.exception("clean-specific-workshop-interest-list: guild is None")
                    return
                channel = self.bot.get_channel(WORKSHOP_INTEREST)
                msg = await channel.fetch_message(workshopInterest[workshop]["messageId"])
                try:
                    await msg.edit(embed=self.getWorkshopEmbed(guild, workshop))
                except Exception as e:
                    Logger.exception(f"{ctx.author} | {e}")
                await ctx.send(embed=Embed(title="✅ Cleared workshop list!", description=f"Cleared workshop list '{worskhopListName}'.", color=Color.green()))
                break
        else:
            await ctx.send(embed=Embed(title="❌ Invalid workshop name", description=f"Could not find workshop '{worskhopListName}'.", color=Color.red()))


class WorkshopInterestButton(discord.ui.Button):
    """Handling all workshop interest buttons."""
    def __init__(self, instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance

    async def callback(self, interaction: discord.Interaction):
        await self.instance.updateInterestList(self, interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WorkshopInterest(bot))
