import json
import anvil.server

import secret

EVENTS_STATS_FILE = "data/eventsStats.json"

if __name__ == '__main__':
    anvil.server.connect(secret.anvilStatsUplinkKey)

@anvil.server.callable
def getStats():
    with open(EVENTS_STATS_FILE) as f:
        eventsStats = json.load(f)
    return eventsStats

if __name__ == '__main__':
    if not os.path.exists(EVENTS_STATS_FILE):
        with open(EVENTS_STATS_FILE, "w") as f:
            json.dump({}, f, indent=4)
    anvil.server.wait_forever()