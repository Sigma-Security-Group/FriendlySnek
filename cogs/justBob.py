from secret import DEBUG
import os
import json
import asyncio

from discord import app_commands, Embed, Color
from discord.ext import commands

from constants import *
from __main__ import log, cogsReady
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

LEVELS_FILE = "./cogs/justBob/levels.json"
PLAYERS_PROGRESS_FILE = "./data/justBobPlayersProgress.json"
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
    def __init__(self, bot: commands.Bot) -> None:
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
        """ Play the minigame Just Bob.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        if interaction.channel.id != GENERAL and interaction.channel.id != BOT_SPAM:
            await interaction.response.send_message(f"Sorry, but you can only play Just Bob in <#{GENERAL}> or in <#{BOT_SPAM}>!")
            return
        await interaction.response.send_message("Playing Just Bob...")
        await self.levelSelect(interaction.channel, interaction.user)

    async def levelSelect(self, channel: discord.abc.GuildChannel, player: discord.Member) -> None:
        """ Showing the player the level select prompt.

        Parameters:
        channel (discord.abc.GuildChannel): A disord guild channel.
        player (discord.Member): The player.

        Returns:
        None.
        """
        with open(LEVELS_FILE) as f:
            levels = json.load(f)
        with open(PLAYERS_PROGRESS_FILE) as f:
            playersProgress = json.load(f)
        lastLevelUnlocked = playersProgress.get(str(player.id), 1)
        gameComplete = lastLevelUnlocked > len(levels)
        embed = Embed(title="Just Bob", description="Congratulations, you completed all levels! 🎉\nYou can replay them if you'd like.\nMore levels coming soon!" if gameComplete else f"Choose a level!\n({(lastLevelUnlocked - 1) / len(levels) * 100:.2f}% complete)", color=Color.green() if gameComplete else Color.blue())
        embed.set_footer(text=f"Player: {player.display_name}")

        row = discord.ui.View()
        row.timeout = None
        buttons = []

        for emoji, level in zip(LEVEL_NUMBERS[:lastLevelUnlocked], levels):
            buttons.append(
                JustBobButtons(self, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=level)
            )
        buttons.append(
            JustBobButtons(self, emoji=STOP, style=discord.ButtonStyle.secondary, custom_id="justbob_stop")
        )
        [row.add_item(item=button) for button in buttons]
        msg = await channel.send(embed=embed, view=row)
        self.games[player.id] = {"levelNum": None, "level": None, "playerPos": None, "trophyPositions": None, "doorLevers": None, "openDoors": None, "description": None, "playerId": None, "messageId": msg.id}

    async def buttonHandling(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """ Listens for actions.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        button (discord.ui.Button): The Discord button.

        Returns:
        None.
        """
        if ((interaction.user.id in self.games and self.games[interaction.user.id]["messageId"] == interaction.message.id) or (any(role is not None and role.id == UNIT_STAFF for role in interaction.user.roles) and button.emoji == STOP)):
            try:
                game = self.games[interaction.user.id]
            except KeyError:
                return
            gameMessage = await interaction.channel.fetch_message(game["messageId"])
            if button.emoji in LEVEL_NUMBERS:
                levelNum = LEVEL_NUMBERS.index(button.emoji)
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
                game["playerId"] = interaction.user.id
                await gameMessage.delete()
                embed = self.getGameEmbed(game)

                row = discord.ui.View()
                row.timeout = None
                buttons = [
                    JustBobButtons(self, label="", style=discord.ButtonStyle.success, custom_id=""),
                    JustBobButtons(self, label="", style=discord.ButtonStyle.danger, custom_id=""),
                ]
                [row.add_item(item=button) for button in buttons]
                await author.send(embed=embed, view=row)

                msg = await interaction.channel.send(embed=embed)
                game["messageId"] = msg.id
                for directionEmoji in DIRECTIONS:
                    await msg.add_reaction(directionEmoji)
                await msg.add_reaction(STOP)
            elif button.emoji in DIRECTIONS:
                direction = DIRECTIONS[button.emoji]
                levelComplete = self.makeMove(game, direction)
                embed = self.getGameEmbed(game)
                await gameMessage.edit(embed=embed)
                if levelComplete:
                    await asyncio.sleep(1)
                    await gameMessage.delete()
                    await self.levelSelect(interaction.channel, interaction.user)
            elif button.emoji == STOP:
                del self.games[interaction.user.id]
                await gameMessage.delete()

    def getGameEmbed(self, game) -> Embed:
        """ Generates the player game embed.

        Parameters:
        game: The player game.

        Returns:
        Embed.
        """
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

    def makeMove(self, game, direction: tuple) -> bool:
        """ Processes the player movement request.

        Parameters:
        game: The player game.
        direction (tuple): A tuple containing the movement specifications.

        Returns:
        bool.
        """
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


class JustBobButtons(discord.ui.Button):
    def __init__(self, instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance

    async def callback(self, interaction: discord.Interaction):
        await self.instance.buttonHandling(self.message, self, interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JustBob(bot))
