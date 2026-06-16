#!/usr/bin/env python3
"""
Updates the README's "Latest Projects" and "Recent Contributions" sections.

- Latest Projects: the user's most recently pushed public repos (own, non-fork),
  excluding the pinned/featured ones.
- Recent Contributions: the user's most recent public pull requests opened on
  repositories owned by someone else, excluding the already-featured contribution.

Runs in GitHub Actions with the built-in GITHUB_TOKEN (read-only public access
is enough). No extra secrets required.
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error

USERNAME = os.environ.get("USERNAME", "Man-ishu678")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
README_PATH = os.environ.get("README_PATH", "README.md")

# Featured items already shown statically — keep them out of the auto lists.
FEATURED_REPOS = {"standloop", "ai-dental-appointment-agent", "resume-rag-recruiter-ai"}
FEATURED_CONTRIBUTIONS = {"lm-evaluation-harness"}

MAX_PROJECTS = 5
MAX_CONTRIBUTIONS = 5

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": f"{USERNAME}-profile-readme-bot",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} for {url}: {e.read().decode()[:300]}", file=sys.stderr)
        return None
    except Exception as e:  # noqa: BLE001
        print(f"Error for {url}: {e}", file=sys.stderr)
        return None


def fmt_date(iso):
    return iso.split("T")[0] if iso else ""


def build_latest_projects():
    repos = get(f"{API}/users/{USERNAME}/repos?sort=pushed&per_page=100&type=owner")
    if not repos:
        return "_Could not load latest projects right now._"

    rows = []
    for r in repos:
        name = r.get("name", "")
        if r.get("fork") or r.get("archived") or r.get("private"):
            continue
        if name.lower() in FEATURED_REPOS:
            continue
        if name == USERNAME:  # the profile repo itself
            continue
        desc = (r.get("description") or "—").strip()
        lang = r.get("language") or ""
        lang_badge = f" `{lang}`" if lang else ""
        rows.append(
            f"- **[{name}]({r['html_url']})**{lang_badge} — {desc} "
            f"<sub>updated {fmt_date(r.get('pushed_at'))}</sub>"
        )
        if len(rows) >= MAX_PROJECTS:
            break

    return "\n".join(rows) if rows else "_No other public projects yet._"


def build_recent_contributions():
    # Recent PRs authored by the user, newest first, across all of GitHub.
    url = (
        f"{API}/search/issues?q=author:{USERNAME}+type:pr"
        f"&sort=created&order=desc&per_page=50"
    )
    data = get(url)
    if not data or "items" not in data:
        return "_Could not load recent contributions right now._"

    seen = set()
    rows = []
    for pr in data["items"]:
        repo_url = pr.get("repository_url", "")  # .../repos/{owner}/{repo}
        parts = repo_url.rstrip("/").split("/")
        if len(parts) < 2:
            continue
        owner, repo = parts[-2], parts[-1]
        # Only contributions to repos owned by someone else.
        if owner.lower() == USERNAME.lower():
            continue
        if repo.lower() in FEATURED_CONTRIBUTIONS:
            continue
        key = f"{owner}/{repo}"
        if key in seen:
            continue
        seen.add(key)
        state = pr.get("state", "open")
        emoji = "✅" if pr.get("pull_request", {}).get("merged_at") else (
            "🔀" if state == "open" else "📦"
        )
        rows.append(
            f"- {emoji} **[{key}](https://github.com/{key})** — "
            f"[{pr.get('title', 'PR').strip()}]({pr.get('html_url')}) "
            f"<sub>{fmt_date(pr.get('created_at'))}</sub>"
        )
        if len(rows) >= MAX_CONTRIBUTIONS:
            break

    return "\n".join(rows) if rows else "_No external contributions yet._"


def replace_section(content, name, new_block):
    start = f"<!--START_SECTION:{name}-->"
    end = f"<!--END_SECTION:{name}-->"
    pattern = re.compile(
        re.escape(start) + r".*?" + re.escape(end), re.DOTALL
    )
    replacement = f"{start}\n{new_block}\n{end}"
    if not pattern.search(content):
        print(f"WARNING: markers for '{name}' not found", file=sys.stderr)
        return content
    return pattern.sub(replacement, content)


def main():
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    content = replace_section(content, "latest-projects", build_latest_projects())
    content = replace_section(content, "recent-contributions", build_recent_contributions())

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("README updated.")


if __name__ == "__main__":
    main()
