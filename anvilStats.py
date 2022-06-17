import json
import pysftp
import anvil.server
import anvil.users

import secret

EVENTS_HISTORY_FILE = "data/eventsHistory.json"

FTP_A3DS_FOLDER = "/144.48.106.194_2316/A3DS"

if __name__ == "__main__":
    anvil.server.connect(secret.ANVIL_STATS_UPLINK_KEY)

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
def getSsgRep(numLogs=2):
    user = anvil.users.get_user()
    if user is None or not user["Is_Staff"]:
        return None
    files = []
    reports = []
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None
    with pysftp.Connection("euc-ogs7.armahosts.com", port=8822, username=secret.FTP_USERNAME, password=secret.FTP_PASSWORD, cnopts=cnopts, default_path="/euc-ogs7.armahosts.com_2482/mpmissions") as sftp:
        for filename in sftp.listdir():
            if filename.endswith(".rpt"):
                files.append(filename)
        for filename in sorted(files, reverse=True)[:numLogs]:
            sftp.get_d(filename, "./tmp/")
            with open(f"./tmp/{filename}") as f:
                for l in f.readlines():
                    if "SSG REP" in l and "SSG REP JIP Exec added" not in l and "SSG REP Added " not in l:
                        reports.append(l)

    return sorted(reports, reverse=True)

if __name__ == "__main__":
    anvil.server.wait_forever()
