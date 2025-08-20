#!/usr/bin/env python3
"""
Update the Descriptions and Status column (✅ / 🕓 / 💤) in profile/README.md.
"""

import os
import pathlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from github import Github

ORG = "eclipse-score"
gh = Github(os.getenv("GITHUB_TOKEN"))
NOW = datetime.now(timezone.utc)


def calc_state(pushed_at: datetime) -> str:
    # TODO: use e.g. last 3 commits, instead of only one last commit

    # Note: 27 makes most sense at the time of writing, to exclude a global search & replace of license files
    DAYS_STALE = int(os.getenv("DAYS_STALE", "27"))
    DAYS_OBSOLETE = int(os.getenv("DAYS_OBSOLETE", "90"))

    cut1 = NOW - timedelta(days=DAYS_STALE)
    cut2 = NOW - timedelta(days=DAYS_OBSOLETE)

    if pushed_at <= cut2:
        return "💤 obsolete"
    if pushed_at <= cut1:
        return "🕓 stale"
    return "✅ active"


@dataclass
class RepoData:
    name: str
    description: str
    status: str


def query_github_org_for_repo_data(gh: Github, org: str):
    # TODO: pagination once we hit 100 repos
    return {
        repo.name: RepoData(
            name=repo.name,
            description=repo.description,
            status=calc_state(repo.pushed_at),
        )
        for repo in gh.get_organization(org).get_repos()
    }


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
