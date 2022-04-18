# Schedule.py

## Command descriptions
SCHEDULE_COMMAND_DESCRIPTION = "Create {0} to add to the schedule."
CHANGE_TIME_ZONE_COMMAND_DESCRIPTION = "Change your time zone preferences for your next scheduled event."
REFRESH_SCHEDULE_COMMAND_DESCRIPTION = "Refreshing the schedule. Use this command if an event was deleted without using the reactions."

## Schedule messages
SCHEDULE_INTRO_MESSAGE = "Welcome to the schedule channel!\nTo schedule an operation you can use the `/operation` command (or `/bop`) and follow the instructions in your DM's.\nFor a workshop use `/workshop` or `/ws`.\nLastly, for generic events use `/event`.\n\nIf you haven't set a preferred time zone yet you will be prompted to do so when you schedule any kind of event. If you want to set, change or delete your time zone preference you may do so with the `/changetimezone` command.\n\nThe times you see on the schedule are based on your __local time zone__.\nThe event colors can be used to quickly identify what type of event it is:\n🟩 Operation `/operation` or `/bop`\n🟦 Workshop `/workshop` or `/ws`\n🟨 Event `/event`\n\nIf you have any suggestions for new features or encounter any bugs, please contact {0} and/or {1}."
SCHEDULE_EMPTY_1 = "...\nNo bop?\n...\nSnek is sad"
SCHEDULE_EMPTY_2 = ":cry:"

## Reminders
SCHEDULE_REMINDER_VOICE = " If you are in-game, please get in <#{0}> or <#{1}>. If you are not making it to this {event['type'].lower()}, please hit decline ❌ on the <#{2}>."
SCHEDULE_REMINDER_INGAME = " If you are in-game, please please hit accept ✅ on the <#{0}>."

## Responses
SCHEDULE_EVENT_CREATED = "✅ {0} created!"
SCHEDULE_EVENT_EDITED = "✅ {0} edited!"
SCHEDULE_EVENT_DELETED = "✅ {0} deleted!"
SCHEDULE_RESERVABLE_COMPLETED = "✅ Role reservation completed!"
SCHEDULE_RESERVABLE_CANCELLED = "❌ Role reservation canceled!"
SCHEDULE_EVENT_MESSAGE_PROGRESS = "Scheduling... Standby for {0}..."
SCHEDULE_EVENT_MESSAGE_DONE = "{0} on [schedule](<https://discord.com/channels/{1}/{2}/{3}>)!"
SCHEDULE_TEMPLATE_SAVED = "✅ Template saved!"
SCHEDULE_TEMPLATE_DISCARD = "❌ Template not saved!"
SCHEDULE_REFRESHING = "Refreshing <#{0}>..."

## Errors
SCHEDULE_INPUT_ERROR = "❌ Wrong input!"
SCHEDULE_BOP_NO_SPACE = "❌ Sorry, seems like there's no space left in the :b:op!"
SCHEDULE_RESERVABLE_SCHEDULE_ERROR = "❌ Schedule was updated while you were reserving a role. Try again!"
SCHEDULE_EVENT_EDIT_ERROR = "❌ Schedule was updated while you were editing your operation. Try again!"
SCHEDULE_EVENT_ERROR_COLLISION = "❌ There is a collision with another event!"
SCHEDULE_EVENT_ERROR_PADDING_EARLY = "❌ Your operation would start less than an hour after the previous event ends!"
SCHEDULE_EVENT_ERROR_PADDING_LATE = "❌ There is another event starting less than an hour after this one ends!"
SCHEDULE_EVENT_ERROR_DESCRIPTION = "Check the schedule and try inputting a another time!"

