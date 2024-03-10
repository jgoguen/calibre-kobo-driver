#!/usr/bin/env python3
# vim: ft=python:syntax=python:expandtab:autoindent:ts=4:sts=4

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile

from urllib.request import Request
from urllib.request import urlopen


CALIBRE_VERSION_RE = re.compile(r"^.+\(.+ ([\d\.]+)\)$")
CALIBRE_REMOTE_VERSION_RE = re.compile(r"^calibre\-([\d\.]+)[\.\-]")
PLATFORM = platform.system().lower()
REPO_DIR = os.path.realpath(sys.argv[0])
while REPO_DIR != os.path.realpath("/"):
    if os.path.isdir(os.path.join(REPO_DIR, ".git")) or os.path.isdir(
        os.path.join(REPO_DIR, ".hg")
    ):
        break
    REPO_DIR = os.path.dirname(REPO_DIR)
if REPO_DIR == os.path.realpath("/"):
    raise Exception("Could not find repository root")
if PLATFORM == "darwin":
    PKG_EXT = ".dmg"
else:
    ARCH = "x86_64" if platform.architecture()[0] == "64bit" else "i686"
    PKG_EXT = f"-{ARCH}.txz"


def extract_calibre_pkg(pkg_path: str) -> None:
    calibre_dir = os.path.join(REPO_DIR, "calibre-py3")
    if os.path.isdir(calibre_dir):
        shutil.rmtree(calibre_dir)
    os.makedirs(calibre_dir)
    print(f"Ready to extract to {calibre_dir}")

    if PLATFORM == "darwin":
        dmg_name = os.path.basename(pkg_path).rpartition(".")[0]
        cmd_list = [
            ["/usr/bin/hdiutil", "attach", pkg_path],
            [
                "/usr/bin/rsync",
                "--archive",
                "--partial",
                "--progress",
                "--delete",
                f"{os.path.join('/Volumes', dmg_name, 'calibre.app')}/",
                f"{calibre_dir}/",
            ],
            ["/usr/bin/hdiutil", "unmount", os.path.join("/Volumes", dmg_name)],
        ]
        for cmd in cmd_list:
            print(f"Running macOS extraction command: {cmd}")
            subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
    else:
        # Thanks Debian!
        tar_path = None
        paths = [
            "/usr/bin/tar",
            "/bin/tar",
        ]
        for p in paths:
            if os.path.exists(p):
                tar_path = p
                break
        if tar_path is None:
            raise RuntimeError("tar not found!")

        print("Extracting Linux calibre package")
        subprocess.run(
            [
                tar_path,
                "--extract",
                "--xz",
                "--file",
                pkg_path,
                "--directory",
                calibre_dir,
            ],
            stderr=sys.stderr,
            check=True,
        )


def get_calibre() -> None:
    # skipcq: BAN-B310
    api_resp = urlopen(
        "https://api.github.com/repos/kovidgoyal/calibre/releases/latest"
    )
    if api_resp.status != 200:
        raise Exception(
            f"Github API request returned HTTP{api_resp.status} {api_resp.reason}"
        )

    print(f"Got HTTP{api_resp.status} {api_resp.reason} from Github API")

    release_data = json.load(api_resp)
    print("Loaded Github release data")

    for asset in release_data["assets"]:
        if asset["name"].endswith(PKG_EXT):
            print(f"Found desired asset name: {asset['name']}")
            if asset["browser_download_url"].lower().startswith("http"):
                pkg_req = Request(asset["browser_download_url"])
            else:
                raise ValueError(
                    "Browser download URL does not begin with http/https: "
                    + asset["browser_download_url"]
                )

            with urlopen(pkg_req) as pkg_resp:
                if pkg_resp.status != 200:
                    raise Exception(
                        "Calibre download returned "
                        + f"HTTP{pkg_resp.status} {pkg_resp.reason}"
                    )

            with tempfile.TemporaryDirectory() as tmpdir:
                pkg_file = os.path.join(tmpdir, asset["name"])
                with open(pkg_file, "wb") as f:
                    f.write(pkg_resp.read())
                print(f"Downloaded calibre package {pkg_file}")
                extract_calibre_pkg(pkg_file)

            return None

    raise Exception("No calibre package could be found")


if __name__ == "__main__":
    get_calibre()
