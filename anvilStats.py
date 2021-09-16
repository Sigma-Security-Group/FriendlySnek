import os
import json
import anvil.server

import secret

EVENTS_STATS_FILE = "data/eventsStats.json"
EVENTS_HISTORY_FILE = "data/eventsHistory.json"

if __name__ == '__main__':
    anvil.server.connect(secret.anvilStatsUplinkKey)

@anvil.server.callable
def getStats():
    with open(EVENTS_STATS_FILE) as f:
        eventsStats = json.load(f)
    return eventsStats

@anvil.server.callable
def getEventsHistory():
    with open(EVENTS_HISTORY_FILE) as f:
        eventsHistory = json.load(f)
    return eventsHistory

if __name__ == '__main__':
    if not os.path.exists(EVENTS_STATS_FILE):
        with open(EVENTS_STATS_FILE, "w") as f:
            json.dump({}, f, indent=4)
    anvil.server.wait_forever()