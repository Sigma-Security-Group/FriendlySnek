import os
import json
import asyncio

from discord import app_commands, Embed, Color
from discord.ext import commands

from constants import *
from __main__ import log, cogsReady, DEBUG
if DEBUG:
    from constants.debug import *

"""
Levels structure. WIP levels use emojis for easier level design, but when a level gets added to the official levels.json file, all emojis are replaced with corresponding characters:
    🟪 -> #
    ⬛ ->
    🙂 -> P
    🏆 -> T
    🟧 -> D
    🔶 -> L

[
    [
        "Level 1",  # Used only for easier navigation through the json file. Not used in code
        [
            [
                "############",
                "#   #      #",
                "# P #      #",
                "#   #      #",
                "#   #      #",
                "#   #      #",
                "#   #      #",
                "#   #      #",
                "#   #      #",
                "############"
            ],
            [
                "############",
                "#     #    #",
                "#     #    #",
                "#     #    #",
                "#    ##    #",
                "#    ##    #",
                "#    #     #",
                "#    #     #",
                "#    #     #",
                "############"
            ],
            [
                "############",
                "#      #   #",
                "#      #   #",
                "#      #   #",
                "#      #   #",
                "#      #   #",
                "#      #   #",
                "#      # T #",
                "#      #   #",
                "############"
            ]
        ],
        [0, 2, 2],  # Starting location [layer, row, column]
        [[2, 7, 9]],  # Ending locations [[layer, row, column], ...]
        [
            {"l": [1, 1, 1], "d": [2, 2, 2], "m": 5}
        ],  # Door levers [{"l": [lever layer, lever row, lever column], "d": [door layer, door row, door column], "m": moves before closing door}, ...]
        "Use reactions to move. Use :cyclone: to warp through the different planes of existence in the level. Your goal is to  find your way to the trophy"  # Level message (could be tutorial, hint, story or anything. to be put in embed description)
    ],
    [
        "Level 2",
        ...
    ]
]
"""

LEVELS_FILE = "cogs/justBob/levels.json"
PLAYERS_PROGRESS_FILE = "data/justBobPlayersProgress.json"
LEVEL_NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
DIRECTIONS = {
    "👈": (0, 0, -1),
    "👇": (0, 1, 0),
    "👆": (0, -1, 0),
    "👉": (0, 0, 1),
    "🌀": (1, 0, 0)
}
STOP = "🗑"

PLAYER = "🙂"
WINNING_PLAYER = "😎"
TROPHY = "🏆"
FLOOR = "⬛"
WALL = "🟪"
DOOR = "🟧"
LEVER = "🔶"

