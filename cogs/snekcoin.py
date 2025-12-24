import os, re, json, asyncio, discord, logging
import pytz  # type: ignore

from datetime import datetime, timedelta, timezone
from dateutil.parser import parse as datetimeParse  # type: ignore
from typing import *
from random import random, randint, choice, choices

from discord.ext import commands, tasks  # type: ignore

from utils import Utils  # type: ignore
import secret
from constants import *
if secret.DEBUG:
    from constants.debug import *

log = logging.getLogger("FriendlySnek")



class Snekcoin(commands.Cog):
    """SnekCoin Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Snekcoin"))
        self.bot.cogsReady["snekcoin"] = True

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Snekcoin on_ready: guild is None")
            return


    @staticmethod
    async def getWallet(userId: int) -> Optional[Dict[str, int]]:
        """Get the wallet of a user.

        Parameters:
        userId (int): The user ID.

        Returns:
        dict: The user's wallet.
        """
        try:
            with open(WALLETS_FILE) as f:
                wallets = json.load(f)
        except FileNotFoundError:
            wallets = {}
        except Exception:
            log.exception("Snekcoin getWallet: Failed to load wallets file.")
            return None

        userIdStr = str(userId)
        userWallet = wallets.get(userIdStr, {"timesCommended": 0, "sentCommendations": 0, "money": 0, "moneySpent": 0})
        return userWallet


    @staticmethod
    async def updateWallet(userId: int, amount: int) -> None:
        """Save the wallet of a user.

        Parameters:
        userId (int): The user ID.
        amount (int): The amount to update in the user's wallet.

        Returns:
        None.
        """
        try:
            with open(WALLETS_FILE) as f:
                wallets = json.load(f)
        except FileNotFoundError:
            wallets = {}
        except Exception:
            log.exception("Snekcoin updateWallet: Failed to load wallets file.")
            return

        userIdStr = str(userId)
        userWallet = wallets.get(userIdStr, {"timesCommended": 0, "sentCommendations": 0, "money": 0, "moneySpent": 0})
        userWallet["money"] += amount
        if amount < 0:
            userWallet["moneySpent"] -= amount
        wallets[userIdStr] = userWallet

        try:
            with open(WALLETS_FILE, "w") as f:
                json.dump(wallets, f, indent=4)
        except Exception:
            log.exception("Snekcoin updateWallet: Failed to save wallets file.")


    @staticmethod
    async def gambleCoinFlip(userId: int, gambleAmount: int) -> bool:
        """Gamble a coin flip.

        Parameters:
        userId (int): The user ID.
        walletData (dict): The user's wallet data.

        Returns:
        bool: True if the user wins, False otherwise.
        dict: The updated wallet data.
        payout = 1.5 * gambleAmount
        """
        log.debug(f"Snekcoin gambleCoinFlip: User {userId} is gambling a coin flip.")
        results = True if random() < 0.62 else False # ~7% house edge with 1.5x payout
        payout = round(0.5 * gambleAmount)
        if results:
            await Snekcoin.updateWallet(userId, int(payout))
        if not results:
            await Snekcoin.updateWallet(userId, -gambleAmount)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, gambleAmount)
        return results, payout


    @staticmethod
    async def gambleDiceRoll(userId: int, gambleAmount: int) -> Tuple[bool, int, int]:
        """Gamble a dice roll.

        Parameters:
        userId (int): The user ID.
        walletData (dict): The user's wallet data.

        Returns:
        bool: True if the user wins, False otherwise.
        dict: The updated wallet data.
        payout = 1.9 * gambleAmount
        """
        log.debug(f"Snekcoin gambleDiceRoll: User {userId} is gambling a dice roll.")
        casinoEdge = True if random() < 0.0358 else False # ~7% casino edge with 1.9x payout
        userRoll = randint(1, 6)
        botRoll = randint(1, 6)
        winnings = round(0.9 * gambleAmount)
        if casinoEdge:
            botRoll = 6
        results = True if userRoll > botRoll else False if userRoll < botRoll else None
        if results:
            await Snekcoin.updateWallet(userId, int(winnings))
            return results, userRoll, botRoll, winnings
        if results is None:
            return results, userRoll, botRoll, winnings
        if not results:
            await Snekcoin.updateWallet(userId, -gambleAmount)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, gambleAmount)
        return results, userRoll, botRoll, winnings

    @staticmethod
    async def gambleSlots(userId: int, gambleAmount: int) -> Tuple[bool, List[str], int]:
        """Gamble a slots game.

        Parameters:
        userId (int): The user ID.
        gambleAmount (int): The amount to gamble.

        Returns:
        bool: True if the user wins, False otherwise.
        List[str]: The reels that were spun.
        int: The winnings amount.
        """
        log.debug(f"Snekcoin gambleSlots: User {userId} is gambling a slots game.")
        symbolData = {
            "🍒": {"weight": 0.6, "payout": 3.2},
            "🍋": {"weight": 0.15, "payout": 3.2},
            "🔔": {"weight": 0.08, "payout": 3.2},
            "⭐": {"weight": 0.06, "payout": 3.2},
            "💎": {"weight": 0.1, "payout": 7},
            "7️⃣": {"weight": 0.01, "payout": 25},
        }

        symbols = list(symbolData.keys())
        weights = [symbolData[symbol]["weight"] for symbol in symbols]

        reel1 = choice(choices(symbols, weights=weights, k=1))
        reel2 = choice(choices(symbols, weights=weights, k=1))
        reel3 = choice(choices(symbols, weights=weights, k=1))
        reels = [reel1, reel2, reel3]

        # Determine winnings
        if reel1 == reel2 == reel3:
            payoutMultiplier = symbolData[reel1]["payout"]
            winnings = gambleAmount * payoutMultiplier
            await Snekcoin.updateWallet(userId, round(winnings))
            return True, reels, winnings
        else:
            await Snekcoin.updateWallet(userId, -gambleAmount)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, gambleAmount)
            return False, reels, 0


# ===== </Gamble> =====

    @discord.app_commands.command(name="gamble")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(MEMBER)
    async def gamble(self, interaction: discord.Interaction) -> None:
        """Gamble your SnekCoins away!

        Builds button view for gambling games.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)
        log.debug(f"Snekcoin gamble: {interaction.user.id} [{interaction.user.display_name}] is opening the gambling menu.")

        embed = discord.Embed(title="🎲 SnekCoin Gambling 🎲", color=discord.Color.green(), description="Choose a game to play:")
        embed.add_field(name="🪙 Coin Flip 🪙", value="Flip a coin, win on heads!\nPayout: `1.5x`", inline=False)
        embed.add_field(name="🎲 Dice Roll 🎲", value="Roll a dice against the bot, largest roll wins!\nPayout: `1.9x`", inline=False)
        embed.add_field(name="🎰 Slots 🎰", value="50 coin bet, match 3 symbols to win big!\nPayout:\n🍒,🍋,🔔, ⭐ = `2.8x`\n💎 = `7x`\n7️⃣ = `25x`", inline=False)
        view = discord.ui.View(timeout=60)
        view.add_item(SnekcoinButton(None, label="🪙 Coin Flip 🪙", style=discord.ButtonStyle.success, custom_id="gambleCoinFlip", row=0))
        view.add_item(SnekcoinButton(None, label="🎲 Dice Roll 🎲", style=discord.ButtonStyle.success, custom_id="gambleDiceRoll", row=0))
        view.add_item(SnekcoinButton(None, label="🎰 Slots 🎰", style=discord.ButtonStyle.success, custom_id="gambleSlots", row=1))
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ===== </Gamble> =====

    @commands.command(name="snekleaderboard")
    async def snekLeaderboard(self, ctx: commands.Context) -> None:
        """Displays the SnekCoin leaderboard.

        Parameters:
        ctx (commands.Context): The command context.

        Returns:
        None.
        """
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Snekcoin snekleaderboard: ctx.guild not discord.Guild")
            return

        try:
            with open(WALLETS_FILE) as f:
                wallets = json.load(f)
        except Exception:
            wallets = {}

        embed = discord.Embed(title="🏆 SnekCoin Leaderboard 🏆", color=discord.Color.gold(), description = "")
        desLimit = DISCORD_LIMITS["message_embed"]["embed_description"]
        wallets = dict(sorted(wallets.items(), key=lambda item: item[1].get("money", 0), reverse=True))

        try:
            i = 1
            for userId in wallets:
                member = ctx.guild.get_member(int(userId))
                if member is None:
                    continue
                if wallets[userId].get("money", 0) == 0:
                    continue
                if len(embed.description + f"{i}. {member.mention}:🪙 `{wallets[userId].get('money', 0)}` SnekCoins\n") > desLimit:
                    await ctx.send(embed=embed)
                    embed.description = ""
                embed.description += f"{i}. {member.mention}:🪙 `{wallets[userId].get('money', 0)}` SnekCoins\n"
                i += 1
        except:
            log.exception("Snekcoin snekleaderboard: Failed to generate leaderboard fields.")
        await ctx.send(embed=embed)

    @commands.command(name="changesnekcoins")
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def changeSnekCoins(self, ctx: commands.Context, member: discord.Member, addRemove: str, amount: int) -> None:
        """Changes the amount of SnekCoins in a member's wallet.

        Parameters:
        ctx (commands.Context): The command context.
        member (discord.Member): Target member.
        addRemove (str): "add" to add SnekCoins, "remove" to remove SnekCoins.
        amount (int): Amount of SnekCoins to add or remove.

        Returns:
        None.
        """
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Snekcoin changeSnekCoins: ctx.guild not discord.Guild")
            return
        log.info(f"{ctx.author.id} [{ctx.author.display_name}] is changing SnekCoins for {member.id} [{member.display_name}]: {addRemove} {amount}")

        responses = {
            "add": {
                "add", "give", "grant", "award", "credit"
            },
            "remove": {
                "remove", "subtract", "deduct", "take", "revoke", "penalize", "debit"
            }
        }
        addRemove = addRemove.lower()
        if addRemove not in responses["add"] and addRemove not in responses["remove"]:
            await ctx.send("❌ Invalid operation! Use `add` or `remove`.")
            return
        if amount <= 0:
            await ctx.send("❌ Amount must be a positive integer!")
            return

        try:
            with open(WALLETS_FILE) as f:
                wallets = json.load(f)
        except FileNotFoundError:
            wallets = {}
        except Exception:
            await ctx.send("❌ Failed to load wallets file.")
            log.exception("Snekcoin changeSnekCoins: Failed to load wallets file.")
            return

        targetEntry = wallets.get(str(member.id), {"timesCommended": 0, "sentCommendations": 0, "money": 0, "moneySpent": 0})
        if addRemove in responses["add"]:
            targetEntry["money"] = int(targetEntry.get("money", 0)) + amount
            operationText = "added to"
        else:
            targetEntry["money"] = int(targetEntry.get("money", 0)) - amount
            operationText = "removed from"

        wallets[str(member.id)] = targetEntry
        try:
            with open(WALLETS_FILE, "w") as f:
                json.dump(wallets, f, indent=4)
        except Exception:
            log.warning("Snekcoin changeSnekCoins: Failed to save wallets file.")

        await ctx.send(f"✅ `{amount}` SnekCoins have been {operationText} {member.display_name}'s wallet.")


    @discord.app_commands.command(name="checkwallet")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.describe(user="User to check the wallet of (defaults to yourself).")
    @discord.app_commands.checks.has_any_role(MEMBER)
    async def checkWallet(self, interaction: discord.Interaction, user: discord.User | None = None) -> None:
        """Check your SnekCoin wallet.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)
        log.debug(f"Snekcoin checkWallet: {interaction.user.id} [{interaction.user.display_name}] is checking their wallet.")

        walletData = await Snekcoin.getWallet(user.id if user else interaction.user.id)
        if walletData is None:
            await interaction.followup.send("❌ Failed to retrieve your wallet data.", ephemeral=True)
            return

        embed = discord.Embed(title="💰 SnekCoin Wallet 💰", color=discord.Color.green())
        embed.add_field(name="Current Balance", value=f"🪙 `{walletData['money']}` SnekCoins", inline=False)
        embed.add_field(name="Total SnekCoins Spent", value=f"🪙 `{walletData['moneySpent']}` SnekCoins", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)


class SnekcoinButton(discord.ui.Button):
    """Handling all snekcoin buttons."""
    def __init__(self, message: discord.Message | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            log.exception("GambleButton callback: interaction.user not discord.Member")
            return

        if interaction.message is None:
            log.exception("GambleButton callback: interaction.message is None")
            return

        if not isinstance(interaction.guild, discord.Guild):
            log.exception("GambleButton callback: interaction.guild not discord.Guild")
            return

        customId = interaction.data["custom_id"]

        if customId == "gambleCoinFlip":
            view = self.view
            await interaction.response.send_modal(
                SnekcoinModal(
                    title="🪙 Coin Flip 🪙",
                    customId="gambleCoinFlipModal",
                    userId=interaction.user.id,
                    eventMsg=interaction.message,
                    view=view,
                )
            )
        if customId == "gambleDiceRoll":
            view = self.view
            await interaction.response.send_modal(
                SnekcoinModal(
                    title="🎲 Dice Roll 🎲",
                    customId="gambleDiceRollModal",
                    userId=interaction.user.id,
                    eventMsg=interaction.message,
                    view=view,
                )
            )
        if customId == "gambleSlots":
            embed = discord.Embed(title="🎰 Slots 🎰")
            money = (await Snekcoin.getWallet(interaction.user.id))['money']
            if money < 50:
                await interaction.response.send_message("❌ You need at least 50 SnekCoins to play Slots!", ephemeral=True)
                return
            if money is None:
                await interaction.followup.send("❌ Failed to retrieve your wallet data.", ephemeral=True)
                return
            if money < 50:
                await interaction.followup.send("❌ You need at least 50 SnekCoins to play Slots!", ephemeral=True)
                return

            winner, reels, winnings = await Snekcoin.gambleSlots(interaction.user.id, 50)
            if winner:
                embed.description = f"{interaction.user.mention} spun the slots:"
                embed.add_field(name=f"{' | '.join(reels)}", value="", inline=False)
                embed.add_field(name="", value=f"\n🎉 Congratulations! You won `{round(winnings)}` SnekCoins! 🎉\nCurrent Balance: `{(await Snekcoin.getWallet(interaction.user.id))['money']}`", inline=False)
                embed.color = discord.Color.green()
            else:
                embed.description = f"{interaction.user.mention} spun the slots:"
                embed.add_field(name=f"{' | '.join(reels)}", value="", inline=False)
                embed.add_field(name="", value=f"\n😢 You lost `50` SnekCoins! 😢\nCurrent Balance: `{(await Snekcoin.getWallet(interaction.user.id))['money']}`", inline=False)
                embed.color = discord.Color.red()
                embed.set_footer(text="You might want to call the gambler's anonymous helpline.")
            await interaction.response.send_message("Returning to gambling menu...", ephemeral=True, embed=interaction.message.embeds[0], view=self.view, delete_after=15)
            await interaction.followup.send(embed=embed, ephemeral=False)


class SnekcoinModal(discord.ui.Modal):
    """Handling all snekcoin modals."""
    def __init__(self, title: str, customId: str, userId: int, eventMsg: discord.Message, view: discord.ui.View | None = None) -> None:
        # Append userId to customId to not collide on multi-user simultaneous execution
        super().__init__(title=title, custom_id=f"{customId}_{userId}")
        self.eventMsg = eventMsg
        self.view = view
        self.userId = userId

        # Amount input
        self.amount: discord.ui.TextInput = discord.ui.TextInput(
            label="Amount to gamble",
            style=discord.TextStyle.short,
            required=True,
            min_length=1,
            max_length=10,
            placeholder="Amount to gamble (e.g., 100)",
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("SnekcoinModal on_submit: interaction.guild not discord.Guild")
            return

        customId = interaction.data["custom_id"].rsplit("_", 1)[0]

        if customId == "gambleCoinFlipModal":
            embed = discord.Embed(title="🪙 Coin Flip 🪙")
            try:
                amount = int(self.amount.value.strip())
            except ValueError:
                await interaction.response.send_message("❌ Invalid amount! Please enter a positive integer.", ephemeral=True)
                return
            if int(amount) <= 1:
                await interaction.response.send_message("❌ Amount must be above 1!", ephemeral=True)
                return
            if (amount > (await Snekcoin.getWallet(interaction.user.id))['money']):
                await interaction.response.send_message("❌ You do not have enough SnekCoins to gamble that amount!", ephemeral=True)
                return

            winner, payout = await Snekcoin.gambleCoinFlip(self.userId, amount)
            if winner:
                embed.description = f"It was Heads!\n{interaction.user.mention} gambled and won `{payout}` SnekCoins on a coin flip! 🎉\nCurrent Balance: `{(await Snekcoin.getWallet(interaction.user.id))['money']}`"
                embed.color = discord.Color.green()
            else:
                embed.description = f"It was Tails!\n{interaction.user.mention} gambled away and lost `{amount}` SnekCoins! 😢\nCurrent Balance: `{(await Snekcoin.getWallet(interaction.user.id))['money']}`"
                embed.color = discord.Color.red()

        if customId == "gambleDiceRollModal":
            embed = discord.Embed(title="🎲 Dice Roll 🎲")
            try:
                amount = int(self.amount.value.strip())
            except ValueError:
                await interaction.response.send_message("❌ Invalid amount! Please enter a positive integer.", ephemeral=True)
                return
            if int(amount) <= 1:
                await interaction.response.send_message("❌ Amount must be above 1!", ephemeral=True)
                return
            if (amount > (await Snekcoin.getWallet(interaction.user.id))['money']):
                await interaction.response.send_message("❌ You do not have enough SnekCoins to gamble that amount!", ephemeral=True)
                return

            winner, userRoll, botRoll, winnings = await Snekcoin.gambleDiceRoll(self.userId, amount)
            if winner:
                embed.description = f"{interaction.user.mention} rolled a `{userRoll}` against the bot's `{botRoll}` and won `{winnings}` SnekCoins 🎉\nCurrent Balance: `{(await Snekcoin.getWallet(interaction.user.id))['money']}`"
                embed.color = discord.Color.green()
            elif winner is None:
                embed.description = f"{interaction.user.mention} rolled a `{userRoll}` against the bot's `{botRoll}`. It's a tie! No SnekCoins were won or lost.\nCurrent Balance: `{(await Snekcoin.getWallet(interaction.user.id))['money']}`"
                embed.color = discord.Color.yellow()
            else:
                embed.description = f"{interaction.user.mention} rolled a `{userRoll}` against the bot's `{botRoll}` and lost `{amount}` SnekCoins! 😢\nCurrent Balance: `{(await Snekcoin.getWallet(interaction.user.id))['money']}`"
                embed.color = discord.Color.red()

        await interaction.response.send_message("Returning to gambling menu...", ephemeral=True, embed=interaction.message.embeds[0], view=self.view, delete_after=15)
        await interaction.followup.send(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    Snekcoin.gamble.error(Utils.onSlashError)
    await bot.add_cog(Snekcoin(bot))