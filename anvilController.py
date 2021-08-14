import os
import json
import anvil.server

import secret

if __name__ == "__main__":
    anvil.server.connect(secret.anvilUplinkKey)

ANVIL_CONTROLLER_FILE = "anvilController.json"

@anvil.server.callable
def isCommingSoonWall1Open():
    with open(ANVIL_CONTROLLER_FILE) as f:
        anvilController = json.load(f)
    return anvilController.get("isCommingSoonWall1Open", False)

@anvil.server.callable
def isCommingSoonWall2Open():
    with open(ANVIL_CONTROLLER_FILE) as f:
        anvilController = json.load(f)
    return anvilController.get("isCommingSoonWall2Open", False)

@anvil.server.callable
def openCommingSoonWall1():
    with open(ANVIL_CONTROLLER_FILE) as f:
        anvilController = json.load(f)
    anvilController["isCommingSoonWall1Open"] = True
    with open(ANVIL_CONTROLLER_FILE, "w") as f:
        json.dump(anvilController, f, indent=4)

@anvil.server.callable
def openCommingSoonWall2():
    with open(ANVIL_CONTROLLER_FILE) as f:
        anvilController = json.load(f)
    anvilController["isCommingSoonWall2Open"] = True
    with open(ANVIL_CONTROLLER_FILE, "w") as f:
        json.dump(anvilController, f, indent=4)

@anvil.server.callable
def closeCommingSoonWall1():
    with open(ANVIL_CONTROLLER_FILE) as f:
        anvilController = json.load(f)
    anvilController["isCommingSoonWall1Open"] = False
    with open(ANVIL_CONTROLLER_FILE, "w") as f:
        json.dump(anvilController, f, indent=4)

@anvil.server.callable
def closeCommingSoonWall2():
    with open(ANVIL_CONTROLLER_FILE) as f:
        anvilController = json.load(f)
    anvilController["isCommingSoonWall2Open"] = False
    with open(ANVIL_CONTROLLER_FILE, "w") as f:
        json.dump(anvilController, f, indent=4)

if __name__ == '__main__':
    if not os.path.exists(ANVIL_CONTROLLER_FILE):
        with open(ANVIL_CONTROLLER_FILE, "w") as f:
            json.dump({
                "isCommingSoonWall1Open": False,
                "isCommingSoonWall2Open": False
            }, f, indent=4)
    anvil.server.wait_forever()