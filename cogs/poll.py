import re, discord, logging

from datetime import datetime, timezone
from discord.ext import commands  # type: ignore

from secret import DEBUG
from constants import *
if DEBUG:
    from constants.debug import *

EMOJI_NUMBERS: tuple = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")

log = logging.getLogger("FriendlySnek")

class Poll(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Poll"))
        self.bot.cogsReady["poll"] = True

    @discord.app_commands.command(name="poll")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.describe(
        multivote = "If you're able to vote for multiple options.",
        title = "Title",
        option1 = "Option 1",
        description = "Description",
        option2 = "Option 2",
        option3 = "Option 3",
        option4 = "Option 4",
        option5 = "Option 5",
        option6 = "Option 6",
        option7 = "Option 7",
        option8 = "Option 8",
        option9 = "Option 9",
        option10 = "Option 10"
    )
    @discord.app_commands.choices(multivote = [discord.app_commands.Choice(name="Multiple votes", value="Yes"), discord.app_commands.Choice(name="One vote", value="No")])
    async def poll(self, interaction: discord.Interaction, multivote: discord.app_commands.Choice[str], title: str, option1: str, description: str = "", option2: str = "", option3: str = "", option4: str = "", option5: str = "", option6: str = "", option7: str = "", option8: str = "", option9: str = "", option10: str = "") -> None:
        """Create a poll with up to 10 options.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        multivote (discord.app_commands.Choice[str]): If a user is able to cast their votes on multiple options.
        title (str): Poll title.
        option1 (str): Poll option 1.
        description (str): Poll description.
        option2 (str): Poll option 2.
        option3 (str): Poll option 3.
        option4 (str): Poll option 4.
        option5 (str): Poll option 5.
        option6 (str): Poll option 6.
        option7 (str): Poll option 7.
        option8 (str): Poll option 8.
        option9 (str): Poll option 9.
        option10 (str): Poll option 10.

        Returns:
        None.
        """
        log.info(f"{interaction.user.id} [{interaction.user.display_name}] Created a poll!")
        group = {
            "Creator": interaction.user.display_name,
            "Multivote": True if multivote.value == "Yes" else False
        }
        embed = discord.Embed(title=title, description=f"{description}\n\n", color=discord.Color.gold())
        embed.set_footer(text=f"Poll by {interaction.user.display_name}")
        embed.timestamp = datetime.now(timezone.utc)
        if embed.description is None:
            log.exception("Poll poll: embed.description is None")
            return

        options = [option1, option2, option3, option4, option5, option6, option7, option8, option9, option10]
        isOneOption = any(options[1:])
        optionCount = 0
        for optionInp in options:
            if optionInp != "":
                embed.description += f"{EMOJI_NUMBERS[optionCount]}{' **(0%)**' * isOneOption} {optionInp}\n"
                group[f"poll_vote_{optionCount}"] = []
                optionCount += 1

        try:
            row = PollView(self)
            row.timeout = None
            buttons = []
            for num in range(optionCount):
                buttons.append(PollButton(self, group, emoji=EMOJI_NUMBERS[num], label="(0)", style=discord.ButtonStyle.secondary, custom_id=f"poll_vote_{num}"))
                row.add_item(item=buttons[num])
            buttons.append(PollButton(self, group, emoji="👀", style=discord.ButtonStyle.primary, custom_id="results"))
            row.add_item(item=buttons[-1])
            await interaction.response.send_message(embed=embed, view=row)
        except Exception as e:
            log.exception(f"{interaction.user.id} [{interaction.user.display_name}]")

    @staticmethod
    async def buttonHandling(button: discord.ui.Button, interaction: discord.Interaction, group: dict) -> None:
        """ Handling all poll button interactions.

        Parameters:
        button (discord.ui.Button): The Discord button.
        interaction (discord.Interaction): The Discord interaction.
        group (dict): Poll specifics, e.g. multivote & voters.

        Returns:
        None.
        """
        if button.custom_id == "results":
            embed = discord.Embed(title="Poll results", color=discord.Color.green())
            for key, value in group.items():
                if key.startswith("poll_vote_"):
                    embed.add_field(name=EMOJI_NUMBERS[int(key.split("_")[-1])], value="\n".join([member.mention for voterId in value if interaction.guild is not None and (member := interaction.guild.get_member(voterId)) is not None]) if len(value) > 0 else "No votes", inline=True)
            embed.set_footer(text=f"Poll by {group['Creator']}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            if not isinstance(interaction.channel, discord.TextChannel):
                log.exception("Poll buttonHandling: interaction.channel not discord.TextChannel")
                return
            if interaction.message is None:
                log.exception("Poll buttonHandling: interaction.message is None")
                return

            msg = await interaction.channel.fetch_message(interaction.message.id)

            embed = msg.embeds[0]
            if embed.description is None:
                log.exception("Poll buttonHandling: embed.description is None")
                return

            optionRows = (EMOJI_NUMBERS[0] + embed.description.split(EMOJI_NUMBERS[0])[1]).split("\n")

            if button.view is None:
                log.exception("Poll buttonHandling: button.view is None")
                return
            row = button.view

            for num in range(len(optionRows)):  # Loop through the amount of buttons
                if button.view.children[num].custom_id == button.custom_id and interaction.user.id not in group[button.custom_id]:  # If pressed button (register vote) is same as iteration
                    if not group["Multivote"]:  # One vote per person
                        for i in range(len(optionRows)):  # Remove previous user votes
                            if interaction.user.id in group[f"poll_vote_{i}"]:
                                group[f"poll_vote_{i}"].remove(interaction.user.id)
                    group[button.custom_id].append(interaction.user.id)
                elif button.view.children[num].custom_id == button.custom_id and interaction.user.id in group[button.custom_id]:  # If pressed button (remove registered vote) is same as iteration
                    group[button.custom_id].remove(interaction.user.id)

            for btnNum in range(len(row.children)):
                if row.children[btnNum].custom_id.startswith("poll_vote_"):
                    row.children[btnNum].label = f"({len(group[f'poll_vote_{btnNum}'])})"
            await interaction.response.edit_message(view=row)

            if len(button.view.children) == 2:
                return  # Do not continue editing the message if there's only 1 option (+ Eyes emoji)

            voteCount: list = [int(button.label[1:][:-1]) for button in row.children if button.custom_id.startswith("poll_vote_")]  # Get all votes from poll
            voteSum = sum(voteCount) or 1  # Sums all votes - but if 0, change to 1 (not divide by 0)

            newPercentText: list = []
            for rowNum in range(len(optionRows)):
                percent = round((voteCount[rowNum] / voteSum) * 100)  # Ints
                newPercentText.append(re.sub(POLL_PERCENT_REGEX, f"({percent}%)", optionRows[rowNum]))
            percentTextMaxLen = max([len(percentText) for percentText in re.findall(POLL_PERCENT_REGEX, "".join(newPercentText))])
            for rowNum in range(len(optionRows)):
                padding = "\u2000" * (percentTextMaxLen - len(re.findall(POLL_PERCENT_REGEX, newPercentText[rowNum])[0]))
                splitter = re.search(POLL_PERCENT_REGEX, newPercentText[rowNum]).span(0)[1]  # Find the character pos where the percentText ends
                optionRows[rowNum] = newPercentText[rowNum][:splitter] + padding + newPercentText[rowNum][splitter:]  # Add padding after percentText

            embed.description = embed.description.split(EMOJI_NUMBERS[0])[0] + "\n".join(optionRows)  # Concat "description" with options
            await msg.edit(embed=embed)

            userVotes = ', '.join([EMOJI_NUMBERS[int(buttonId.split('_')[-1])] for buttonId, ppl in group.items() if buttonId.startswith("poll_vote_") and interaction.user.id in ppl])  # E.g. 8️⃣, 9️⃣, 🔟
            await interaction.followup.send(("(Multi-vote poll)" if group["Multivote"] else "(Single vote poll)") + f"\nYou've voted for:\n{userVotes if len(userVotes) > 0 else 'Nothing.'}", ephemeral=True)

        except Exception as e:
            log.exception(f"{interaction.user.id} [{interaction.user.display_name}]")


class PollView(discord.ui.View):
    def __init__(self, instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance


class PollButton(discord.ui.Button):
    def __init__(self, instance, group: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.group = group

    async def callback(self, interaction: discord.Interaction):
        await self.instance.buttonHandling(self, interaction, self.group)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Poll(bot))
