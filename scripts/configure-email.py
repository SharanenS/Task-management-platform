"""Configure the approved Gmail sender using hidden terminal credential entry."""

import argparse
import getpass
import sys
import warnings

from email_delivery import SENDER, EmailConfigurationError, configure_gmail, delivery_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("gmail", "status"))
    args = parser.parse_args()
    if args.action == "status":
        mode = delivery_status()
        print("Delivery mode: " + mode + ".")
        if mode == "gmail":
            print(
                "Configured sender: "
                + SENDER
                + ". Actual inbox receipt must be verified separately."
            )
        return 0
    if not sys.stdin.isatty():
        raise EmailConfigurationError("interactive_terminal_required")
    print("Configure sender: " + SENDER)
    print("Enter its Google app password privately. Your normal Google password is not used.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass("Gmail app password (hidden): ")
    configure_gmail(password)
    print("Gmail authentication and realm configuration verified. No email was sent.")
    print(
        "Use the portal to send an activation email to a recipient you control, "
        "then verify receipt."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except EmailConfigurationError as error:
        print("Email setup failed: " + str(error) + ". Private details omitted.", file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Email setup failed; private details omitted.", file=sys.stderr)
        sys.exit(1)
