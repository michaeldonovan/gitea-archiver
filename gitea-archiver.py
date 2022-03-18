#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import requests
import json
import sys
import os
from typing import List, Dict, Optional
import urllib

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


def list_branches(
    session: requests.Session, url: str, user: str, repo: str
) -> Optional[List[str]]:
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
    archive_file = f"{branch}.zip"
    with session.get(f"{url}/repos/{user}/{repo}/archive/{archive_file}") as r:
        r.raise_for_status()
        os.makedirs(os.path.join(dest, repo), exist_ok=True)
        with open(os.path.join(dest, repo, archive_file), "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def archive(url_base: str, token: str, dest: str) -> None:
    url = urllib.parse.urljoin(url_base, "/api/v1")
    session = requests.Session()
    session.headers.update(
        {"Content-type": "application/json", "Authorization": f"token {token}"}
    )

    user = get_user(session, url)

    if not acquire_lock(dest):
        print(
            "Another archive job is running, aborting. If the previous job crashed, run with --break-locks",
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
                print(f"Checking {user}/{repo}/{branch}... ", end="")
                cached_commit = cache[user][repo].get(branch)
                if cached_commit == last_commit:
                    print("cache up to date")
                else:
                    print("found new commits")
                    archive_branch(session, url, user, repo, branch, dest)
                    cache[user][repo][branch] = last_commit
                    write_cache(cache, dest)

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

    archive(args.url, args.token, args.dest)
