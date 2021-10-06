# Introduction

Friendly Snek is a discord bot made for Sigma Security Group that implements custom commands and features to make Sigma members' lifes easier.

# Requirements

The bot requires Python 3.8+ to run.

# Getting Started

The bot needs a file `secret.py` in the project's root folder which defines a few variables. These are:
* token (str)
* tokenDev (str)
* ftpHost (str)
* ftpPort (int)
* ftpUsername (str)
* ftpPassword (str)

This json file allows some functionalities from the bot to be controlled through an external controller (the controller implemented in anvilController.py is meant to connect to a web app made with anvil.app)

All of the constants in `constants/debug.py` are made to work on Adrian's personal BTR (Bot Testing Range). If you want to make the bot work on another test server you will need to replace all the IDs in said file.

You can easily control whether the bot should use the debug server instead of the Sigma server by creating a file called `DEBUG` in the project's root folder (the file can be empty or contain any gibberish, it doesn't matter).

To run the bot just run `python3 main.py`. Make sure however that you have all dependencies installed by running `python3 -m pip install -r requirements.txt`.

# Extra Info

Trello: https://trello.com/b/MwPeCK1w/friendly-snek-features