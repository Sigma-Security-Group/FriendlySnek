SCHEDULE_INTRO_MESSAGE = "Welcome to the schedule channel. To schedule an operation you can use the **`/operation`** command (or **`/bop`**) and follow the instructions through DMs. For a workshop use **`/workshop`** or **`/ws`** and for a generic event use **`/event`**. If you haven't set a preferred time zone yet you will be prompted to do so when you schedule any kind of event. If you want to set, change or delete your time zone preference you can do so with the **`/changetimezone`** command.\n\nYou can use the colored strip to the left of each event to quickly know its type at a glance. The colors are:\n🟩 Operation `/operation` or `/bop`\n🟦 Workshop `/workshop` or `/ws`\n🟨 Event `/event`\n\nIf you have any features suggestions or encounter any bugs, please contact {0} and/or {1}."

SCHEDULE_REMINDER_VOICE = " If you are in-game, please get in <#{0}> or <#{1}>. If you are not making it to this {event['type'].lower()}, please hit decline :x: on the <#{2}>."
SCHEDULE_REMINDER_INGAME = " If you are in-game, please please hit accept :white_check_mark: on the <#{0}>."

SCHEDULE_EVENT_DONE = "✅ Event created"

SCHEDULE_TIME_ZONE_QUESTION = ":clock1: What is your preferred time zone?"
SCHEDULE_TIME_ZONE_CHANGING = "Changing time zone preferences..."
SCHEDULE_TIME_ZONE_DONE = "✅ Time zone preferences changed"
SCHEDULE_TIME_ZONE_FILE_OCCUPIED = ":clock3: Time zones file is occupied. This happens rarely, but give it just a few seconds"
SCHEDULE_TIME_ZONE_UNSET = "You don't have a preferred time zone set."
SCHEDULE_TIME_ZONE_INFORMATION = " Enter `none`, a number from the list or any time zone name from the column \"TZ DATABASE NAME\" in the following [Wikipedia article](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to make your choice. If you enter `none` or something invalid your current preference will be deleted and you will be asked again the next time you schedule an event. You can change or delete your preferred time zone at any time with the `/changetimezone` command."
