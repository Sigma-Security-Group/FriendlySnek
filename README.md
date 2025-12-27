# FriendlySnek

A Discord bot made for *Sigma Security Group* that implements custom commands and features to make Sigma members' lifes easier.

## Prerequisites

* [Discord Application](https://discord.com/developers/applications) with Bot and all intents enabled

* [Python 3.12+](https://www.python.org/)

* Installed dependencies:
    * (Recommended) [UV](https://docs.astral.sh/uv/getting-started/installation/): `uv sync`
    * [Pip](https://pip.pypa.io/en/stable/installation/): `python -m pip install -r requirements.txt`

## Getting Started

The bot needs the file `secret.py` in the project's root folder in order to run. Create the file according to the following codeblock:

```py
TOKEN = ""  # Token used if DEBUG is False
TOKEN_DEV = ""  # Token used if DEBUG is True
DEBUG = True

MOD_UPDATE_ACTIVE = False  # Toggle checking mod updates from Steam
SME_REMINDER_ACTIVE = False  # Toggle SME reminders every month
SME_BIG_BROTHER = False  # Toggle summarizing SME activity every 6 months
WORKSHOP_INTEREST_WIPE = False  # Toggle wiping workshop interest list every new year
SPREADSHEET_ACTIVE = False  # Toggle modification to recruitment Google spreadsheet

SFTP = {  # SFTP credentials to server(s)
    "0.0.0.0": {
        "name": "My Server",
        "port": 8822,
        "directory": "0.0.0.0_2302/mpmissions",
        "username": "ftp_user",
        "password": "ftp_password",
    },
}

REDDIT_ACTIVE = False  # Toggle Reddit recruitment posts
REDDIT = {  # Reddit account credentials
    "client_id": "",
    "client_secret": "",
    "password": ""
}

DISCORD_LOGGING = {  # Log levels based on type of event
    "upload_mission_file": True,
    "upload_file": True,
    "voice_dynamic_create": True,
    "voice_dynamic_name": True,
    "voice_dynamic_limit": False,
    "channel_create": True,
    "channel_delete": True,
    "user_join": True,
    "user_leave": True,
    "user_kick": True,
    "user_ban": True,
    "user_unban": True,
}
```

* You can easily toggle the bot's debug mode by changing the DEBUG variable in `secret.py`. On debug mode, the bot will use the debug server (`debug.py` constants).

* All constants in `constants/debug.py` are for Adrian's personal Bot Testing Range (BTR). If you want the bot to work on another server you must replace all the IDs in said file.

* To start the bot run:
    * UV: `uv run main.py`
    * Pip: `<python> main.py`
