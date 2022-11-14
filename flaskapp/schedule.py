"""TODO
MVP
    ✅ Create Events
    ❌ Edit Events
    ❌ Delete Events

Little question mark info box next to some inputs
    Reservable Roles -> Enter each role into a new line
    Duration -> 24h clock where the...
    !! Workshop Linking -> Linking pings the members interested and removes them after completing the ws!

Switch between Op, WS, Event
    Should we have a common input list? Like title, description, URL etc?

Templates
    Select menu
    Javascript input.value = Template.shit.value
"""
import os, random, json, re, pytz, asyncio

from discord import Embed, Color, utils
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, timedelta, time
from dateutil.parser import parse as datetimeParse
from constants import *
from cryptography.fernet import Fernet
from logger import Logger
log = Logger()

from secret import DEBUG
if DEBUG:
    from constants.debug import *

fileDirname = os.path.dirname(__file__)
app = Flask(__name__, template_folder=f"{fileDirname}/templates", static_folder=f"{fileDirname}/static")

# TODO Move to constants?
EVENTS_FILE = "data/events.json"
TIME_FORMAT_HTML = "%Y-%m-%dT%H:%M"
KEY_FILE = "data/key.key"
UTC = pytz.UTC
TIMEOUT_EMBED = Embed(title=ERROR_TIMEOUT, color=Color.red())

# Training map first, then the rest in alphabetical order
MAPS = [
    "Training Map",
    "Altis",
    "Anizay",
    "Bukovina",
    "Bystrica",
    "Chernarus (Autumn)",
    "Chefnarus (Summer)",
    "Chernarus (Winter)",
    "Desert",
    "Dingor v3.82",
    "Fapovo v1.8",
    "Hellanmaa",
    "Hellanmaa winter",
    "Isla Abramia v3.9",
    "Khoramshahr",
    "Kujari",
    "Kunduz, Afghanistan",
    "Lingor v3.9.5",
    "Livonia",
    "Malden 2035",
    "Mutambara",
    "Niakala",
    "Porto",
    "Proving Grounds",
    "Pulau",
    "Rahmadi",
    "Sahrani",
    "Sanagasta, Pampa de la Viuda, I a",
    "Sefrou-Ramal",
    "Shapur",
    "Southern Sahrani",
    "Stratis",
    "Takistan",
    "Takistan Mountains",
    "Tanoa",
    "United Sahrani",
    "Utes",
    "Vinjesvingen",
    "Virolahti",
    "Virtual Reality",
    "Zargabad"
]

mapsValue = [{"value": "", "text": "No Map", "isSelected": False}] + [{"value": map_, "text": map_, "isSelected": False} for map_ in MAPS]
attendeesValue = [{"value": str(opt), "text": str(opt), "isSelected": False} for opt in ["No Limit", "Anonymous", "Hidden"] + list(range(1, 51))]
timeValue = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00:00")
with open("data/workshopInterest.json") as f:
    workshops = json.load(f).keys()


# The commit hash that the bot is running on
try:
    with open("./.git/logs/refs/heads/main") as f:
        commitHash = f.readlines()[-1].split()[1][:7]  # last line, second column, first 7 characters
except Exception:
    commitHash = "Nope"

LIMITS = {
    "title": 256,
    "description": 4096,
    "fieldValue": 1024
}


@app.route("/")
def index():
    # TODO Make this a dashboard instead of redirecting
    return redirect("/event", code=302)


