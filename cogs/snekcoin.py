import json, discord, logging

from typing import Dict, Tuple, List
from random import random, randint, choice, choices

from discord.ext import commands  # type: ignore

from utils import Utils  # type: ignore
import secret
from constants import *
if secret.DEBUG:
    from constants.debug import *

log = logging.getLogger("FriendlySnek")


@discord.app_commands.guilds(GUILD)
@discord.app_commands.checks.has_any_role(MEMBER)
class Snekcoin(commands.GroupCog, name = "snekcoin"):
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
    async def getWallet(userId: int) -> Dict[str, int] | None:
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
    async def gambleCoinFlip(userId: int, gambleAmount: int) -> Tuple[bool, int]:
        """Gamble a coin flip.
        payout = 1.5 * gambleAmount

        Parameters:
        userId (int): The user ID.
        gambleAmount (int): The amount to gamble.

        Returns:
        bool: True if the user wins, False otherwise.
        int: The payout amount.
        """
        log.debug(f"Snekcoin gambleCoinFlip: User {userId} is gambling a coin flip.")
        results = random() < 0.62 # ~7% house edge with 1.5x payout
        payout = round(0.5 * gambleAmount)
        if results:
            await Snekcoin.updateWallet(userId, payout)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, -payout)

        if not results:
            await Snekcoin.updateWallet(userId, -gambleAmount)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, gambleAmount)

        return results, payout


    @staticmethod
    async def gambleDiceRoll(userId: int, gambleAmount: int) -> Tuple[bool | None, int, int, int]:
        """Gamble a dice roll.
        payout = 1.9 * gambleAmount

        Parameters:
        userId (int): The user ID.
        gambleAmount (int): The amount to gamble.

        Returns:
        bool | None: True if the user wins, False otherwise. None if tie.
        int: The user's roll.
        int: The bot's roll.
        int: The winnings amount.
        """
        log.debug(f"Snekcoin gambleDiceRoll: User {userId} is gambling a dice roll.")
        casinoEdge = True if random() < 0.0358 else False # ~7% casino edge with 1.9x payout
        userRoll = randint(1, 6)
        botRoll = randint(1, 6)
        winnings = round(0.9 * gambleAmount)
        if casinoEdge:
            botRoll = 6

        results = None if userRoll == botRoll else userRoll > botRoll
        if results:
            await Snekcoin.updateWallet(userId, winnings)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, -winnings)
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
            await Snekcoin.updateWallet(FRIENDLY_SNEK, -round(winnings))
            return True, reels, winnings
        else:
            await Snekcoin.updateWallet(userId, -gambleAmount)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, gambleAmount)
            return False, reels, 0


# ===== </Gamble> =====

    @discord.app_commands.command(name="gamble")
    async def gamble(self, interaction: discord.Interaction) -> None:
        """Gamble your SnekCoins away!

        Builds button view for gambling games.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        None.
        """
        log.debug(f"Snekcoin gamble: {interaction.user.id} [{interaction.user.display_name}] is opening the gambling menu.")

        embed = discord.Embed(title="🎲 SnekCoin Gambling 🎲", color=discord.Color.green(), description="Choose a game to play:")
        embed.add_field(name="🪙 Coin Flip 🪙", value="Flip a coin, win on heads!\nPayout: `1.5x`", inline=False)
        embed.add_field(name="🎲 Dice Roll 🎲", value="Roll a dice against the bot, largest roll wins!\nPayout: `1.9x`", inline=False)
        embed.add_field(name="🎰 Slots 🎰", value="50 coin bet, match 3 symbols to win big!\nPayout:\n🍒,🍋,🔔, ⭐ = `2.8x`\n💎 = `7x`\n7️⃣ = `25x`", inline=False)

        view = discord.ui.View(timeout=60)
        view.add_item(SnekcoinButton(None, emoji="🪙", label="Coin Flip", style=discord.ButtonStyle.success, custom_id="gambleCoinFlip", row=0))
        view.add_item(SnekcoinButton(None, emoji="🎲", label="Dice Roll", style=discord.ButtonStyle.success, custom_id="gambleDiceRoll", row=0))
        view.add_item(SnekcoinButton(None, emoji="🎰", label="Slots", style=discord.ButtonStyle.success, custom_id="gambleSlots", row=1))

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True, delete_after=30.0)


