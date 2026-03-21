import json
import random
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from main import DB_PATH, DEFAULT_GLOBAL_RATING, hash_password, init_db


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


def ensure_league(conn: sqlite3.Connection, li: int, owner_id: int, owner_username: str) -> int:
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


def main() -> None:
    random.seed(42)
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        user_ids = [ensure_user(conn, i) for i in range(1, 21)]
        username_by_id = {
            int(row["id"]): str(row["username"])
            for row in conn.execute("SELECT id, username FROM users WHERE username LIKE 'demo__'")
        }

        for li in range(1, 6):
            owner_id = user_ids[li - 1]
            league_id = ensure_league(conn, li, owner_id, username_by_id.get(owner_id, ""))

            # deterministic pool per league
            start = (li - 1) * 4
            pool = user_ids[start:start + 12]
            if owner_id not in pool:
                pool = [owner_id] + pool[:11]
            pool = pool[:12]

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
        print("Users demo01..demo20 / password demo1234")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
