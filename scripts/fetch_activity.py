#!/usr/bin/env python3
"""Fetch a small public-only activity feed without assuming full event payloads."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER = "WizardLoop"
PUBLIC_URL = f"https://api.github.com/users/{USER}/events/public"
ALLOWED = {"PushEvent", "IssuesEvent", "PullRequestEvent", "PullRequestReviewEvent", "ReleaseEvent"}


def event_record(event: dict) -> dict | None:
    """Reduced GitHub event payloads often omit authors, commits, or PR details."""
    if event.get("public") is not True:
        return None
    actor = (event.get("actor") or {}).get("login", "")
    if actor.lower() != USER.lower() or actor.lower().endswith("[bot]"):
        return None
    repo = (event.get("repo") or {}).get("name", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        return None
    if repo.lower() == f"{USER}/{USER}".lower():
        return None
    kind = event.get("type")
    if kind not in ALLOWED:
        return None
    payload = event.get("payload") or {}
    action = payload.get("action", "")
    url = f"https://github.com/{repo}"
    if kind == "PushEvent":
        text = f"Pushed updates to {repo}"
    elif kind == "IssuesEvent":
        if action not in {"opened", "closed", "reopened"}:
            return None
        number = (payload.get("issue") or {}).get("number")
        text = f"{action.capitalize()} issue" + (f" #{number}" if isinstance(number, int) else "") + f" in {repo}"
        if isinstance(number, int):
            url += f"/issues/{number}"
    elif kind == "PullRequestEvent":
        if action not in {"opened", "closed", "reopened", "synchronize"}:
            return None
        pr = payload.get("pull_request") or {}
        number = payload.get("number", pr.get("number"))
        verb = "Merged" if action == "closed" and pr.get("merged") else {"synchronize": "Updated"}.get(action, action.capitalize())
        text = f"{verb} pull request" + (f" #{number}" if isinstance(number, int) else "") + f" in {repo}"
        if isinstance(number, int):
            url += f"/pull/{number}"
    elif kind == "PullRequestReviewEvent":
        number = (payload.get("pull_request") or {}).get("number")
        text = "Reviewed a pull request" + (f" #{number}" if isinstance(number, int) else "") + f" in {repo}"
        if isinstance(number, int):
            url += f"/pull/{number}"
    else:
        if action != "published":
            return None
        release = payload.get("release") or {}
        tag = str(release.get("tag_name", ""))[:100]
        text = "Published a release" + (f" ({tag})" if tag else "") + f" in {repo}"
        url += "/releases"
    date = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("GitHub event date has no timezone")
    return {"date": date.astimezone(timezone.utc).strftime("%Y-%m-%d"), "text": text, "url": url}


def collect_events(fetch_page, now: datetime) -> list[dict]:
    cutoff = now - timedelta(days=90)
    records = []
    seen = set()
    for page in range(1, 4):
        events = fetch_page(page)
        if not isinstance(events, list):
            raise ValueError("GitHub Events API did not return a list")
        for event in events:
            if not isinstance(event, dict):
                raise ValueError("GitHub Events API returned a malformed event")
            record = event_record(event)
            if record is None:
                continue
            date = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
            if date < cutoff or date > now + timedelta(minutes=5):
                continue
            key = event.get("id") or (record["date"], record["text"])
            if key not in seen:
                records.append(record)
                seen.add(key)
            if len(records) == 3:
                return records
        if len(events) < 100:
            break
    return records


def fetch_page(page: int) -> list:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to fetch public activity")
    request = Request(
        f"{PUBLIC_URL}?per_page=100&page={page}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "WizardLoop-profile-metrics",
        },
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise RuntimeError(f"Public activity request failed (HTTP {error.code}); old assets are retained") from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("Public activity request failed; old assets are retained") from None
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError("Public activity request did not complete")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records = collect_events(fetch_page, datetime.now(timezone.utc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Fetched {len(records)} qualifying public activity events.")


if __name__ == "__main__":
    main()