# ===== </Gamble> =====

    @discord.app_commands.command(name="snekleaderboard")
    async def snekLeaderboard(self, interaction: discord.Interaction) -> None:
        """Displays the SnekCoin leaderboard with pages.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        Returns:
        None.
        """
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("Snekcoin snekleaderboard: interaction.guild not discord.Guild")
            return

        try:
            with open(WALLETS_FILE) as f:
                wallets = json.load(f)
        except Exception:
            wallets = {}

        # Sort wallets by money in descending order
        wallets = dict(sorted(wallets.items(), key=lambda item: item[1].get("money", 0), reverse=True))

        # Build leaderboard pages as embeds
        embeds = []
        view = discord.ui.View(timeout=60)
        embed = discord.Embed(title="🏆 SnekCoin Leaderboard 🏆", color=discord.Color.gold())
        embed.description = ""
        count, pages = 1, 1

        for user in wallets:
            member = interaction.guild.get_member(int(user))
            if member is None:
                continue
            if wallets[user].get("money", 0) == 0:
                continue
            if len(embed.description) + len(f"{count}. **{member.mention}** - 🪙 `{wallets[user].get('money', 0)}` SnekCoins\n") > DISCORD_LIMITS["message_embed"]["embed_description"]:
                embeds.append(embed)
                embed = discord.Embed(title="🏆 SnekCoin Leaderboard 🏆", color=discord.Color.gold())
                embed.description = ""
                pages += 1
            embed.description += f"{count}. **{member.mention}** - 🪙 `{wallets[user].get('money', 0)}` SnekCoins\n"
            count += 1
        if embed.description:
            embeds.append(embed)
        for embed in embeds:
            embed.set_footer(text=f"Page {embeds.index(embed)+1} of {len(embeds)}")

        if len(embeds) > 1:
            view.add_item(SnekcoinButton(None, label="Previous", style=discord.ButtonStyle.primary, custom_id="leaderboardPrevious", row=0))
            view.add_item(SnekcoinButton(None, label="Next", style=discord.ButtonStyle.primary, custom_id="leaderboardNext", row=0))
            SnekcoinButton.leaderboardEmbeds = embeds
            SnekcoinButton.leaderboardCurrentPage = 0
        await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True, delete_after=60.0)


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

        auditLogs = self.bot.get_channel(AUDIT_LOGS)
        if auditLogs is None or not isinstance(auditLogs, discord.TextChannel):
            log.exception("Snekcoin changeSnekCoins: auditLogs channel is None or not discord.TextChannel")
            return
        embed = discord.Embed(
            title="🪙 SnekCoin Wallet Change 🪙",
            description=f"{ctx.author.mention} has {operationText} `{amount}` SnekCoins {'to' if operationText == 'added to' else 'from'} {member.mention}'s wallet.",
            color=discord.Color.blue()
        )
        await auditLogs.send(embed=embed)


    @commands.command(name="tradesnekcoins")
    @commands.has_any_role(*CMD_LIMIT_STAFF)
    async def tradeSnekCoins(self, ctx: commands.Context, fromMember: discord.Member, toMember: discord.Member, amount: int) -> None:
        """Trades SnekCoins from one member to another.

        Parameters:
        ctx (commands.Context): The command context.
        fromMember (discord.Member): Member to take SnekCoins from.
        toMember (discord.Member): Member to give SnekCoins to.
        amount (int): Amount of SnekCoins to trade.

        Returns:
        None.
        """
        if not isinstance(ctx.guild, discord.Guild):
            log.exception("Snekcoin tradeSnekCoins: ctx.guild not discord.Guild")
            return
        log.info(f"{ctx.author.id} [{ctx.author.display_name}] is trading SnekCoins from {fromMember.id} [{fromMember.display_name}] to {toMember.id} [{toMember.display_name}]: {amount}")

        if amount <= 0:
            await ctx.send("❌ Amount must be a positive integer!")
            return

        await Snekcoin.updateWallet(fromMember.id, -amount)
        await Snekcoin.updateWallet(toMember.id, amount)

        await ctx.send(f"✅ `{amount}` SnekCoins have been traded from {fromMember.display_name} to {toMember.display_name}.")

        auditLogs = self.bot.get_channel(AUDIT_LOGS)
        if auditLogs is None or not isinstance(auditLogs, discord.TextChannel):
            log.exception("Snekcoin tradeSnekCoins: auditLogs channel is None or not discord.TextChannel")
            return
        embed = discord.Embed(
            title="🪙 SnekCoin Trade 🪙",
            description=f"{ctx.author.mention} has traded `{amount}` SnekCoins from {fromMember.mention} to {toMember.mention}.",
            color=discord.Color.blue()
        )
        await auditLogs.send(embed=embed)


    @discord.app_commands.command(name="checkwallet")
    @discord.app_commands.describe(user="User to check the wallet of (defaults to yourself).")
    async def checkWallet(self, interaction: discord.Interaction, user: discord.User | None = None) -> None:
        """Check your SnekCoin wallet.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        user (discord.User | None): The user to check the wallet of.

        Returns:
        None.
        """
        log.debug(f"Snekcoin checkWallet: {interaction.user.id} [{interaction.user.display_name}] is checking their wallet.")

        walletData = await Snekcoin.getWallet(user.id if user else interaction.user.id)
        if walletData is None:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True, delete_after=15.0)
            return

        embed = discord.Embed(title="💰 SnekCoin Wallet 💰", color=discord.Color.green())
        embed.add_field(name="Current Balance", value=f"🪙 `{walletData['money']}` SnekCoins", inline=False)
        embed.add_field(name="Total SnekCoins Spent", value=f"🪙 `{walletData['moneySpent']}` SnekCoins", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30.0)


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
            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None or userWallet["money"] is None:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True, delete_after=15.0)
                return

            if userWallet["money"] < 50:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Insufficient funds", description=f"You need at least 50 SnekCoins to play Slots!\nWallet balance: `{userWallet['money']}` SnekCoins"), ephemeral=True, delete_after=15.0)
                return

            winner, reels, winnings = await Snekcoin.gambleSlots(interaction.user.id, 50)
            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True, delete_after=15.0)
                return

            if winner:
                embed.color = discord.Color.green()
                embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
                embed.add_field(name="Result", value=f"{' | '.join(reels)}", inline=False)
                embed.add_field(name="🪙 You won!", value=f"**{round(winnings)}** SnekCoins", inline=False)
                embed.add_field(name="💰 Balance", value=f"**{userWallet['money']}** SnekCoins")
            else:
                embed.color = discord.Color.red()
                embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
                embed.add_field(name="Result", value=f"{' | '.join(reels)}", inline=False)
                embed.add_field(name="You lost", value=f"**50** SnekCoins", inline=False)
                embed.add_field(name="💰 Balance", value=f"**{userWallet['money']}** SnekCoins")
                embed.add_field(name="\u200B", value="-# [Gamblers anonymous helpline](https://gamblersanonymous.org/)", inline=False)

            await interaction.response.send_message("Returning to gambling menu...", ephemeral=True, embed=interaction.message.embeds[0], view=self.view, delete_after=15.0)
            await interaction.followup.send(embed=embed, ephemeral=False)

        if customId == "leaderboardPrevious":
            if not SnekcoinButton.leaderboardEmbeds:
                log.exception("SnekcoinButton callback: No embeds found for leaderboardPrevious")
                return
            if SnekcoinButton.leaderboardCurrentPage == 0:
                SnekcoinButton.leaderboardCurrentPage = len(SnekcoinButton.leaderboardEmbeds) - 1
            else:
                SnekcoinButton.leaderboardCurrentPage -= 1
            await interaction.response.edit_message(embed=SnekcoinButton.leaderboardEmbeds[SnekcoinButton.leaderboardCurrentPage])
        if customId == "leaderboardNext":
            if not SnekcoinButton.leaderboardEmbeds:
                log.exception("SnekcoinButton callback: No embeds found for leaderboardNext")
                return
            if SnekcoinButton.leaderboardCurrentPage == len(SnekcoinButton.leaderboardEmbeds) - 1:
                SnekcoinButton.leaderboardCurrentPage = 0
            else:
                SnekcoinButton.leaderboardCurrentPage += 1
            await interaction.response.edit_message(embed=SnekcoinButton.leaderboardEmbeds[SnekcoinButton.leaderboardCurrentPage])


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
            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True, delete_after=15.0)
                return

            embed = discord.Embed(title="🪙 Coin Flip 🪙")
            try:
                amount = int(self.amount.value.strip())
            except ValueError:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Please enter a positive integer."), ephemeral=True, delete_after=15.0)
                return
            if int(amount) <= 1:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Amount must be above 1!"), ephemeral=True, delete_after=15.0)
                return
            if (amount > userWallet["money"]):
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Insufficient funds", description=f"You do not have enough SnekCoins to gamble that amount!\nWallet balance: `{userWallet['money']}` SnekCoins"), ephemeral=True, delete_after=15.0)
                return

            winner, payout = await Snekcoin.gambleCoinFlip(self.userId, amount)
            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True, delete_after=15.0)
                return

            if winner:
                embed.color = discord.Color.green()
                embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
                embed.add_field(name="Result", value="Heads")
                embed.add_field(name="🪙 You won!", value=f"**{payout}** SnekCoins", inline=False)
                embed.add_field(name="💰 Balance", value=f"**{userWallet['money']}** SnekCoins")
            else:
                embed.color = discord.Color.red()
                embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
                embed.add_field(name="Result", value="Tails")
                embed.add_field(name="You lost", value=f"**{amount}** SnekCoins", inline=False)
                embed.add_field(name="💰 Balance", value=f"**{userWallet['money']}** SnekCoins")

        if customId == "gambleDiceRollModal":
            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True, delete_after=15.0)
                return

            embed = discord.Embed(title="🎲 Dice Roll 🎲")
            try:
                amount = int(self.amount.value.strip())
            except ValueError:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Please enter a positive integer."), ephemeral=True, delete_after=15.0)
                return
            if int(amount) <= 1:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Amount must be above 1!"), ephemeral=True, delete_after=15.0)
                return
            if (amount > userWallet["money"]):
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Insufficient funds", description=f"You do not have enough SnekCoins to gamble that amount!\nWallet balance: `{userWallet['money']}` SnekCoins"), ephemeral=True, delete_after=15.0)
                return

            winner, userRoll, botRoll, winnings = await Snekcoin.gambleDiceRoll(self.userId, amount)
            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True, delete_after=15.0)
                return

            if winner:
                embed.color = discord.Color.green()
                embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
                embed.add_field(name="Result", value=f"You rolled: **{userRoll}**\nSnek rolled: **{botRoll}**")
                embed.add_field(name="🪙 You won!", value=f"**{winnings}** SnekCoins", inline=False)
                embed.add_field(name="💰 Balance", value=f"**{userWallet['money']}** SnekCoins")

            elif winner is None:
                embed.color = discord.Color.gold()
                embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
                embed.add_field(name="Result", value=f"You rolled: **{userRoll}**\nSnek rolled: **{botRoll}**")
                embed.add_field(name="It's a tie!", value=f"No SnekCoins were won or lost", inline=False)
                embed.add_field(name="💰 Balance", value=f"**{userWallet['money']}** SnekCoins")

            else:
                embed.color = discord.Color.red()
                embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
                embed.add_field(name="Result", value=f"You rolled: **{userRoll}**\nSnek rolled: **{botRoll}**")
                embed.add_field(name="You lost", value=f"**{amount}** SnekCoins", inline=False)
                embed.add_field(name="💰 Balance", value=f"**{userWallet['money']}** SnekCoins")

        await interaction.response.send_message("Returning to gambling menu...", ephemeral=True, embed=interaction.message.embeds[0], view=self.view, delete_after=15.0)
        await interaction.followup.send(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    Snekcoin.gamble.error(Utils.onSlashError)
    Snekcoin.checkWallet.error(Utils.onSlashError)
    Snekcoin.snekLeaderboard.error(Utils.onSlashError)
    await bot.add_cog(Snekcoin(bot))