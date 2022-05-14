####################
# Jokes.py
####################

## Command descriptions
DADJOKE_COMMAND_DESCRIPTION = "Telling you a good joke using the icanhazdadjoke.com API."


####################
# JustBob.py
####################

## Command descriptions
JUSTBOB_COMMAND_DESCRIPTION = "Play the minigame Just Bob."

## Misc
JUSTBOB_CHANNEL_RESTRAIN = "Sorry, but you can only play Just Bob in <#{0}> or in <#{1}>!"
JUSTBOB_PLAYING = "Playing Just Bob..."
JUSTBOB_COMPLETION = "Congratulations, you completed all levels! 🎉\nYou can replay them if you'd like.\nMore levels coming soon!"


####################
# MissionUploader.py
####################

## Command descriptions
MISSION_UPLOAD_COMMAND_DESCRIPTION = "Upload a mission PBO file to the server."

## Errors
MISSION_UPLOAD_ERROR_NO_FILE = "❌ You didn't upload a file. Please upload the mission file!"
MISSION_UPLOAD_ERROR_TOO_MANY_FILES = "❌ You supplied too many files. Plese only upload one file!"
MISSION_UPLOAD_ERROR_NO_PBO = "❌ This is not a PBO file. Please upload a PBO file!"
MISSION_UPLOAD_ERROR_DUPLICATE = "❌ This file already exists. Please rename the file and reupload it!"

## Logging
MISSION_UPLOAD_LOG_UPLOADING = "{0} ({1}#{2}) is uploading a mission file..."
MISSION_UPLOAD_LOG_UPLOADED = "{0} ({1}#{2}) uploaded a mission file!"

## Misc
MISSION_UPLOAD_RESPONSE = "Upload mission file in DMs..."
MISSION_UPLOAD_PROMPT = "Upload the mission file you want to put on the server."
MISSION_UPLOAD_UPLOADING = "Uploading mission file..."
MISSION_UPLOAD_UPLOADED = "Mission file uploaded!"


####################
# Poll.py
####################

## Command descriptions
POLL_COMMAND_DESCRIPTION = "Create a poll."

## Misc
POLL_PERCENT_REGEX = r"\(\d+\.?\d*%\)\s*"

####################
# Schedule.py
####################

## Command descriptions
SCHEDULE_COMMAND_DESCRIPTION = "Create {0} to add to the schedule."
CHANGE_TIME_ZONE_COMMAND_DESCRIPTION = "Change your time zone preferences for your next scheduled event."
REFRESH_SCHEDULE_COMMAND_DESCRIPTION = "Refreshes the schedule. Use this command if an event was deleted without using the reactions."

## Schedule messages
SCHEDULE_INTRO_MESSAGE = "Welcome to the schedule channel!\nTo schedule an operation you can use the `/operation` command (or `/bop`) and follow the instructions in your DMs.\nFor a workshop use `/workshop` or `/ws`.\nLastly, for generic events use `/event`.\n\nIf you haven't set a preferred time zone yet you will be prompted to do so when you schedule any kind of event. If you want to set, change or delete your time zone preference you may do so with the `/changetimezone` command.\n\nThe times you see on the schedule are based on your __local time zone__.\n\nThe event colors can be used to quickly identify what type of event it is:\n🟩 Operation `/operation` or `/bop`\n🟦 Workshop `/workshop` or `/ws`\n🟨 Event `/event`\n\nIf you have any suggestions for new features or encounter any bugs, please contact: {0}."
SCHEDULE_EMPTY_1 = "...\nNo bop?\n...\nSnek is sad"
SCHEDULE_EMPTY_2 = ":cry:"

## Reminders
SCHEDULE_REMINDER_VOICE = " If you are in-game, please get in <#{0}> or <#{1}>. If you are not making it to this {2}, please hit decline ❌ on the <#{3}>."
SCHEDULE_REMINDER_INGAME = " If you are in-game, please hit accept ✅ on the <#{0}>."

