#from cryptography.fernet import Fernet
#with open("data/key.key", "rb") as keyFile:
#    fern = Fernet(keyFile.read())

#""" LONG ASS URL SHIT
#edit = (fern.encrypt(b"eventId=1043278468311416883{/}eventType=Operation{/}title=New Operation{/}description=once upon a great time...{/}externalURL=https://duckduckgo.com{/}reservableRoles=A-10C Pilot\nActual ffs{/}map=Altis{/}attendees=9{/}time=2022-12-14T09:00{/}duration=03:00")).decode("utf-8")

#aide = fern.encrypt(b"229212817448894464").decode("utf-8")

#print("\n\nhttp://127.0.0.1:5000/event?aide=" + aide + "&edit=" + edit)"""


## CREATING EVENT
#"""edit = fern.encrypt(b"authorId=229212817448894464").decode("utf-8")
#print("\n\nhttp://127.0.0.1:5000/event?info=" + edit)"""


## EDITING EVENT
#edit = fern.encrypt(b"eventId=1043307946953674803").decode("utf-8")
#print("\n\nhttp://127.0.0.1:5000/event?info=" + edit)

import os, random, json, pytz, asyncio, datetime

from discord import Embed, Color, utils
from flask import Flask, render_template, request, redirect
from copy import deepcopy
from datetime import datetime, timedelta
from dateutil.parser import parse as datetimeParse
from dateutil import tz
from constants import *
from cryptography.fernet import Fernet
from logger import Logger

#durationStr = "02:00"
#duration = datetime.time.fromisoformat(durationStr)
duration = timedelta(hours=2, minutes=0)

(starttime := datetimeParse("2069-04-20T04:20", tzinfos={"CDT": tz.gettz("UTC")}))
print(starttime)
print((starttime + duration).strftime("%Y-%m-%dT%H:%M"))
#(datetimeParse(starttime) + duration).strftime("%Y-%m-%dT%H:%M")
