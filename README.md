# FriendlySnek

## Introduction

Friendly Snek is a Discord bot made for *Sigma Security Group* that implements custom commands and features to make Sigma members' lifes easier.

## Prerequisites

The bot requires Python 3.10+ to run.

## Getting Started

You must have a [Discord Application](https://discord.com/developers/applications) with Bot enabled as well as all intents.

The bot needs a file `secret.py` in the project's root folder which defines a few variables. These are:

```py
token:str
tokenDev:str
ftpHost:str
ftpPort:int
ftpUsername:str
ftpPassword:str
```

All of the constants in `constants/debug.py` are made to work on Adrian's personal BTR (Bot Testing Range). If you want to make the bot work on another test server you will need to replace all the IDs in said file.

You can easily control whether the bot should use the debug server instead of the Sigma server by creating a file called `DEBUG` in the project's root folder (the file can be empty or contain any gibberish, it doesn't matter).

Make sure that you have all dependencies installed by running `python3 -m pip install -r requirements.txt`.

To run the bot, just run `python3 -OO main.py`.

To setup slash commands then you need to do something. GIYF & RTFM.