## Responses
CHECK_CREATED = "✅ {0} created!"
CHECK_EDITED = "✅ {0} edited!"
CHECK_DELETED = "✅ {0} deleted!"
CHECK_COMPLETED = "✅ {0} completed!"
ABORT_CANCELED = "❌ {0} canceled!"
SCHEDULE_TEMPLATE_SAVED = "✅ Template saved as `{0}`!"
SCHEDULE_TEMPLATE_DISCARD = "❌ Template not saved!"
RESPONSE_EVENT_PROGRESS = "Scheduling... Standby for {0}..."
RESPONSE_EVENT_DONE = "The {0} `{1}` is now on [schedule](<https://discord.com/channels/{2}/{3}/{4}>)!"
RESPONSE_REFRESHING = "Refreshing <#{0}>..."
RESPONSE_TIME_ZONE = "Changing time zone preferences..."

## Errors
SCHEDULE_INPUT_ERROR = "❌ Invalid input!"
SCHEDULE_BOP_NO_SPACE = "❌ Sorry, seems like there's no space left in the :b:op!"
SCHEDULE_RESERVABLE_SCHEDULE_ERROR = "❌ Schedule was updated while you were reserving a role. Try again!"
SCHEDULE_EVENT_EDIT_ERROR = "❌ Schedule was updated while you were editing your operation. Try again!"
SCHEDULE_EVENT_ERROR_COLLISION = "❌ There is a collision with another event!"
SCHEDULE_EVENT_ERROR_PADDING_EARLY = "❌ Your operation would start less than an hour after the previous event ends!"
SCHEDULE_EVENT_ERROR_PADDING_LATE = "❌ There is another event starting less than an hour after this one ends!"
SCHEDULE_EVENT_ERROR_DESCRIPTION = "Check the schedule and try inputting a another time!"

## Event
SCHEDULE_EVENT_EDIT = ":pencil2: What would you like to edit?"

### Type
SCHEDULE_EVENT_TYPE = ":pencil2: What is the type of your event?"

### Title
SCHEDULE_EVENT_TITLE = ":pencil2: What is the title of your {0}?"
SCHEDULE_EVENT_TITLE_OPERATION_REMINDER = "Remeber, operation names should start with the word `Operation`\nE.g. Operation Red Tide."

### Description
SCHEDULE_EVENT_DESCRIPTION_QUESTION = ":notepad_spiral: What is the description?"
SCHEDULE_EVENT_DESCRIPTION = "Current description:\n```{0}```"

### URL
SCHEDULE_EVENT_URL_TITLE = ":notebook_with_decorative_cover: Enter `none` or a URL"
SCHEDULE_EVENT_URL_DESCRIPTION = "E.g. Signup sheet, Briefing, OPORD, etc."

### Reservable Roles
SCHEDULE_EVENT_RESERVABLE = "Reservable Roles"
SCHEDULE_EVENT_RESERVABLE_DIALOG = "Enter `none`, or `n` if there are none.\n\nOtherwise, type each reservable role in a new line (Shift + Enter)."
SCHEDULE_EVENT_RESERVABLE_DIALOG_EDIT = "\n(Editing the name of a role will make it vacant, but roles which keep their exact names will keep their reservations)."
SCHEDULE_EVENT_RESERVABLE_LIST_CURRENT = "Current reservable roles"

SCHEDULE_RESERVABLE_QUESTION = "Which role would you like to reserve?"
SCHEDULE_RESERVABLE_PROMPT = "Enter a number from the list\nEnter `none` un-reserve any role you have occupied.\nIf you enter anything invalid it will cancel the role reservation."

### Map
SCHEDULE_EVENT_MAP_PROMPT = ":globe_with_meridians: Choose a map"

### Attendees
SCHEDULE_EVENT_MAX_PLAYERS = ":family_man_boy_boy: What is the maximum number of attendees?"
SCHEDULE_EVENT_MAX_PLAYERS_DESCRIPTION = "Enter a positive number to set a limit.\nEnter `none` to set no limit.\nEnter `anonymous` to count attendance anonymously.\nEnter `hidden` to not count attendance."

