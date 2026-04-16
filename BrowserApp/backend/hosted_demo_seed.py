"""
Seed demo leagues on the hosted API by calling real endpoints.

Usage:
    python hosted_demo_seed.py [--api https://rstrating-accounts-api.onrender.com]

Flow:
1. Log in as demo01  -> create leagues  -> create multi-use invites
2. Log in as demo02..demo10 -> accept both invites
"""

import argparse
import sys
import urllib.request
import urllib.error
import json
from typing import Any

DEFAULT_API = "https://rstrating-accounts-api.onrender.com"
OWNER = "demo01"
MEMBERS = [f"demo{i:02d}" for i in range(2, 11)]
PASSWORD = "demo1234"

LEAGUES = [
    {
        "name": "RST Friday League",
        "football_type": "outdoor",
        "goal_size": "large",
        "region": "Ljubljana",
        "description": "Weekly outdoor Friday sessions. All demo players welcome.",
    },
    {
        "name": "RST Indoor Cup",
        "football_type": "indoor",
        "goal_size": "small",
        "region": "Maribor",
        "description": "Indoor mini football. Fast-paced, competitive, great fun.",
    },
]


def call(api: str, path: str, method: str = "GET", body: dict | None = None, token: str | None = None) -> Any:
    url = api.rstrip("/") + path
    data = json.dumps(body).encode() if body else None
    headers: dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail}") from exc


def login(api: str, username: str) -> str:
    resp = call(api, "/auth/login", "POST", {"username": username, "password": PASSWORD})
    return str(resp["access_token"])


def ensure_league(api: str, token: str, payload: dict) -> int:
    """Create league if it doesn't already exist (owner is demo01). Returns league id."""
    lobby = call(api, "/lobby", token=token)
    for league in lobby.get("leagues", []):
        if league["name"] == payload["name"]:
            print(f"  League '{payload['name']}' already exists (id={league['id']})")
            return int(league["id"])
    league = call(api, "/leagues", "POST", payload, token=token)
    print(f"  Created league '{league['name']}' (id={league['id']})")
    return int(league["id"])


def ensure_invites(api: str, owner_token: str, league_id: int, needed: int) -> list[str]:
    """Return a list of single-use invite tokens, creating fresh ones as needed."""
    detail = call(api, f"/leagues/{league_id}", token=owner_token)
    available: list[str] = [
        str(inv["token"])
        for inv in detail.get("invites", [])
        if not inv["revoked"] and inv["use_count"] < inv["max_uses"]
    ]
    while len(available) < needed:
        inv = call(api, f"/leagues/{league_id}/invites", "POST", token=owner_token)
        available.append(str(inv["token"]))
    print(f"    League {league_id}: {len(available)} invite token(s) ready")
    return available


def accept_invite(api: str, member_token: str, invite_token: str, username: str) -> bool:
    try:
        call(api, "/league-invites/accept", "POST", {"token": invite_token}, token=member_token)
        return True
    except RuntimeError as exc:
        msg = str(exc)
        if "already a member" in msg.lower() or "409" in msg:
            return False  # already joined, fine
        print(f"    ERROR {username}: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=DEFAULT_API)
    args = parser.parse_args()
    api: str = args.api.rstrip("/")

    print(f"Target API: {api}\n")

    # --- Step 1: owner creates leagues and gets invite pools ---
    print(f"Logging in as {OWNER}...")
    owner_token = login(api, OWNER)

    # Map league_name -> list of invite tokens (one per member needed)
    league_invite_pools: list[list[str]] = []
    league_ids: list[int] = []
    for league_payload in LEAGUES:
        print(f"Ensuring league: {league_payload['name']}")
        league_id = ensure_league(api, owner_token, league_payload)
        league_ids.append(league_id)
        invite_pool = ensure_invites(api, owner_token, league_id, needed=len(MEMBERS))
        league_invite_pools.append(invite_pool)

    # --- Step 2: each member consumes one invite per league ---
    print(f"\nAdding {len(MEMBERS)} members to all leagues...")
    for i, username in enumerate(MEMBERS):
        try:
            member_token = login(api, username)
        except RuntimeError as exc:
            print(f"  SKIP {username}: login failed ({exc})")
            continue
        joined = 0
        for pool in league_invite_pools:
            inv_token = pool[i] if i < len(pool) else None
            if inv_token and accept_invite(api, member_token, inv_token, username):
                joined += 1
        print(f"  {username}: joined {joined} new league(s)")

    # --- Summary ---
    print("\nVerifying final state...")
    owner_token = login(api, OWNER)
    lobby = call(api, "/lobby", token=owner_token)
    for league in lobby.get("leagues", []):
        print(f"  {league['name']}: {league['member_count']} member(s)")

    print("\nDone. Credentials: demo01..demo10 / demo1234")


if __name__ == "__main__":
    main()
