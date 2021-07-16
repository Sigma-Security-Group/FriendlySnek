# Introduction

Friendly Snek is a discord bot made for Sigma Security Group that implements custom commands and features to make Sigma members' lifes easier.

# Getting Started

The bot needs a file `token` in the project's root folder which holds the secret token to connect to the bot account. You can also define a file `tokenDev` with the token of the debug bot account if you want to use the debug mode (also useful for dev). All of the constants in `constants/debug.py` are made to work on Adrian's personal BTR (Bot Testing Range). If you want to make the bot work on another test server you will need to replace all the IDs in said file.

You can easily control whether the bot should use the debug server instead of the Sigma server by creating a file called `DEBUG` in the project's root folder (the file can be empty or contain any gibberish, it doesn't matter).

To run the bot just run `python3 main.py`. Make sure however that you have all dependencies installed by running `python3 -m pip install -r requirements.txt`.

# Extra Info

Trello: https://trello.com/b/MwPeCK1w/friendly-snek-features