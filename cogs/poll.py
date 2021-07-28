import discord
from discord.embeds import Embed
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *


class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        log.debug("Poll Cog is ready", flush=True)
        cogsReady["poll"] = True

    @cog_ext.cog_slash(name="poll", guild_ids=[SERVER], description="ccommand to create a poll", options=[
                create_option(name="name",
                 description="Poll name",
                 option_type=3,
                 required=True),
                 create_option(name="option1",
                 description="First option in poll",
                 option_type=3,
                 required=True),
                 create_option(name="option2",
                 description="First second in poll",
                 option_type=3,
                 required=True),
                 create_option(name="option3",
                 description="Third option in poll",
                 option_type=3,
                 required=False),
                 create_option(name="option4",
                 description="Fourth option in poll",
                 option_type=3,
                 required=False),
                 create_option(name="option5",
                 description="Fifth option in poll",
                 option_type=3,
                 required=False),
                 create_option(name="option6",
                 description="Sixth option in poll",
                 option_type=3,
                 required=False)])
    async def poll(self, ctx: SlashContext,name: str, option1: str, option2: str, option3: str =None,option4: str =None,option5: str =None,option6: str =None):
        print(option3)
        msg = Embed(title=name, color = discord.Colour.random(), description=f"1. {option1}\n 2. {option2}\n")
        if(option3 != None):
            msg.description += f"3. {option3}\n"
        if(option4 != None):
            msg.description += f"3. {option4}\n"
        if(option5 != None):
            msg.description += f"3. {option5}\n"
        if(option6 != None):
            msg.description += f"3. {option6}\n"
        poll = await ctx.send(embed=msg)
        await poll.add_reaction(emoji='1️⃣')
        await poll.add_reaction(emoji='2️⃣')
        if(option3 != None):
            await poll.add_reaction(emoji='3️⃣')
        if(option4 != None):
            await poll.add_reaction(emoji='4️⃣')
        if(option5 != None):
            await poll.add_reaction(emoji='5️⃣')
        if(option6 != None):
            await poll.add_reaction(emoji='6️⃣')

def setup(bot):
    bot.add_cog(Poll(bot))