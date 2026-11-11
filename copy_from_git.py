#!/usr/bin/env python3
"""
reconstruct_history.py

Walks the full git history of a JSON data file, collects every record
that ever existed (including ones later deleted), deduplicates by
(timestamp, value), and writes a single consolidated output file.

Preserves top-level metadata fields (name, mac_address, data_types, etc.)
from the most recent commit.

Usage:
    python reconstruct_history.py \
        --repo   /path/to/your/repo \
        --file   data/logs.json \
        --output consolidated.json

Expected file structure:
    {
      "data": {
        "va_temperature":    [[timestamp, value], ...],
        "va_humidity":       [[timestamp, value], ...],
        "battery_percentage":[[timestamp, value], ...]
      },
      "data_types": { ... },   <- preserved from latest commit
      "name": "Bath",          <- preserved from latest commit
      "mac_address": ""        <- preserved from latest commit
    }
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


# ── git helpers ───────────────────────────────────────────────────────────────

def git(repo: Path, *args) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True
    )
    return result.stdout


def all_commits_for_file(repo: Path, file_path: str) -> list[str]:
    """All commit hashes that touched file_path, oldest first."""
    log = git(repo, "log", "--follow", "--format=%H", "--reverse", "--", file_path)
    return [h.strip() for h in log.splitlines() if h.strip()]


def file_at_commit(repo: Path, commit: str, file_path: str) -> dict | None:
    """Parsed JSON of file_path at a given commit, or None on error."""
    try:
        blob = git(repo, "show", f"{commit}:{file_path}")
        return json.loads(blob)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None

# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Reconstruct full Tuya history from git commits."
    )
    parser.add_argument("--repo",   required=True,
                        help="Path to the git repository root")
    parser.add_argument("--file",   required=True,
                        help="Relative path to the JSON file inside the repo "
                             "(e.g. data/Bath.json)")
    parser.add_argument("--output", default="consolidated.json",
                        help="Output file path (default: consolidated.json)")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not (repo / ".git").exists():
        print(f"Error: {repo} does not appear to be a git repository.", file=sys.stderr)
        sys.exit(1)



if __name__ == "__main__":
    from read_sensor import setupArgParser, loadSensorsFromJSON 
    args = setupArgParser().parse_args()
    devices = loadSensorsFromJSON(args.deviceJSON)
    from os import system

    tmp_folder = "/tmp/copy_device_log/"
    git_repo ="/home/user/TemperatureMonitoring/"
    system (f"mkdir -p {tmp_folder}")
    for device in devices:
        device.load_local_db(args.dbFolder)
        git_db = f"data_records/{device.name}.json"
        tmp_json = f"{tmp_folder}/{device.name}.json"
        for commit in all_commits_for_file(repo = git_repo,  
                                           file_path=git_db):
            with open(tmp_json, 'w') as f:
                json.dump(file_at_commit(repo = git_repo, 
                           commit = commit, 
                           file_path = git_db), f)
            device.load_local_db(tmp_folder)
    system (f"rm -r {tmp_folder}")
    
