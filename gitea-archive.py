#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import requests
import json
import sys
import os
import tqdm


def list_branches(
    session: requests.Session, url: str, user: str, repo: str
) -> List[str]:
    with session.get(f"{url}/repos/{user}/{repo}/branches") as r:
        r.raise_for_status()

        branches = json.loads(r.text)
        for branch in branches:
            yield branch["name"]


def list_repos(session: requests.Session, url: str, user: str) -> List[str]:
    with session.get(f"{url}/user/repos") as r:
        r.raise_for_status()

        repos = json.loads(r.text)
        for repo in repo:
            yield repo["name"]


def get_user(session: requests.Session, url: str) -> str:
    with session.get(f"{url}/user") as r:
        r.raise_for_status()

        user = json.loads(r.text)
        return user["login"]


def archive_branch(
    session: requests.Session, user: str, url: str, repo: str, branch: str, dest: str
) -> None:
    archive_file = f"{branch}.zip"
    with session.get(f"{url}/repos/{user}/archive/{archive_file}") as r:
        r.raise_for_status()
        with open(os.path.join(dest, repo, archive_file), "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def archive(url: str, token: str, dest: str) -> None:
    session = requests.Session()
    session.headers.update(
        {"Content-type": "application/json", "Authorization": f"token {token}"}
    )

    user = get_user(session, url)

    print("Archiving...")
    for repo in tqdm(list_repos(session, url, user)):
        for branch in list_branches(session, url, user, repo):
            archive_branch(session, url, user, repo, branch, dest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Downloads archives of all gitea repositories for a user."
    )
    parser.add_argument("--url", help="Gitea instance URL")
    parser.add_argument("--token", help="Gitea access token")
    parser.add_argument("--dest", help="Archive destination")

    args = parser.parse_args()
    archive(args.url, args.token, args.dest)
