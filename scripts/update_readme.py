#!/usr/bin/env python3
"""
Update the Status column (✅ / 🕓 / 💤) inside the block bounded by
<!-- REPO_STATUS_START --> … <!-- REPO_STATUS_END --> in profile/README.md.
"""

from datetime import datetime, timezone, timedelta
import os, pathlib, re
from github import Github

# ────────────────────────── configuration ──────────────────────────
ORG               = "eclipse-score"
DAYS_STALE        = int(os.getenv("DAYS_STALE", "30"))
DAYS_OBSOLETE     = int(os.getenv("DAYS_OBSOLETE", "180"))
TOKEN             = os.getenv("GITHUB_TOKEN")
MD_FILE           = pathlib.Path("profile/README.md")
START, END        = "<!-- REPO_STATUS_START -->", "<!-- REPO_STATUS_END -->"

# ────────────────────────── fetch repo data ─────────────────────────
now   = datetime.now(timezone.utc)
cut1  = now - timedelta(days=DAYS_STALE)
cut2  = now - timedelta(days=DAYS_OBSOLETE)

def classify(pushed_at):
    if pushed_at <= cut2:
        return "💤 obsolete"
    if pushed_at <= cut1:
        return "🕓 stale"
    return "✅ active"

gh = Github(TOKEN)
status_by_name = {
    repo.name.lower(): classify(repo.pushed_at)
    for repo in gh.get_organization(ORG).get_repos()
}

# ────────────────────────── regex helpers ──────────────────────────
row_rx = re.compile(
    r'^(?P<prefix>\|\s*\[(?P<name>[^\]]+)\]\([^)]+\)\s*\|\s*[^|]*?\s*\|\s*)'
    r'(?P<status>[^|]+?)'
    r'(?P<suffix>\s*\|)$',
    re.MULTILINE,
)

def update_row(m: re.Match) -> str:
    desired = status_by_name.get(m.group('name').lower(), m.group('status'))
    return f"{m.group('prefix').rstrip()} {desired}{m.group('suffix')}"

block_rx = re.compile(f"{START}[\\s\\S]*?{END}", re.MULTILINE)

def patch_block(block: str) -> str:
    return row_rx.sub(update_row, block)

# ────────────────────────── read-modify-write ───────────────────────
original = MD_FILE.read_text()
updated  = block_rx.sub(lambda m: patch_block(m.group(0)), original)

if updated != original:
    MD_FILE.write_text(updated)
    print("README updated.")
else:
    print("No update.")