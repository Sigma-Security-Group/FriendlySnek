import logging, gspread

from datetime import datetime

from discord.ext import commands  # type: ignore
from google.oauth2.service_account import Credentials
from typing import *
from dataclasses import dataclass

from secret import DEBUG
from constants import *
if DEBUG:
    from constants.debug import *


log = logging.getLogger("FriendlySnek")


TARGET_WORKSHEET_ID = 11741916 # Recruitment Logs
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]
ws = None
credentials = Credentials.from_service_account_file("spreadsheet_account_creds.json", scopes=SCOPES)
gc = gspread.authorize(credentials)
sh = gc.open_by_key("17siSuyOUn0S1U1l1bf1gJGx9b7Tgrb1rzVquK_7qHmc")

worksheets = sh.worksheets()
for worksheet in worksheets:
    if worksheet.id == TARGET_WORKSHEET_ID:
        ws = worksheet
        break

log.debug(f"Spreadsheet: using spreadsheet '{sh.title}' and worksheet '{ws.title}' ({ws.id})")


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
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.debug(LOG_COG_READY.format("Spreadsheet"))
        self.bot.cogsReady["spreadsheet"] = True

    @staticmethod
    def memberJoin(member: discord.Member) -> None:
        Spreadsheet.createOrUpdateUserRow(
            ws,
            displayName=member.display_name,
            dateJoined=datetime.strftime(member.joined_at, "%d/%m/%Y") if member.joined_at else None,
            userId=str(member.id),
            status=dropdownStatus.values[0]
        )

    @staticmethod
    def getNewEntryRowId(worksheet: gspread.worksheet) -> int:
        col_values = worksheet.col_values(2) # Column B
        return len(col_values) + 1

    @staticmethod
    def getUserRowId(worksheet: gspread.worksheet, userId: int) -> int | None:
        col_values = worksheet.col_values(5)  # Column E is the 5th column
        for idx, value in enumerate(col_values):
            if value == str(userId):
                return idx + 1  # Row numbers are 1-indexed
        return None

    @staticmethod
    def createOrUpdateUserRow(worksheet: gspread.worksheet, *, rowNum: int | None = None, displayName: str | None = None, dateJoined: str | None = None, dateLastReply: str | None = None, userId: str | None = None, lastPromotion: str | None = None, status: str | None = None, position: str | None = None, seen: bool | None = None, teamId: int | None = None, teamName: str | None = None, teamDate: str | None = None) -> None:
        # User row (starting from column B):
        # - Discord Name
        # - Date Joined
        # - Date of Last Reply
        # - Discord User ID
        # - Last Promotion
        # - Status
        # - Position
        # - Seen
        # - Team ID
        # - Name
        # - Date

        if not rowNum and not userId:
            log.exception("Spreadsheet createOrUpdateUserRow: one of row number or userid must be provided")
            return

        # Use userId to get rowNum
        if not rowNum:
            rowNum = Spreadsheet.getUserRowId(worksheet, str(userId))

            # User not found
            if not rowNum:
                newEntryRowId = Spreadsheet.getNewEntryRowId(ws)
                worksheet.update([[displayName, dateJoined, dateLastReply, userId, lastPromotion, status, position, seen, teamId, teamName, teamDate]], f"B{newEntryRowId}")
                log.debug(f"Spreadsheet createOrUpdateUserRow: Created row for user id '{userId}' at row number '{rowNum}'")

            # User found
            else:
                worksheet.update([[displayName, dateJoined, dateLastReply, userId, lastPromotion, status, position, seen, teamId, teamName, teamDate]], f"B{rowNum}")
                log.debug(f"Spreadsheet createOrUpdateUserRow: Updated row for user id '{userId}' at row number '{rowNum}'")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Spreadsheet(bot))
