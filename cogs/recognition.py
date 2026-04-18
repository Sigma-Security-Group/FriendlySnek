import json, re, discord, logging

from copy import deepcopy
from datetime import datetime, timezone
from typing import *
from random import random, randint, choice

from discord.ext import commands  # type: ignore

from utils import Utils  # type: ignore
import secret
from constants import *
if secret.DEBUG:
    from constants.debug import *


PROMOTION_RECOMMENDATION_CONFIRMATION_TEXT = (
    "Promotion recommendations should only be made after thorough evaluation against the rank criteria. Approval requires that both the Primary and Secondary recommender have directly observed the individual consistently meeting all criteria for the proposed rank over multiple operations. Recommendations that do not meet this standard should not be submitted.\n\n"
    "Review the full set of criteria for the recommended rank and confirm that the individual meets all these requirements by typing `I confirm` below."
)


log = logging.getLogger("FriendlySnek")


async def send_interaction_response(
    interaction: discord.Interaction,
    *,
    content: str | None = None,
    embed: discord.Embed = discord.Embed(),
    embeds: list[discord.Embed] | None = None,
    ephemeral: bool = True,
    delete_after: float | None = None,
    view: discord.ui.View = discord.ui.View()
) -> None:
    embeds = [] if embeds is None else embeds
    if not embeds and embed:
        embeds = [embed]
    if interaction.response.is_done():
        await interaction.followup.send(content=content, embeds=embeds, ephemeral=ephemeral, view=view)
    else:
        await interaction.response.send_message(content=content, embeds=embeds, ephemeral=ephemeral, delete_after=delete_after, view=view)


