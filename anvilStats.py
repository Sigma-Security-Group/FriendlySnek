import os
import json
from ftplib import FTP
import anvil.server
import anvil.users

import secret

EVENTS_HISTORY_FILE = "data/eventsHistory.json"
FULL_ACTIVITY_FILE = "data/fullActivityLog.json"
ACTIVITY_FILE = "data/activityLog.json"
MEMBERS_FILE = "data/members.json"

FTP_A3DS_FOLDER = "/144.48.106.194_2316/A3DS"

if __name__ == '__main__':
    anvil.server.connect(secret.anvilStatsUplinkKey)

@anvil.server.callable
def getStats():
    with open(EVENTS_HISTORY_FILE) as f:
        eventsHistory = json.load(f)
    stats = {}
    for event in eventsHistory:
      if event.get("type", "Operation") not in stats:
        stats[event.get("type", "Operation")] = []
      stats[event.get("type", "Operation")].append({
        "accepted": min(event["maxPlayers"], len("accepted")) if event["maxPlayers"] is not None else len(event["accepted"]),
        "standby": max(0, len("accepted") - event["maxPlayers"]) if event["maxPlayers"] is not None else 0,
        "declined": len(event["declined"]),
        "tentative": len(event["tentative"]),
        "maxPlayers": event["maxPlayers"],
        "reservableRoles": len(event["reservableRoles"]) if event["reservableRoles"] is not None else 0,
        "reservedRoles": len([role for role, member in event["reservableRoles"].items() if member is not None]) if event["reservableRoles"] is not None else 0,
        "map": event["map"],
        "time": event["time"],
        "duration": event["duration"],
        "autoDeleted": event["autoDeleted"]
      })
    return stats

@anvil.server.callable
def getEventsHistory():
    with open(EVENTS_HISTORY_FILE) as f:
        eventsHistory = json.load(f)
    return eventsHistory

@anvil.server.callable
def getDiscordActivity():
    with open(ACTIVITY_FILE) as f:
        activity = json.load(f)
    return activity

@anvil.server.callable
def getDiscordMembers():
    with open(MEMBERS_FILE) as f:
        members = json.load(f)
    return members

@anvil.server.callable
def getFullDiscordActivity():
    with open(FULL_ACTIVITY_FILE) as f:
        fullActivity = json.load(f)
    return fullActivity

@anvil.server.callable
def getSsgRep():
    user = anvil.users.get_user()
    if user is None or not user["Is_Staff"]:
        return None
    reports = []
    with FTP() as ftp:
        ftp.connect(host=secret.ftpHost, port=secret.ftpPort)
        ftp.login(user=secret.ftpUsername, passwd=secret.ftpPassword)
        ftp.cwd(FTP_A3DS_FOLDER)
        for filename in sorted(ftp.nlst()):
            if filename.endswith(".rpt"):
                ftp.retrlines(f"RETR {filename}", lambda l, r=reports: (r.append(l) if "SSG REP" in l else None))
    return sorted(reports, reverse=True)

if __name__ == '__main__':
    anvil.server.wait_forever()