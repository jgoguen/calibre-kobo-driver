#!/usr/bin/env python3

import os
import subprocess


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATIONS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "translations")


def main() -> None:
    with open(os.path.expanduser("~/.transifexrc"), "w") as f:
        f.write(
            f"""[https://www.transifex.com]
api_hostname = https://api.transifex.com
hostname = https://www.transifex.com
password = {os.environ['TX_API_KEY']}
username = api
"""
        )

    tx_dir = os.path.join(TRANSLATIONS_DIR, ".tx")
    os.makedirs(tx_dir, mode=0o700, exist_ok=False)
    with open(os.path.join(tx_dir, "config"), "w") as f:
        f.write(
            """[main]
host = https://www.transifex.com

[calibre-kobo-driver.all]
file_filter = <lang>.po
source_file = messages.pot
source_lang = en_CA
type = PO
            """
        )

    cmd = ["tx", "--traceback", "--root", TRANSLATIONS_DIR, "push", "-s"]
    subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
