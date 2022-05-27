# FriendlySnek

## Introduction

Friendly Snek is a Discord bot made for *Sigma Security Group* that implements custom commands and features to make Sigma members' lifes easier.

## Prerequisites

The bot requires Python 3.10+ to run.

## Getting Started

You must have a [Discord Application](https://discord.com/developers/applications) with Bot enabled, along with all intents.

The bot needs the file `secret.py` in the project's root folder in order to run. You can either create it yourself, or run the bot without it for it to create the file automatically with a good template. \
The file needs to declare the following variables:

```py
TOKEN:str
TOKEN_DEV:str
FTP_HOST:str
FTP_PORT:int
FTP_USERNAME:str
FTP_PASSWORD:str
DEBUG:bool
```

You can easily toggle the bot's debug mode by changing the DEBUG variable in `secret.py`. On debug mode, the bot will use the debug server (`debug.py` constants).

All constants in `constants/debug.py` are for Adrian's personal Bot Testing Range (BTR). If you want the bot to work on another server you must replace all the IDs in said file.

Make sure to install all dependencies by executing: `python -m pip install -r requirements.txt`.

Run the bot by executing: `python -O main.py`.
