from secret import DEBUG
import re
from datetime import datetime

from discord import app_commands, Embed, Color
from discord.ext import commands

from constants import *
from __main__ import log, cogsReady
if DEBUG:
    from constants.debug import *


emojiNumbers: tuple = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")

class Poll(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Poll"), flush=True)
        cogsReady["poll"] = True

    @app_commands.command(name="poll")
    @app_commands.guilds(GUILD)
    @app_commands.describe(
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
    async def poll(
        self,
        interaction: discord.Interaction,
        title: str,
        option1: str,
        description: str = "",
        option2: str = None,
        option3: str = None,
        option4: str = None,
        option5: str = None,
        option6: str = None,
        option7: str = None,
        option8: str = None,
        option9: str = None,
        option10: str = None
    ) -> None:
        """ Create a poll with up to 10 options.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
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
        embed = Embed(title=title, description=f"{description}\n\n", color=Color.gold())
        embed.set_footer(text=f"Poll by {interaction.user.display_name}")
        embed.timestamp = datetime.utcnow()

        options = [option1, option2, option3, option4, option5, option6, option7, option8, option9, option10]
        isOneOption = any(options[1:])
        optionCount: int = 0
        for optionInp in options:
            if optionInp is not None:
                embed.description += f"{emojiNumbers[optionCount]}{' **(0%)**' * isOneOption} {optionInp}\n"
                optionCount += 1

        try:
            await interaction.response.send_message(embed=embed)
            poll = await interaction.original_message()
            for x in range(optionCount):
                await poll.add_reaction(emojiNumbers[x])
        except Exception as e:
            print(interaction.user, e)

    async def reactionShit(self, payload: discord.RawReactionActionEvent) -> None:
        """ Handles all poll reactions.

        Parameters:
        payload (discord.RawReactionActionEvent): The raw reaction event.

        Returns:
        None.
        """
        if payload.user_id in FRIENDLY_SNEKS:
            return

        channel = self.bot.get_channel(payload.channel_id)
        msg = await channel.fetch_message(payload.message_id)

        if hasattr(payload, "member") and hasattr(payload.member, "bot") and payload.member.bot:
            return

        if msg.author.id in FRIENDLY_SNEKS and payload.channel_id != SCHEDULE and payload.channel_id != WORKSHOP_INTEREST and payload.emoji.name in emojiNumbers and len(msg.embeds) > 0 and msg.embeds[0].footer.text and msg.embeds[0].footer.text.startswith("Poll by"):
            embed = msg.embeds[0]
            optionRows = (emojiNumbers[0] + embed.description.split(emojiNumbers[0])[1]).split("\n")
            if len(optionRows) == 1:
                return  # Do not continue editing the message if there's 1 option

            reactionCount: list = [reaction.count for reaction in msg.reactions if reaction.emoji in emojiNumbers]  # Get all reactions from msg that is in emojiNumbers
            reactionSum = (sum(reactionCount) - len(reactionCount)) or 1  # Sums all reactions on msg, excl. the bot, but if 0, change to 1 (not divide by 0)

            newPercentText: list = []
            for rowNum in range(len(optionRows)):
                # percent = f'{((reactionCount[rowNum] - 1) / reactionSum) * 100:.1f}'.strip('0').strip('.') or 0  # Floats
                percent = round(((reactionCount[rowNum] - 1) / reactionSum) * 100)  # Ints
                newPercentText.append(re.sub(POLL_PERCENT_REGEX, f"({percent}%)", optionRows[rowNum]))

            percentTextMaxLen = max([len(percentText) for percentText in re.findall(POLL_PERCENT_REGEX, "".join(newPercentText))])
            for rowNum in range(len(optionRows)):
                padding = "\u2000" * (percentTextMaxLen - len(re.findall(POLL_PERCENT_REGEX, newPercentText[rowNum])[0]))
                splitter = re.search(POLL_PERCENT_REGEX, newPercentText[rowNum]).span(0)[1]  # Find the character pos where the percentText ends
                optionRows[rowNum] = newPercentText[rowNum][:splitter] + padding + newPercentText[rowNum][splitter:]  # Add padding after percentText

            embed.description = embed.description.split(emojiNumbers[0])[0] + "\n".join(optionRows)  # Concat "description" with options
            await msg.edit(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """ Listens for reaction additions.

        Parameters:
        payload (discord.RawReactionActionEvent): The raw reaction event.

        Returns:
        None.
        """
        await self.reactionShit(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """ Listens for reaction removals.

        Parameters:
        payload (discord.RawReactionActionEvent): The raw reaction event.

        Returns:
        None.
        """
        await self.reactionShit(payload)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Poll(bot))