@app.route("/event", methods=["GET", "POST"])
def createEvent():
    if request.method == "GET":
        sendToTemplate = {}
        sendToTemplate["title"] = "Create An Event"

        with open("constants/opAdjectives.txt") as eventsFile:
            adjectives = eventsFile.readlines()
            adj = random.choice(adjectives).strip("\n")

        with open("constants/opNouns.txt") as eventsFile:
            nouns = eventsFile.readlines()
            nou = random.choice(nouns).strip("\n")

        titlePlaceholder = f"Operation {adj.capitalize()} {nou.capitalize()}"
        evenTypeFields = {}

        # Common Fields
        evenTypeFields["Common"] = [
            {
                "label": "Event Type",
                "type": "select",
                "name": "eventType",
                "value": [
                    {"value": "Operation", "text": "Operation", "isSelected": True},
                    {"value": "Workshop", "text": "Workshop", "isSelected": False},
                    {"value": "Event", "text": "Event", "isSelected": False},
                ],
                "isRequired": True,
                "isReadOnly": False,
            }
        ]

        # Operation Fields
        evenTypeFields["Operation"] = [
            {
                "label": "Title",
                "type": "text",
                "name": "title",
                "placeholder": titlePlaceholder,
                "value": "",
                "maxLen": LIMITS["title"],
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "Description",
                "type": "textarea",
                "name": "description",
                "placeholder": "Once upon a time...",
                "maxLen": LIMITS["description"],
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "External URL",
                "type": "text",
                "name": "externalURL",
                "placeholder": "https://example.com",
                "value": "",
                "maxLen": LIMITS["fieldValue"],
                "isRequired": False,
                "isReadOnly": False,
            },
            # Future upgrade: Make JavaScript add a new input text box when the previous one has text in. So one role per box
            {
                "label": "Reservable Roles",
                "type": "textarea",
                "name": "reservableRoles",
                "placeholder": "Actual\n2IC\nJTAC\nA-10C Pilot",
                "maxLen": LIMITS["fieldValue"],
                "isRequired": False,
                "isReadOnly": False,
            },
            {
                "label": "Map",
                "type": "select",
                "name": "map",
                "value": mapsValue,
                "isRequired": False,
                "isReadOnly": False,
            },
            {
                "label": "Attendees",
                "type": "select",
                "name": "attendees",
                "value": attendeesValue,
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "Time",
                "type": "datetime-local",
                "name": "time",
                "placeholder": "",
                "value": timeValue,
                "maxLen": "",
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "Duration",
                "type": "time",
                "name": "duration",
                "placeholder": "",
                "value": "02:00",
                "maxLen": "",
                "isRequired": True,
                "isReadOnly": False,
            },
        ]

        # Workshop Fields
        evenTypeFields["Workshop"] = [
            {
                "label": "Title",
                "type": "text",
                "name": "title",
                "placeholder": "Fixed Wing Workshop",
                "value": "",
                "maxLen": LIMITS["title"],
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "Description",
                "type": "textarea",
                "name": "description",
                "placeholder": "You'll learn how to bomb the shit out of...",
                "maxLen": LIMITS["description"],
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "External URL",
                "type": "text",
                "name": "externalURL",
                "placeholder": "https://example.com",
                "value": "",
                "maxLen": LIMITS["fieldValue"],
                "isRequired": False,
                "isReadOnly": False,
            },
            # Future upgrade: Make JavaScript add a new input text box when the previous one has text in. So one role per box
            {
                "label": "Reservable Roles",
                "type": "textarea",
                "name": "reservableRoles",
                "placeholder": "Actual\n2IC\nJTAC\nA-10C Pilot",
                "maxLen": LIMITS["fieldValue"],
                "isRequired": False,
                "isReadOnly": False,
            },
            {
                "label": "Map",
                "type": "select",
                "name": "map",
                "value": mapsValue,
                "isRequired": False,
                "isReadOnly": False,
            },
            {
                "label": "Attendees",
                "type": "select",
                "name": "attendees",
                "value": attendeesValue,
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "Time",
                "type": "datetime-local",
                "name": "time",
                "placeholder": "",
                "value": timeValue,
                "maxLen": "",
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "Duration",
                "type": "time",
                "name": "duration",
                "placeholder": "",
                "value": "02:00",
                "maxLen": "",
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "Workshop Interest Linking",
                "type": "select",
                "name": "workshopInterest",
                "value": [{"value": "NoWorkshop", "text": "No Workshop", "isSelected": True}] + [{"value": workshop, "text": workshop, "isSelected": False} for workshop in workshops],
                "isRequired": False,
                "isReadOnly": False,
            },
        ]

        # Event Fields
        evenTypeFields["Event"] = [
            {
                "label": "Title",
                "type": "text",
                "name": "title",
                "placeholder": "Purge Day",
                "value": "",
                "maxLen": LIMITS["title"],
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "Description",
                "type": "textarea",
                "name": "description",
                "placeholder": "S̸̲͝p̵̣̐ȯ̴̻ỏ̵̥̯k̸̮̩̐y̵̼̍͝ ̵̛̖̾t̶̩̹̏͂ì̴̳̼͠m̴̞̄͊͜ẽ̴͚͉",
                "maxLen": LIMITS["description"],
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "External URL",
                "type": "text",
                "name": "externalURL",
                "placeholder": "https://example.com",
                "value": "",
                "maxLen": LIMITS["fieldValue"],
                "isRequired": False,
                "isReadOnly": False,
            },
            # Future upgrade: Make JavaScript add a new input text box when the previous one has text in. So one role per box
            {
                "label": "Reservable Roles",
                "type": "textarea",
                "name": "reservableRoles",
                "placeholder": "Dead man\nFlying ghoul 1-1\nHumongous Moyai",
                "maxLen": LIMITS["fieldValue"],
                "isRequired": False,
                "isReadOnly": False,
            },
            {
                "label": "Map",
                "type": "select",
                "name": "map",
                "value": mapsValue,
                "isRequired": False,
                "isReadOnly": False,
            },
            {
                "label": "Attendees",
                "type": "select",
                "name": "attendees",
                "value": attendeesValue,
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "Time",
                "type": "datetime-local",
                "name": "time",
                "placeholder": "",
                "value": timeValue,
                "maxLen": "",
                "isRequired": True,
                "isReadOnly": False,
            },
            {
                "label": "Duration",
                "type": "time",
                "name": "duration",
                "placeholder": "",
                "value": "02:00",
                "maxLen": "",
                "isRequired": True,
                "isReadOnly": False,
            },
        ]



        # Fetch URL args
        args = request.args
        # Get crypto key
        with open(KEY_FILE, "rb") as keyFile:
            fern = Fernet(keyFile.read())

        # Fetch AuthorId
        authorIdEncoded = args.get("aide")  # AuthorIDEncoded (AIDE)
        if authorIdEncoded is None:
            sendToTemplate["authorId"] = 0
        else:
            try:
                # Get author id
                aide = fern.decrypt(authorIdEncoded.encode("utf-8"))
                sendToTemplate["authorId"] = int(aide)
            except Exception as e:  # User prob changed the arg - TODO redirect user to error page, tell em to execute /event again + when aide is None
                print(e)
                sendToTemplate["authorId"] = 0
        #print(f"AuthorId: {sendToTemplate['authorId']}")  # DEBUG


        editEncoded = args.get("edit")
        if editEncoded is not None:
            try:
                """ Example of edit :: ?edit=(messageId=123,eventType="ws") """
                edit = fern.decrypt(editEncoded.encode("utf-8")).decode("utf-8")
                #print(f"EDIT: {edit}")

                sendToTemplate["title"] = "Edit An Event"
                editStuff = {}
                eventType = "Operation"
                for item in edit.split("{/}"):  # TODO Make this another char instead / More secure
                    if item.startswith("eventType"):
                        eventType = item.split("=")[1]
                    else:
                        itemSplit = item.split("=")
                        editStuff[itemSplit[0]] = itemSplit[1]

                # Set select option Selected
                for commonField in evenTypeFields["Common"]:
                    if commonField["name"] == "eventType":
                        for option in commonField["value"]:
                            option["isSelected"] = (eventType == option["text"])
                        break


                # EventId
                sendToTemplate["eventId"] = editStuff.pop("eventId")  # Remove eventId and send it to template directly

                # Apply edit info to form (value)
                for dic in evenTypeFields[eventType]:
                    if dic["name"] in editStuff:

                        if dic["type"] == "textarea":
                            dic["placeholder"] = "JS_CHANGE_VALUE" + editStuff[dic["name"]]  # Textarea doesn't have value attr. Set it later with JS (identify it with pre-str)

                        elif dic["type"] == "select":
                            for option in dic["value"]:
                                if option["text"] == editStuff[dic["name"]]:
                                    option["isSelected"] = True

                        else:
                            dic["value"] = editStuff[dic["name"]]

                #print(editStuff)
            except Exception as e:
                print(e)
                ...  # Redirect to error page, refer to generate new link

        sendToTemplate["eventTypeFields"] = evenTypeFields.items()
        return render_template("event.html", sendToTemplate=sendToTemplate)


    """ === RECIEVEING FORM === """

    eventId = request.form.get("eventId")
    eventType = request.form.get("eventType", "Operation")
    durationStr = request.form.get("duration", "02:00")
    duration = time.fromisoformat(durationStr)
    duration = timedelta(hours=duration.hour, minutes=duration.minute)
    resRoles = {}
    for role in reservableRoles.split("\r\n") if (reservableRoles := request.form.get("reservableRoles")) is not None else []:
        resRoles[role] = None

    newEvent = {
        "authorId": int(request.form.get("authorId")),
        "type": eventType,  # Operation, Workshop, Event
        "title": request.form.get("title", "Event Title"),
        "description": request.form.get("description", "Event Description"),
        "externalURL": externalURL if (externalURL := request.form.get("externalURL")) != "" else None,
        "reservableRoles": resRoles,
        "map": request.form.get("map"),
        "maxPlayers": attendees if (attendees := request.form.get("attendees")) != "NoLimit" else None,
        #"time": (starttime := request.form.get("time", "2069-04-20T04:20")),
        #"endTime": (datetimeParse(starttime) + duration).strftime("%Y-%m-%dT%H:%M"),
        "time": "2022-12-14 09:00 AM",
        "endTime": "2022-12-14 12:00 PM",
        "duration": durationStr,
        "accepted": [],
        "declined": [],
        "tentative": [],
        "messageId": None
    }
    if eventType == "Workshop":
        newEvent["workshopInterest"] = workshopInterest if (workshopInterest := request.form.get("workshopInterest")) != "NoWorkshop" else None

    with open("data/events.json") as eventsFile:
        events = json.load(eventsFile)


    if eventId is None:  # Creating an event
        events.append(newEvent)
        with open("data/events.json", "w", encoding="utf-8") as eventsFile:
            json.dump(events, eventsFile, indent=4)

        #return "OK DEBUG - WITHOUT BOT"
        app.botClient.loop.create_task(updateSchedule())

        return "OK"

    else:  # Editing an event
        print(f"eventId: {eventId}")
        for event in events:
            if eventId == event["messageId"]:  # Finding the right event
                if events["time"] != newEvent["time"]:  # If time differs (this can be more intelligent to prevent resending schedule as often)
                    events.remove(event)
                    events.append(newEvent)
                    with open("data/events.json", "w", encoding="utf-8") as eventsFile:
                        json.dump(events, eventsFile, indent=4)

                else:
                    event.update(newEvent)  # Set updated values
                    with open("data/events.json", "w", encoding="utf-8") as eventsFile:
                        json.dump(events, eventsFile, indent=4)
                    app.botClient.loop.create_task(editMsg(SCHEDULE, eventId, getEventEmbed(newEvent)))
                break

        return "OK"


