from discord import Embed, Colour
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option
from datetime import datetime
import re

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *

emojiNumbers: tuple = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")

class Poll(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Poll"), flush=True)
        cogsReady["poll"] = True

    @cog_ext.cog_slash(
        name="poll",
        guild_ids=[SERVER],
        description=POLL_COMMAND_DESCRIPTION,
        options=[
            create_option(
                name="title",
                description="Title",
                option_type=3,
                required=True
            ),
            create_option(
                name="option1",
                description="Option 1",
                option_type=3,
                required=True
            ),
            create_option(
                name="description",
                description="Description",
                option_type=3,
                required=False
            ),
            create_option(
                name="option2",
                description="Option 2",
                option_type=3,
                required=False
            ),
            create_option(
                name="option3",
                description="Option 3",
                option_type=3,
                required=False
            ),
            create_option(
                name="option4",
                description="Option 4",
                option_type=3,
                required=False
            ),
            create_option(
                name="option5",
                description="Option 5",
                option_type=3,
                required=False
            ),
            create_option(
                name="option6",
                description="Option 6",
                option_type=3,
                required=False
            ),
            create_option(
                name="option7",
                description="Option 7",
                option_type=3,
                required=False
            ),
            create_option(
                name="option8",
                description="Option 8",
                option_type=3,
                required=False
            ),
            create_option(
                name="option9",
                description="Option 9",
                option_type=3,
                required=False
            ),
            create_option(
                name="option10",
                description="Option 10",
                option_type=3,
                required=False
            )
        ]
    )
    async def poll(self, ctx: SlashContext, title: str, option1: str, description: str = "", option2: str = None, option3: str = None, option4: str = None, option5: str = None, option6: str = None, option7: str = None, option8: str = None, option9: str = None, option10: str = None) -> None:
        embed = Embed(title=title, description=f"{description}\n\n", color=Colour.gold())
        embed.set_footer(text=f"Poll by {ctx.author}")
        embed.timestamp = datetime.utcnow()

        emojiNumbers: tuple = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")
        options = [option1, option2, option3, option4, option5, option6, option7, option8, option9, option10]
        isOneOption = any(options[1:])
        optionCount: int = 0
        for optionInp in options:
            if optionInp is not None:
                embed.description += f"{emojiNumbers[optionCount]}{' **(0%)**' * isOneOption} {optionInp}\n"
                optionCount += 1

        try:
            poll = await ctx.send(embed=embed)
            for x in range(optionCount):
                await poll.add_reaction(emoji=emojiNumbers[x])
        except Exception as e:
            print(ctx.author, e)

    async def reactionShit(self, payload) -> None:
        if payload.member.id not in FRIENDLY_SNEKS:
            return

        channel = self.bot.get_channel(payload.channel_id)
        msg = await channel.fetch_message(payload.message_id)

        if hasattr(payload.member, "bot") and payload.member.bot:
            return

        if payload.channel_id != SCHEDULE and payload.channel_id != WORKSHOP_INTEREST and payload.emoji.name in emojiNumbers:
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
    async def on_raw_reaction_add(self, payload) -> None:
        await self.reactionShit(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload) -> None:
        await self.reactionShit(payload)

def setup(bot) -> None:
    bot.add_cog(Poll(bot))
