#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import os
import shutil
import sys
import urllib.parse
from typing import Dict, List, Tuple

import requests

lock_file = "cache.lock"
cache_file = "cache.json"


def acquire_lock(dest: str) -> bool:
    lock_file_path = os.path.join(dest, lock_file)
    if os.path.exists(lock_file_path):
        return False
    open(lock_file_path, "w").close()
    return True


def break_lock(dest: str) -> None:
    lock_file_path = os.path.join(dest, lock_file)
    if os.path.exists(lock_file_path):
        os.remove(lock_file_path)


def read_cache(dest: str) -> Dict:
    try:
        with open(os.path.join(dest, cache_file), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def write_cache(cache: Dict, dest: str) -> None:
    with open(os.path.join(dest, cache_file), "w") as f:
        json.dump(cache, f, indent=4)


def archive_filename(branch: str) -> str:
    return f"{branch}.zip"


def archive_filepath(dest: str, repo: str, branch: str) -> str:
    return os.path.join(dest, repo, archive_filename(branch))


def list_branches(
    session: requests.Session, url: str, user: str, repo: str
) -> List[Tuple[str, str]]:
    with session.get(f"{url}/repos/{user}/{repo}/branches") as r:
        r.raise_for_status()
        branches = json.loads(r.text)
        return [(branch["name"], branch["commit"]["id"]) for branch in branches]


def list_repos(session: requests.Session, url: str, user: str) -> List[str]:
    with session.get(f"{url}/user/repos") as r:
        r.raise_for_status()
        repos = json.loads(r.text)
        return [repo["name"] for repo in repos]


def get_user(session: requests.Session, url: str) -> str:
    with session.get(f"{url}/user") as r:
        r.raise_for_status()
        user = json.loads(r.text)
        return user["login"]


def archive_branch(
    session: requests.Session, url: str, user: str, repo: str, branch: str, dest: str
) -> None:
    archive_file = archive_filename(branch)
    with session.get(f"{url}/repos/{user}/{repo}/archive/{archive_file}") as r:
        r.raise_for_status()
        archive_path = archive_filepath(dest, repo, branch)
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
        with open(archive_path, "wb") as f:
            shutil.copyfileobj(r.raw, f)


def archive(url_base: str, token: str, dest: str) -> None:
    url = urllib.parse.urljoin(url_base, "/api/v1")
    session = requests.Session()
    session.headers.update(
        {"Content-type": "application/json", "Authorization": f"token {token}"}
    )

    user = get_user(session, url)

    os.makedirs(args.dest, exist_ok=True)

    if not acquire_lock(dest):
        print(
            "Another archive job is running, aborting. "
            "If the previous job crashed, run with --break-locks",
            file=sys.stderr,
        )
        sys.exit(1)

    cache = read_cache(dest)

    if not cache.get(user):
        cache[user] = {}

    try:
        print("Getting repos for user")
        for repo in list_repos(session, url, user):
            if not cache[user].get(repo):
                cache[user][repo] = {}

            for branch, last_commit in list_branches(session, url, user, repo):
                print(f"Checking {user}/{repo}/{branch}")
                cached_commit = cache[user][repo].get(branch)
                archive_file = archive_filepath(dest, repo, branch)
                if cached_commit == last_commit and os.path.exists(archive_file):
                    print("-> Archive up to date")
                else:
                    print("-> Found new commits. Downloading...")
                    archive_branch(
                        session=session,
                        url=url,
                        user=user,
                        repo=repo,
                        branch=branch,
                        dest=dest,
                    )
                    cache[user][repo][branch] = last_commit
                    write_cache(cache, dest)
                    print(f"-> Downloaded to {archive_file}")
                print()

        break_lock(dest)
    except Exception as e:
        break_lock(dest)
        raise e


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Downloads archives of all gitea repositories for a user."
    )
    parser.add_argument("--url", help="Gitea instance URL", required=True)
    parser.add_argument("--token", help="Gitea access token", required=True)
    parser.add_argument("--dest", help="Archive destination", required=True)
    parser.add_argument("--break-locks", help="Break cache lock", action="store_true")

    args = parser.parse_args()

    if args.break_locks:
        break_lock(args.dest)

    try:
        archive(args.url, args.token, args.dest)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
