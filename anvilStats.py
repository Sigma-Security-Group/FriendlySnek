import os
import json
import anvil.server

import secret

# EVENTS_STATS_FILE = "data/eventsStats.json"
EVENTS_HISTORY_FILE = "data/eventsHistory.json"
FULL_ACTIVITY_FILE = "data/fullActivityLog.json"
ACTIVITY_FILE = "data/activityLog.json"
MEMBERS_FILE = "data/members.json"

if __name__ == '__main__':
    anvil.server.connect(secret.anvilStatsUplinkKey)

# @anvil.server.callable
# def getStats():
#     with open(EVENTS_STATS_FILE) as f:
#         eventsStats = json.load(f)
#     return eventsStats

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

if __name__ == '__main__':
    anvil.server.wait_forever()