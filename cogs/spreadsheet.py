import logging, gspread

from datetime import datetime

from discord.ext import commands, tasks  # type: ignore
from google.oauth2.service_account import Credentials
from typing import *

import secret
from constants import *
if secret.DEBUG:
    from constants.debug import *


log = logging.getLogger("FriendlySnek")


TARGET_WORKSHEET_ID = 11741916 # Recruitment Logs
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]


class Dropdown:
    def __init__(self, title: str, reference: str | None, values: List[str]):
        self.title = title
        self.reference = reference
        self.values = values

    #def getNextValue(self, currentValue: str) -> str | None:
    #    if currentValue not in self.values:
    #        return None
    #    idx = self.values.index(currentValue)
    #    nextIdx = (idx + 1) % len(self.values)
    #    return self.values[nextIdx]


dropdownStatus = Dropdown(
    title="Status",
    reference="variables!$F$6:$F$13",
    values=["Prospect",
            "Recently Verified",
            "Verified",
            "Recently Passed NW",
            "Candidate",
            "Recently Promoted",
            "Associate"]
)


class Spreadsheet(commands.Cog):
    ROW_STARTING_INDEX = 7
    COLUMN_STARTING_INDEX = 2

    WORKSHEET_COLUMNS = {
        "displayName": COLUMN_STARTING_INDEX,
        "dateJoined": COLUMN_STARTING_INDEX + 1,
        "dateLastReply": COLUMN_STARTING_INDEX + 2,
        "userId": COLUMN_STARTING_INDEX + 3,
        "lastPromotion": COLUMN_STARTING_INDEX + 4,
        "status": COLUMN_STARTING_INDEX + 5,
        "position": COLUMN_STARTING_INDEX + 6,
        "seen": COLUMN_STARTING_INDEX + 7,
        "teamId": COLUMN_STARTING_INDEX + 8,
        "teamName": COLUMN_STARTING_INDEX + 9,
        "teamDate": COLUMN_STARTING_INDEX + 10
    }

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @staticmethod
    def getWorksheet() -> gspread.worksheet.Worksheet | None:
        try:
            credentials = Credentials.from_service_account_file("spreadsheet_account_creds.json", scopes=SCOPES)
            gc = gspread.authorize(credentials)
            sh = gc.open_by_key("17siSuyOUn0S1U1l1bf1gJGx9b7Tgrb1rzVquK_7qHmc")
        except Exception as e:
            log.warning(f"Spreadsheet getWorksheet: failed to authenticate or open spreadsheet: {e}")
            return

        worksheets = sh.worksheets()
        for worksheet in worksheets:
            if worksheet.id == TARGET_WORKSHEET_ID:
                log.debug(f"Spreadsheet getWorksheet: using spreadsheet '{sh.title}' and worksheet '{worksheet.title}' ({worksheet.id})")
                return worksheet
        log.warning(f"Spreadsheet getWorksheet: worksheet with id '{TARGET_WORKSHEET_ID}' not found")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Spreadsheet"))
        self.bot.cogsReady["spreadsheet"] = True

        if not secret.SPREADSHEET_ACTIVE:
            return

        if secret.SPREADSHEET_ACTIVE and not secret.DEBUG and not self.kickTaggedMembers.is_running():
            self.kickTaggedMembers.start()

    @staticmethod
    def memberJoin(member: discord.Member) -> None:
        if not secret.SPREADSHEET_ACTIVE:
            return
        worksheet = Spreadsheet.getWorksheet()
        if not worksheet:
            return

        Spreadsheet.createOrUpdateUserRow(
            worksheet,
            displayName=member.display_name,
            dateJoined=datetime.strftime(member.joined_at, "%d/%m/%Y") if member.joined_at else None,
            userId=str(member.id),
            status=dropdownStatus.values[0]
        )

    @staticmethod
    def getNewEntryRowId(worksheet: gspread.worksheet.Worksheet) -> int:
        col_values = worksheet.col_values(Spreadsheet.WORKSHEET_COLUMNS["displayName"])
        return len(col_values) + 1

    @staticmethod
    def getUserRowId(worksheet: gspread.worksheet.Worksheet, userId: int) -> int | None:
        col_values = worksheet.col_values(Spreadsheet.WORKSHEET_COLUMNS["userId"])
        for idx, value in enumerate(col_values):
            if value == str(userId):
                return idx + 1  # Row numbers are 1-indexed
        return None

    @staticmethod
    def createOrUpdateUserRow(
        worksheet: gspread.worksheet.Worksheet | None, *,
        rowNum: int | None = None,
        displayName: str | None = None,
        dateJoined: str | None = None,
        dateLastReply: str | None = None,
        userId: str | None = None,
        lastPromotion: str | None = None,
        status: str | None = None,
        position: str | None = None,
        operationsAttended: str | None = None,
        seen: bool | None = None,
        teamId: int | None = None,
        teamName: str | None = None,
        teamDate: str | None = None) -> None:
        # User row (starting from column B):
        # - Discord Name
        # - Date Joined
        # - Date of Last Reply
        # - Discord User ID
        # - Last Promotion
        # - Status
        # - Position
        # - Operations Attended
        # - Seen
        # - Team ID
        # - Name
        # - Date

        if not worksheet or not secret.SPREADSHEET_ACTIVE:
            log.debug("Spreadsheet createOrUpdateUserRow: spreadsheet not active or worksheet is none")
            return

        if not rowNum and not userId:
            log.exception("Spreadsheet createOrUpdateUserRow: one of row number or userid must be provided")
            return

        # Use userId to get rowNum
        if not rowNum:
            rowNum = Spreadsheet.getUserRowId(worksheet, str(userId))

            # User not found
            if not rowNum:
                newEntryRowId = Spreadsheet.getNewEntryRowId(worksheet)
                rowNum = newEntryRowId
                log.debug(f"Spreadsheet createOrUpdateUserRow: Created row for user id '{userId}' at row number '{newEntryRowId}'")

            # User found
            else:
                log.debug(f"Spreadsheet createOrUpdateUserRow: Updated row for user id '{userId}' at row number '{rowNum}'")

        worksheet.update([[
            displayName,
            dateJoined,
            dateLastReply,
            userId,
            lastPromotion,
            status,
            position,
            operationsAttended,
            seen,
            teamId,
            teamName,
            teamDate
        ]], f"B{rowNum}")

    @tasks.loop(hours=6)
    async def kickTaggedMembers(self) -> None:
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.exception("Spreadsheet kickTaggedMembers: guild is none")
            return

        worksheet = Spreadsheet.getWorksheet()
        if not worksheet:
            return

        columnUserIds = worksheet.col_values(Spreadsheet.WORKSHEET_COLUMNS["userId"])[Spreadsheet.ROW_STARTING_INDEX - 1:]
        columnPositions = worksheet.col_values(Spreadsheet.WORKSHEET_COLUMNS["position"])[Spreadsheet.ROW_STARTING_INDEX - 1:]

        rowsToDelete = []
        for userId, userPosition in zip(columnUserIds, columnPositions):
            if not userId or userPosition != "Remove":
                continue

            member = guild.get_member(int(userId))

            # Member not in guild
            if member is None:
                log.debug(f"Spreadsheet kickTaggedMembers: User id '{userId}' not found in server. Marking row for removal")

            # Member in guild
            else:
                log.debug(f"Spreadsheet kickTaggedMembers: Kicked user '{member.display_name}' ('{userId}') from server. Marking row for removal")
                try:
                    await guild.kick(member, reason="Tagged for removal in spreadsheet")
                except discord.HTTPException:
                    log.exception(f"Spreadsheet kickTaggedMembers: Failed to kick user '{member.display_name}' ('{userId}'). Not marking row for removal")
                    continue

            rowsToDelete.append(Spreadsheet.ROW_STARTING_INDEX + columnUserIds.index(userId))

        for row in sorted(rowsToDelete, reverse=True):
            worksheet.update([["", "", "", "", "", "", "Unknown", "", "", "", ""]], f"B{row}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Spreadsheet(bot))
