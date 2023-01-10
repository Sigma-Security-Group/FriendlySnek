from secret import DEBUG
import os, json

from discord import Embed, Color
from discord.ext import commands

from constants import *
from __main__ import log, cogsReady
if DEBUG:
    from constants.debug import *


WORKSHOP_INTEREST_FILE = "data/workshopInterest.json"

DEFAULT_WORKSHOP_INTEREST_LISTS = {
    "Breacher": {
        "emoji": "🚪",
        "role": SME_BREACHER,
        "description": "Become an expert in close-quarters battle (CQB)."  # Unverifed description.
    },
    "Mechanised": {
        "emoji": "🛡️",
        "role": SME_MECHANISED,
        "description": "A short course on driving, gunning, and commanding a 6.21 million dollar reason the heavy weapons guy is useless."
    },
    "RPV-SO": {
        "emoji": "🛩️",
        "role": SME_RPV_SO,
        "description": "Learn how to employ recon and attack Remote Piloted Vehicles (Drones)."
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
        "description": "Learn how to administer combat aid to wounded personnel in a timely and effective manner."  # Unverifed description.
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
        "role": (UNIT_STAFF, ADVISOR, SPECIALIST, TECHNICIAN),
        "description": "Learn what you need to know before attending an operation in Sigma Security Group."
    }
}


class WorkshopInterest(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("WorkshopInterest"), flush=True)
        cogsReady["workshopInterest"] = True

        if not os.path.exists(WORKSHOP_INTEREST_FILE):
            # JSON dump template
            workshopInterest = {}
            for name in DEFAULT_WORKSHOP_INTEREST_LISTS.keys():
                workshopInterest[name] = {
                    "members": []
                }

            # Write to file
            with open(WORKSHOP_INTEREST_FILE, "w") as f:
                json.dump(workshopInterest, f, indent=4)

        await self.updateChannel()

    async def updateChannel(self) -> None:
        """ Updates the interest channel with all messages.

        Parameters:
        None.

        Returns:
        None.
        """
        # TODO Goddamnit I hate this fucking resend shit. Please implement persistent views

        channel = self.bot.get_channel(WORKSHOP_INTEREST)
        await channel.purge(limit=None, check=lambda message: message.author.id in FRIENDLY_SNEKS)
        await channel.send("Welcome to the Workshop Interest Channel! Here you can show interest for different workshops!\nYou'll be pinged when a workshop you are interested in is scheduled!")

        guild = self.bot.get_guild(GUILD_ID)

        for workshop in DEFAULT_WORKSHOP_INTEREST_LISTS.items():
            # Fetch embed
            embed = self.getWorkshopEmbed(guild, workshop)

            # Do button stuff
            row = discord.ui.View()
            row.timeout = None
            buttons = (
                WorkshopInterestButtons(self, row=0, label="Interested", style=discord.ButtonStyle.success, custom_id="add"),
                WorkshopInterestButtons(self, row=0, label="Not Interested", style=discord.ButtonStyle.danger, custom_id="remove")
            )
            for button in buttons:
                row.add_item(item=button)

            await channel.send(embed=embed, view=row)

    def getWorkshopEmbed(self, guild: discord.Guild, workshop: tuple) -> Embed:
        """ Generates an embed from the given workshop.

        Parameters:
        guild (discord.Guild): The target guild.
        workshop (tuple): The workshop event. [0] Name. [1] emoji, role, desc.

        Returns:
        discord.Embed: The generated embed.
        """
        embed = Embed(title=f"{workshop[1]['emoji']} {workshop[0]}", description=workshop[1]["description"], color=Color.dark_blue())

        with open(WORKSHOP_INTEREST_FILE) as f:
            workshopInterest = json.load(f)
            removedMember = False

        # Get the interested member's name. If they aren't found, remove them
        interestedMembers = ""
        for memberID in workshopInterest[workshop[0]]["members"]:
            member = guild.get_member(memberID)
            if member is not None:
                interestedMembers += member.display_name + "\n"
            else:
                workshopInterest[workshop[0]]["members"].remove(memberID)
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
        # 1 discord.Role
        if workshop[1]["role"] and isinstance(workshop[1]["role"], int):
            smes = [sme.display_name for sme in guild.get_role(workshop[1]["role"]).members]
            if smes:
                embed.set_footer(text=f"SME{'s' * (len(smes) > 1)}: {', '.join(smes)}")

        # >1 discord.Role
        elif workshop[1]["role"] and isinstance(workshop[1]["role"], tuple):
            smeroles = [guild.get_role(role).name for role in workshop[1]["role"]]
            embed.set_footer(text=f"SME roles: {', '.join(smeroles)}")

        return embed

    async def updateInterestList(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """ Handling all workshop interest button interactions.

        Parameters:
        button (discord.ui.Button): The Discord button.
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        try:
            with open(WORKSHOP_INTEREST_FILE) as f:
                workshopInterest = json.load(f)
            wsTitle = interaction.message.embeds[0].title

            # Brute force emoji removal, produces title
            for i in range(len(wsTitle)):
                if wsTitle[i:] in DEFAULT_WORKSHOP_INTEREST_LISTS:
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

            try:
                await interaction.response.edit_message(embed=self.getWorkshopEmbed(interaction.guild, (wsTitle, DEFAULT_WORKSHOP_INTEREST_LISTS[wsTitle])))
            except Exception as e:
                log.exception(f"{interaction.user} | {e}")

        except Exception as e:
            log.exception(f"{interaction.user} | {e}")


class WorkshopInterestButtons(discord.ui.Button):
    def __init__(self, instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance

    async def callback(self, interaction: discord.Interaction):
        await self.instance.updateInterestList(self, interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WorkshopInterest(bot))