## Event
SCHEDULE_EVENT_EDIT = ":pencil2: What would you like to edit?"
SCHEDULE_EVENT_TYPE = ":pencil2: What is the type of your event?"
SCHEDULE_EVENT_TITLE = ":pencil2: What is the title of your {0}?"
SCHEDULE_EVENT_TITLE_OPERATION_REMINDER = "Remeber, operation names should start with the word 'Operation'\ne.g. Operation Red Tide"
SCHEDULE_EVENT_DESCRIPTION_QUESTION = ":notepad_spiral: What is the description?"
SCHEDULE_EVENT_DESCRIPTION = "Current description:\n```{0}```"
SCHEDULE_EVENT_URL_TITLE = ":notebook_with_decorative_cover: Enter `none` or a URL."
SCHEDULE_EVENT_URL_DESCRIPTION = "e.g. Signup sheet / Briefing / OPORD."
SCHEDULE_EVENT_RESERVABLE_QUESTION = "Are there any reservable roles?"
SCHEDULE_EVENT_RESERVABLE_PROMPT = "Enter `yes` or `y` if there are reservable roles or enter anything else if there are not."
SCHEDULE_EVENT_RESERVABLE_LIST_TITLE = "Type each reservable role in its own line (in a single message)."
SCHEDULE_EVENT_RESERVABLE_LIST_DESCRIPTION = "Press Shift + Enter to insert a newline. Editing the name of a role will make it vacant, but roles which keep their exact names will keep their reservations)."
SCHEDULE_EVENT_RESERVABLE_LIST_CURRENT = "Current reservable roles."
SCHEDULE_EVENT_MAP_PROMPT = ":globe_with_meridians: Choose a map."
SCHEDULE_EVENT_MAX_PLAYERS = ":family_man_boy_boy: What is the maximum number of attendees?"
SCHEDULE_EVENT_TIME_ZONE_QUESTION = ":clock1: It appears that you haven't set your preferred time zone yet. What is your preferred time zone?"
SCHEDULE_EVENT_TIME_ZONE_PROMPT = "Enter `none`, a number from the list or any time zone name from the column \"TZ DATABASE NAME\" in the following [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to make your choice. If you enter `none` or something invalid UTC will be assumed and you will be asked again the next time you schedule an event. You can change or delete your preferred time zone at any time with the `/changeTimeZone` command."
SCHEDULE_EVENT_SELECTED_TIME_ZONE = "Your current time zone preference is '{0}'."
SCHEDULE_EVENT_TIME = "What is the time of the {0}?"
SCHEDULE_EVENT_TIME_FORMAT = "e.g. `2022-04-18 11:36 AM`."
SCHEDULE_EVENT_TIME_TOMORROW = "Time was detected to be in the past 24h and was set to tomorrow."
SCHEDULE_EVENT_TIME_TOMORROW_PREVIEW = "Input time: <t:{0}:F>\nSelected time: <t:{1}:F>."
SCHEDULE_EVENT_TIME_PAST_QUESTION = "It appears that the selected time is in the past. Are you sure you want to set it to this?"
SCHEDULE_EVENT_TIME_PAST_PROMPT = "Enter `yes` or `y` to keep this time. Enter anything else to change it to another time."
SCHEDULE_EVENT_DURATION_QUESTION = "What is the duration of the {0}?"
SCHEDULE_EVENT_DURATION_PROMPT = "E.g.\n`30m`\n`2h`\n`4h 30m`\n`2h30`"
SCHEDULE_EVENT_DURATION_REGEX = r"^\s*((([1-9]\d*)?\d\s*h(\s*([0-5])?\d\s*m?)?)|(([0-5])?\d\s*m))\s*$"
SCHEDULE_EVENT_TEMPLATE_TITLE = ":clipboard: Select a template."
SCHEDULE_EVENT_TEMPLATE_DESCRIPTION = "Enter a template number or `none` to make a workshop from scratch."
SCHEDULE_EVENT_TEMPLATE_SAVE_QUESTION = "Do you wish to save this workshop as a template?"
SCHEDULE_EVENT_TEMPLATE_SAVE_PROMPT = "Enter `yes` or `y` if you want to save it or enter anything else otherwise."
SCHEDULE_EVENT_TEMPLATE_SAVE_NAME_QUESTION = "Which name would you like to save the template as?"
SCHEDULE_EVENT_TEMPLATE_SAVE_NAME_PROMPT = "Enter `none` to make it the same as the title."
SCHEDULE_EVENT_WAITING_LIST = ":link: Which workshop waiting list is your workshop linked to?"
SCHEDULE_EVENT_CONFIRM_DELETE = "Are you sure you want to delete this event?"

