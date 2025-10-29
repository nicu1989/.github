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
Collect extended metrics across all repositories in eclipse-score
and write them into a Markdown report file.
"""

import os
import pathlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from github import Github

ORG = "eclipse-score"
OUTPUT_DIR = pathlib.Path("profile")
OUTPUT_FILE = OUTPUT_DIR / "metrics.md"

gh = Github(os.getenv("GITHUB_TOKEN"))
NOW = datetime.now(timezone.utc)

@dataclass
class RepoData:
    name: str
    description: str
    last_commit: Optional[str]
    open_issues: int
    open_prs: int
    bazel_version: str
    lint_config: str
    ci_setup: str
    test_coverage: str
    latest_release: Optional[str]
    stars: int
    forks: int

def file_exists(repo, path):
    try:
        repo.get_contents(path)
        return True
    except:
        return False


def detect_bazel_version(repo):
    try:
        content = repo.get_contents(".bazelversion").decoded_content.decode()
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            return line
    except Exception:
        pass

    pattern = re.compile(r'\b\d+\.\d+(?:\.\d+)?\b')
    for ws_name in ["WORKSPACE", "WORKSPACE.bzlmod"]:
        try:
            content = repo.get_contents(ws_name).decoded_content.decode()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("#"):
                    continue
                match = pattern.search(line)
                if match:
                    return match.group(0)
        except Exception:
            continue

    return "⚠️ missing"


def detect_lint_config(repo):
    for candidate in [".gitlint", ".editorconfig", ".pre-commit-config.yaml"]:
        if file_exists(repo, candidate):
            return "✅ yes"
    return "❌ no"

def detect_ci_setup(repo):
    for candidate in [".github/workflows", "Jenkinsfile"]:
        if file_exists(repo, candidate):
            return "✅ yes"
    return "❌ no"

def detect_test_coverage(repo):
    for candidate in ["coverage.yml", "coverage.xml", "pytest.ini", ".coveragerc"]:
        if file_exists(repo, candidate):
            return "✅ yes"
    return "❌ no"

def get_latest_release_date(repo):
    try:
        release = repo.get_latest_release()
        return release.published_at.date().isoformat()
    except:
        return None

def query_github_org_for_repo_data(gh: Github, org: str):
    repo_data_list = []
    user = gh.get_user(org)
    for repo in user.get_repos():
        description = repo.description or ""
        last_commit = repo.pushed_at.date().isoformat() if repo.pushed_at else None
        open_issues = repo.open_issues_count
        open_prs = repo.get_pulls(state="open").totalCount
        bazel_version = detect_bazel_version(repo)
        lint_config = detect_lint_config(repo)
        ci_setup = detect_ci_setup(repo)
        test_coverage = detect_test_coverage(repo)
        latest_release = get_latest_release_date(repo)
        stars = repo.stargazers_count
        forks = repo.forks_count

        repo_data_list.append(
            RepoData(
                name=repo.name,
                description=description.replace("|", "‖"),
                last_commit=last_commit,
                open_issues=open_issues,
                open_prs=open_prs,
                bazel_version=bazel_version,
                lint_config=lint_config,
                ci_setup=ci_setup,
                test_coverage=test_coverage,
                latest_release=latest_release,
                stars=stars,
                forks=forks,
            )
        )
    return repo_data_list

def render_markdown(repos):
    header = (
        f"# Cross-Repo Metrics Report\n\n"
        f"Generated on {NOW.isoformat()}\n\n"
        "| Repo |Last Commit | Issues | PRs | Bazel | Lint | CI | Test Coverage | Latest Release | Stars | Forks |\n"
        "|------|------------|--------|-----|-------|------|----|---------------|----------------|-------|-------|"
    )
    rows = []
    for r in sorted(repos, key=lambda x: x.name.lower()):
        rows.append(
            f"| [{r.name}](https://github.com/{ORG}/{r.name}) | {r.last_commit or '-'} | "
            f"{r.open_issues} | {r.open_prs} | {r.bazel_version} | {r.lint_config} | "
            f"{r.ci_setup} | {r.test_coverage} | {r.latest_release or '-'} | {r.stars} | {r.forks} |"
        )
    return "\n".join([header] + rows)

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    repos = query_github_org_for_repo_data(gh, ORG)
    md = render_markdown(repos)
    OUTPUT_FILE.write_text(md, encoding="utf-8")
    print(f"Wrote {len(repos)} repos to {OUTPUT_FILE}")
