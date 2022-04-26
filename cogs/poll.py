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
                description="Poll title",
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
                name="option2",
                description="Option 2",
                option_type=3,
                required=True
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
            )
        ]
    )
    async def poll(self, ctx: SlashContext, title: str, option1: str, option2: str, option3: str = None, option4: str = None, option5: str = None, option6: str = None):
        embed = Embed(title=title, color=Colour.gold(), description=f"1. {option1}\n 2. {option2}\n")
        embed.set_footer(text=f"Poll by {ctx.author}")
        embed.timestamp = datetime.utcnow()

        emojiNumbers: tuple = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣")

        if (option3 != None):
            embed.description += f"3. {option3}\n"
        if (option4 != None):
            embed.description += f"3. {option4}\n"
        if (option5 != None):
            embed.description += f"3. {option5}\n"
        if (option6 != None):
            embed.description += f"3. {option6}\n"
        poll = await ctx.send(embed=embed)
        await poll.add_reaction(emoji='1️⃣')
        await poll.add_reaction(emoji='2️⃣')
        if (option3 != None):
            await poll.add_reaction(emoji='3️⃣')
        if (option4 != None):
            await poll.add_reaction(emoji='4️⃣')
        if (option5 != None):
            await poll.add_reaction(emoji='5️⃣')
        if (option6 != None):
            await poll.add_reaction(emoji='6️⃣')

def setup(bot):
    bot.add_cog(Poll(bot))