async def editMsg(channel: int, msgId: int, embed: Embed):
    await app.botClient.get_channel(channel).fetch_message(msgId).edit(embed=embed)

async def updateSchedule() -> None:
    """ Updates the schedule channel with all messages. """

    guild = app.botClient.get_guild(GUILD_ID)
    channel = guild.get_channel(SCHEDULE)

    await channel.purge(limit=None, check=lambda m: m.author.id in FRIENDLY_SNEKS)

    row = ScheduleView()
    row.timeout = None
    issueButton = ScheduleButton(row=0, emoji="📩", label="Create Ticket", style=discord.ButtonStyle.secondary, custom_id="issues_and_suggestions")
    row.add_item(item=issueButton)

    await channel.send(f"__Welcome to the schedule channel!__\nTo schedule an operation you can use the `/operation` command (or `/bop`) and follow the instructions in your DMs.\nFor a workshop use `/workshop` or `/ws`.\nLastly, for generic events use `/event`.\n\nIf you haven't set a preferred time zone yet you will be prompted to do so when you schedule any kind of event.\nIf you want to set, change or delete your time zone preference you may do so with the `/changetimezone` command.\n\nThe times you see on the schedule are based on __your local time zone__.\n\nThe event colors can be used to quickly identify what type of event it is:\n🟩 Operation `/operation` or `/bop`.\n🟦 Workshop `/workshop` or `/ws`.\n🟨 Event `/event`.\n\n**Github**: <https://github.com/Sigma-Security-Group/FriendlySnek> - Prod. hash `{commitHash}`.\n\nIf you have any suggestions for new features or encounter any bugs, please contact: {', '.join([f'**{channel.guild.get_member(name).display_name}**' for name in DEVELOPERS if channel.guild.get_member(name) is not None])} - or simply click the button below!", view=row)

    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE) as f:
                events = json.load(f)
            if len(events) == 0:
                await channel.send("...\nNo bop?\n...\nSnek is sad")
                await channel.send(":cry:")
                return

            newEvents: list[dict] = []
            for event in sorted(events, key=lambda e: datetime.strptime(e["time"], TIME_FORMAT_HTML), reverse=True):
                embed = getEventEmbed(event)

                row = ScheduleView()
                row.timeout = None
                buttons = []

                # Add attendance buttons if maxPlayers is not hidden
                if event["maxPlayers"] != "hidden":
                    buttons.extend([
                        ScheduleButton(row=0, label="Accept", style=discord.ButtonStyle.success, custom_id="accept"),
                        ScheduleButton(row=0, label="Decline", style=discord.ButtonStyle.danger, custom_id="decline"),
                        ScheduleButton(row=0, label="Decline (Time)", style=discord.ButtonStyle.danger, custom_id="declineForTiming"),
                        ScheduleButton(row=0, label="Tentative", style=discord.ButtonStyle.primary, custom_id="tentative")
                    ])
                    if event["reservableRoles"] is not None:
                        buttons.append(ScheduleButton(row=0, label="Reserve", style=discord.ButtonStyle.secondary, custom_id="reserve"))

                buttons.extend([
                    ScheduleButton(row=1, label="Edit", style=discord.ButtonStyle.secondary, custom_id="edit"),
                    ScheduleButton(row=1, label="Delete", style=discord.ButtonStyle.secondary, custom_id="delete")
                ])
                for button in buttons:
                    row.add_item(item=button)

                msg = await channel.send(embed=embed, view=row)
                event["messageId"] = msg.id
                newEvents.append(event)
            with open(EVENTS_FILE, "w") as f:
                json.dump(newEvents, f, indent=4)
        except Exception as e:
            log.exception(e)
    else:
        with open(EVENTS_FILE, "w") as f:
            json.dump([], f, indent=4)