class JustBob(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        if not os.path.exists(PLAYERS_PROGRESS_FILE):
            with open(PLAYERS_PROGRESS_FILE, "w") as f:
                json.dump({}, f, indent=4)
        self.games = {}

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("JustBob"), flush=True)
        cogsReady["justBob"] = True

    @app_commands.command(name="justbob")
    @app_commands.guilds(GUILD)
    async def justBob(self, interaction: discord.Interaction) -> None:
        """ Play the minigame Just Bob. """
        if interaction.channel.id != GENERAL and interaction.channel.id != BOT_SPAM:
            await interaction.response.send_message(f"Sorry, but you can only play Just Bob in <#{GENERAL}> or in <#{BOT_SPAM}>!")
            return
        await interaction.response.send_message("Playing Just Bob...")
        await self.levelSelect(interaction.channel, interaction.user)

    async def levelSelect(self, channel, player) -> None:
        with open(LEVELS_FILE) as f:
            levels = json.load(f)
        with open(PLAYERS_PROGRESS_FILE) as f:
            playersProgress = json.load(f)
        lastLevelUnlocked = playersProgress.get(str(player.id), 1)
        gameComplete = lastLevelUnlocked > len(levels)
        embed = Embed(title="Just Bob", description="Congratulations, you completed all levels! 🎉\nYou can replay them if you'd like.\nMore levels coming soon!" if gameComplete else f"Choose a level!\n({(lastLevelUnlocked - 1) / len(levels) * 100:.2f}% complete)", color=Color.green() if gameComplete else Color.blue())
        embed.set_footer(text=f"Player: {player.display_name}")
        msg = await channel.send(embed=embed)
        self.games[player.id] = {"levelNum": None, "level": None, "playerPos": None, "trophyPositions": None, "doorLevers": None, "openDoors": None, "description": None, "playerId": None, "messageId": msg.id}
        for emoji, _ in zip(LEVEL_NUMBERS[:lastLevelUnlocked], levels):
            await msg.add_reaction(emoji)
        await msg.add_reaction(STOP)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if self.bot.ready and payload.member is not None and not payload.member.bot and ((payload.member is not None and payload.member.id in self.games and self.games[payload.member.id]["messageId"] == payload.message_id) or (any(role is not None and role.id == UNIT_STAFF for role in payload.member.roles) and payload.emoji.name == STOP)):
            channel = self.bot.get_channel(payload.channel_id)
            try:
                game = self.games[payload.member.id]
            except KeyError:
                return
            gameMessage = await channel.fetch_message(game["messageId"])
            if payload.emoji.name in LEVEL_NUMBERS:
                levelNum = LEVEL_NUMBERS.index(payload.emoji.name)
                with open(LEVELS_FILE) as f:
                    levels = json.load(f)
                _, level, startPos, trophyPositions, doorLevers, description = levels[levelNum]
                game["levelNum"] = levelNum
                game["level"] = level
                game["playerPos"] = startPos
                game["trophyPositions"] = trophyPositions
                game["doorLevers"] = doorLevers
                game["openDoors"] = []  # Format for each open door is [[door layer, door row, door column], remaining moves until close]
                game["description"] = description
                game["playerId"] = payload.member.id
                await gameMessage.delete()
                embed = self.getGameEmbed(game)
                msg = await channel.send(embed=embed)
                game["messageId"] = msg.id
                for directionEmoji in DIRECTIONS:
                    await msg.add_reaction(directionEmoji)
                await msg.add_reaction(STOP)
            elif payload.emoji.name in DIRECTIONS:
                direction = DIRECTIONS[payload.emoji.name]
                levelComplete = self.makeMove(game, direction)
                embed = self.getGameEmbed(game)
                await gameMessage.edit(embed=embed)
                if levelComplete:
                    await asyncio.sleep(1)
                    await gameMessage.delete()
                    await self.levelSelect(channel, payload.member)
            elif payload.emoji.name == STOP:
                del self.games[payload.member.id]
                await gameMessage.delete()

            try:
                await gameMessage.remove_reaction(payload.emoji, payload.member)
            except Exception:
                pass

    def getGameEmbed(self, game) -> Embed:
        guild = self.bot.get_guild(GUILD_ID)
        embed = Embed(title=f"Just Bob (Lvl {game['levelNum'] + 1})", description=game["description"], color=Color.blue())

        playerLayer, playerRow, playerCol = game["playerPos"]
        board = game["level"][playerLayer]
        boardRows = []
        for r in range(len(board)):
            boardRow = []
            for c in range(len(board[r])):
                if board[r][c] == "#":
                    tile = WALL
                else:
                    tile = FLOOR
                isLever = False
                isDoor = False
                for doorLever in game["doorLevers"]:
                    if [playerLayer, r, c] == doorLever["l"]:
                        isLever = True
                        break
                    if [playerLayer, r, c] == doorLever["d"]:
                        for openDoorPos, _ in game["openDoors"]:
                            if [playerLayer, r, c] == openDoorPos:
                                break
                        else:
                            isDoor = True
                            break
                if isDoor:
                    tile = DOOR
                if isLever:
                    tile = LEVER
                for trophyLayer, trophyRow, trophyCol in game["trophyPositions"]:
                    if playerLayer == trophyLayer and (r, c) == (trophyRow, trophyCol):
                        tile = TROPHY
                        break
                if (r, c) == (playerRow, playerCol):
                    tile = PLAYER
                    if [playerLayer, playerRow, playerCol] in game["trophyPositions"]:
                        tile = WINNING_PLAYER
                boardRow.append(tile)
            boardRows.append("".join(boardRow))
        embed.add_field(name="\u200B", value="\n".join(boardRows) if len(boardRows) > 0 else "\u200B")

        player = guild.get_member(game["playerId"])
        embed.set_footer(text=f"Player: {player.display_name if player is not None else 'UNKNOWN'}")

        return embed

    def makeMove(self, game, direction) -> bool:
        dl, dr, dc = direction
        levelComplete = False
        playerLayer, playerRow, playerCol = game["playerPos"]
        level = game["level"]
        newLayer = (playerLayer + dl) % len(level)
        newRow = (playerRow + dr) % len(level[newLayer])
        newCol = (playerCol + dc) % len(level[newLayer][newRow])
        if level[newLayer][newRow][newCol] != "#":
            collidingWithDoor = False
            for doorLever in game["doorLevers"]:
                if [newLayer, newRow, newCol] == doorLever["d"]:
                    for openDoorPos, _ in game["openDoors"]:
                        if openDoorPos == doorLever["d"]:
                            break
                    else:
                        collidingWithDoor = True
                        break
            if not collidingWithDoor:
                game["playerPos"] = [newLayer, newRow, newCol]
                doorsClosed = []
                for i, (openDoorPos, timer) in enumerate(game["openDoors"]):
                    if timer <= 1:
                        doorsClosed.append(game["openDoors"][i])
                    else:
                        game["openDoors"][i] = [openDoorPos, timer - 1]
                for door in doorsClosed:
                    game["openDoors"].remove(door)
                for doorLever in game["doorLevers"]:
                    if [newLayer, newRow, newCol] == doorLever["l"]:
                        for i, (openDoorPos, _) in enumerate(game["openDoors"]):
                            if openDoorPos == doorLever["d"]:
                                game["openDoors"][i][1] = doorLever["m"]
                                break
                        else:
                            game["openDoors"].append([doorLever["d"], doorLever["m"]])
        if game["playerPos"] in game["trophyPositions"]:
            with open(PLAYERS_PROGRESS_FILE) as f:
                playersProgress = json.load(f)
            playersProgress[str(game["playerId"])] = max(playersProgress.get(str(game["playerId"]), 1), game["levelNum"] + 2)
            with open(PLAYERS_PROGRESS_FILE, "w") as f:
                json.dump(playersProgress, f, indent=4)
            del self.games[game["playerId"]]
            levelComplete = True
        return levelComplete

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JustBob(bot))