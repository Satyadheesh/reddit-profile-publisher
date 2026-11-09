"""Publish reviewed, factual SatyaDheesh profile updates through Reddit OAuth.

The default is dry-run.  A real submission requires --publish and explicit
credentials in the environment.  This module intentionally has no discovery,
commenting, voting, or browser-automation functionality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
STATE = ROOT / "state" / "post_log.json"
USER_AGENT = "SatyaDheeshProfilePublisher/0.1 (non-commercial civic-information publisher)"
VALID_STATUSES = {"live", "building", "vision"}


class ValidationError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_log() -> list[dict[str, Any]]:
    if not STATE.exists():
        return []
    return load_json(STATE).get("posts", [])


def save_log(posts: list[dict[str, Any]]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"posts": posts}, indent=2) + "\n", encoding="utf-8")


def content_hash(draft: dict[str, Any]) -> str:
    value = f"{draft['title']}\n{draft['body']}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_draft(draft: dict[str, Any], registry: dict[str, dict[str, str]]) -> None:
    required = {"id", "publish_on", "title", "body", "claims"}
    missing = required - set(draft)
    if missing:
        raise ValidationError(f"draft {draft.get('id', '<unknown>')} is missing {sorted(missing)}")
    if not draft["title"].strip() or not draft["body"].strip():
        raise ValidationError(f"draft {draft['id']} has blank text")
    if len(draft["title"]) > 300:
        raise ValidationError(f"draft {draft['id']} title is longer than 300 characters")
    if not isinstance(draft["claims"], list) or not draft["claims"]:
        raise ValidationError(f"draft {draft['id']} needs at least one approved claim")
    for claim in draft["claims"]:
        record = registry.get(claim)
        if not record:
            raise ValidationError(f"draft {draft['id']} references unknown claim {claim!r}")
        if record["status"] not in VALID_STATUSES:
            raise ValidationError(f"claim {claim!r} has invalid status")


def choose_draft(today: date, drafts: list[dict[str, Any]], log: list[dict[str, Any]]) -> dict[str, Any] | None:
    posted_ids = {entry["draft_id"] for entry in log}
    posted_hashes = {entry["content_hash"] for entry in log}
    if any(entry.get("published_on") == today.isoformat() for entry in log):
        return None
    for draft in sorted(drafts, key=lambda item: (item["publish_on"], item["id"])):
        if date.fromisoformat(draft["publish_on"]) <= today and draft["id"] not in posted_ids and content_hash(draft) not in posted_hashes:
            return draft
    return None


def oauth_token() -> str:
    required = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"missing required environment variables: {', '.join(missing)}")
    response = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(os.environ["REDDIT_CLIENT_ID"], os.environ["REDDIT_CLIENT_SECRET"]),
        data={"grant_type": "password", "username": os.environ["REDDIT_USERNAME"], "password": os.environ["REDDIT_PASSWORD"]},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Reddit OAuth response did not include an access token")
    return token


def submit(draft: dict[str, Any], token: str, username: str) -> str:
    # Profile posting must be explicitly approved for this app/account by Reddit.
    response = requests.post(
        "https://oauth.reddit.com/api/submit",
        headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
        data={"sr": f"u_{username}", "kind": "self", "title": draft["title"], "text": draft["body"], "sendreplies": "false", "api_type": "json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json().get("json", {})
    errors = payload.get("errors", [])
    if errors:
        raise RuntimeError(f"Reddit rejected the submission: {errors}")
    post_id = payload.get("data", {}).get("id")
    if not post_id:
        raise RuntimeError("Reddit submission response did not include a post ID")
    return str(post_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true", help="Submit the due draft to the official profile")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the due draft without network access")
    parser.add_argument("--date", dest="run_date", help="ISO date for a deterministic dry run (YYYY-MM-DD)")
    args = parser.parse_args()
    if args.publish and args.dry_run:
        raise SystemExit("Choose either --publish or --dry-run")

    capabilities = load_json(CONTENT / "capabilities.json")["capabilities"]
    registry = {item["id"]: item for item in capabilities}
    drafts = load_json(CONTENT / "drafts.json")["drafts"]
    for draft in drafts:
        validate_draft(draft, registry)

    log = load_log()
    today = date.fromisoformat(args.run_date) if args.run_date else date.today()
    draft = choose_draft(today, drafts, log)
    if not draft:
        print("No due, unposted draft. Nothing to do.")
        return 0

    print(f"Selected draft: {draft['id']}\nTitle: {draft['title']}\n\n{draft['body']}")
    if not args.publish:
        print("\nDry run complete; no Reddit request was made.")
        return 0

    username = os.environ.get("REDDIT_USERNAME", "")
    post_id = submit(draft, oauth_token(), username)
    log.append({
        "draft_id": draft["id"],
        "content_hash": content_hash(draft),
        "post_id": post_id,
        "published_on": today.isoformat(),
        "published_at": datetime.now(timezone.utc).isoformat(),
    })
    save_log(log)
    print(f"Published Reddit post {post_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
