#!/usr/bin/env python3
# vim: ft=python:syntax=python:expandtab:autoindent:ts=4:sts=4

import argparse
import concurrent.futures
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile

from multiprocessing import Lock
from urllib.request import urlopen


CALIBRE_VERSION_RE = re.compile(r"^.+\(.+ ([\d\.]+)\)$")
CALIBRE_REMOTE_VERSION_RE = re.compile(r"^calibre\-([\d\.]+)[\.\-]")
PLATFORM = platform.system().lower()
REPO_DIR = os.path.realpath(sys.argv[0])
LOG_LOCK = Lock()
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


def log(msg: str) -> None:
    global LOG_LOCK
    with LOG_LOCK:
        print(msg)


def extract_calibre_pkg(pkg_path: str, py_ver: int = 3) -> None:
    calibre_dir = os.path.join(REPO_DIR, f"calibre-py{py_ver}")
    if os.path.isdir(calibre_dir):
        shutil.rmtree(calibre_dir)
    os.makedirs(calibre_dir)
    log(f"Ready to extract to {calibre_dir}")

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
            log(f"Running macOS extraction command: {cmd}")
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        log("Extracting Linux calibre package")
        subprocess.run(
            [
                tar_path,
                "--extract",
                "--xz",
                "--file",
                pkg_path,
                "--directory",
                calibre_dir,
            ]
        )


def get_calibre_py3() -> None:
    api_resp = urlopen(
        "https://api.github.com/repos/kovidgoyal/calibre/releases/latest"
    )
    if api_resp.status != 200:
        raise Exception(
            f"Github API request returned HTTP{api_resp.status} {api_resp.reason}"
        )

    log(f"Got HTTP{api_resp.status} {api_resp.reason} from Github API")

    release_data = json.load(api_resp)
    log("Loaded Github release data")

    for asset in release_data["assets"]:
        if asset["name"].endswith(PKG_EXT):
            log(f"Found desired asset name: {asset['name']}")
            pkg_resp = urlopen(asset["browser_download_url"])
            if pkg_resp.status != 200:
                raise Exception(
                    "Calibre-Py3 download returned "
                    f"HTTP{pkg_resp.status} {pkg_resp.reason}"
                )

            with tempfile.TemporaryDirectory() as tmpdir:
                pkg_file = os.path.join(tmpdir, asset["name"])
                with open(pkg_file, "wb") as f:
                    f.write(pkg_resp.read())
                log(f"Downloaded calibre package {pkg_file}")
                extract_calibre_pkg(pkg_file, 3)

            return None

    raise Exception("No calibre-py3 package could be found")


def get_calibre_py2() -> None:
    calibre_pkg = "https://download.calibre-ebook.com/4.23.0/calibre-4.23.0"
    if PLATFORM == "darwin":
        calibre_pkg += ".dmg"
    else:
        calibre_pkg += "-x86_64.txz"
    pkg_resp = urlopen(calibre_pkg)
    if pkg_resp.status != 200:
        raise Exception(
            "Calibre-py2 package request returned "
            f"HTTP{pkg_resp.status} {pkg_resp.reason}"
        )

    pkg_file_name = os.path.basename(calibre_pkg)
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_file = os.path.join(tmpdir, pkg_file_name)
        with open(pkg_file, "wb") as f:
            f.write(pkg_resp.read())
        log(f"Downloaded calibre-py2 package {pkg_file}")
        extract_calibre_pkg(pkg_file, 2)

        return None

    raise Exception("No calibre-py2 package could be found")


def main(opts: argparse.Namespace) -> None:
    fetch_py2 = fetch_py3 = False

    if opts.version is None:
        fetch_py2 = fetch_py3 = True
    elif opts.version == "2.7" or opts.version == "2":
        fetch_py2 = True
    elif opts.version.startswith("3.") or opts.version == "3":
        fetch_py3 = True
    else:
        raise ValueError(f"Invalid Python version: {opts.version}")

    with concurrent.futures.ProcessPoolExecutor() as pool:
        if fetch_py2:
            log("Adding executor for get_calibre_py2")
            pool.submit(get_calibre_py2)

        if fetch_py3:
            log("Adding executor for get_calibre_py3")
            pool.submit(get_calibre_py3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "version",
        type=str,
        default=None,
        nargs="?",
        help="A single Python version to target (default: both 2.7 and 3.x)",
    )
    opts = parser.parse_args()
    main(opts)
