####################
# Generic
####################

## Misc
COMMAND_PREFIX = "-"
TIME_FORMAT = "%Y-%m-%d %I:%M %p"
SCHEDULE_CANCEL = "Enter `cancel` to abort this command."
SCHEDULE_NUMBER_FROM_TO_OR_NONE = "Enter `none` or a number from **{0}** - **{1}**."
SCHEDULE_EVENT_TEMPLATE_SAVE_NAME_QUESTION = "Which name would you like to save the template as?"

## Error
ERROR_TIMEOUT = ":clock3: You were too slow, try again!"

## Logging
LOG_COG_READY = "{0} cog is ready!"
LOG_COULDNT_START = "Couldn't start {0}!"
LOG_CHECKING = "Checking {0}..."


## Time in seconds
TIME_ONE_MIN = 60  # Short
TIME_TEN_MIN = 600  # Normal
TIME_THIRTY_MIN = 1800  # Long


###################
# Poll.py
####################

POLL_PERCENT_REGEX = r"\(\d+\.?\d*%\)\s*"


####################
# Schedule.py
####################

SCHEDULE_EVENT_SELECTED_TIME_ZONE = "Your current time zone preference is `{0}`."
RESPONSE_EVENT_PROGRESS = "Scheduling... Standby for {0}..."
RESPONSE_EVENT_DONE = "`{0}` is now on [schedule](<https://discord.com/channels/{1}/{2}/{3}>)!"

## Errors
SCHEDULE_EVENT_ERROR_DESCRIPTION = "Enter `edit` to input a new time.\nEnter `override` to override this warning."

### Title
SCHEDULE_EVENT_TITLE = ":pencil2: What is the title of your {0}?"

### Description
SCHEDULE_EVENT_DESCRIPTION_QUESTION = ":notepad_spiral: What is the description?"
SCHEDULE_EVENT_DESCRIPTION = "Current description:\n```{0}```"

### URL
SCHEDULE_EVENT_URL_TITLE = ":notebook_with_decorative_cover: Enter `none` or a URL"
SCHEDULE_EVENT_URL_DESCRIPTION = "E.g. Signup sheet, Briefing, OPORD, etc."

### Reservable Roles
SCHEDULE_EVENT_RESERVABLE = "Reservable Roles"
SCHEDULE_EVENT_RESERVABLE_DIALOG = "Enter `none`, or `n` if there are none.\n\nOtherwise, type each reservable role in a new line (Shift + Enter)."

### Map
SCHEDULE_EVENT_MAP_PROMPT = ":globe_with_meridians: Choose a map"

### Attendees
SCHEDULE_EVENT_MAX_PLAYERS = ":family_man_boy_boy: What is the maximum number of attendees?"
SCHEDULE_EVENT_MAX_PLAYERS_DESCRIPTION = "Enter a number to set a limit.\nEnter `none` to set no limit.\nEnter `anonymous` to count attendance anonymously.\nEnter `hidden` to not count attendance."

### Time Zone
SCHEDULE_EVENT_SELECTED_TIME_ZONE = "Your current time zone preference is `{0}`."

### Time
SCHEDULE_EVENT_TIME = "What is the time of the {0}?"
SCHEDULE_EVENT_TIME_TOMORROW = "Time was detected to be in the past 24h and was set to tomorrow."
SCHEDULE_EVENT_TIME_TOMORROW_PREVIEW = "Input time: {0}.\nSelected time: {1}."
SCHEDULE_EVENT_TIME_PAST_QUESTION = "It appears that the selected time is in the past. Are you sure you want to set it to this?"
SCHEDULE_EVENT_TIME_PAST_PROMPT = "Enter `yes` or `y` to keep this time.\nEnter anything else to change it to another time."

### Duration
SCHEDULE_EVENT_DURATION_QUESTION = "What is the duration of the {0}?"
SCHEDULE_EVENT_DURATION_PROMPT = "E.g.\n`30m`\n`2h`\n`4h 30m`\n`2h30`"
SCHEDULE_EVENT_DURATION_REGEX = r"^\s*((([1-9]\d*)?\d\s*h(\s*([0-5])?\d\s*m?)?)|(([0-5])?\d\s*m))\s*$"

### Templates
SCHEDULE_EVENT_TEMPLATE_ACTION_REGEX = r"(edit |delete )?\d+"
SCHEDULE_EVENT_TEMPLATE_SAVE_NAME_QUESTION = "Which name would you like to save the template as?"
SCHEDULE_EVENT_CONFIRM_DELETE = "Are you sure you want to delete this {0}?"
