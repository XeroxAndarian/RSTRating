import json
import random
import secrets
import sqlite3
import argparse
from datetime import datetime, timedelta, timezone

from main import DB_PATH, DEFAULT_GLOBAL_RATING, hash_password, init_db


DEFAULT_DEMO_USERS = 10
DEFAULT_DEMO_LEAGUES = 3


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_user(conn: sqlite3.Connection, idx: int) -> int:
    username = f"demo{idx:02d}"
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if row:
        return int(row["id"])
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO users (
            username, password_hash, email, name, surname, nicknames,
            display_name, role, attendance, wins, goals, assists,
            global_rating, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'user', 0, 0, 0, 0, ?, ?, ?)
        """,
        (
            username,
            hash_password("demo1234"),
            f"{username}@demo.local",
            f"Name{idx}",
            f"Surname{idx}",
            json.dumps([f"P{idx}"]),
            f"Player {idx}",
            DEFAULT_GLOBAL_RATING,
            ts,
            ts,
        ),
    )
    return int(conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"])


def ensure_league(conn: sqlite3.Connection, li: int, owner_id: int) -> int:
    name = f"Demo League {chr(64 + li)}"
    row = conn.execute("SELECT id FROM leagues WHERE name = ?", (name,)).fetchone()
    ts = now_iso()
    if row:
        league_id = int(row["id"])
        conn.execute(
            "UPDATE leagues SET goal_size = ?, region = ?, football_type = ? WHERE id = ?",
            (
                "large" if li % 2 else "small",
                f"Region {li}",
                "outdoor" if li % 2 else "indoor",
                league_id,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO leagues (name, sport, football_type, goal_size, region, invite_code, description, owner_id, created_at, updated_at)
            VALUES (?, 'football', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                "outdoor" if li % 2 else "indoor",
                "large" if li % 2 else "small",
                f"Region {li}",
                secrets.token_hex(3).upper(),
                f"Auto-seeded demo league {li}",
                owner_id,
                ts,
                ts,
            ),
        )
        league_id = int(conn.execute("SELECT id FROM leagues WHERE name = ?", (name,)).fetchone()["id"])

    owner_membership = conn.execute(
        "SELECT id FROM league_memberships WHERE league_id = ? AND user_id = ?", (league_id, owner_id)
    ).fetchone()
    if not owner_membership:
        conn.execute(
            "INSERT INTO league_memberships (league_id, user_id, role, joined_at) VALUES (?, ?, 'owner', ?)",
            (league_id, owner_id, ts),
        )
    return league_id


def reset_existing_demo_data(conn: sqlite3.Connection) -> None:
    demo_user_ids = [
        int(row["id"])
        for row in conn.execute("SELECT id FROM users WHERE username LIKE 'demo__'")
    ]
    demo_league_ids = [
        int(row["id"])
        for row in conn.execute("SELECT id FROM leagues WHERE name LIKE 'Demo League %'")
    ]

    if demo_league_ids:
        placeholders = ",".join("?" for _ in demo_league_ids)
        conn.execute(f"DELETE FROM match_events WHERE match_id IN (SELECT id FROM matches WHERE league_id IN ({placeholders}))", demo_league_ids)
        conn.execute(f"DELETE FROM match_registrations WHERE match_id IN (SELECT id FROM matches WHERE league_id IN ({placeholders}))", demo_league_ids)
        conn.execute(f"DELETE FROM matches WHERE league_id IN ({placeholders})", demo_league_ids)
        conn.execute(f"DELETE FROM league_player_stats WHERE league_id IN ({placeholders})", demo_league_ids)
        conn.execute(f"DELETE FROM league_memberships WHERE league_id IN ({placeholders})", demo_league_ids)
        conn.execute(f"DELETE FROM leagues WHERE id IN ({placeholders})", demo_league_ids)

    if demo_user_ids:
        placeholders = ",".join("?" for _ in demo_user_ids)
        conn.execute(f"DELETE FROM notifications WHERE user_id IN ({placeholders})", demo_user_ids)
        conn.execute(f"DELETE FROM users WHERE id IN ({placeholders})", demo_user_ids)


def ensure_league_player_stats(conn: sqlite3.Connection, league_id: int, user_id: int) -> None:
    row = conn.execute(
        "SELECT id FROM league_player_stats WHERE league_id = ? AND user_id = ?", (league_id, user_id)
    ).fetchone()
    if row:
        return
    conn.execute(
        """
        INSERT INTO league_player_stats (league_id, user_id, attendance, wins, goals, assists, rating)
        VALUES (?, ?, 0, 0, 0, 0, ?)
        """,
        (league_id, user_id, DEFAULT_GLOBAL_RATING + random.randint(-50, 50)),
    )


def ensure_match_bundle(conn: sqlite3.Connection, league_id: int, created_by: int, member_ids: list[int]) -> None:
    existing = conn.execute("SELECT COUNT(*) AS n FROM matches WHERE league_id = ?", (league_id,)).fetchone()["n"]
    if int(existing) >= 2:
        return

    now = datetime.now(timezone.utc)

    # Upcoming/registration-open match
    m1_title = f"League {league_id} Friday Session"
    row = conn.execute("SELECT id FROM matches WHERE league_id = ? AND title = ?", (league_id, m1_title)).fetchone()
    if not row:
        created = now_iso()
        scheduled = (now + timedelta(days=2)).isoformat()
        reg_open = (now - timedelta(hours=2)).isoformat()
        preview_token = secrets.token_urlsafe(16)
        conn.execute(
            """
            INSERT INTO matches (
                league_id, title, location, scheduled_at, registration_opens_at,
                max_participants, notes, status, team_a, team_b, score_a, score_b,
                started_at, ended_at, created_by, created_at, updated_at, preview_token
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'registration_open', '[]', '[]', 0, 0, NULL, NULL, ?, ?, ?, ?)
            """,
            (
                league_id,
                m1_title,
                "Demo Pitch",
                scheduled,
                reg_open,
                14,
                "Seeded demo upcoming match",
                created_by,
                created,
                created,
                preview_token,
            ),
        )
        m1_id = int(conn.execute("SELECT id FROM matches WHERE league_id = ? AND title = ?", (league_id, m1_title)).fetchone()["id"])
        for pos, uid in enumerate(member_ids[:10], start=1):
            conn.execute(
                """
                INSERT OR IGNORE INTO match_registrations (match_id, user_id, status, position, registered_at, offered_at)
                VALUES (?, ?, 'registered', ?, ?, NULL)
                """,
                (m1_id, uid, pos, now_iso()),
            )

    # Completed match with events
    m2_title = f"League {league_id} Last Week"
    row = conn.execute("SELECT id FROM matches WHERE league_id = ? AND title = ?", (league_id, m2_title)).fetchone()
    if not row:
        created = now_iso()
        started = (now - timedelta(days=7, hours=1)).isoformat()
        ended = (now - timedelta(days=7)).isoformat()
        team_a = member_ids[:5]
        team_b = member_ids[5:10]
        preview_token = secrets.token_urlsafe(16)
        conn.execute(
            """
            INSERT INTO matches (
                league_id, title, location, scheduled_at, registration_opens_at,
                max_participants, notes, status, team_a, team_b, score_a, score_b,
                started_at, ended_at, created_by, created_at, updated_at, preview_token
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, 3, 2, ?, ?, ?, ?, ?, ?)
            """,
            (
                league_id,
                m2_title,
                "Demo Pitch",
                (now - timedelta(days=7)).isoformat(),
                (now - timedelta(days=9)).isoformat(),
                14,
                "Seeded completed match",
                json.dumps(team_a),
                json.dumps(team_b),
                started,
                ended,
                created_by,
                created,
                created,
                preview_token,
            ),
        )
        m2_id = int(conn.execute("SELECT id FROM matches WHERE league_id = ? AND title = ?", (league_id, m2_title)).fetchone()["id"])
        for pos, uid in enumerate(team_a + team_b, start=1):
            conn.execute(
                """
                INSERT OR IGNORE INTO match_registrations (match_id, user_id, status, position, registered_at, offered_at)
                VALUES (?, ?, 'registered', ?, ?, NULL)
                """,
                (m2_id, uid, pos, now_iso()),
            )

        # Minimal event feed
        for i, uid in enumerate(team_a[:3]):
            conn.execute(
                """
                INSERT INTO match_events (match_id, event_type, user_id, team, event_seconds, created_at, undone)
                VALUES (?, 'goal', ?, 'a', ?, ?, 0)
                """,
                (m2_id, uid, 600 + i * 300, now_iso()),
            )
        for i, uid in enumerate(team_b[:2]):
            conn.execute(
                """
                INSERT INTO match_events (match_id, event_type, user_id, team, event_seconds, created_at, undone)
                VALUES (?, 'goal', ?, 'b', ?, ?, 0)
                """,
                (m2_id, uid, 750 + i * 420, now_iso()),
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo users, leagues, and matches.")
    parser.add_argument("--users", type=int, default=DEFAULT_DEMO_USERS, help="Number of demo users to ensure (default: 10)")
    parser.add_argument("--leagues", type=int, default=DEFAULT_DEMO_LEAGUES, help="Number of demo leagues to ensure (default: 3)")
    parser.add_argument("--reset", action="store_true", help="Delete existing demo users/leagues before seeding.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.users < 10:
        raise SystemExit("--users must be at least 10 so seeded matches can be fully populated.")
    if args.leagues < 1:
        raise SystemExit("--leagues must be at least 1.")

    random.seed(42)
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if args.reset:
            reset_existing_demo_data(conn)
            conn.commit()

        user_ids = [ensure_user(conn, i) for i in range(1, args.users + 1)]
        username_by_id = {
            int(row["id"]): str(row["username"])
            for row in conn.execute("SELECT id, username FROM users WHERE username LIKE 'demo__'")
        }

        for li in range(1, args.leagues + 1):
            owner_id = user_ids[li - 1]
            league_id = ensure_league(conn, li, owner_id)

            # Deterministic rotating pool so each league has enough players even with smaller demo user sets.
            start = (li - 1) * 3
            rotated = user_ids[start:] + user_ids[:start]
            pool = rotated[: min(12, len(user_ids))]
            if owner_id not in pool:
                pool = [owner_id] + pool[: max(0, min(11, len(user_ids) - 1))]

            for idx, uid in enumerate(pool):
                role = "owner" if uid == owner_id else ("admin" if idx in (1, 2) else "member")
                conn.execute(
                    """
                    INSERT OR IGNORE INTO league_memberships (league_id, user_id, role, joined_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (league_id, uid, role, now_iso()),
                )
                # Update role for existing memberships as well
                conn.execute(
                    "UPDATE league_memberships SET role = ? WHERE league_id = ? AND user_id = ?",
                    (role, league_id, uid),
                )
                ensure_league_player_stats(conn, league_id, uid)

            ensure_match_bundle(conn, league_id, owner_id, pool)

        conn.commit()
        print(f"Seed done. DB: {DB_PATH}")
        print(f"Users demo01..demo{args.users:02d} / password demo1234")
        print(f"Leagues seeded: {args.leagues}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
