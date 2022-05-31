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
        "Use the buttons to move.\nPress :cyclone: to warp through the different planes of existence in the level.\nYour goal is to find your way to the :trophy:!"  # Level message (could be tutorial, hint, story or anything. to be put in embed description)
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
        log.info(f"{interaction.user.display_name} ({interaction.user}) is playing Just Bob!")
        await interaction.response.send_message("Playing Just Bob...")
        if interaction.user.id in self.games:  # Remove previous active Just Bob game if it exists
            msg = await interaction.channel.fetch_message(self.games[interaction.user.id]["messageId"])
            del self.games[interaction.user.id]
            await msg.delete()
        self.games[interaction.user.id] = {"levelNum": None, "level": None, "playerPos": None, "trophyPositions": None, "doorLevers": None, "openDoors": None, "description": None, "playerId": None, "messageId": None, "messageChangeCounter": 0}
        await self.levelSelect(interaction)

    async def levelSelect(self, interaction: discord.Interaction) -> None:
        """ Showing the player the level select prompt.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        with open(LEVELS_FILE) as f:
            levels = json.load(f)
        with open(PLAYERS_PROGRESS_FILE) as f:
            playersProgress = json.load(f)
        lastLevelUnlocked = playersProgress.get(str(interaction.user.id), 1)
        gameComplete = lastLevelUnlocked > len(levels)
        embed = Embed(title="Just Bob", description="Congratulations, you completed all levels! 🎉\nYou can replay them if you'd like.\nMore levels coming soon:tm:!" if gameComplete else f"Choose a level!\n({(lastLevelUnlocked - 1) / len(levels) * 100:.2f}% complete)", color=Color.green() if gameComplete else Color.blue())
        embed.set_footer(text=f"Player: {interaction.user.display_name}")

        self.games[interaction.user.id]["messageChangeCounter"] += 1
        row = JustBobView(self, interaction, self.games[interaction.user.id]["messageChangeCounter"])
        row.timeout = TIME_TEN_MIN
        buttons = []
        for emoji, _ in zip(LEVEL_NUMBERS[:lastLevelUnlocked], levels):
            buttons.append(JustBobButton(self, emoji=emoji, style=discord.ButtonStyle.secondary))
        buttons.append(JustBobButton(self, emoji=STOP, style=discord.ButtonStyle.secondary))
        [row.add_item(item=button) for button in buttons]

        msg = await interaction.channel.send(embed=embed, view=row)
        self.games[interaction.user.id]["messageId"] = msg.id

    async def buttonHandling(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """ Listens for actions.

        Parameters:
        button (discord.ui.Button): The Discord button.
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        if ((interaction.user.id in self.games and self.games[interaction.user.id]["messageId"] == interaction.message.id) or (any(role is not None and role.id == UNIT_STAFF for role in interaction.user.roles) and button.emoji == STOP)):
            try:
                game = self.games[interaction.user.id]
            except KeyError:
                return

            emoji = str(button.emoji)
            if emoji in LEVEL_NUMBERS:
                levelNum = LEVEL_NUMBERS.index(emoji)
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
                game["messageChangeCounter"] += 1

                embed = self.getGameEmbed(game)
                row = JustBobView(self, interaction, self.games[interaction.user.id]["messageChangeCounter"])
                row.timeout = TIME_TEN_MIN
                buttons = []
                for directionEmoji in DIRECTIONS:
                    buttons.append(JustBobButton(self, emoji=directionEmoji, style=discord.ButtonStyle.secondary))
                buttons.append(JustBobButton(self, emoji=STOP, style=discord.ButtonStyle.secondary))
                [row.add_item(item=button) for button in buttons]
                await interaction.response.edit_message(embed=embed, view=row)

            elif emoji in DIRECTIONS:
                direction = DIRECTIONS[emoji]
                levelComplete = self.makeMove(game, direction)
                embed = self.getGameEmbed(game)
                await interaction.response.edit_message(embed=embed)

                if levelComplete:
                    await asyncio.sleep(1)
                    await interaction.message.delete()
                    game["messageChangeCounter"] += 1
                    await self.levelSelect(interaction)

            elif emoji == STOP:
                del self.games[interaction.user.id]
                game["messageChangeCounter"] += 1
                await interaction.message.delete()
                #await interaction.response.edit_message(content="Terminated Just Bob!", embed=None, view=None)

        else:
            await interaction.response.send_message("This is not for you!", ephemeral=True)

    def getGameEmbed(self, game) -> Embed:
        """ Generates the player game embed.

        Parameters:
        game: The player game.

        Returns:
        Embed.
        """
        guild = self.bot.get_guild(GUILD_ID)
        embed = Embed(title=f"Just Bob (Level {game['levelNum'] + 1})", description=game["description"], color=Color.blue())

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
            levelComplete = True
        return levelComplete


class JustBobView(discord.ui.View):
    def __init__(self, instance, interaction, messageChangeCounter, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.interaction = interaction
        self.messageChangeCounter = messageChangeCounter

    async def on_timeout(self: discord.ui.View):
        try:
            msg = await self.interaction.channel.fetch_message(self.instance.games[self.interaction.user.id]["messageId"])
            if self.messageChangeCounter == self.instance.games[self.interaction.user.id]["messageChangeCounter"]:  # If time'd out buttons are the same as the displayed ones
                for btn in self.children:
                    btn.disabled = True
                await msg.edit(view=self)
                del self.instance.games[self.interaction.user.id]
                await asyncio.sleep(5)
                await msg.delete()
        except Exception:
            pass

class JustBobButton(discord.ui.Button):
    def __init__(self, instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance

    async def callback(self: discord.ui.Button, interaction: discord.Interaction):
        await self.instance.buttonHandling(self, interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JustBob(bot))