def getEventEmbed(event: dict) -> Embed:
    """ Generates an embed from the given event.

    Parameters:
    event (dict): The event.

    Returns:
    Embed: The generated embed.
    """
    guild = app.botClient.get_guild(GUILD_ID)

    colors = {
        "Operation": Color.green(),
        "Workshop": Color.blue(),
        "Event": Color.gold()
    }
    embed = Embed(title=event["title"], description=event["description"], color=colors[event.get("type", "Operation")])

    if event["reservableRoles"] is not None:
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        embed.add_field(name=f"Reservable Roles ({len([role for role, memberId in event['reservableRoles'].items() if memberId is not None])}/{len(event['reservableRoles'])}) 👤", value="\n".join(f"{roleName} - {('*' + member.display_name + '*' if (member := guild.get_member(memberId)) is not None else '**VACANT**') if memberId is not None else '**VACANT**'}" for roleName, memberId in event["reservableRoles"].items()), inline=False)

    durationHours = int(event["duration"].split(":")[0])
    embed.add_field(name="\u200B", value="\u200B", inline=False)
    embed.add_field(name="Time", value=f"{utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT_HTML)), style='F')} - {utils.format_dt(UTC.localize(datetime.strptime(event['endTime'], TIME_FORMAT_HTML)), style='t' if durationHours < 24 else 'F')}", inline=(durationHours < 24))
    embed.add_field(name="Duration", value=event["duration"], inline=True)

    if event["map"] is not None:
        embed.add_field(name="Map", value=event["map"], inline=False)

    if event["externalURL"] is not None:
        embed.add_field(name="\u200B", value="\u200B", inline=False)
        embed.add_field(name="External URL", value=event["externalURL"], inline=False)
    embed.add_field(name="\u200B", value="\u200B", inline=False)

    accepted = [member.display_name for memberId in event["accepted"] if (member := guild.get_member(memberId)) is not None]
    standby = []
    if event["maxPlayers"] is not None and len(accepted) > event["maxPlayers"]:
        accepted, standby = accepted[:event["maxPlayers"]], accepted[event["maxPlayers"]:]
    declined = [member.display_name for memberId in event["declined"] if (member := guild.get_member(memberId)) is not None]
    tentative = [member.display_name for memberId in event["tentative"] if (member := guild.get_member(memberId)) is not None]

    if event["maxPlayers"] is None or (event["maxPlayers"] is not None and event["maxPlayers"] > 0):
        embed.add_field(name=f"Accepted ({len(accepted)}/{event['maxPlayers']}) ✅" if event["maxPlayers"] is not None else f"Accepted ({len(accepted)}) ✅", value="\n".join(name for name in accepted) if len(accepted) > 0 else "-", inline=True)
        embed.add_field(name=f"Declined ❌ ({len(declined)})", value=("\n".join("\n".join("❌ " + name for name in declined)) if len(declined) > 0 else "-"), inline=True)
        embed.add_field(name=f"Tentative ({len(tentative)}) ❓", value="\n".join(name for name in tentative) if len(tentative) > 0 else "-", inline=True)
        if len(standby) > 0:
            embed.add_field(name=f"Standby ({len(standby)}) :clock3:", value="\n".join(name for name in standby), inline=False)

    elif event["maxPlayers"] != "hidden":
        embed.add_field(name=f"Accepted ({len(accepted + standby)}) ✅", value="\u200B", inline=True)
        embed.add_field(name=f"Declined ❌ ({len(declined)})", value="\u200B", inline=True)
        embed.add_field(name=f"Tentative ({len(tentative)}) ❓", value="\u200B", inline=True)

    author = guild.get_member(event["authorId"])
    embed.set_footer(text=f"Created by {author.display_name}") if author else embed.set_footer(text="Created by Unknown User")
    embed.timestamp = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT_HTML))

    return embed


