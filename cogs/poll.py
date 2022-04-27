from discord import Embed, Colour
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option
from datetime import datetime

from constants import *

from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *

emojiNumbers: tuple = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")

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
    async def poll(self, ctx: SlashContext, title: str, option1: str, option2: str = None, description: str = "", option3: str = None, option4: str = None, option5: str = None, option6: str = None, option7: str = None, option8: str = None, option9: str = None, option10: str = None):
        embed = Embed(title=title, description=f"{description}\n\n", color=Colour.gold())
        embed.set_footer(text=f"Poll by {ctx.author}")
        embed.timestamp = datetime.utcnow()

        emojiNumbers: tuple = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")
        options = [option1, option2, option3, option4, option5, option6, option7, option8, option9, option10]
        optionCount: int = 0
        for optionInp in options:
            if optionInp is not None:
                embed.description += f"{emojiNumbers[optionCount]} {optionInp}\n"
                optionCount += 1

        try:
            poll = await ctx.send(embed=embed)

            for x in range(optionCount):
                await poll.add_reaction(emoji=emojiNumbers[x])
        except Exception as e:
            print(ctx.author, e)

    async def reactionShit(self, payload):
        channel = self.bot.get_channel(payload.channel_id)
        msg = await channel.fetch_message(payload.message_id)

        #print("="*25)
        #print(payload)
        #print("="*25)
        #print(payload.member)
        #print("="*25)
        #print(payload.member.bot)
        #print("="*25)

        if hasattr(payload.member, "bot") and payload.member.bot:
            return

        if  payload.channel_id != SCHEDULE and payload.channel_id != WORKSHOP_INTEREST and payload.emoji.name in emojiNumbers:

            reactionCount: list = []
            for reaction in msg.reactions:
                reactionCount.append(reaction.count)

            #print("="*25)
            #print(reactionCount)
            #print("="*25)
            #print(msg.embeds[0].description)
            #print("="*25)
            #print()
            #print("="*25)

            #descRows = msg.embeds[0].description.split("\n").pop(0).pop(0)

            #return

            """
            <
            RawReactionActionEvent
                message_id=968633347985272874
                user_id=229212817448894464
                channel_id=864487446611623986
                guild_id=864441968776052747
                emoji=
                    PartialEmoji
                    animated=False
                    name='1️⃣'
                    id=None
                >
                event_type='REACTION_ADD'
                member=<
                    Member
                    id=229212817448894464
                    name='Froggi22'
                    discriminator='3436'
                    bot=False
                    nick=None
                    guild=<
                        Guild
                        id=864441968776052747
                        name='Bot Testing Range'
                        shard_id=None
                        chunked=True
                        member_count=8
                    >
                >
            >
            """


            """
            <
            RawReactionActionEvent
                message_id=968571513504665671
                user_id=942214717945036820
                channel_id=864487446611623986
                guild_id=864441968776052747
                emoji=<
                    PartialEmoji
                    animated=False
                    name='2️⃣'
                    id=None
                >
                event_type='REACTION_ADD'
                member=<
                    Member
                    id=942214717945036820
                    name='Froggi Friendly Snek'
                    discriminator='1563'
                    bot=True
                    nick=None
                    guild=<
                        Guild
                        id=864441968776052747
                        name='Bot Testing Range'
                        shard_id=None
                        chunked=True
                        member_count=8
                    >
                >
            >
            <
            Message
                id=968599937317220382
                channel=<TextChannel
                id=864487446611623986
                name='arma-discussion'
                position=5
                nsfw=False
                news=False
                category_id=864441969286578176
            >
            type=<MessageType.default: 0>
            author=<Member id=942214717945036820
                name='Froggi Friendly Snek' discriminator='1563' bot=True nick=None guild=<Guild id=864441968776052747 name='Bot Testing Range' shard_id=None chunked=True member_count=8>> flags=<MessageFlags value=0>>
            """

            """
            try:

                channel = self.bot.get_channel(payload.channel_id)
                msg = await channel.fetch_message(payload.message_id)
                print("="*25)
                print("="*25)
                print(payload)
                print("="*25)
                print(msg.content)
                print("="*25)
                print(msg.embeds)
                print("="*25)
                print(msg.reactions)
                print("="*25)
            except Exception as e:
                print(e)
            """

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self.reactionShit(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self.reactionShit(payload)

def setup(bot):
    bot.add_cog(Poll(bot))
