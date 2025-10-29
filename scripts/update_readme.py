# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************

#!/usr/bin/env python3
"""
Update the Descriptions and Status column (✅ / 🕓 / 💤) in profile/README.md.
"""

import os
import pathlib
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from github import Github

ORG = "eclipse-score"
gh = Github(os.getenv("GITHUB_TOKEN"))
NOW = datetime.now(timezone.utc)


def calc_state(pushed_at: datetime) -> str:
    # TODO: use e.g. last 3 commits, instead of only one last commit

    DAYS_STALE = 30
    DAYS_OBSOLETE = 90

    cut1 = NOW - timedelta(days=DAYS_STALE)
    cut2 = NOW - timedelta(days=DAYS_OBSOLETE)

    if pushed_at <= cut2:
        return "💤 obsolete"
    if pushed_at <= cut1:
        return "🕓 stale"
    return "✅ active"


def get_last_commit(repo):
    import requests

    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"}

    query = """
    query($owner: String!, $name: String!, $branchCount: Int!) {
      repository(owner: $owner, name: $name) {
        refs(refPrefix: "refs/heads/", first: $branchCount, orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
          nodes {
            name
            target {
              ... on Commit {
                committedDate
                author {
                  user {
                    login
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    variables = {
        "owner": repo.owner.login,
        "name": repo.name,
        "branchCount": 100
    }

    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
    )
    if response.status_code != 200:
        print(f"⚠️ GraphQL request failed for {repo.name}: {response.status_code} {response.text}")
        return None

    data = response.json()
    if "errors" in data:
        print(f"⚠️ GraphQL error for {repo.name}: {data['errors']}")
        return None

    branches = data.get("data", {}).get("repository", {}).get("refs", {}).get("nodes", [])
    latest = None

    for branch in branches:
        commit = branch.get("target")
        if not commit:
            continue
        author = commit.get("author", {}).get("user")
        if not author:
            continue
        login = author.get("login", "").lower()
        if login.endswith("[bot]") or "bot" in login:
            continue
        dt = datetime.fromisoformat(commit["committedDate"].replace("Z", "+00:00"))
        if latest is None or dt > latest:
            latest = dt

    return latest


@dataclass
class RepoData:
    name: str
    description: str
    status: str


def query_github_org_for_repo_data(gh: Github, org: str):
    # TODO: pagination once we hit 100 repos
    repos = gh.get_organization(org).get_repos()
    data = {}

    for repo in repos:
        print(f"🔍 Checking {repo.name} ...")
        last_commit = get_last_commit(repo)
        if last_commit:
            status = calc_state(last_commit)
        else:
            status = "💤 obsolete"

        data[repo.name] = RepoData(
            name=repo.name,
            description=repo.description or "(no description)",
            status=status,
        )
        time.sleep(1)  # small sleep to avoid hitting rate limits
    return data



def update_line(line: str, repo_data: dict[str, RepoData]) -> str:
    # Change lines starting with "| [repo]"
    m = re.match(r"^\| \[(.*)\]", line)
    if not m:
        return line

    repo: str = m.group(1)
    data = repo_data.pop(repo)

    return f"| [{repo}](https://github.com/eclipse-score/{repo}) | {data.description} | {data.status} |"


def update_readme(original: str, repo_data: dict[str, RepoData]) -> str:
    # Apply update_line to each line
    return "\n".join(
        map(lambda line: update_line(line, repo_data), original.splitlines())
    )


if __name__ == "__main__":
    repo_data = query_github_org_for_repo_data(gh, ORG)

    MD_FILE = pathlib.Path("profile/README.md")

    original = MD_FILE.read_text()
    updated = update_readme(original, repo_data)

    for repo in repo_data:
        print(
            f"Missing repo: {repo} - {repo_data[repo].description} ({repo_data[repo].status})"
        )

    if updated != original:
        _ = MD_FILE.write_text(updated)
        print("README updated.")
    else:
        print("No update.")
