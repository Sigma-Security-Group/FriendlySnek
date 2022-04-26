from discord import Embed, Colour
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option
from datetime import datetime

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *

class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
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
    async def poll(self, ctx: SlashContext, title: str, option1: str, option2: str, description: str = "", option3: str = None, option4: str = None, option5: str = None, option6: str = None, option7: str = None, option8: str = None, option9: str = None, option10: str = None):
        embed = Embed(title=title, description=f"{description}\n\n", color=Colour.gold())
        embed.set_footer(text=f"Poll by {ctx.author}")
        embed.timestamp = datetime.utcnow()

        emojiNumbers: tuple = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")
        optionCount: int = 0
        for num in range(len(emojiNumbers)):
            optionInp = eval(f"option{num + 1}")
            if optionInp is not None:
                embed.description += f"{emojiNumbers[optionCount]} {optionInp}\n"
                optionCount += 1

        try:
            poll = await ctx.send(embed=embed)

            for x in range(optionCount):
                await poll.add_reaction(emoji=emojiNumbers[x])
        except Exception as e:
            print(ctx.author, e)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id == SCHEDULE or payload.channel_id == WORKSHOP_INTEREST:
            return
        """
        try:
            channel = self.bot.get_channel(payload.channel_id)
            msg = await channel.fetch_message(payload.message_id)
            print("="*25)
            print("="*25)
            # print(payload)
            print(msg.reactions)
            print("="*25)
        except Exception as e:
            print(e)
        """


def setup(bot):
    bot.add_cog(Poll(bot))