async def buttonHandling(self, message: discord.Message | None, button: discord.ui.Button, interaction: discord.Interaction) -> None:
    """ Handling all schedule button interactions.

    Parameters:
    message (None | discord.Message): If the message is provided, it's used along with some specific button action.
    button (discord.ui.Button): The Discord button.
    interaction (discord.Interaction): The Discord interaction.

    Returns:
    None.
    """

    try:
        if not interaction.user.dm_channel:
            await interaction.user.create_dm()

        with open(EVENTS_FILE) as f:
            events = json.load(f)

        scheduleNeedsUpdate = True
        originalMsgId = interaction.message.id
        fetchMsg = False
        event_: list[dict] = [event for event in events if event["messageId"] == interaction.message.id]
        if button.custom_id == "accept":
            event = event_[0]
            if interaction.user.id in event["declined"]:
                event["declined"].remove(interaction.user.id)
            if interaction.user.id in event["tentative"]:
                event["tentative"].remove(interaction.user.id)
            if interaction.user.id not in event["accepted"]:
                event["accepted"].append(interaction.user.id)

        elif button.custom_id == "decline":
            event = event_[0]
            if interaction.user.id in event["accepted"]:
                event["accepted"].remove(interaction.user.id)
            if interaction.user.id in event["tentative"]:
                event["tentative"].remove(interaction.user.id)
            if interaction.user.id not in event["declined"]:
                event["declined"].append(interaction.user.id)
            if event["reservableRoles"] is not None:
                for roleName in event["reservableRoles"]:
                    if event["reservableRoles"][roleName] == interaction.user.id:
                        event["reservableRoles"][roleName] = None

        elif button.custom_id == "declineForTiming":
            event = event_[0]
            if interaction.user.id in event["accepted"]:
                event["accepted"].remove(interaction.user.id)
            if interaction.user.id in event["tentative"]:
                event["tentative"].remove(interaction.user.id)
            if interaction.user.id in event["declined"]:
                event["declined"].remove(interaction.user.id)
            if event["reservableRoles"] is not None:
                for roleName in event["reservableRoles"]:
                    if event["reservableRoles"][roleName] == interaction.user.id:
                        event["reservableRoles"][roleName] = None

        elif button.custom_id == "tentative":
            event = event_[0]
            if interaction.user.id in event["accepted"]:
                event["accepted"].remove(interaction.user.id)
            if interaction.user.id in event["declined"]:
                event["declined"].remove(interaction.user.id)
            if interaction.user.id not in event["tentative"]:
                event["tentative"].append(interaction.user.id)
            if event["reservableRoles"] is not None:
                for roleName in event["reservableRoles"]:
                    if event["reservableRoles"][roleName] == interaction.user.id:
                        event["reservableRoles"][roleName] = None

        elif button.custom_id == "reserve":
            event = event_[0]
            await interaction.response.send_message(RESPONSE_GOTO_DMS.format(interaction.user.dm_channel.jump_url), ephemeral=True)
            reservingOutput = await self.reserveRole(interaction.user, event)
            if not reservingOutput:
                return
            fetchMsg = True

        elif button.custom_id == "edit":
            event = event_[0]
            if interaction.user.id == event["authorId"] or any(role.id == UNIT_STAFF or role.id == SERVER_HAMSTER for role in interaction.user.roles):
                await interaction.response.send_message(RESPONSE_GOTO_DMS.format(interaction.user.dm_channel.jump_url), ephemeral=True)
                reorderEvents = await self.editEvent(interaction.user, event, isTemplateEdit=False)
                if reorderEvents:
                    with open(EVENTS_FILE, "w") as f:
                        json.dump(events, f, indent=4)
                    await self.updateSchedule()
                    return
            else:
                await interaction.response.send_message(RESPONSE_UNALLOWED.format("edit"), ephemeral=True)
                return
            fetchMsg = True

        elif button.custom_id == "delete":
            event = event_[0]
            if interaction.user.id == event["authorId"] or any(role.id == UNIT_STAFF or role.id == SERVER_HAMSTER for role in interaction.user.roles):
                await interaction.response.send_message(RESPONSE_GOTO_DMS.format(interaction.user.dm_channel.jump_url), ephemeral=True)
                embed = Embed(title=SCHEDULE_EVENT_CONFIRM_DELETE.format(f"{event['type'].lower()}: `{event['title']}`"), color=Color.orange())
                deletePrompts = [discord.Message]
                row = ScheduleView(deletePrompts)
                row.timeout = TIME_ONE_MIN
                buttons = [
                    ScheduleButton(self, interaction.message, row=0, label="Delete", style=discord.ButtonStyle.success, custom_id="delete_event_confirm"),
                    ScheduleButton(self, interaction.message, row=0, label="Cancel", style=discord.ButtonStyle.danger, custom_id="delete_event_cancel"),
                ]
                for button in buttons:
                    row.add_item(item=button)
                message = await interaction.user.send(embed=embed, view=row)
                deletePrompts[0] = message
            else:
                await interaction.response.send_message(RESPONSE_UNALLOWED.format("delete"), ephemeral=True)
                return
            scheduleNeedsUpdate = False

        elif button.custom_id == "delete_event_confirm":
            scheduleNeedsUpdate = False
            for button in button.view.children:
                button.disabled = True
            await interaction.response.edit_message(view=button.view)
            event = [event for event in events if event["messageId"] == message.id][0]
            await message.delete()
            try:
                log.info(f"{interaction.user.display_name} ({interaction.user}) deleted the event: {event['title']}")
                await interaction.user.dm_channel.send(embed=Embed(title=f"✅ {event['type']} deleted!", color=Color.green()))

                utcNow = UTC.localize(datetime.utcnow())
                startTime = UTC.localize(datetime.strptime(event["time"], TIME_FORMAT_HTML))
                if event["maxPlayers"] != "anonymous" and utcNow > startTime + timedelta(minutes=30):
                    await self.saveEventToHistory(event)
                else:
                    guild = self.bot.get_guild(GUILD_ID)
                    for memberId in event["accepted"] + event.get("declinedForTiming", []) + event["tentative"]:
                        member = guild.get_member(memberId)
                        if member is not None:
                            embed = Embed(title=f"🗑 {event.get('type', 'Operation')} deleted: {event['title']}!", description=f"The {event.get('type', 'Operation').lower()} was scheduled to run:\n{utils.format_dt(UTC.localize(datetime.strptime(event['time'], TIME_FORMAT_HTML)), style='F')}", color=Color.red())
                            try:
                                await member.send(embed=embed)
                            except Exception as e:
                                log.warning(f"{member} | {e}")
            except Exception as e:
                log.exception(f"{interaction.user} | {e}")
            events.remove(event)

        elif button.custom_id == "delete_event_cancel":
            for button in button.view.children:
                button.disabled = True
            await interaction.response.edit_message(view=button.view)
            await self.cancelCommand(interaction.user.dm_channel, "Event deletion")
            return

        elif button.custom_id == "issues_and_suggestions":
            log.info(f"{interaction.user.display_name} ({interaction.user}) created a ticket!")
            try:
                scheduleNeedsUpdate = False
                await interaction.response.send_message(RESPONSE_GOTO_DMS.format(interaction.user.dm_channel.jump_url), ephemeral=True)
                embed = Embed(title="Ticket", description="Thank you for reaching out to us!\nPlease tell us what's on your mind in **one** message below!\nInclude screenshot(s) if suitable!", color=Color.orange())
                embed.set_footer(text=SCHEDULE_CANCEL)
                msg = await interaction.user.send(embed=embed)
                dmChannel = msg.channel
            except Exception as e:
                log.exception(f"{interaction.user} | {e}")
                return

            try:
                response = await self.bot.wait_for("message", timeout=TIME_TEN_MIN, check=lambda msg, author=interaction.user, dmChannel=dmChannel: msg.channel == dmChannel and msg.author == author)
                concern = response.content.strip()
                if concern.lower() == "cancel":
                    await self.cancelCommand(dmChannel, "Ticket")
                    return
            except asyncio.TimeoutError:
                await dmChannel.send(embed=TIMEOUT_EMBED)
                return

            try:
                embed = Embed(title="✅ Ticket sent", description="Thank you for contacting us!\nWe will respond as soon as possible.", color=Color.green())
                devs = [interaction.guild.get_member(developer) for developer in DEVELOPERS if interaction.guild.get_member(developer) is not None]
                embed.set_footer(text=f"Developers: {', '.join([dev.display_name for dev in devs])}")
                msg = await interaction.user.send(embed=embed)
            except Exception as e:
                log.exception(f"{interaction.user} | {e}")
                return

            try:
                embed = Embed(title="Incoming Ticket", description=f"Reporter: {interaction.user.mention} - {interaction.user}\n**Message:**\n{concern}", color=0xFF69B4, timestamp=datetime.now())
                embed.set_footer(text=f"Reporter ID: {interaction.user.id}")
                [await dev.send(embed=embed, files=([await attachment.to_file() for attachment in response.attachments] if len(response.attachments) > 0 else None)) for dev in devs]
            except Exception as e:
                log.exception(f"{interaction.user} | {e}")

        if scheduleNeedsUpdate:
            try:
                embed = self.getEventEmbed(event)
                if fetchMsg:  # Could be better - could be worse...
                    msg = await interaction.channel.fetch_message(originalMsgId)
                    await msg.edit(embed=embed)
                else:
                    await interaction.response.edit_message(embed=embed)
            except Exception as e:
                log.exception(f"{interaction.user} | {e}")

        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=4)
    except Exception as e:
        log.exception(f"{interaction.user} | {e}")


@app.route("/shutdown")
def shutdown():
    os.system("taskkill /f /im python.exe")
    return redirect("/event")

@app.route("/test")
def test():
    app.botClient.loop.create_task(updateSchedule())
    return redirect("/event")


class ScheduleView(discord.ui.View):
    def __init__(self, message: list[discord.Message] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message  # Message to reference when view has timeout

    async def on_timeout(self):
        try:
            for button in self.children:
                button.disabled = True
            message = self.message[0]
            await message.edit(view=self)
        except Exception as e:
            log.exception(e)


class ScheduleButton(discord.ui.Button):
    def __init__(self, message: discord.Message = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message

    async def callback(self, interaction: discord.Interaction):
        await buttonHandling(self.message, self, interaction)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