### Time Zone
SCHEDULE_EVENT_TIME_ZONE_QUESTION = ":clock1: It appears that you haven't set your preferred time zone yet. What is your preferred time zone?"
SCHEDULE_EVENT_TIME_ZONE_PROMPT = "Enter `none`, a number from the list or any time zone name from the column \"**TZ DATABASE NAME**\" in this [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).\nIf you enter `none` or something invalid, UTC will be assumed and you will be asked again the next time you schedule an event. You can change or delete your preferred time zone with `/changetimezone`."
SCHEDULE_EVENT_SELECTED_TIME_ZONE = "Your current time zone preference is `{0}`."

SCHEDULE_TIME_ZONE_QUESTION = ":clock1: What's your preferred time zone?"
SCHEDULE_TIME_ZONE_UNSET = "You don't have a preferred time zone set."
SCHEDULE_TIME_ZONE_POPULAR = "Popular Time Zones"
SCHEDULE_TIME_ZONE_INFORMATION = "\n\nEnter a number from the list below.\nEnter any time zone name from the column \"**TZ DATABASE NAME**\" in this [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)."
SCHEDULE_TIME_ZONE_OPTION_ERASE = "\nEnter `none` to erase current preferences."

### Time
SCHEDULE_EVENT_TIME = "What is the time of the {0}?"
SCHEDULE_EVENT_TIME_FORMAT = "E.g. `2022-04-18 11:36 AM`."
SCHEDULE_EVENT_TIME_TOMORROW = "Time was detected to be in the past 24h and was set to tomorrow."
SCHEDULE_EVENT_TIME_TOMORROW_PREVIEW = "Input time: <t:{0}:F>\nSelected time: <t:{1}:F>."
SCHEDULE_EVENT_TIME_PAST_QUESTION = "It appears that the selected time is in the past. Are you sure you want to set it to this?"
SCHEDULE_EVENT_TIME_PAST_PROMPT = "Enter `yes` or `y` to keep this time. Enter anything else to change it to another time."

### Duration
SCHEDULE_EVENT_DURATION_QUESTION = "What is the duration of the {0}?"
SCHEDULE_EVENT_DURATION_PROMPT = "E.g.\n`30m`\n`2h`\n`4h 30m`\n`2h30`"
SCHEDULE_EVENT_DURATION_REGEX = r"^\s*((([1-9]\d*)?\d\s*h(\s*([0-5])?\d\s*m?)?)|(([0-5])?\d\s*m))\s*$"

### Templates
SCHEDULE_EVENT_TEMPLATE_TITLE = ":clipboard: Templates"
SCHEDULE_EVENT_TEMPLATE_DESCRIPTION = "Enter a template number or `none` to make a workshop from scratch.\n\nEdit template: `edit` + template number. E.g. `edit 2`.\nDelete template: `delete` + template number. E.g. `delete 4`. **IRREVERSIBLE!**"
SCHEDULE_EVENT_TEMPLATE_LIST_TITLE = "Templates"
SCHEDULE_EVENT_TEMPLATE_ACTION_REGEX = r"(edit |delete )?\d+"
SCHEDULE_EVENT_TEMPLATE_SAVE_QUESTION = "Do you wish to save this workshop as a template?"
SCHEDULE_EVENT_TEMPLATE_SAVE_PROMPT = "Enter `yes` or `y` if you want to save it or enter anything else otherwise."
SCHEDULE_EVENT_TEMPLATE_SAVE_NAME_QUESTION = "Which name would you like to save the template as?"
SCHEDULE_EVENT_TEMPLATE_SAVE_NAME_PROMPT = "Enter `none` to make it the same as the title."
SCHEDULE_EVENT_WAITING_LIST = ":link: Which workshop waiting list is your workshop linked to?"
SCHEDULE_EVENT_CONFIRM_DELETE = "Are you sure you want to delete this {0}?"

