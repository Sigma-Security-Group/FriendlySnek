# FriendlySnek

A Discord bot made for *Sigma Security Group* that implements custom commands and features to make Sigma members' lifes easier.

## Prerequisites

* Python 3.10+.

* [Discord Application](https://discord.com/developers/applications) with Bot and all intents enabled.

* Installed dependencies: `python -m pip install -r requirements.txt`.

## Getting Started

The bot needs the file `secret.py` in the project's root folder in order to run. You can either create it yourself, or run the bot without it for it to create the file automatically with a good template. \
The file needs to declare the following variables:

```py
TOKEN = ""
TOKEN_DEV = ""
DEBUG = True

MOD_UPDATE_ACTIVE = False
SME_REMINDER_ACTIVE = False
SME_BIG_BROTHER = False

SFTP = {
    "0.0.0.0": {
        "username": "",
        "password": ""
    },
}

REDDIT_ACTIVE = False
REDDIT = {
    "client_id": "",
    "client_secret": "",
    "password": ""
}
```

You can easily toggle the bot's debug mode by changing the DEBUG variable in `secret.py`. On debug mode, the bot will use the debug server (`debug.py` constants).

All constants in `constants/debug.py` are for Adrian's personal Bot Testing Range (BTR). If you want the bot to work on another server you must replace all the IDs in said file.

Run the bot by executing: `python main.py`.