class Recognition(commands.Cog):
    """Recognition Cog."""
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @staticmethod
    def _getPromotionTrackRanks(member: discord.Member) -> list[int]:
        return [role.id for role in member.roles if role.id in PROMOTION_TRACK_RANKS]

    @staticmethod
    def _meetsPromotionRecommendationRequirement(member: discord.Member, targetRankId: int) -> bool:
        requiredRoleIds = PROMOTION_RECOMMENDATION_MINIMUM_RECOMMENDER_ROLES.get(targetRankId, ())
        memberRoleIds = {role.id for role in member.roles}
        return any(roleId in memberRoleIds for roleId in requiredRoleIds)

    @staticmethod
    def _formatRoleMentions(guild: discord.Guild, roleIds: Iterable[int]) -> str:
        roleMentions = []
        for roleId in roleIds:
            role = guild.get_role(roleId)
            roleMentions.append(role.mention if role is not None else f"`{roleId}`")
        return " or ".join(roleMentions)

    @staticmethod
    def _validatePromotionRecommendation(
        guild: discord.Guild,
        *,
        memberId: int,
        firstRecommenderId: int,
        secondRecommenderId: int,
        targetRankId: int | None = None
    ) -> tuple[dict[str, Any] | None, discord.Embed | None]:
        member = guild.get_member(memberId)
        firstRecommender = guild.get_member(firstRecommenderId)
        secondRecommender = guild.get_member(secondRecommenderId)

        roleMember = guild.get_role(MEMBER)
        if roleMember is None:
            log.exception("Recognition _validatePromotionRecommendation: MEMBER role not found in guild")
            return None, discord.Embed(title="❌ Server misconfiguration", description="The server is missing the required MEMBER role. Please contact Unit Staff.", color=discord.Color.red())

        if not isinstance(member, discord.Member):
            return None, discord.Embed(title="❌ Member not found", color=discord.Color.red())
        if not isinstance(firstRecommender, discord.Member):
            log.exception("Recognition _validatePromotionRecommendation: firstRecommender not discord.Member")
            return None, discord.Embed(title="❌ Failed to resolve the Primary recommender", color=discord.Color.red())
        if not isinstance(secondRecommender, discord.Member):
            return None, discord.Embed(title="❌ Secondary recommender not found", color=discord.Color.red())

        if member.bot:
            return None, discord.Embed(title="❌ Invalid target", description="You cannot recommend bots for promotion.", color=discord.Color.red())
        if MEMBER not in {role.id for role in firstRecommender.roles}:
            return None, discord.Embed(title="❌ Invalid recommender", description=f"The Primary recommender {firstRecommender.mention} does not have the {roleMember.mention} role.", color=discord.Color.red())
        if secondRecommender.bot:
            return None, discord.Embed(title="❌ Invalid recommender", description="The Secondary recommender cannot be a bot.", color=discord.Color.red())
        if MEMBER not in {role.id for role in secondRecommender.roles}:
            return None, discord.Embed(title="❌ Invalid recommender", description=f"The Secondary recommender {secondRecommender.mention} does not have the {roleMember.mention} role.", color=discord.Color.red())
        if member.id == firstRecommender.id:
            return None, discord.Embed(title="❌ Invalid target", description="You cannot recommend yourself for promotion.", color=discord.Color.red())
        if member.id == secondRecommender.id:
            return None, discord.Embed(title="❌ Invalid recommender", description="The Secondary recommender cannot be the member being recommended.", color=discord.Color.red())
        if firstRecommender.id == secondRecommender.id:
            return None, discord.Embed(title="❌ Duplicate recommenders", description="Promotion recommendations require two different recommenders.", color=discord.Color.red())

        memberRankIds = Recognition._getPromotionTrackRanks(member)
        if len(memberRankIds) == 0:
            return None, discord.Embed(title="❌ No promotion rank found", description=f"{member.mention} does not have a recognized promotion-track rank.", color=discord.Color.red())
        if len(memberRankIds) > 1:
            return None, discord.Embed(title="❌ Ambiguous promotion rank", description=f"{member.mention} has multiple promotion-track ranks. Please contact Unit Staff.", color=discord.Color.red())

        currentRankId = memberRankIds[0]
        if currentRankId == PROSPECT:
            return None, discord.Embed(title="❌ Invalid target", description=f"{member.mention} is a Prospect and must go through the interview process instead.", color=discord.Color.red())
        if currentRankId not in PROMOTION_RECOMMENDATION_SOURCE_RANKS:
            return None, discord.Embed(title="❌ Invalid target", description=f"{member.mention} cannot be recommended for promotion from their current rank.", color=discord.Color.red())
        if MEMBER not in {role.id for role in member.roles}:
            return None, discord.Embed(title="❌ Invalid target", description=f"{member.mention} does not have the {roleMember.mention} role.", color=discord.Color.red())

        allowedTargetIds = tuple(PROMOTION_RECOMMENDATION_ALLOWED_TARGETS.get(currentRankId, ()))
        if len(allowedTargetIds) == 0:
            return None, discord.Embed(title="❌ No possible promotion", description=f"{member.mention} cannot be recommended for promotion through this command.", color=discord.Color.red())

        if targetRankId is not None:
            if targetRankId not in allowedTargetIds:
                targetRole = guild.get_role(targetRankId)
                targetLabel = targetRole.mention if targetRole is not None else f"`{targetRankId}`"
                return None, discord.Embed(title="❌ Invalid promotion target", description=f"{member.mention} cannot be recommended for {targetLabel} through this command.", color=discord.Color.red())

            requiredRoleIds = PROMOTION_RECOMMENDATION_MINIMUM_RECOMMENDER_ROLES.get(targetRankId, ())
            if len(requiredRoleIds) == 0:
                return None, discord.Embed(title="❌ Recommendation rule missing", description="Snek is missing the qualification rule for this recommendation.", color=discord.Color.red())

            targetRole = guild.get_role(targetRankId)
            targetLabel = targetRole.mention if targetRole is not None else f"`{targetRankId}`"
            requirements = Recognition._formatRoleMentions(guild, requiredRoleIds)

            if not Recognition._meetsPromotionRecommendationRequirement(firstRecommender, targetRankId):
                return None, discord.Embed(
                    title="❌ Primary recommender does not qualify",
                    description=f"{firstRecommender.mention} must have one of these roles to recommend {member.mention} for {targetLabel}: {requirements}",
                    color=discord.Color.red()
                )

            if not Recognition._meetsPromotionRecommendationRequirement(secondRecommender, targetRankId):
                return None, discord.Embed(
                    title="❌ Secondary recommender does not qualify",
                    description=f"{secondRecommender.mention} must have one of these roles to recommend {member.mention} for {targetLabel}: {requirements}",
                    color=discord.Color.red()
                )

        return {
            "member": member,
            "firstRecommender": firstRecommender,
            "secondRecommender": secondRecommender,
            "currentRankId": currentRankId,
            "allowedTargetIds": allowedTargetIds,
            "targetRankId": targetRankId,
        }, None

    @staticmethod
    def _truncatePromotionAdditionalComments(additionalComments: str | None) -> str | None:
        if additionalComments is None:
            return None
        additionalCommentsValue = additionalComments.strip()
        if additionalCommentsValue == "":
            return None
        maxLength = DISCORD_LIMITS["message_embed"]["embed_field_value"]
        if len(additionalCommentsValue) > maxLength:
            return additionalCommentsValue[:maxLength - 3] + "..."
        return additionalCommentsValue

    @staticmethod
    async def _getPromotionCriteriaEmbed(guild: discord.Guild, targetRankId: int) -> discord.Embed | None:
        rankStructureChannel = guild.get_channel(RANK_STRUCTURE)
        if not isinstance(rankStructureChannel, discord.TextChannel):
            log.exception("Recognition _getPromotionCriteriaEmbed: rankStructureChannel not discord.TextChannel")
            return None

        targetRole = guild.get_role(targetRankId)
        targetRankName = str(targetRankId) if targetRole is None else targetRole.name
        async for message in rankStructureChannel.history(limit=100):
            for embed in message.embeds:
                if embed.title and embed.title.lower().startswith(targetRankName.lower()):
                    return deepcopy(embed)
        return None

    @staticmethod
    async def _sendPromotionRecommendationPreview(
        interaction: discord.Interaction,
        *,
        memberId: int,
        memberDisplayName: str,
        firstRecommenderId: int,
        secondRecommenderId: int,
        targetRankId: int,
        additionalComments: str | None = None
    ) -> None:
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("Recognition _sendPromotionRecommendationPreview: interaction.guild not discord.Guild")
            return

        guild = interaction.guild
        validationResult, validationError = Recognition._validatePromotionRecommendation(
            guild,
            memberId=memberId,
            firstRecommenderId=firstRecommenderId,
            secondRecommenderId=secondRecommenderId,
            targetRankId=targetRankId,
        )
        if validationError is not None:
            await send_interaction_response(interaction, embed=validationError)
            return
        if validationResult is None:
            log.exception("Recognition _sendPromotionRecommendationPreview: validationResult is None")
            return

        member = cast(discord.Member, validationResult["member"])
        firstRecommender = cast(discord.Member, validationResult["firstRecommender"])
        secondRecommender = cast(discord.Member, validationResult["secondRecommender"])
        currentRankId = cast(int, validationResult["currentRankId"])
        targetRankId = cast(int, validationResult["targetRankId"])
        currentRole = guild.get_role(currentRankId)
        targetRole = guild.get_role(targetRankId)

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)

        previewEmbeds: list[discord.Embed] = []
        criteriaEmbed = await Recognition._getPromotionCriteriaEmbed(guild, targetRankId)
        if criteriaEmbed is not None:
            previewEmbeds.append(criteriaEmbed)
        else:
            rankStructureChannel = guild.get_channel(RANK_STRUCTURE)
            channelMention = rankStructureChannel.mention if isinstance(rankStructureChannel, discord.TextChannel) else "`#rank-structure`"
            previewEmbeds.append(
                discord.Embed(
                    title="Criteria Preview Unavailable",
                    description=(
                        f"Snek could not find a matching criteria embed for "
                        f"{targetRole.mention if targetRole is not None else f'`{targetRankId}`'} in {channelMention}. "
                        "Review the rank criteria manually before continuing."
                    ),
                    color=discord.Color.orange()
                )
            )

        summaryEmbed = discord.Embed(title="Promotion Recommendation Review", color=discord.Color.pink(), timestamp=datetime.now(timezone.utc))
        if currentRankId in (MERCENARY, OPERATOR) and targetRankId in (TACTICIAN, STRATEGIST) or currentRankId in (TACTICIAN, STRATEGIST) and targetRankId in (MERCENARY, OPERATOR):
            summaryEmbed.title = "Promotion Recommendation Review *[Senior Rank Track Change]*"

        summaryEmbed.add_field(name="Current Rank", value=currentRole.mention if currentRole is not None else f"`{currentRankId}`", inline=True)
        summaryEmbed.add_field(name="Recommended Rank", value=targetRole.mention if targetRole is not None else f"`{targetRankId}`", inline=True)
        summaryEmbed.add_field(name="\u200B", value="\u200B", inline=True)
        summaryEmbed.add_field(name="Primary", value=firstRecommender.mention, inline=True)
        summaryEmbed.add_field(name="Secondary", value=secondRecommender.mention, inline=True)
        summaryEmbed.add_field(name="\u200B", value="\u200B", inline=True)
        if additionalCommentsValue := Recognition._truncatePromotionAdditionalComments(additionalComments):
            summaryEmbed.add_field(name="Additional Comments", value=additionalCommentsValue, inline=False)
        summaryEmbed.add_field(name="\u200B", value="\u200B", inline=False)
        summaryEmbed.add_field(name="Next Steps", value=f"1. Verify that **{memberDisplayName}** meets all criteria above.\n2. Once complete, click the button below to submit final confirmation.", inline=False)
        previewEmbeds.append(summaryEmbed)

        await send_interaction_response(
            interaction,
            embeds=previewEmbeds,
            view=PromotionRecommendationPreviewView(
                memberId=memberId,
                memberDisplayName=member.display_name,
                firstRecommenderId=firstRecommenderId,
                secondRecommenderId=secondRecommenderId,
                targetRankId=targetRankId,
                additionalComments=additionalComments
            ),
            ephemeral=True
        )

    @staticmethod
    def _buildPromotionRecommendationEmbed(
        guild: discord.Guild,
        member: discord.Member,
        currentRankId: int,
        targetRankId: int,
        firstRecommender: discord.Member,
        secondRecommender: discord.Member,
        additionalComments: str | None,
        *,
        includeAdditionalComments: bool = True,
        reviewRequired: bool | None = None,
        reviewText: str | None = None,
        includeReviewState: bool = False,
        agreeVoterIds: Sequence[int] = (),
        disagreeVoterIds: Sequence[int] = (),
        abstainVoterIds: Sequence[int] = (),
        agreeRationales: Mapping[int, str] | None = None,
        disagreeRationales: Mapping[int, str] | None = None,
        actionTakenText: str | None = None
    ) -> discord.Embed:
        currentRole = guild.get_role(currentRankId)
        targetRole = guild.get_role(targetRankId)
        embed = discord.Embed(
            title=f"Promotion Recommendation: {member.display_name}",
            description=f"{member.mention} has been recommended for promotion.",
            color=discord.Color.pink(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Current Rank", value=currentRole.mention if currentRole is not None else f"`{currentRankId}`", inline=True)
        embed.add_field(name="Recommended Rank", value=targetRole.mention if targetRole is not None else f"`{targetRankId}`", inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(name="Primary", value=firstRecommender.mention, inline=True)
        embed.add_field(name="Secondary", value=secondRecommender.mention, inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)

        if includeAdditionalComments and (additionalCommentsValue := Recognition._truncatePromotionAdditionalComments(additionalComments)):
            embed.add_field(name="Additional Comments", value=additionalCommentsValue, inline=False)
        if reviewText is None and reviewRequired is not None:
            reviewText = "Advisor and Unit Staff review required." if reviewRequired else "Unit Staff review required."
        if reviewText is not None and not includeReviewState:
            embed.add_field(name="Review", value=reviewText, inline=False)

        if includeReviewState:
            embed.add_field(name="\u200B", value="\u200B", inline=False)
            embed.add_field(name=f"Agree ({len(agreeVoterIds)}) \N{THUMBS UP SIGN}", value=Recognition._formatPromotionVoteSummary(agreeVoterIds), inline=True)
            embed.add_field(name=f"Disagree ({len(disagreeVoterIds)}) \N{THUMBS DOWN SIGN}", value=Recognition._formatPromotionVoteSummary(disagreeVoterIds), inline=True)
            embed.add_field(name=f"Abstain ({len(abstainVoterIds)}) \N{RAISED HAND}", value=Recognition._formatPromotionVoteSummary(abstainVoterIds), inline=True)
            if agreeRationales or disagreeRationales:
                embed.add_field(name="\u200B", value="\u200B", inline=False)
            for voterId, rationale in sorted((agreeRationales or {}).items()):
                voter = guild.get_member(voterId)
                displayName = str(voterId) if not isinstance(voter, discord.Member) else voter.display_name
                embed.add_field(name=Recognition._formatPromotionRationaleFieldName("Agree Rationale", displayName), value=Recognition._formatPromotionRationaleFieldValue(rationale), inline=False)
            for voterId, rationale in sorted((disagreeRationales or {}).items()):
                voter = guild.get_member(voterId)
                displayName = str(voterId) if not isinstance(voter, discord.Member) else voter.display_name
                embed.add_field(name=Recognition._formatPromotionRationaleFieldName("Disagree Rationale", displayName), value=Recognition._formatPromotionRationaleFieldValue(rationale), inline=False)
            if actionTakenText is not None:
                embed.add_field(name="Action Taken", value=actionTakenText, inline=False)
        return embed

    @staticmethod
    def _formatPromotionVoteSummary(voterIds: Sequence[int]) -> str:
        mentions = "\n".join(f"<@{voterId}>" for voterId in voterIds)
        return mentions if mentions else "-"

    @staticmethod
    def _formatPromotionRationaleFieldName(prefix: str, displayName: str) -> str:
        maxLength = DISCORD_LIMITS["message_embed"]["embed_field_name"]
        return f"{prefix} - {displayName.strip() or 'Unknown'}"[:maxLength]

    @staticmethod
    def _formatPromotionRationaleFieldValue(rationale: str) -> str:
        maxLength = DISCORD_LIMITS["message_embed"]["embed_field_value"]
        rationaleValue = rationale.strip() or "No rationale provided."
        if len(rationaleValue) <= maxLength:
            return rationaleValue
        return f"{rationaleValue[:maxLength - 3].rstrip()}..."

    @staticmethod
    def _buildPromotionReviewView(*, memberId: int, currentRankId: int, targetRankId: int, juniorPromotion: bool) -> discord.ui.View:
        scope = "junior" if juniorPromotion else "senior"
        view = discord.ui.View(timeout=None)
        view.add_item(PromotionReviewAssentButton(memberId, currentRankId, targetRankId, scope))
        view.add_item(PromotionReviewDisagreementButton(memberId, currentRankId, targetRankId, scope))
        view.add_item(PromotionReviewAbstainButton(memberId, currentRankId, targetRankId, scope))
        view.add_item(PromotionReviewExecuteButton(memberId, currentRankId, targetRankId, scope))
        view.add_item(PromotionReviewDiscardButton(memberId, currentRankId, targetRankId, scope))
        return view

    @staticmethod
    def _getPromotionRecommendationAdditionalComments(message: discord.Message | None) -> str | None:
        if message is None or len(message.embeds) == 0:
            return None
        for field in message.embeds[0].fields:
            if field.name == "Additional Comments":
                additionalComments = field.value.strip()
                return additionalComments or None
        return None

    @staticmethod
    def _extractMentionedUserId(value: str) -> int | None:
        match = re.search(r"<@!?(\d+)>", value)
        return None if match is None else int(match.group(1))

    @staticmethod
    def _extractMentionedUserIds(value: str) -> list[int]:
        return [int(userId) for userId in re.findall(r"<@!?(\d+)>", value)]

    @staticmethod
    def _getPromotionRecommendationRecommenderIds(message: discord.Message | None) -> tuple[int | None, int | None]:
        if message is None or len(message.embeds) == 0:
            return None, None
        firstRecommenderId = None
        secondRecommenderId = None
        for field in message.embeds[0].fields:
            if field.name == "Primary":
                firstRecommenderId = Recognition._extractMentionedUserId(field.value)
            elif field.name == "Secondary":
                secondRecommenderId = Recognition._extractMentionedUserId(field.value)
        return firstRecommenderId, secondRecommenderId

    @staticmethod
    def _getPromotionRecommendationVoteIds(message: discord.Message | None, *, fieldName: str) -> list[int]:
        if message is None or len(message.embeds) == 0:
            return []
        for field in message.embeds[0].fields:
            if field.name.startswith(fieldName):
                return Recognition._extractMentionedUserIds(field.value)
        return []

    @staticmethod
    def _getPromotionRecommendationCurrentVoteIds(message: discord.Message | None, *, vote: str) -> list[int]:
        if vote == "agree":
            return Recognition._getPromotionRecommendationVoteIds(message, fieldName="Agree")
        if vote == "disagree":
            return Recognition._getPromotionRecommendationVoteIds(message, fieldName="Disagree")
        return Recognition._getPromotionRecommendationVoteIds(message, fieldName="Abstain")

    @staticmethod
    def _getPromotionRecommendationRationales(message: discord.Message | None, *, vote: str) -> dict[int, str]:
        if message is None or len(message.embeds) == 0:
            return {}
        currentVoteIds = Recognition._getPromotionRecommendationCurrentVoteIds(message, vote=vote)
        rationaleFields = [
            field.value.strip()
            for field in message.embeds[0].fields
            if field.name.startswith("Agree Rationale - " if vote == "agree" else "Disagree Rationale - ")
        ]

        rationales: dict[int, str] = {}
        for voterId, rationale in zip(currentVoteIds, rationaleFields):
            if rationale != "":
                rationales[voterId] = rationale
        return rationales

    @staticmethod
    def _getPromotionRecommendationActionTaken(message: discord.Message | None) -> str | None:
        if message is None or len(message.embeds) == 0:
            return None
        for field in message.embeds[0].fields:
            if field.name == "Action Taken":
                value = field.value.strip()
                return value or None
        return None

    @staticmethod
    def _promotionReviewButtonsDisabled(message: discord.Message | None) -> bool:
        if message is None:
            return False
        hasButtons = False
        for row in message.components:
            for child in getattr(row, "children", []):
                if getattr(child, "custom_id", None) is not None:
                    hasButtons = True
                    if not getattr(child, "disabled", False):
                        return False
        return hasButtons

    @staticmethod
    def _buildPromotionActionLogEmbed(
        guild: discord.Guild,
        *,
        member: discord.Member,
        currentRankId: int,
        targetRankId: int,
        firstRecommender: discord.Member,
        secondRecommender: discord.Member,
        actor: discord.Member,
        additionalComments: str | None,
        action: str
    ) -> discord.Embed:
        currentRole = guild.get_role(currentRankId)
        targetRole = guild.get_role(targetRankId)
        isExecute = action == "execute"
        embed = discord.Embed(
            title="Promotion Recommendation Accepted" if isExecute else "Promotion Recommendation Discarded",
            color=discord.Color.green() if isExecute else discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Action By", value=actor.mention, inline=True)
        embed.add_field(name="Action Taken", value="Promoted" if isExecute else "Discarded", inline=True)
        embed.add_field(name="Current Rank", value=currentRole.mention if currentRole is not None else f"`{currentRankId}`", inline=True)
        embed.add_field(name="Recommended Rank", value=targetRole.mention if targetRole is not None else f"`{targetRankId}`", inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(name="Primary", value=firstRecommender.mention, inline=True)
        embed.add_field(name="Secondary", value=secondRecommender.mention, inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        if additionalCommentsValue := Recognition._truncatePromotionAdditionalComments(additionalComments):
            embed.add_field(name="Additional Comments", value=additionalCommentsValue, inline=False)
        embed.set_footer(text=f"Member ID: {member.id} | Actor ID: {actor.id}")
        embed.set_thumbnail(url=member.display_avatar.url)
        return embed

    @staticmethod
    async def _buildPromotionReviewEmbedFromMessage(
        guild: discord.Guild,
        *,
        reviewMessage: discord.Message,
        memberId: int,
        currentRankId: int,
        targetRankId: int,
        scope: str,
        agreeVoterIds: Sequence[int] | None = None,
        disagreeVoterIds: Sequence[int] | None = None,
        abstainVoterIds: Sequence[int] | None = None,
        agreeRationales: Mapping[int, str] | None = None,
        disagreeRationales: Mapping[int, str] | None = None,
        actionTakenText: str | None = None
    ) -> discord.Embed | None:
        member = guild.get_member(memberId)
        firstRecommenderId, secondRecommenderId = Recognition._getPromotionRecommendationRecommenderIds(reviewMessage)
        firstRecommender = guild.get_member(firstRecommenderId)
        secondRecommender = guild.get_member(secondRecommenderId)
        if not isinstance(member, discord.Member):
            return None
        if not isinstance(firstRecommender, discord.Member) or not isinstance(secondRecommender, discord.Member):
            return None

        return Recognition._buildPromotionRecommendationEmbed(
            guild,
            member,
            currentRankId,
            targetRankId,
            firstRecommender,
            secondRecommender,
            Recognition._getPromotionRecommendationAdditionalComments(reviewMessage),
            reviewText="Unit Staff review required." if scope == "junior" else "Advisor and Unit Staff review required.",
            includeReviewState=True,
            agreeVoterIds=agreeVoterIds if agreeVoterIds is not None else Recognition._getPromotionRecommendationCurrentVoteIds(reviewMessage, vote="agree"),
            disagreeVoterIds=disagreeVoterIds if disagreeVoterIds is not None else Recognition._getPromotionRecommendationCurrentVoteIds(reviewMessage, vote="disagree"),
            abstainVoterIds=abstainVoterIds if abstainVoterIds is not None else Recognition._getPromotionRecommendationCurrentVoteIds(reviewMessage, vote="abstain"),
            agreeRationales=agreeRationales if agreeRationales is not None else Recognition._getPromotionRecommendationRationales(reviewMessage, vote="agree"),
            disagreeRationales=disagreeRationales if disagreeRationales is not None else Recognition._getPromotionRecommendationRationales(reviewMessage, vote="disagree"),
            actionTakenText=actionTakenText if actionTakenText is not None else Recognition._getPromotionRecommendationActionTaken(reviewMessage)
        )

    @staticmethod
    async def handlePromotionRecommendationVote(
        interaction: discord.Interaction,
        *,
        vote: str,
        memberId: int,
        currentRankId: int,
        targetRankId: int,
        scope: str,
        rationale: str | None = None,
        reviewMessage: discord.Message | None = None
    ) -> None:
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("Recognition handlePromotionRecommendationVote: interaction.guild not discord.Guild")
            return
        if not isinstance(interaction.user, discord.Member):
            log.exception("Recognition handlePromotionRecommendationVote: interaction.user not discord.Member")
            return
        if reviewMessage is None:
            reviewMessage = interaction.message
        if reviewMessage is None:
            log.exception("Recognition handlePromotionRecommendationVote: interaction.message is None")
            return

        guild = interaction.guild
        voter = interaction.user
        if rationale is None:
            existingRationales = Recognition._getPromotionRecommendationRationales(reviewMessage, vote="agree" if vote == "assent" else "disagree")
            await interaction.response.send_modal(
                PromotionRecommendationVoteRationaleModal(
                    memberId=memberId,
                    currentRankId=currentRankId,
                    targetRankId=targetRankId,
                    scope=scope,
                    vote=vote,
                    reviewChannelId=reviewMessage.channel.id,
                    reviewMessageId=reviewMessage.id,
                    existingRationale=existingRationales.get(voter.id)
                )
            )
            return

        allowedRoleIds = {UNIT_STAFF} if scope == "junior" else {UNIT_STAFF, ADVISOR}
        if not any(role.id in allowedRoleIds for role in voter.roles):
            await interaction.response.send_message("You are not allowed to review this promotion recommendation.", ephemeral=True)
            return
        if Recognition._promotionReviewButtonsDisabled(reviewMessage):
            await interaction.response.send_message("This promotion recommendation has already been closed.", ephemeral=True)
            return

        agreeVoterIds = set(Recognition._getPromotionRecommendationCurrentVoteIds(reviewMessage, vote="agree"))
        disagreeVoterIds = set(Recognition._getPromotionRecommendationCurrentVoteIds(reviewMessage, vote="disagree"))
        abstainVoterIds = set(Recognition._getPromotionRecommendationCurrentVoteIds(reviewMessage, vote="abstain"))
        agreeRationales = Recognition._getPromotionRecommendationRationales(reviewMessage, vote="agree")
        disagreeRationales = Recognition._getPromotionRecommendationRationales(reviewMessage, vote="disagree")
        agreeVoterIds.discard(voter.id)
        disagreeVoterIds.discard(voter.id)
        abstainVoterIds.discard(voter.id)
        agreeRationales.pop(voter.id, None)
        disagreeRationales.pop(voter.id, None)
        if vote == "assent":
            agreeVoterIds.add(voter.id)
            agreeRationales[voter.id] = rationale.strip()
        elif vote == "disagreement":
            disagreeVoterIds.add(voter.id)
            disagreeRationales[voter.id] = rationale.strip()
        else:
            abstainVoterIds.add(voter.id)

        updatedEmbed = await Recognition._buildPromotionReviewEmbedFromMessage(
            guild,
            reviewMessage=reviewMessage,
            memberId=memberId,
            currentRankId=currentRankId,
            targetRankId=targetRankId,
            scope=scope,
            agreeVoterIds=tuple(sorted(agreeVoterIds)),
            disagreeVoterIds=tuple(sorted(disagreeVoterIds)),
            abstainVoterIds=tuple(sorted(abstainVoterIds)),
            agreeRationales=agreeRationales,
            disagreeRationales=disagreeRationales
        )
        if updatedEmbed is None:
            await interaction.response.send_message("Failed to update votes for this promotion recommendation.", ephemeral=True)
            return

        view = Recognition._buildPromotionReviewView(
            memberId=memberId,
            currentRankId=currentRankId,
            targetRankId=targetRankId,
            juniorPromotion=scope == "junior"
        )
        if interaction.message is not None and interaction.message.id == reviewMessage.id:
            await interaction.response.edit_message(embed=updatedEmbed, view=view)
        else:
            await reviewMessage.edit(embed=updatedEmbed, view=view)
            await interaction.response.send_message("Vote recorded.", ephemeral=True)

    @staticmethod
    async def handlePromotionRecommendationExecute(
        interaction: discord.Interaction,
        *,
        memberId: int,
        currentRankId: int,
        targetRankId: int,
        scope: str,
        reviewMessage: discord.Message | None = None
    ) -> None:
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("Recognition handlePromotionRecommendationExecute: interaction.guild not discord.Guild")
            return
        if not isinstance(interaction.user, discord.Member):
            log.exception("Recognition handlePromotionRecommendationExecute: interaction.user not discord.Member")
            return
        if reviewMessage is None:
            reviewMessage = interaction.message
        if reviewMessage is None:
            log.exception("Recognition handlePromotionRecommendationExecute: interaction.message is None")
            return

        guild = interaction.guild
        executor = interaction.user
        if not any(role.id == UNIT_STAFF for role in executor.roles):
            await interaction.response.send_message("Only Unit Staff can execute this promotion.", ephemeral=True)
            return
        if Recognition._promotionReviewButtonsDisabled(reviewMessage):
            await interaction.response.send_message("This promotion recommendation has already been closed.", ephemeral=True)
            return

        firstRecommenderId, secondRecommenderId = Recognition._getPromotionRecommendationRecommenderIds(reviewMessage)
        member = guild.get_member(memberId)
        firstRecommender = guild.get_member(firstRecommenderId)
        secondRecommender = guild.get_member(secondRecommenderId)
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Failed to resolve the member for this promotion recommendation.", ephemeral=True)
            return
        if not isinstance(firstRecommender, discord.Member) or not isinstance(secondRecommender, discord.Member):
            await interaction.response.send_message("Failed to resolve the recommenders for this promotion recommendation.", ephemeral=True)
            return

        currentRole = guild.get_role(currentRankId)
        targetRole = guild.get_role(targetRankId)
        if currentRole is None or targetRole is None:
            await interaction.response.send_message("This promotion recommendation references a missing rank role.", ephemeral=True)
            return
        if currentRole not in member.roles:
            await interaction.response.send_message(f"{member.mention} no longer has the expected current rank for this recommendation.", ephemeral=True)
            return

        await interaction.response.defer()
        auditReason = f"Promotion executed from recommendation by {executor}."
        await member.remove_roles(currentRole, reason=auditReason)
        await member.add_roles(targetRole, reason=auditReason)

        updatedEmbed = await Recognition._buildPromotionReviewEmbedFromMessage(
            guild,
            reviewMessage=reviewMessage,
            memberId=memberId,
            currentRankId=currentRankId,
            targetRankId=targetRankId,
            scope=scope,
            actionTakenText=f"Promotion executed by {executor.mention}"
        )
        if updatedEmbed is None:
            await interaction.followup.send("Promotion executed, but the review message could not be updated.", ephemeral=True)
            return

        await reviewMessage.edit(embed=updatedEmbed, view=None)
        additionalComments = Recognition._getPromotionRecommendationAdditionalComments(reviewMessage)
        executionEmbed = Recognition._buildPromotionActionLogEmbed(
            guild,
            member=member,
            currentRankId=currentRankId,
            targetRankId=targetRankId,
            firstRecommender=firstRecommender,
            secondRecommender=secondRecommender,
            actor=executor,
            additionalComments=additionalComments,
            action="execute"
        )
        channelAuditLogs = guild.get_channel(AUDIT_LOGS)
        if isinstance(channelAuditLogs, discord.TextChannel):
            await channelAuditLogs.send(embed=executionEmbed)
        else:
            log.exception("Recognition handlePromotionRecommendationExecute: channelAuditLogs not discord.TextChannel")

    @staticmethod
    async def handlePromotionRecommendationDiscard(
        interaction: discord.Interaction,
        *,
        memberId: int,
        currentRankId: int,
        targetRankId: int,
        scope: str,
        reviewMessage: discord.Message | None = None
    ) -> None:
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("Recognition handlePromotionRecommendationDiscard: interaction.guild not discord.Guild")
            return
        if not isinstance(interaction.user, discord.Member):
            log.exception("Recognition handlePromotionRecommendationDiscard: interaction.user not discord.Member")
            return
        if reviewMessage is None:
            reviewMessage = interaction.message
        if reviewMessage is None:
            log.exception("Recognition handlePromotionRecommendationDiscard: interaction.message is None")
            return

        guild = interaction.guild
        actor = interaction.user
        if not any(role.id == UNIT_STAFF for role in actor.roles):
            await interaction.response.send_message("Only Unit Staff can discard this recommendation.", ephemeral=True)
            return
        if Recognition._promotionReviewButtonsDisabled(reviewMessage):
            await interaction.response.send_message("This promotion recommendation has already been closed.", ephemeral=True)
            return

        await interaction.response.defer()
        updatedEmbed = await Recognition._buildPromotionReviewEmbedFromMessage(
            guild,
            reviewMessage=reviewMessage,
            memberId=memberId,
            currentRankId=currentRankId,
            targetRankId=targetRankId,
            scope=scope,
            actionTakenText=f"Recommendation discarded by {interaction.user.mention}"
        )
        if updatedEmbed is None:
            await interaction.followup.send("Failed to discard this promotion recommendation.", ephemeral=True)
            return

        await reviewMessage.edit(embed=updatedEmbed, view=None)
        firstRecommenderId, secondRecommenderId = Recognition._getPromotionRecommendationRecommenderIds(reviewMessage)
        member = guild.get_member(memberId)
        firstRecommender = guild.get_member(firstRecommenderId)
        secondRecommender = guild.get_member(secondRecommenderId)
        if not isinstance(member, discord.Member):
            return
        if not isinstance(firstRecommender, discord.Member) or not isinstance(secondRecommender, discord.Member):
            return

        actionEmbed = Recognition._buildPromotionActionLogEmbed(
            guild,
            member=member,
            currentRankId=currentRankId,
            targetRankId=targetRankId,
            firstRecommender=firstRecommender,
            secondRecommender=secondRecommender,
            actor=actor,
            additionalComments=Recognition._getPromotionRecommendationAdditionalComments(reviewMessage),
            action="discard"
        )
        channelAuditLogs = guild.get_channel(AUDIT_LOGS)
        if isinstance(channelAuditLogs, discord.TextChannel):
            await channelAuditLogs.send(embed=actionEmbed)
        else:
            log.exception("Recognition handlePromotionRecommendationDiscard: channelAuditLogs not discord.TextChannel")

    @staticmethod
    async def processPromotionRecommendationSubmission(
        interaction: discord.Interaction,
        *,
        memberId: int,
        firstRecommenderId: int,
        secondRecommenderId: int,
        additionalComments: str | None = None,
        targetRankId: int
    ) -> None:
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("Recognition processPromotionRecommendationSubmission: interaction.guild not discord.Guild")
            return

        guild = interaction.guild
        validationResult, validationError = Recognition._validatePromotionRecommendation(
            guild,
            memberId=memberId,
            firstRecommenderId=firstRecommenderId,
            secondRecommenderId=secondRecommenderId,
            targetRankId=targetRankId,
        )
        if validationError is not None:
            await send_interaction_response(interaction, embed=validationError)
            return
        if validationResult is None:
            log.exception("Recognition processPromotionRecommendationSubmission: validationResult is None")
            await send_interaction_response(interaction, embed=discord.Embed(title="Promotion recommendation validation failed", color=discord.Color.red()))
            return

        member = cast(discord.Member, validationResult["member"])
        firstRecommender = cast(discord.Member, validationResult["firstRecommender"])
        secondRecommender = cast(discord.Member, validationResult["secondRecommender"])
        currentRankId = cast(int, validationResult["currentRankId"])
        targetRankId = cast(int, validationResult["targetRankId"])
        targetRole = guild.get_role(targetRankId)
        targetLabel = targetRole.mention if targetRole is not None else f"`{targetRankId}`"

        channelCommendations = guild.get_channel(COMMENDATIONS)
        reviewChannel = guild.get_channel(STAFF_CHAT if targetRankId in (CANDIDATE, ASSOCIATE, CONTRACTOR) else ADVISOR_STAFF_COMMS)
        if not isinstance(channelCommendations, discord.TextChannel):
            log.exception("Recognition processPromotionRecommendationSubmission: commendationsChannel not discord.TextChannel")
            await send_interaction_response(interaction, embed=discord.Embed(title="Commendations channel not found", color=discord.Color.red()))
            return
        if not isinstance(reviewChannel, discord.TextChannel):
            log.exception("Recognition processPromotionRecommendationSubmission: reviewChannel not discord.TextChannel")
            await send_interaction_response(interaction, embed=discord.Embed(title="Staff review channel not found", color=discord.Color.red()))
            return

        roleUnitStaff = guild.get_role(UNIT_STAFF)
        roleAdvisor = guild.get_role(ADVISOR)
        juniorPromotion = targetRankId in (CANDIDATE, ASSOCIATE, CONTRACTOR)

        commendationsEmbed = Recognition._buildPromotionRecommendationEmbed(
            guild, member, currentRankId, targetRankId, firstRecommender, secondRecommender, additionalComments,
            includeAdditionalComments=False,
            reviewText="Unit Staff review required." if juniorPromotion else "Advisor and Unit Staff review required."
        )
        await channelCommendations.send(member.mention, embed=commendationsEmbed)

        reviewEmbed = Recognition._buildPromotionRecommendationEmbed(
            guild, member, currentRankId, targetRankId, firstRecommender, secondRecommender, additionalComments,
            reviewText="Unit Staff review required." if juniorPromotion else "Advisor and Unit Staff review required.",
            includeReviewState=True
        )
        reviewMentions = roleUnitStaff.mention if juniorPromotion and roleUnitStaff is not None else " ".join(role.mention for role in (roleAdvisor, roleUnitStaff) if role is not None) or None
        await reviewChannel.send(
            content=reviewMentions,
            embed=reviewEmbed,
            view=Recognition._buildPromotionReviewView(memberId=member.id, currentRankId=currentRankId, targetRankId=targetRankId, juniorPromotion=juniorPromotion)
        )

        responseLines = [f"Promotion recommendation submitted for {member.mention} to {targetLabel}."]
        responseLines.append(f"Check it out in {channelCommendations.mention}.")
        responseLines.append(f"Review request sent to {reviewChannel.mention}.")
        await send_interaction_response(interaction, content="\n".join(responseLines), ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Recognition"))
        self.bot.cogsReady["recognition"] = True

    @discord.app_commands.command(name="recommend-for-promotion")
    @discord.app_commands.describe(member="Member to recommend for promotion", second_recommender="Second qualified recommender", additional_comments="Additional comments for the promotion recommendation (optional)")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(MEMBER)
    async def recommendForPromotion(self, interaction: discord.Interaction, member: discord.Member, second_recommender: discord.Member, *, additional_comments: str | None = None) -> None:
        """Recommend a member for promotion."""
        if not isinstance(interaction.user, discord.Member):
            log.exception("Recognition recommendForPromotion: interaction.user not discord.Member")
            return
        if not isinstance(interaction.guild, discord.Guild):
            log.exception("Recognition recommendForPromotion: interaction.guild not discord.Guild")
            return

        validationResult, validationError = Recognition._validatePromotionRecommendation(
            interaction.guild,
            memberId=member.id,
            firstRecommenderId=interaction.user.id,
            secondRecommenderId=second_recommender.id,
        )
        if validationError is not None:
            await interaction.response.send_message(embed=validationError, ephemeral=True)
            return
        if validationResult is None:
            log.exception("Recognition recommendForPromotion: validationResult is None")
            await interaction.response.send_message(embed=discord.Embed(title="❌ Promotion recommendation validation failed", color=discord.Color.red()), ephemeral=True)
            return

        allowedTargetIds = cast(tuple[int, ...], validationResult["allowedTargetIds"])
        if len(allowedTargetIds) > 1:
            await interaction.response.send_modal(
                PromotionRecommendationTargetModal(
                    memberId=member.id,
                    memberDisplayName=member.display_name,
                    firstRecommenderId=interaction.user.id,
                    secondRecommenderId=second_recommender.id,
                    allowedTargetIds=allowedTargetIds,
                    additionalComments=additional_comments,
                    guild=interaction.guild,
                )
            )
            return

        targetRankId = allowedTargetIds[0]
        validationResult, validationError = Recognition._validatePromotionRecommendation(
            interaction.guild,
            memberId=member.id,
            firstRecommenderId=interaction.user.id,
            secondRecommenderId=second_recommender.id,
            targetRankId=targetRankId,
        )
        if validationError is not None:
            await interaction.response.send_message(embed=validationError, ephemeral=True)
            return
        if validationResult is None:
            log.exception("Recognition recommendForPromotion: single-target validationResult is None")
            await interaction.response.send_message(embed=discord.Embed(title="❌ Promotion recommendation validation failed", color=discord.Color.red()), ephemeral=True)
            return

        await Recognition._sendPromotionRecommendationPreview(
            interaction,
            memberId=member.id,
            memberDisplayName=member.display_name,
            firstRecommenderId=interaction.user.id,
            secondRecommenderId=second_recommender.id,
            additionalComments=additional_comments,
            targetRankId=targetRankId,
        )

    @discord.app_commands.command(name="commend")
    @discord.app_commands.describe(member="Member to commend", reason="Reason for the commendation")
    @discord.app_commands.guilds(GUILD)
    @discord.app_commands.checks.has_any_role(MEMBER)
    async def commend(self, interaction: discord.Interaction, member: discord.Member, reason: str) -> None:
        """ Commend a member for good performance in an operation.

        Parameters:
        interaction (discord.Interaction): The Discord interaction.
        member (discord.Member): Member to commend.
        reason (str): Reason for the commendation.

        Returns:
        None.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)
        if member.bot:
            await interaction.followup.send(embed=discord.Embed(title="❌ Invalid target", description="You cannot commend bots.", color=discord.Color.red()), ephemeral=True)
            return
        if member.id == interaction.user.id:
            await interaction.followup.send(embed=discord.Embed(title="❌ Invalid target", description="You cannot commend yourself.", color=discord.Color.red()), ephemeral=True)
            return

        try:
            with open(WALLETS_FILE) as f:
                wallets = json.load(f)
        except Exception:
            wallets = {}

        senderEntry = wallets.get(str(interaction.user.id), {"timesCommended": 0, "sentCommendations": 0, "money": 0, "moneySpent": 0})
        targetEntry = wallets.get(str(member.id), {"timesCommended": 0, "sentCommendations": 0, "money": 0, "moneySpent": 0})
        targetEntry["timesCommended"] = targetEntry.get("timesCommended", 0) + 1
        senderEntry["sentCommendations"] = senderEntry.get("sentCommendations", 0) + 1
        wallets[str(interaction.user.id)] = senderEntry
        wallets[str(member.id)] = targetEntry

        actionPhrases = [
            "has been commended!", "just got commended!", "was commended!", "earned a commendation!",
            "got commended!", "picked up a commendation!", "just got a commendation!", "received a commendation!",
            "was just commended!", "'s getting some love!", "'s been given a commendation!", "'s commendation is now here!",
            "was given a commendation!", "was marked for a commendation!", "logged positive performance!",
            "has received the hawk tuah!", "got a pat on the back!"
        ]
        commentaryPhrases = [
            "Sssnek thinks you did great too.", "Nice work.", "Clean job on that one.", "Solid stuff.", "Snek gives a lil nod.",
            "Keep doing your thing.", "That tracks.", "Well deserved.", "Snek quietly approves.", "Good momentum.",
            "That's a win in my book.", "Smooth move.", "You love to see it.", "That's some good work right there.",
            "Snek's kinda proud ngl.", "Strong showing.", "Solid all around.", "Ssssolid effort.", "Definitely earned it.",
            "Keep that energy going.", "You must have L shaped really well.", "I'm sure they have plenty of war stories to tell.",
            "I wish you were my battle buddy.", "<@&483984125531783180> would be proud.", "Snek approves.", "Thats how it's done!", "Is this peak performance?"
        ]

        embed = discord.Embed(
            title=f"{member.display_name} has been commended by {interaction.user.display_name}!",
            description=f"{member.mention} {choice(actionPhrases)} {choice(commentaryPhrases)}",
            color=discord.Color.green()
        )
        embed.add_field(name="Reason:", value=reason, inline=False)

        bonusAmount = randint(100, 150) if random() < 0.30 else 0
        if bonusAmount > 0:
            embed.add_field(name="Bonus:", value=f"Received `{bonusAmount}` SnekCoins! \N{COIN}", inline=False)
            targetEntry["money"] = int(targetEntry.get("money", 0)) + bonusAmount

        try:
            with open(WALLETS_FILE, "w") as f:
                json.dump(wallets, f, indent=4)
        except Exception:
            log.warning("Recognition commend: Failed to save wallets file.")

        embed.set_footer(text="I think they like you!")
        embed.timestamp = datetime.now(timezone.utc)
        channel = member.guild.get_channel(COMMENDATIONS)
        if not isinstance(channel, discord.TextChannel):
            log.exception("Recognition commend: channel not discord.TextChannel")
            return

        msgContent = f"You have commended {member.mention}."
        if bonusAmount != 0:
            msgContent += f"\n\N{PARTY POPPER} They received `{bonusAmount}` SnekCoins \N{PARTY POPPER}"
        msgContent += f"\nCheck it out in {channel.mention}!"
        await interaction.followup.send(msgContent, ephemeral=True)
        await channel.send(f"\N{PARTY POPPER} {member.mention} \N{PARTY POPPER}", embed=embed)


class BasePromotionReviewDynamicButton(discord.ui.DynamicItem[discord.ui.Button], template=r"^$"):
    ACTION = ""
    LABEL = ""
    STYLE = discord.ButtonStyle.secondary
    EMOJI: str | None = None

    def __init__(self, memberId: int, currentRankId: int, targetRankId: int, scope: str) -> None:
        self.memberId = memberId
        self.currentRankId = currentRankId
        self.targetRankId = targetRankId
        self.scope = scope
        super().__init__(discord.ui.Button(label=self.LABEL, style=self.STYLE, emoji=self.EMOJI, row=0, custom_id=f"promorev_{self.ACTION}_{memberId}_{currentRankId}_{targetRankId}_{scope}"))

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        return cls(int(match.group("member_id")), int(match.group("current_rank_id")), int(match.group("target_rank_id")), match.group("scope"))

    async def callback(self, interaction: discord.Interaction):
        raise NotImplementedError


class PromotionReviewAssentButton(BasePromotionReviewDynamicButton, template=r"promorev_a_(?P<member_id>\d+)_(?P<current_rank_id>\d+)_(?P<target_rank_id>\d+)_(?P<scope>junior|senior)"):
    ACTION = "a"
    STYLE = discord.ButtonStyle.primary
    EMOJI = "\N{THUMBS UP SIGN}"

    async def callback(self, interaction: discord.Interaction):
        await Recognition.handlePromotionRecommendationVote(interaction, vote="assent", memberId=self.memberId, currentRankId=self.currentRankId, targetRankId=self.targetRankId, scope=self.scope)


class PromotionReviewDisagreementButton(BasePromotionReviewDynamicButton, template=r"promorev_d_(?P<member_id>\d+)_(?P<current_rank_id>\d+)_(?P<target_rank_id>\d+)_(?P<scope>junior|senior)"):
    ACTION = "d"
    STYLE = discord.ButtonStyle.primary
    EMOJI = "\N{THUMBS DOWN SIGN}"

    async def callback(self, interaction: discord.Interaction):
        await Recognition.handlePromotionRecommendationVote(interaction, vote="disagreement", memberId=self.memberId, currentRankId=self.currentRankId, targetRankId=self.targetRankId, scope=self.scope)


class PromotionReviewAbstainButton(BasePromotionReviewDynamicButton, template=r"promorev_b_(?P<member_id>\d+)_(?P<current_rank_id>\d+)_(?P<target_rank_id>\d+)_(?P<scope>junior|senior)"):
    ACTION = "b"
    STYLE = discord.ButtonStyle.primary
    EMOJI = "\N{RAISED HAND}"

    async def callback(self, interaction: discord.Interaction):
        await Recognition.handlePromotionRecommendationVote(interaction, vote="abstain", memberId=self.memberId, currentRankId=self.currentRankId, targetRankId=self.targetRankId, scope=self.scope, rationale="")


class PromotionReviewExecuteButton(BasePromotionReviewDynamicButton, template=r"promorev_x_(?P<member_id>\d+)_(?P<current_rank_id>\d+)_(?P<target_rank_id>\d+)_(?P<scope>junior|senior)"):
    ACTION = "x"
    LABEL = "Execute Promotion"

    async def callback(self, interaction: discord.Interaction):
        if interaction.message is None:
            log.exception("PromotionReviewExecuteButton callback: interaction.message is None")
            return
        await interaction.response.send_modal(PromotionReviewActionConfirmationModal(action="execute", memberId=self.memberId, currentRankId=self.currentRankId, targetRankId=self.targetRankId, scope=self.scope, reviewMessage=interaction.message))


class PromotionReviewDiscardButton(BasePromotionReviewDynamicButton, template=r"promorev_r_(?P<member_id>\d+)_(?P<current_rank_id>\d+)_(?P<target_rank_id>\d+)_(?P<scope>junior|senior)"):
    ACTION = "r"
    LABEL = "Discard Recommendation"

    async def callback(self, interaction: discord.Interaction):
        if interaction.message is None:
            log.exception("PromotionReviewDiscardButton callback: interaction.message is None")
            return
        await interaction.response.send_modal(PromotionReviewActionConfirmationModal(action="discard", memberId=self.memberId, currentRankId=self.currentRankId, targetRankId=self.targetRankId, scope=self.scope, reviewMessage=interaction.message))


class PromotionRecommendationTargetModal(discord.ui.Modal):
    def __init__(self, *, memberId: int, memberDisplayName: str, firstRecommenderId: int, secondRecommenderId: int, allowedTargetIds: Iterable[int], guild: discord.Guild | None, additionalComments: str | None = None) -> None:
        super().__init__(title=f"Target Rank: {memberDisplayName[:28]}", custom_id="schedule_modal_promotion_target")
        self.memberId = memberId
        self.memberDisplayName = memberDisplayName
        self.firstRecommenderId = firstRecommenderId
        self.secondRecommenderId = secondRecommenderId
        self.additionalComments = additionalComments
        self.targetRank = discord.ui.Label(
            text="Select the recommended rank",
            component=discord.ui.RadioGroup(
                custom_id="schedule_select_promotion_target",
                required=True,
                options=[
                    discord.RadioGroupOption(label=role.name if role is not None else str(targetRankId), value=str(targetRankId))
                    for targetRankId in tuple(allowedTargetIds)
                    for role in [guild.get_role(targetRankId) if guild is not None else None]
                ],
            )
        )
        self.add_item(self.targetRank)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(self.targetRank.component, discord.ui.RadioGroup):
            await interaction.response.send_message("Failed to submit recommendation: Invalid target selector.", ephemeral=True)
            return
        selectedTargetRank = self.targetRank.component.value
        if selectedTargetRank is None:
            await interaction.response.send_message("Please choose a rank before continuing.", ephemeral=True)
            return
        await Recognition._sendPromotionRecommendationPreview(
            interaction,
            memberId=self.memberId,
            memberDisplayName=self.memberDisplayName,
            firstRecommenderId=self.firstRecommenderId,
            secondRecommenderId=self.secondRecommenderId,
            additionalComments=self.additionalComments,
            targetRankId=int(selectedTargetRank),
        )


class PromotionRecommendationPreviewView(discord.ui.View):
    def __init__(self, *, memberId: int, memberDisplayName: str, firstRecommenderId: int, secondRecommenderId: int, targetRankId: int, additionalComments: str | None = None) -> None:
        super().__init__(timeout=300)
        self.memberId = memberId
        self.memberDisplayName = memberDisplayName
        self.firstRecommenderId = firstRecommenderId
        self.secondRecommenderId = secondRecommenderId
        self.targetRankId = targetRankId
        self.additionalComments = additionalComments

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.firstRecommenderId:
            await interaction.response.send_message("Only the Primary recommender can submit the confirmation modal.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Open Confirmation", style=discord.ButtonStyle.primary)
    async def openConfirmation(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        targetRole = interaction.guild.get_role(self.targetRankId) if isinstance(interaction.guild, discord.Guild) else None
        await interaction.response.send_modal(
            PromotionRecommendationConfirmationModal(
                memberId=self.memberId,
                memberDisplayName=self.memberDisplayName,
                firstRecommenderId=self.firstRecommenderId,
                secondRecommenderId=self.secondRecommenderId,
                targetRankId=self.targetRankId,
                targetRankName=targetRole.name if targetRole is not None else str(self.targetRankId),
                additionalComments=self.additionalComments,
            )
        )


class PromotionRecommendationConfirmationModal(discord.ui.Modal):
    def __init__(self, *, memberId: int, memberDisplayName: str, firstRecommenderId: int, secondRecommenderId: int, targetRankId: int, targetRankName: str, additionalComments: str | None = None) -> None:
        super().__init__(title="Confirm Promotion Recommendation", custom_id="schedule_modal_promotion_confirmation")
        self.memberId = memberId
        self.firstRecommenderId = firstRecommenderId
        self.secondRecommenderId = secondRecommenderId
        self.targetRankId = targetRankId
        self.additionalComments = additionalComments
        self.add_item(discord.ui.TextDisplay(content=f"Recommending **{memberDisplayName}** for Promotion to **{targetRankName}**"))
        self.add_item(discord.ui.TextDisplay(content=PROMOTION_RECOMMENDATION_CONFIRMATION_TEXT))
        self.confirmationInput = discord.ui.Label(
            text="Type `I confirm` to submit",
            component=discord.ui.TextInput(custom_id="schedule_text_promotion_confirmation", style=discord.TextStyle.short, placeholder="I confirm", required=True, max_length=32)
        )
        self.add_item(self.confirmationInput)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(self.confirmationInput.component, discord.ui.TextInput):
            await interaction.response.send_message("Failed to submit recommendation: Invalid confirmation input.", ephemeral=True)
            return
        if self.confirmationInput.component.value != "I confirm":
            await interaction.response.send_message("Confirmation failed. Type `I confirm` exactly to submit this recommendation.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await Recognition.processPromotionRecommendationSubmission(interaction, memberId=self.memberId, firstRecommenderId=self.firstRecommenderId, secondRecommenderId=self.secondRecommenderId, additionalComments=self.additionalComments, targetRankId=self.targetRankId)


class PromotionReviewActionConfirmationModal(discord.ui.Modal):
    def __init__(self, *, action: Literal["execute", "discard"], memberId: int, currentRankId: int, targetRankId: int, scope: str, reviewMessage: discord.Message) -> None:
        super().__init__(title="Confirm Execute Promotion" if action == "execute" else "Confirm Discard Recommendation", custom_id=f"schedule_modal_promotion_review_{action}")
        self.action = action
        self.memberId = memberId
        self.currentRankId = currentRankId
        self.targetRankId = targetRankId
        self.scope = scope
        self.reviewMessage = reviewMessage
        self.add_item(discord.ui.TextDisplay(content="Are you sure you want to continue with the promotion?" if action == "execute" else "Are you sure you want to discard this recommendation?"))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.action == "execute":
            await Recognition.handlePromotionRecommendationExecute(interaction, memberId=self.memberId, currentRankId=self.currentRankId, targetRankId=self.targetRankId, scope=self.scope, reviewMessage=self.reviewMessage)
            return
        await Recognition.handlePromotionRecommendationDiscard(interaction, memberId=self.memberId, currentRankId=self.currentRankId, targetRankId=self.targetRankId, scope=self.scope, reviewMessage=self.reviewMessage)


class PromotionRecommendationVoteRationaleModal(discord.ui.Modal):
    def __init__(self, *, memberId: int, currentRankId: int, targetRankId: int, scope: str, vote: str, reviewChannelId: int, reviewMessageId: int, existingRationale: str | None = None) -> None:
        emoji = "\N{THUMBS UP SIGN}" if vote == "assent" else "\N{THUMBS DOWN SIGN}"
        super().__init__(title=f"Rationale for {emoji} vote", custom_id=f"schedule_modal_promotion_vote_{vote}")
        self.memberId = memberId
        self.currentRankId = currentRankId
        self.targetRankId = targetRankId
        self.scope = scope
        self.vote = vote
        self.reviewChannelId = reviewChannelId
        self.reviewMessageId = reviewMessageId
        self.rationale = discord.ui.TextInput(label=f"Rationale for {emoji} vote:", custom_id="schedule_text_promotion_vote_rationale", style=discord.TextStyle.long, default=existingRationale, required=True, min_length=1, max_length=1000)
        self.add_item(self.rationale)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.guild, discord.Guild):
            await interaction.response.send_message("Failed to submit vote rationale: Guild not found.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(self.reviewChannelId)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Failed to submit vote rationale: Review channel not found.", ephemeral=True)
            return
        try:
            reviewMessage = await channel.fetch_message(self.reviewMessageId)
        except Exception as error:
            log.exception(f"PromotionRecommendationVoteRationaleModal on_submit: failed to fetch review message - {error}")
            await interaction.response.send_message("Failed to submit vote rationale: Review message not found.", ephemeral=True)
            return
        rationale = self.rationale.value.strip()
        if rationale == "":
            await interaction.response.send_message("A rationale is required.", ephemeral=True)
            return
        await Recognition.handlePromotionRecommendationVote(interaction, vote=self.vote, memberId=self.memberId, currentRankId=self.currentRankId, targetRankId=self.targetRankId, scope=self.scope, rationale=rationale, reviewMessage=reviewMessage)


async def setup(bot: commands.Bot) -> None:
    Recognition.recommendForPromotion.error(Utils.onSlashError)
    Recognition.commend.error(Utils.onSlashError)
    await bot.add_cog(Recognition(bot))
    bot.add_dynamic_items(
        PromotionReviewAssentButton,
        PromotionReviewDisagreementButton,
        PromotionReviewAbstainButton,
        PromotionReviewExecuteButton,
        PromotionReviewDiscardButton
    )
