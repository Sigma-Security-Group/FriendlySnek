import json, discord, logging

from typing import Dict, Tuple, List, Literal
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
        userWallet = wallets.get(userIdStr, {"timesCommended": 0, "sentCommendations": 0, "money": 0, "moneySpent": 0, "timesBumped": 0})
        return userWallet


    @staticmethod
    async def updateWallet(
        userId: int,
        walletType: Literal["timesCommended", "sentCommendations", "money", "moneySpent", "timesBumped"],
        amount: int
    ) -> None:
        """Update the wallet type of a user.

        Parameters:
        userId (int): The user ID.
        walletType (str): The type of wallet to update.
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

        if walletType not in {"timesCommended", "sentCommendations", "money", "moneySpent", "timesBumped"}:
            log.exception(f"Snekcoin updateWallet: Invalid walletType '{walletType}'")
            return

        userIdStr = str(userId)
        defaultWallet = {"timesCommended": 0, "sentCommendations": 0, "money": 0, "moneySpent": 0, "timesBumped": 0}
        userWallet = wallets.get(userIdStr, defaultWallet)
        if not isinstance(userWallet, dict):
            userWallet = defaultWallet.copy()

        if walletType == "money":
            userWallet["money"] += amount
            if amount < 0:
                userWallet["moneySpent"] -= amount

        if walletType in {"timesCommended", "sentCommendations", "timesBumped"}:
            if userWallet.get(walletType) is None:
                userWallet[walletType] = 0
            userWallet[walletType] += amount

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
        results = random() < 0.62 # ~7% house edge with 1.5x payout
        payout = round(0.5 * gambleAmount)
        if results:
            await Snekcoin.updateWallet(userId, "money", payout)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, "money", -payout)

        if not results:
            await Snekcoin.updateWallet(userId, "money", -gambleAmount)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, "money", gambleAmount)

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
        casinoEdge = True if random() < 0.0358 else False # ~7% casino edge with 1.9x payout
        userRoll = randint(1, 6)
        botRoll = randint(1, 6)
        winnings = round(0.9 * gambleAmount)
        if casinoEdge:
            botRoll = 6

        results = None if userRoll == botRoll else userRoll > botRoll
        if results:
            await Snekcoin.updateWallet(userId, "money", winnings)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, "money", -winnings)
            return results, userRoll, botRoll, winnings

        if results is None:
            return results, userRoll, botRoll, winnings

        if not results:
            await Snekcoin.updateWallet(userId, "money", -gambleAmount)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, "money", gambleAmount)

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
            await Snekcoin.updateWallet(userId, "money", round(winnings))
            await Snekcoin.updateWallet(FRIENDLY_SNEK, "money", -round(winnings))
            return True, reels, winnings
        else:
            await Snekcoin.updateWallet(userId, "money", -gambleAmount)
            await Snekcoin.updateWallet(FRIENDLY_SNEK, "money", gambleAmount)
            return False, reels, 0

    @staticmethod
    async def gambleMenu(interaction: discord.Interaction) -> Tuple[discord.Embed, discord.ui.View] | None:
        """Build the gambling menu.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.

        Returns:
        discord.Embed: The gambling menu embed.
        discord.ui.View: The gambling menu view.
        """
        embed = discord.Embed(title="🎲 SnekCoin Gambling 🎲", color=discord.Color.green(), description="Choose a game to play:")
        embed.add_field(name="🪙 Coin Flip 🪙", value="Flip a coin, win on heads!\nPayout: `1.5x`", inline=False)
        embed.add_field(name="🎲 Dice Roll 🎲", value="Roll a dice against the bot, largest roll wins!\nPayout: `1.9x`", inline=False)
        embed.add_field(name="🎰 Slots 🎰", value="50 coin bet, match 3 symbols to win big!\nPayout:\n🍒,🍋,🔔, ⭐ = `2.8x`\n💎 = `7x`\n7️⃣ = `25x`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", inline=False)

        wallet = await Snekcoin.getWallet(interaction.user.id)
        if wallet is None:
            await interaction.response.send_message(
                embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve wallet information."),
                ephemeral=True,
                delete_after=15.0
            )
            return

        embed.add_field(name="Current Balance", value=f"🪙 `{wallet['money']}` SnekCoins", inline=False)

        view = discord.ui.View(timeout=60)
        view.add_item(SnekcoinButton(None, emoji="🪙", label="Coin Flip", style=discord.ButtonStyle.success, custom_id=f"snekcoin_button_coinFlip_{interaction.user.id}"))
        view.add_item(SnekcoinButton(None, emoji="🎲", label="Dice Roll", style=discord.ButtonStyle.success, custom_id=f"snekcoin_button_diceRoll_{interaction.user.id}"))
        view.add_item(SnekcoinButton(None, emoji="🎰", label="Slots", style=discord.ButtonStyle.success, custom_id=f"snekcoin_button_slots_{interaction.user.id}", row=1))

        return embed, view


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
        await interaction.response.defer(ephemeral=True, thinking=True)

        menu = await Snekcoin.gambleMenu(interaction)
        if menu is None:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not build gambling menu."), ephemeral=True, delete_after=15.0)
            return

        embed, view = menu
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ===== </Gamble> =====

    @discord.app_commands.command(name="leaderboard")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        """Displays the SnekCoin leaderboard with pages.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        Returns:
        None.
        """
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("Snekcoin leaderboard: interaction.guild not discord.Guild")
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

        if not embeds:
            await interaction.response.send_message(
                embed=discord.Embed(color=discord.Color.red(), title="🏆 SnekCoin Leaderboard 🏆", description="No leaderboard entries yet."),
                ephemeral=True,
                delete_after=30.0
            )
            return

        if len(embeds) > 1:
            view.add_item(SnekcoinButton(None, label="Previous", style=discord.ButtonStyle.primary, custom_id=f"snekcoin_button_leaderboardPrevious_{interaction.user.id}"))
            view.add_item(SnekcoinButton(None, label="Next", style=discord.ButtonStyle.primary, custom_id=f"snekcoin_button_leaderboardNext_{interaction.user.id}"))
            SnekcoinButton.leaderboardEmbeds = embeds
            SnekcoinButton.leaderboardCurrentPage = 0
        await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True, delete_after=60.0)


    @discord.app_commands.command(name="payday")
    @discord.app_commands.describe(actual="Who was the Actual?",
                                   tl1="Team leader to get paid. (Optional)",
                                   tl2="Team leader to get paid. (Optional)",
                                   tl3="Team leader to get paid. (Optional)",
                                   tl4="Team leader to get paid. (Optional)",
                                   tl5="Team leader to get paid. (Optional)",
                                   )
    @discord.app_commands.checks.has_any_role(*CMD_LIMIT_ZEUS)
    async def payday(self, interaction: discord.Interaction, actual: discord.Member, tl1: discord.Member | None = None, tl2: discord.Member | None = None, tl3: discord.Member | None = None, tl4: discord.Member | None = None, tl5: discord.Member | None = None) -> None:
        """Pays SnekCoins to Zeus who runs the command, Actual, and TLs after an operation.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        actual (discord.Member): The Actual to pay.
        tl1 (discord.Member | None): Team leader to pay.
        tl2 (discord.Member | None): Team leader to pay.
        tl3 (discord.Member | None): Team leader to pay.
        tl4 (discord.Member | None): Team leader to pay.
        tl5 (discord.Member | None): Team leader to pay.

        Returns:
        None.
        """
        log.debug(f"Snekcoin payday: {interaction.user.id} [{interaction.user.display_name}] is processing payday.")
        auditLogs = self.bot.get_channel(AUDIT_LOGS)
        if not isinstance(auditLogs, discord.TextChannel):
            log.exception("Snekcoin payday: auditLogs channel is None or not discord.TextChannel")
            return

        zeusPay,actualPay = randint(100, 200), randint(100, 200)

        if actual.id == interaction.user.id:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid selection", description="You as a Zeus cannot be Actual!"), ephemeral=True, delete_after=15.0)
            return
        if actual.bot:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid selection", description="Actual cannot be a bot!"), ephemeral=True, delete_after=15.0)
            return

        await Snekcoin.updateWallet(interaction.user.id, "money", zeusPay)
        await Snekcoin.updateWallet(actual.id, "money", actualPay)
        paidTLs = {}
        skippedTls = {}

        # Pay TLs
        for tl in [tl1, tl2, tl3, tl4, tl5]:
            if tl is not None:
                if tl.bot:
                    log.warning(f"Snekcoin payday: TL {tl.id} [{tl.display_name}] is the bot, skipping payment.")
                    skippedTls[tl.display_name] = "TL is a bot"
                    continue
                if tl.id == actual.id:
                    log.warning(f"Snekcoin payday: TL {tl.id} [{tl.display_name}] is the Actual, skipping payment.")
                    skippedTls[tl.display_name] = "TL is the Actual"
                    continue
                if tl.id == interaction.user.id:
                    log.warning(f"Snekcoin payday: TL {tl.id} [{tl.display_name}] is the Zeus, skipping payment.")
                    skippedTls[tl.display_name] = "TL is the Zeus"
                    continue
                if tl.get_role(MEMBER) is None:
                    log.warning(f"Snekcoin payday: TL {tl.id} [{tl.display_name}] does not have MEMBER role, skipping payment.")
                    skippedTls[tl.display_name] = "TL does not have MEMBER role"
                    continue
                if tl.mention in paidTLs:
                    log.warning(f"Snekcoin payday: TL {tl.id} [{tl.display_name}] has already been paid, skipping payment.")
                    skippedTls[tl.display_name] = "TL has already been paid"
                    continue
                tlPay = randint(50, 100)
                await Snekcoin.updateWallet(tl.id, "money", tlPay)
                paidTLs[tl.mention] = tlPay

        # Build and send payday summary embed
        embed = discord.Embed(title="💰 Payday Processed 💰", color=discord.Color.gold())
        embed.add_field(name="Zeus", value=f"{interaction.user.mention} hosted the Operation and was paid 🪙 `{zeusPay}` SnekCoins.", inline=False)
        embed.add_field(name="Actual", value=f"{actual.mention} was paid 🪙 `{actualPay}` SnekCoins.", inline=False)
        if paidTLs:
            tlPaymentText = "\n".join([f"{tl}: 🪙 `{amount}` SnekCoins" for tl, amount in paidTLs.items()])
            embed.add_field(name="Team Leaders Paid", value=tlPaymentText, inline=False)
        embed.set_footer(text="Thank you for hosting the operation!")

        commendationsChannel = self.bot.get_channel(COMMENDATIONS)

        if not isinstance(commendationsChannel, discord.TextChannel):
            log.exception("Snekcoin payday: commendationsChannel is None or not discord.TextChannel")
            return

        await commendationsChannel.send(embed=embed)
        if not skippedTls:
            await interaction.response.send_message(
                embed=discord.Embed(color=discord.Color.green(), title="✅ Payday Processed", description="Payday has been processed successfully.\nThank you for hosting!"),
                ephemeral=True,
                delete_after=15.0
            )
        else:
            skippedText = "\n".join([f"- {tl}: {reason}" for tl, reason in skippedTls.items()])
            await interaction.response.send_message(
                embed=discord.Embed(color=discord.Color.gold(), title="✅ Payday Processed", description=f"Payday has been processed successfully.\nThank you for hosting!\n\n⚠️ Some Team Leaders were not paid:\n{skippedText}"),
                ephemeral=True,
                delete_after=30.0
            )

        tlMentions = (f"- Team Leaders:\n" + "\n".join([f"  - {tl}: 🪙 `{amount}` SnekCoins" for tl, amount in paidTLs.items()]) if paidTLs else "")

        embed = discord.Embed(
            title="💰 Payday Executed 💰",
            description=f"{interaction.user.mention} has executed payday.\n\n**Payments:**\n" \
            f"- Zeus: {interaction.user.mention} - 🪙 `{zeusPay}` SnekCoins\n- Actual: {actual.mention} - 🪙 `{actualPay}` SnekCoins\n{tlMentions}",
            color=discord.Color.blue()
        )
        await auditLogs.send(embed=embed)


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
            await ctx.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid operation", description="Use `add` or `remove`."))
            return
        if amount <= 0:
            await ctx.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Amount must be a positive integer."))
            return

        try:
            with open(WALLETS_FILE) as f:
                wallets = json.load(f)
        except FileNotFoundError:
            wallets = {}
        except Exception:
            await ctx.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Failed to load wallets file."))
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

        await ctx.send(embed=discord.Embed(color=discord.Color.green(), title="✅ Wallet updated", description=f"`{amount}` SnekCoins have been {operationText} {member.display_name}'s wallet."))

        auditLogs = self.bot.get_channel(AUDIT_LOGS)
        if not isinstance(auditLogs, discord.TextChannel):
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
            await ctx.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Amount must be a positive integer."))
            return

        await Snekcoin.updateWallet(fromMember.id, "money", -amount)
        await Snekcoin.updateWallet(toMember.id, "money", amount)

        await ctx.send(embed=discord.Embed(color=discord.Color.green(), title="✅ Trade complete", description=f"`{amount}` SnekCoins have been traded from {fromMember.display_name} to {toMember.display_name}."))

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


    @discord.app_commands.command(name="gift")
    @discord.app_commands.describe(user="User to gift SnekCoins to.", amount="Amount of SnekCoins to gift.")
    async def gift(self, interaction: discord.Interaction, user: discord.Member, amount: int) -> None:
        """Gift SnekCoins to another user.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        user (discord.Member): The user to receive the gift.
        amount (int): Amount of SnekCoins to gift.

        Returns:
        None.
        """
        if not isinstance(interaction.user, discord.Member):
            log.exception("Snekcoin gift: interaction.user not discord.Member")
            return

        if user.id == interaction.user.id:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid recipient", description="You cannot gift SnekCoins to yourself."), ephemeral=True, delete_after=15.0)
            return
        if amount <= 0:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Amount must be a positive integer."), ephemeral=True, delete_after=15.0)
            return

        senderWallet = await Snekcoin.getWallet(interaction.user.id)
        if senderWallet is None:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True, delete_after=15.0)
            return
        if senderWallet["money"] < amount:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Insufficient funds", description=f"You do not have enough SnekCoins to gift that amount!\nWallet balance: `{senderWallet['money']}` SnekCoins"), ephemeral=True, delete_after=15.0)
            return

        await Snekcoin.updateWallet(interaction.user.id, "money", -amount)
        await Snekcoin.updateWallet(user.id, "money", amount)

        embed = discord.Embed(
            color=discord.Color.gold(),
            title="SnekCoin Gift 🎁",
            description=f"You gave **{amount}** SnekCoins to {user.mention}"
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
        await interaction.response.send_message(embed=embed)


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

        if customId.startswith("snekcoin_button_bumpBonus_"):
            originalUserId = int(customId.split("_")[3])
            originalMember = interaction.guild.get_member(originalUserId)
            if originalMember is None:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="The original bumper is no longer in the server."), ephemeral=True, delete_after=15.0)
                return

            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True, delete_after=15.0)
                return

            if userWallet["timesBumped"] >= MAX_BUMPS:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Bump Bonus Unavailable", description=f"You have already received the maximum of {MAX_BUMPS} bump bonuses today."), ephemeral=True, delete_after=15.0)
                return

            award = randint(10, 100)
            await interaction.message.delete()
            await Snekcoin.updateWallet(interaction.user.id, "money", award)
            embed = discord.Embed(
                color=discord.Color.green(),
                title="✅ Bonus Awarded",
                description=f"You have been awarded 🪙 `{award}` SnekCoins from {originalMember.mention}'s bump bonus!\nThis does not count towards your daily bump bonus limit."
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
            await interaction.response.send_message(embed=embed)
            return

        if customId.startswith("snekcoin_button_coinFlip"):
            view = self.view
            await interaction.response.send_modal(
                SnekcoinModal(
                    title="🪙 Coin Flip 🪙",
                    customId=f"snekcoin_modal_gambleCoinFlip",
                    userId=interaction.user.id,
                    eventMsg=interaction.message,
                    view=view,
                )
            )
        if customId.startswith("snekcoin_button_diceRoll"):
            view = self.view
            await interaction.response.send_modal(
                SnekcoinModal(
                    title="🎲 Dice Roll 🎲",
                    customId=f"snekcoin_modal_gambleDiceRoll",
                    userId=interaction.user.id,
                    eventMsg=interaction.message,
                    view=view,
                )
            )
        if customId.startswith("snekcoin_button_slots"):
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

            menu = await Snekcoin.gambleMenu(interaction)
            if menu is None:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not build gambling menu."), ephemeral=True, delete_after=15.0)
                return

            await interaction.response.send_message(
                embed=discord.Embed(color=discord.Color.blurple(), title="🎲 Returning to gambling menu"),
                ephemeral=True,
                delete_after=30.0
            )
            menuEmbed, menuView = menu
            await interaction.followup.send(embed=menuEmbed, view=menuView, ephemeral=True)
            await interaction.followup.send(embed=embed, ephemeral=False)

        if customId.startswith("snekcoin_button_leaderboardPrevious"):
            if not SnekcoinButton.leaderboardEmbeds:
                log.exception("SnekcoinButton callback: No embeds found for leaderboardPrevious")
                return
            if SnekcoinButton.leaderboardCurrentPage == 0:
                SnekcoinButton.leaderboardCurrentPage = len(SnekcoinButton.leaderboardEmbeds) - 1
            else:
                SnekcoinButton.leaderboardCurrentPage -= 1
            await interaction.response.edit_message(embed=SnekcoinButton.leaderboardEmbeds[SnekcoinButton.leaderboardCurrentPage])
        if customId.startswith("snekcoin_button_leaderboardNext"):
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

        customId = interaction.data["custom_id"]

        await interaction.response.defer(ephemeral=True, thinking=True)

        if customId.startswith("snekcoin_modal_gambleCoinFlip"):
            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None:
                await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True)
                return

            embed = discord.Embed(title="🪙 Coin Flip 🪙")
            try:
                amount = int(self.amount.value.strip())
            except ValueError:
                await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Please enter a positive integer."), ephemeral=True)
                return
            if int(amount) <= 1:
                await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Amount must be above 1!"), ephemeral=True)
                return
            if (amount > userWallet["money"]):
                await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Insufficient funds", description=f"You do not have enough SnekCoins to gamble that amount!\nWallet balance: `{userWallet['money']}` SnekCoins"), ephemeral=True)
                return

            winner, payout = await Snekcoin.gambleCoinFlip(self.userId, amount)
            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None:
                await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True)
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

        if customId.startswith("snekcoin_modal_gambleDiceRoll"):
            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None:
                await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True)
                return

            embed = discord.Embed(title="🎲 Dice Roll 🎲")
            try:
                amount = int(self.amount.value.strip())
            except ValueError:
                await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Please enter a positive integer."), ephemeral=True)
                return
            if int(amount) <= 1:
                await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Invalid amount", description="Amount must be above 1!"), ephemeral=True)
                return
            if (amount > userWallet["money"]):
                await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Insufficient funds", description=f"You do not have enough SnekCoins to gamble that amount!\nWallet balance: `{userWallet['money']}` SnekCoins"), ephemeral=True)
                return

            winner, userRoll, botRoll, winnings = await Snekcoin.gambleDiceRoll(self.userId, amount)
            userWallet = await Snekcoin.getWallet(interaction.user.id)
            if userWallet is None:
                await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not retrieve your wallet data."), ephemeral=True)
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

        menu = await Snekcoin.gambleMenu(interaction)
        if menu is None:
            await interaction.followup.send(embed=discord.Embed(color=discord.Color.red(), title="❌ Failed", description="Could not build gambling menu."), ephemeral=True)
            return

        menuEmbed, menuView = menu
        await interaction.followup.send(embed=discord.Embed(color=discord.Color.blurple(), title="🎲 Returning to gambling menu"), ephemeral=True)
        await interaction.followup.send(embed=menuEmbed, view=menuView, ephemeral=True)
        await interaction.followup.send(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    Snekcoin.gamble.error(Utils.onSlashError)
    Snekcoin.gift.error(Utils.onSlashError)
    Snekcoin.checkWallet.error(Utils.onSlashError)
    Snekcoin.leaderboard.error(Utils.onSlashError)
    Snekcoin.payday.error(Utils.onSlashError)
    await bot.add_cog(Snekcoin(bot))