## DM Notifications
SCHEDULE_EVENT_START_TIME_CHANGE_TITLE = ":clock3: The starting time has changed for: {0}!"
SCHEDULE_EVENT_START_TIME_CHANGE_DESCRIPTION = "From: <t:{0}:F>\n\u2000\u2000To: <t:{1}:F>"
SCHEDULE_EVENT_DELETED_TITLE = "🗑 {0} deleted: {1}!"
SCHEDULE_EVENT_DELETED_DESCRIPTION = "The {0} was scheduled to run:\n<t:{1}:F>"

## "Enter" prompts
SCHEDULE_NUMBER_FROM_TO = "Enter a number from **{0}** - **{1}**."
SCHEDULE_NUMBER_FROM_TO_OR_NONE = "Enter `none` or a number from **{0}** - **{1}**."
SCHEDULE_CANCEL = "Enter `cancel` to abort this command."

## Logging
LOG_COULDNT_START = "Couldn't start {0}!"
LOG_EDITED_EVENT = "{0} ({1}#{2}) edited {3}."
LOG_CREATING_EVENT = "{0} ({1}#{2}) is creating {3}..."
LOG_CREATED_EVENT = "{0} ({1}#{2}) created {3}!"
LOG_CHECKING = "Checking {0}..."
LOG_SCHEDULE_UPDATE_ERROR = "{0} ({1}#{2}) was {3} but schedule was updated!"


####################
# WorkshopInterest.py
####################

WORKSHOPINTEREST_INTRO = "Welcome to the Workshop Interest Channel! Here you can show interest for different workshops!"
WORKSHOPINTEREST_INTERESTED_PEOPLE = "Interested People ({0})"
WORKSHOPINTEREST_PING = "{0}\nA {1} workshop is up on <#{2}> - which you are interested in.\nIf you're no longer interested, please remove yourself from the list in <#{3}>!"

## Descriptions
NEWCOMER_DESC = "Learn what you need to know before attending an operation in Sigma Security Group."
RW_DESC = "Learn to fly helicopters and provide transport and close air support."
FW_DESC = "Learn the dynamics of using fixed wing and fighter jet aircraft."
JTAC_DESC = "Learn how to direct close air support."  # Unverifed description.
MEDIC_DESC = "Learn how to administer combat aid to wounded personnel in a timely and effective manner. "  # Unverifed description.
HW_DESC = "Learn how to efficiently operate as a machine gun crew, use grenade launchers, and shoot cretins out of shitboxes (AT & AA)."
MARKSMAN_DESC = "Learn how to shoot big bullet far."
BREACHER_DESC = "Become an expert in close-quarters battle (CQB)."  # Unverifed description.
MECHANISED_DESC = "A short course on driving, gunning, and commanding a 6.21 million dollar reason the heavy weapons guy is useless."
RPVSO_DESC = "Learn how to employ recon and attack Remote Piloted Vehicles (Drones)."  # Unverifed description.
TL_DESC = "Learn how to effectively plan and assault targets with a whole team and assets."  # Unverifed description.


####################
# MessageAnalysis.py
####################

ERROR_INVALID_MESSAGE = "❌ Invalid message!"
VIDEO_URLS_REGEX = r"https?:\/\/((www)?(clips)?\.)?(youtu(be)?|twitch|streamable)\.(com|be|tv).+"
ANALYSIS_ILLEGAL_MESSAGE = "The message you just posted in <#{0}> was deleted because no {1} was detected in it.\n\nIf this is an error, then please ask **staff** to post the {1} for you and inform: {2}!"


####################
# Main.py
####################

MAIN_RELOAD_RESPONSE = "Cogs reloaded!"


####################
# Generic
####################

## Misc
COMMAND_PREFIX = "-"

## Error
ERROR_TIMEOUT = ":clock3: You were too slow, try again!"

## Logging
LOG_COG_READY = "{0} cog is ready!"
LOG_BOT_READY = "Bot Ready!"
LOG_BOT_STOPPED = "Bot stopped!"
LOG_ERROR = "An error occured!"

## Time in seconds
TIME_ONE_MIN = 60
TIME_TWO_MIN = 120
TIME_FIVE_MIN = 300
TIME_TEN_MIN = 600
TIME_THIRTY_MIN = 1800
