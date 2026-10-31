'''
Commands to run in the server, for what can't be done from the web:

    python3 -m web.manage invite <folder> <first name> "<club>" [--admin]
    python3 -m web.manage device <folder> "<club>"   (invitation for a new device)
    python3 -m web.manage reset <folder> "<club>"    (forgets all its devices)
'''
import argparse
from pathlib import Path

from web.accounts import Accounts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["invite", "device", "reset"])
    parser.add_argument("folder")
    parser.add_argument("args", nargs="+")
    parser.add_argument("--admin", action="store_true")
    parser.add_argument("--url", default="https://raulillo82.duckdns.org/elo")
    options = parser.parse_args()
    accounts = Accounts(Path(options.folder) / "accounts.db")
    if options.command == "invite":
        name, club = options.args
        token = accounts.create_invite(name, club, options.admin)
    else:
        club = options.args[0]
        user = next(user for user in accounts.list_users() if user["club"] == club)
        if options.command == "reset":
            accounts.remove_devices(user["id"])
            print("Dispositivos borrados")
            return
        token = accounts.create_invite(user_id=user["id"])
    print(f"{options.url}/invite/{token}")


if __name__ == "__main__":
    main()
