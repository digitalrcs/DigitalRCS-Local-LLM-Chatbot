"""Set the address shown to LAN clients without changing bridge networking."""
import argparse
import json
import os
import sys

from settings import CONFIG, load_settings, save_public_bridge_url


def show(settings):
    print("Advertised bridge address: " + (settings["public_bridge_url"] or "Not set"))
    print("LM Studio address (from the bridge PC): " + settings["lm_studio_url"])
    print("The bridge listens on port 8766. This setting only changes the address displayed to users.")
    if "BRIDGE_PUBLIC_URL" in os.environ:
        print("BRIDGE_PUBLIC_URL overrides the saved advertised address for this process.")


def main(argv=None, path=CONFIG):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--show", action="store_true", help="Show the current effective address")
    action.add_argument("--url", help="Save http://SERVER-ADDRESS:8766 as the LAN address")
    action.add_argument("--clear", action="store_true", help="Clear the saved advertised address")
    args = parser.parse_args(argv)
    try:
        if not path.exists():
            print("Run START-HERE to configure the bridge before setting its LAN address.")
            return 1
        settings = load_settings(path)
        show(settings)
        if args.show:
            return 0
        value = "" if args.clear else args.url
        if value is None:
            print("Use the bridge server's home-network address, for example http://SERVER-ADDRESS:8766.")
            value = input("Bridge LAN address (blank keeps the current setting): ").strip()
            if not value:
                print("Address unchanged.")
                return 0
        saved = save_public_bridge_url(value, path)
        print("Saved advertised address: " + (saved or "Not set"))
        if "BRIDGE_PUBLIC_URL" in os.environ:
            print("The BRIDGE_PUBLIC_URL environment override still takes precedence.")
        print("Restart START-FRANKY to update the website. Update the robot's voice bridge address separately.")
        return 0
    except (ValueError, OSError) as exc:
        if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
            print(str(exc))
        else:
            print("Could not read or save bridge settings. Check the local config file and folder permissions.")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nAddress change cancelled.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