## Reservable roles
SCHEDULE_RESERVABLE_QUESTION = "Which role would you like to reserve?"
SCHEDULE_RESERVABLE_PROMPT = "Enter a number from the list, `none` to free up the role you currently have reserved. If you enter anything invalid it will cancel the role reservation"

## DM Notifications
SCHEDULE_EVENT_START_TIME_CHANGE_TITLE = ":clock3: The starting time has changed for: {0}!"
SCHEDULE_EVENT_START_TIME_CHANGE_DESCRIPTION = "From: <t:{0}:F>\n\u2000\u2000To: <t:{1}:F>"
SCHEDULE_EVENT_DELETED_TITLE = "🗑 {0} deleted: {1}!"
SCHEDULE_EVENT_DELETED_DESCRIPTION = "The {0} was scheduled to run:\n<t:{0}:F>"

## "Enter" prompts
SCHEDULE_NUMBER_FROM_TO = "Enter a number from **{0}** - **{1}**."
SCHEDULE_NUMBER_FROM_TO_OR_NONE = "Enter `none` or a number from **{0}** - **{1}**."
SCHEDULE_NUMBER_NON_NEGATIVE_OR_NONE = "Enter `none` or a non-negative number."
SCHEDULE_CANCEL = "Enter `cancel` to keep your current preference."

## Time zone
SCHEDULE_TIME_ZONE_QUESTION = ":clock1: What is your preferred time zone?"
SCHEDULE_TIME_ZONE_CHANGING = "Changing time zone preferences..."
SCHEDULE_TIME_ZONE_DONE = "✅ Time zone preferences changed!"
SCHEDULE_TIME_ZONE_FILE_OCCUPIED = ":clock3: Time zones file is occupied. This happens rarely, but give it just a few seconds..."
SCHEDULE_TIME_ZONE_UNSET = "You don't have a preferred time zone set."
SCHEDULE_TIME_ZONE_INFORMATION = " Enter `none`, a number from the list or any time zone name from the column \"TZ DATABASE NAME\" in the following [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to make your choice. If you enter `none` or something invalid your current preference will be deleted and you will be asked again the next time you schedule an event. You can change or delete your preferred time zone at any time with the `/changetimezone` command."

## Logging
LOG_FRIEND_REQ = "Sending friend request..."
LOG_IS_READY = "{0} is ready!"
LOG_COULDNT_START = "Couldn't start {0}!"
LOG_EDITING_EVENT = "{0} ({1}#{2}) is editing {3}."
LOG_EDITED_EVENT = "{0} ({1}#{2}) edited {3}."
LOG_CREATING_EVENT = "{0} ({1}#{2}) is creating {3}."
LOG_CREATED_EVENT = "{0} ({1}#{2}) created {3}."
LOG_CHECKING = "Checking {0}..."
LOG_DELETE_EVENT_ACTION = "Auto deleting: {0}."
LOG_DELETE_EVENT_NONE = "No events were auto deleted."
LOG_NOTIFICATION_ACCEPTED = "Pinging members in accepted not in VC: {0}"
LOG_NOTIFICATION_VC = "Pinging members in VC not in accepted: {0}"
LOG_SCHEDULE_UPDATE_ERROR = "{0} ({1}#{2}) was {3} but schedule was updated!"

# WorkshopInterest.py
WORKSHOPINTEREST_INTRO = "Welcome to the workshop interest channel. Here you can show interest for different workshops."
WORKSHOPINTEREST_INTERESTED_PEOPLE = "Interested People ({0})"
