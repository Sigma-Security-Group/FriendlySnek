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
    async def poll(self, ctx: SlashContext, title: str, option1: str, option2: str = None, description: str = "", option3: str = None, option4: str = None, option5: str = None, option6: str = None, option7: str = None, option8: str = None, option9: str = None, option10: str = None) -> None:
        embed = Embed(title=title, description=f"{description}\n\n", color=Colour.gold())
        embed.set_footer(text=f"Poll by {ctx.author}")
        embed.timestamp = datetime.utcnow()

        emojiNumbers: tuple = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")
        options = [option1, option2, option3, option4, option5, option6, option7, option8, option9, option10]
        optionCount: int = 0
        for optionInp in options:
            if optionInp is not None:
                embed.description += f"{emojiNumbers[optionCount]} **(0%)** {optionInp}\n"
                optionCount += 1

        try:
            poll = await ctx.send(embed=embed)

            for x in range(optionCount):
                await poll.add_reaction(emoji=emojiNumbers[x])
        except Exception as e:
            print(ctx.author, e)

    async def reactionShit(self, payload) -> None:
        channel = self.bot.get_channel(payload.channel_id)
        msg = await channel.fetch_message(payload.message_id)

        if hasattr(payload.member, "bot") and payload.member.bot:
            return

        if  payload.channel_id != SCHEDULE and payload.channel_id != WORKSHOP_INTEREST and payload.emoji.name in emojiNumbers:
            reactionCount: list = [reaction.count for reaction in msg.reactions if reaction.emoji in emojiNumbers]  # Get all reactions from msg that is in emojiNumbers
            reactionSum = (sum(reactionCount) - len(reactionCount)) or 1  # Sums all reactions on msg, excl. the bot, but if 0, change to 1 (not divide by 0)

            embed = msg.embeds[0]
            msgDesc = embed.description.split("\n")
            optionRows = msgDesc[2:]  # Poll description

            for rowNum in range(len(optionRows)):
                # percent = f'{((reactionCount[rowNum] - 1) / reactionSum) * 100:.1f}'.strip('0').strip('.') or 0  # Floats
                percent = round(((reactionCount[rowNum] - 1) / reactionSum) * 100)  # Ints
                optionRows[rowNum] = re.sub(POLL_PERCENT_REGEX, f"({percent}%)", optionRows[rowNum])  # Replace old percent with new percent

            embed.description = "\n".join(msgDesc[:2] + optionRows)  # Concat "description" with options
            await msg.edit(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload) -> None:
        await self.reactionShit(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload) -> None:
        await self.reactionShit(payload)

def setup(bot) -> None:
    bot.add_cog(Poll(bot))