import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, Field


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "accounts.db"

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
DB_PATH = Path(os.getenv("DB_PATH", str(DEFAULT_DB))).expanduser().resolve()
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,https://xeroxandarian.github.io",
    ).split(",")
    if origin.strip()
]

# Initial admin account seed. Change these via environment variables in production.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "rstadmin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@rstrating.local")
BACKDOOR_PIN = os.getenv("BACKDOOR_PIN", "rst2024")

bearer_scheme = HTTPBearer(auto_error=False)
PBKDF2_ITERATIONS = 210000
LEAGUE_INVITE_EXPIRY_DAYS = 7
DEFAULT_GLOBAL_RATING = 1000.0


class RegisterPayload(BaseModel):
    username: str = Field(min_length=3, max_length=24, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=6, max_length=200)
    email: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    nicknames: list[str] = Field(default_factory=list)
    display_name: str | None = Field(default=None, max_length=100)


class LoginPayload(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    name: str
    surname: str
    nicknames: list[str]
    display_name: str | None
    role: str
    created_at: str


class UserStatsOut(BaseModel):
    attendance: int
    wins: int
    goals: int
    assists: int
    global_rating: float


class LeaguePlayerStatsOut(BaseModel):
    league_id: int
    league_name: str
    attendance: int
    wins: int
    goals: int
    assists: int
    rating: float


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class UpdateMePayload(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    current_password: str | None = Field(default=None, min_length=6, max_length=200)
    new_password: str | None = Field(default=None, min_length=6, max_length=200)


class BackupUserData(BaseModel):
    id: int
    username: str
    password_hash: str
    email: str
    name: str
    surname: str
    nicknames: list[str]
    display_name: str | None
    role: str
    attendance: int
    wins: int
    goals: int
    assists: int
    global_rating: float
    created_at: str
    updated_at: str


class BackupLeagueData(BaseModel):
    id: int
    name: str
    football_type: str
    goal_size: str
    description: str | None
    owner_user_id: int
    owner_username: str
    created_at: str
    updated_at: str


class BackupMembershipData(BaseModel):
    id: int
    league_id: int
    user_id: int
    league_name: str
    username: str
    role: str
    joined_at: str


class BackupInviteData(BaseModel):
    id: int
    league_id: int
    created_by_user_id: int
    league_name: str
    created_by_username: str
    token: str
    created_at: str
    expires_at: str | None
    max_uses: int
    use_count: int
    revoked: int


class BackupLeaguePlayerStatsData(BaseModel):
    id: int
    league_id: int
    user_id: int
    attendance: int
    wins: int
    goals: int
    assists: int
    rating: float


class BackupExportData(BaseModel):
    update: str
    users: dict[str, BackupUserData]
    leagues: dict[str, BackupLeagueData]
    memberships: dict[str, BackupMembershipData]
    invites: dict[str, BackupInviteData]
    league_player_stats: dict[str, BackupLeaguePlayerStatsData]


class BackupImportData(BaseModel):
    users: dict[str, BackupUserData]
    leagues: dict[str, BackupLeagueData] = Field(default_factory=dict)
    memberships: dict[str, BackupMembershipData] = Field(default_factory=dict)
    invites: dict[str, BackupInviteData] = Field(default_factory=dict)
    league_player_stats: dict[str, BackupLeaguePlayerStatsData] = Field(default_factory=dict)


class PasswordResetRequestPayload(BaseModel):
    email: str = Field(max_length=255)


class PasswordResetPayload(BaseModel):
    email: str = Field(max_length=255)
    token: str = Field(min_length=32, max_length=128)
    new_password: str = Field(min_length=6, max_length=200)


class LeagueCreatePayload(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    football_type: str = Field(pattern=r"^(outdoor|indoor)$")
    goal_size: str = Field(pattern=r"^(small|medium|large)$")
    region: str = Field(min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=300)


class JoinLeagueByCodePayload(BaseModel):
    invite_code: str = Field(min_length=4, max_length=16)


class LeagueJoinRequestCreatePayload(BaseModel):
    message: str | None = Field(default=None, max_length=300)


class LeagueJoinRequestDecisionPayload(BaseModel):
    decision: str = Field(pattern=r"^(accept|reject)$")


class LeagueJoinRequestOut(BaseModel):
    id: int
    league_id: int
    user_id: int
    username: str
    display_name: str | None
    status: str
    message: str | None
    requested_at: str
    decided_at: str | None
    decided_by_user_id: int | None


class InviteAcceptPayload(BaseModel):
    token: str = Field(min_length=8, max_length=128)


class LeagueMemberRolePayload(BaseModel):
    role: str = Field(pattern=r"^(member|admin)$")


class LeagueOut(BaseModel):
    id: int
    name: str
    football_type: str
    goal_size: str
    region: str
    invite_code: str
    description: str | None
    owner_id: int
    owner_username: str
    member_role: str
    member_count: int
    created_at: str


class LeagueInviteOut(BaseModel):
    id: int
    league_id: int
    league_name: str
    token: str
    created_at: str
    expires_at: str | None
    max_uses: int
    use_count: int
    revoked: int
    invite_url: str


class LeagueMemberOut(BaseModel):
    user_id: int
    username: str
    display_name: str | None
    role: str
    joined_at: str
    attendance: int
    wins: int
    goals: int
    assists: int
    rating: float


class LeagueDetailOut(BaseModel):
    league: LeagueOut
    members: list[LeagueMemberOut]
    invites: list[LeagueInviteOut]


class LobbyOut(BaseModel):
    user: UserOut
    user_stats: UserStatsOut
    league_player_stats: list[LeaguePlayerStatsOut]
    leagues: list[LeagueOut]
    invites: list[LeagueInviteOut]


class InvitePreviewOut(BaseModel):
    league_id: int
    league_name: str
    football_type: str
    goal_size: str
    description: str | None
    owner_username: str
    expires_at: str | None
    remaining_uses: int
    requires_login: bool = True


class MessageOut(BaseModel):
    detail: str


# ====================== MATCH MANAGEMENT MODELS ======================

MATCH_STATUS = frozenset({"upcoming", "registration_open", "live", "finished", "completed", "cancelled"})
ELO_K = 32.0
WAITLIST_OFFER_MINUTES = 15
UNDO_WINDOW_SECONDS = 30


class MatchCreatePayload(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    scheduled_at: str = Field(min_length=10, max_length=40)
    registration_opens_at: str | None = Field(default=None, max_length=40)
    max_participants: int = Field(default=20, ge=2, le=200)
    notes: str | None = Field(default=None, max_length=1000)


class MatchOut(BaseModel):
    id: int
    league_id: int
    title: str
    location: str | None
    scheduled_at: str
    registration_opens_at: str | None
    max_participants: int
    notes: str | None
    status: str
    registered_count: int
    waitlisted_count: int
    my_registration_status: str | None
    team_a: list[int]
    team_b: list[int]
    score_a: int
    score_b: int
    started_at: str | None
    ended_at: str | None
    created_by_username: str
    created_at: str
    preview_token: str


class MatchRegistrationOut(BaseModel):
    user_id: int
    username: str
    display_name: str | None
    status: str
    registered_at: str
    position: int


class MatchEventOut(BaseModel):
    id: int
    event_type: str
    user_id: int | None
    username: str | None
    team: str | None
    event_seconds: int
    created_at: str
    undone: bool


class MatchDetailOut(BaseModel):
    match: MatchOut
    registrations: list[MatchRegistrationOut]
    events: list[MatchEventOut]


class GoalEventPayload(BaseModel):
    scorer_user_id: int
    assist_user_id: int | None = None
    team: str = Field(pattern=r"^[ab]$")


class NotificationOut(BaseModel):
    id: int
    notif_type: str
    title: str
    message: str
    data: dict
    read: bool
    created_at: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def clean_nicknames(nicknames: list[str] | None) -> list[str]:
    if not nicknames:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for nickname in nicknames:
        value = nickname.strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def nicknames_to_db(nicknames: list[str] | None) -> str:
    return json.dumps(clean_nicknames(nicknames), ensure_ascii=False)


def nicknames_from_db(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed = [part.strip() for part in raw_value.split(",") if part.strip()]
    if not isinstance(parsed, list):
        return []
    return clean_nicknames([str(item) for item in parsed])


def build_invite_url(token: str) -> str:
    base_origin = FRONTEND_ORIGINS[0].rstrip("/") if FRONTEND_ORIGINS else "https://xeroxandarian.github.io"
    return f"{base_origin}/RSTRating/?invite={token}"


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    if column_name not in table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def infer_football_type(old_sport: str | None) -> str:
    if old_sport is None:
        return "outdoor"
    sport = old_sport.strip().lower()
    if "indoor" in sport:
        return "indoor"
    return "outdoor"


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT,
                name TEXT,
                surname TEXT,
                nicknames TEXT,
                display_name TEXT,
                role TEXT NOT NULL DEFAULT 'player',
                attendance INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                goals INTEGER NOT NULL DEFAULT 0,
                assists INTEGER NOT NULL DEFAULT 0,
                global_rating REAL NOT NULL DEFAULT 1000,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        ensure_column(conn, "users", "email", "TEXT")
        ensure_column(conn, "users", "name", "TEXT")
        ensure_column(conn, "users", "surname", "TEXT")
        ensure_column(conn, "users", "nicknames", "TEXT")
        ensure_column(conn, "users", "display_name", "TEXT")
        ensure_column(conn, "users", "attendance", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "users", "wins", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "users", "goals", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "users", "assists", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "users", "global_rating", "REAL NOT NULL DEFAULT 1000")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email) WHERE email IS NOT NULL")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leagues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sport TEXT,
                football_type TEXT NOT NULL DEFAULT 'outdoor',
                goal_size TEXT NOT NULL DEFAULT '5x2',
                region TEXT NOT NULL DEFAULT 'Unknown',
                invite_code TEXT,
                description TEXT,
                owner_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        ensure_column(conn, "leagues", "sport", "TEXT")
        ensure_column(conn, "leagues", "football_type", "TEXT NOT NULL DEFAULT 'outdoor'")
        ensure_column(conn, "leagues", "goal_size", "TEXT NOT NULL DEFAULT '5x2'")
        ensure_column(conn, "leagues", "region", "TEXT NOT NULL DEFAULT 'Unknown'")
        ensure_column(conn, "leagues", "invite_code", "TEXT")

        rows = conn.execute("SELECT id, sport, football_type FROM leagues").fetchall()
        for row in rows:
            football_type = row["football_type"]
            if football_type not in {"outdoor", "indoor"}:
                football_type = infer_football_type(row["sport"])
                conn.execute("UPDATE leagues SET football_type = ? WHERE id = ?", (football_type, row["id"]))

        # Normalize legacy goal_size values to presets.
        legacy_goal_rows = conn.execute("SELECT id, goal_size FROM leagues").fetchall()
        for row in legacy_goal_rows:
            value = str(row["goal_size"] or "").strip().lower()
            mapped = value
            if value in {"5x2", "5m x 2m", "small"}:
                mapped = "small"
            elif value in {"7.32m x 2.44m", "large", "full"}:
                mapped = "large"
            elif value in {"medium", "mid"}:
                mapped = "medium"
            elif value not in {"small", "medium", "large"}:
                mapped = "medium"
            if mapped != value:
                conn.execute("UPDATE leagues SET goal_size = ? WHERE id = ?", (mapped, int(row["id"])))

        # Ensure each league has a permanent invite code.
        leagues_without_codes = conn.execute(
            "SELECT id FROM leagues WHERE invite_code IS NULL OR invite_code = ''"
        ).fetchall()
        for row in leagues_without_codes:
            code = secrets.token_hex(3).upper()
            while conn.execute("SELECT 1 FROM leagues WHERE invite_code = ?", (code,)).fetchone() is not None:
                code = secrets.token_hex(3).upper()
            conn.execute("UPDATE leagues SET invite_code = ? WHERE id = ?", (code, int(row["id"])))

        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_leagues_invite_code ON leagues(invite_code)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS league_memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                UNIQUE(league_id, user_id),
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS league_invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                created_by_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                max_uses INTEGER NOT NULL DEFAULT 1,
                use_count INTEGER NOT NULL DEFAULT 0,
                revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
                FOREIGN KEY(created_by_user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS league_join_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                message TEXT,
                requested_at TEXT NOT NULL,
                decided_at TEXT,
                decided_by_user_id INTEGER,
                UNIQUE(league_id, user_id),
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(decided_by_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS league_player_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                attendance INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                goals INTEGER NOT NULL DEFAULT 0,
                assists INTEGER NOT NULL DEFAULT 0,
                rating REAL NOT NULL DEFAULT 1000,
                UNIQUE(league_id, user_id),
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                location TEXT,
                scheduled_at TEXT NOT NULL,
                registration_opens_at TEXT,
                max_participants INTEGER NOT NULL DEFAULT 20,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'upcoming',
                team_a TEXT NOT NULL DEFAULT '[]',
                team_b TEXT NOT NULL DEFAULT '[]',
                score_a INTEGER NOT NULL DEFAULT 0,
                score_b INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                ended_at TEXT,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                preview_token TEXT,
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
                FOREIGN KEY(created_by) REFERENCES users(id)
            )
            """
        )

        # Lightweight migration for older databases.
        match_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(matches)").fetchall()
        }
        if "preview_token" not in match_columns:
            conn.execute("ALTER TABLE matches ADD COLUMN preview_token TEXT")

        # Ensure one-time unique index and backfill preview tokens for existing rows.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_preview_token ON matches(preview_token)"
        )
        missing_preview_rows = conn.execute(
            "SELECT id FROM matches WHERE preview_token IS NULL OR preview_token = ''"
        ).fetchall()
        for row in missing_preview_rows:
            conn.execute(
                "UPDATE matches SET preview_token = ? WHERE id = ?",
                (secrets.token_urlsafe(16), int(row["id"])),
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS match_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'registered',
                position INTEGER NOT NULL DEFAULT 0,
                registered_at TEXT NOT NULL,
                offered_at TEXT,
                UNIQUE(match_id, user_id),
                FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS match_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                team TEXT,
                event_seconds INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                undone INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                notif_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                data_json TEXT NOT NULL DEFAULT '{}',
                read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.commit()


def ensure_admin_account() -> None:
    with get_conn() as conn:
        existing_admin = conn.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        if existing_admin is not None:
            return

        existing_username = conn.execute("SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
        created_at = utc_now_iso()
        if existing_username is not None:
            conn.execute(
                """
                UPDATE users
                SET role = 'admin', email = COALESCE(email, ?), name = COALESCE(name, 'Admin'),
                    surname = COALESCE(surname, 'User'), updated_at = ?
                WHERE id = ?
                """,
                (normalize_email(ADMIN_EMAIL), created_at, existing_username["id"]),
            )
            conn.commit()
            return

        conn.execute(
            """
            INSERT INTO users (username, password_hash, email, name, surname, nicknames, display_name, role,
                               attendance, wins, goals, assists, global_rating, created_at, updated_at)
            VALUES (?, ?, ?, 'Admin', 'User', '[]', 'Administrator', 'admin',
                    0, 0, 0, 0, ?, ?, ?)
            """,
            (
                ADMIN_USERNAME,
                hash_password(ADMIN_PASSWORD),
                normalize_email(ADMIN_EMAIL),
                DEFAULT_GLOBAL_RATING,
                created_at,
                created_at,
            ),
        )
        conn.commit()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iteration_text, salt_hex, digest_hex = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    try:
        iterations = int(iteration_text)
        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual_digest, expected_digest)


def create_access_token(subject: str) -> str:
    now = utc_now()
    expires = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": int(expires.timestamp()), "iat": int(now.timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def find_user_by_username(username: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT id, username, password_hash, email, name, surname, nicknames, display_name, role,
                   attendance, wins, goals, assists, global_rating, created_at, updated_at
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()


def find_user_by_id(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT id, username, password_hash, email, name, surname, nicknames, display_name, role,
                   attendance, wins, goals, assists, global_rating, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()


def find_user_by_email(email: str) -> sqlite3.Row | None:
    normalized_email = normalize_email(email)
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT id, username, password_hash, email, name, surname, nicknames, display_name, role,
                   attendance, wins, goals, assists, global_rating, created_at, updated_at
            FROM users
            WHERE lower(email) = ?
            """,
            (normalized_email,),
        ).fetchone()


def serialize_user(row: sqlite3.Row) -> UserOut:
    return UserOut(
        id=int(row["id"]),
        username=str(row["username"]),
        email=str(row["email"] or ""),
        name=str(row["name"] or ""),
        surname=str(row["surname"] or ""),
        nicknames=nicknames_from_db(row["nicknames"]),
        display_name=row["display_name"],
        role=str(row["role"]),
        created_at=str(row["created_at"]),
    )


def serialize_user_stats(row: sqlite3.Row) -> UserStatsOut:
    return UserStatsOut(
        attendance=int(row["attendance"] or 0),
        wins=int(row["wins"] or 0),
        goals=int(row["goals"] or 0),
        assists=int(row["assists"] or 0),
        global_rating=float(row["global_rating"] or DEFAULT_GLOBAL_RATING),
    )


def serialize_league(row: sqlite3.Row) -> LeagueOut:
    return LeagueOut(
        id=int(row["id"]),
        name=str(row["name"]),
        football_type=str(row["football_type"]),
        goal_size=str(row["goal_size"]),
        region=str(row["region"] or "Unknown"),
        invite_code=str(row["invite_code"] or ""),
        description=row["description"],
        owner_id=int(row["owner_id"]),
        owner_username=str(row["owner_username"]),
        member_role=str(row["member_role"]),
        member_count=int(row["member_count"]),
        created_at=str(row["created_at"]),
    )


def serialize_invite(row: sqlite3.Row) -> LeagueInviteOut:
    token = str(row["token"])
    return LeagueInviteOut(
        id=int(row["id"]),
        league_id=int(row["league_id"]),
        league_name=str(row["league_name"]),
        token=token,
        created_at=str(row["created_at"]),
        expires_at=row["expires_at"],
        max_uses=int(row["max_uses"]),
        use_count=int(row["use_count"]),
        revoked=int(row["revoked"]),
        invite_url=build_invite_url(token),
    )


def serialize_member(row: sqlite3.Row) -> LeagueMemberOut:
    return LeagueMemberOut(
        user_id=int(row["user_id"]),
        username=str(row["username"]),
        display_name=row["display_name"],
        role=str(row["role"]),
        joined_at=str(row["joined_at"]),
        attendance=int(row["attendance"] or 0),
        wins=int(row["wins"] or 0),
        goals=int(row["goals"] or 0),
        assists=int(row["assists"] or 0),
        rating=float(row["rating"] or DEFAULT_GLOBAL_RATING),
    )


def resolve_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> sqlite3.Row:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    subject = str(payload.get("sub", ""))
    if not subject.startswith("user:"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    try:
        user_id = int(subject.split(":", 1)[1])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc
    user = find_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def resolve_current_admin(current_user: sqlite3.Row = Depends(resolve_current_user)) -> sqlite3.Row:
    if str(current_user["role"]) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def fetch_league_for_user(conn: sqlite3.Connection, league_id: int, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            l.id,
            l.name,
            l.football_type,
            l.goal_size,
            l.region,
            l.invite_code,
            l.description,
            l.owner_id,
            l.created_at,
            lm.role AS member_role,
            owner.username AS owner_username,
            (
                SELECT COUNT(*)
                FROM league_memberships AS member_count_source
                WHERE member_count_source.league_id = l.id
            ) AS member_count
        FROM league_memberships AS lm
        JOIN leagues AS l ON l.id = lm.league_id
        JOIN users AS owner ON owner.id = l.owner_id
        WHERE lm.user_id = ? AND l.id = ?
        """,
        (user_id, league_id),
    ).fetchone()


def fetch_user_leagues(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            l.id,
            l.name,
            l.football_type,
            l.goal_size,
            l.region,
            l.invite_code,
            l.description,
            l.owner_id,
            l.created_at,
            lm.role AS member_role,
            owner.username AS owner_username,
            (
                SELECT COUNT(*)
                FROM league_memberships AS member_count_source
                WHERE member_count_source.league_id = l.id
            ) AS member_count
        FROM league_memberships AS lm
        JOIN leagues AS l ON l.id = lm.league_id
        JOIN users AS owner ON owner.id = l.owner_id
        WHERE lm.user_id = ?
        ORDER BY l.created_at DESC
        """,
        (user_id,),
    ).fetchall()


def fetch_user_league_player_stats(conn: sqlite3.Connection, user_id: int) -> list[LeaguePlayerStatsOut]:
    rows = conn.execute(
        """
        SELECT
            lps.league_id,
            l.name AS league_name,
            lps.attendance,
            lps.wins,
            lps.goals,
            lps.assists,
            lps.rating
        FROM league_player_stats AS lps
        JOIN leagues AS l ON l.id = lps.league_id
        WHERE lps.user_id = ?
        ORDER BY l.name
        """,
        (user_id,),
    ).fetchall()
    return [
        LeaguePlayerStatsOut(
            league_id=int(row["league_id"]),
            league_name=str(row["league_name"]),
            attendance=int(row["attendance"]),
            wins=int(row["wins"]),
            goals=int(row["goals"]),
            assists=int(row["assists"]),
            rating=float(row["rating"]),
        )
        for row in rows
    ]


def fetch_manageable_invites(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            li.id,
            li.league_id,
            l.name AS league_name,
            li.token,
            li.created_at,
            li.expires_at,
            li.max_uses,
            li.use_count,
            li.revoked
        FROM league_invites AS li
        JOIN leagues AS l ON l.id = li.league_id
        JOIN league_memberships AS lm ON lm.league_id = l.id AND lm.user_id = ?
        WHERE lm.role IN ('owner', 'admin') AND li.revoked = 0
        ORDER BY li.created_at DESC
        """,
        (user_id,),
    ).fetchall()


def fetch_league_members(conn: sqlite3.Connection, league_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            lm.user_id,
            u.username,
            u.display_name,
            lm.role,
            lm.joined_at,
            COALESCE(lps.attendance, 0) AS attendance,
            COALESCE(lps.wins, 0) AS wins,
            COALESCE(lps.goals, 0) AS goals,
            COALESCE(lps.assists, 0) AS assists,
            COALESCE(lps.rating, 1000) AS rating
        FROM league_memberships AS lm
        JOIN users AS u ON u.id = lm.user_id
        LEFT JOIN league_player_stats AS lps ON lps.league_id = lm.league_id AND lps.user_id = lm.user_id
        WHERE lm.league_id = ?
        ORDER BY CASE lm.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, u.username
        """,
        (league_id,),
    ).fetchall()


def fetch_league_invites(conn: sqlite3.Connection, league_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT li.id, li.league_id, l.name AS league_name, li.token, li.created_at, li.expires_at, li.max_uses, li.use_count, li.revoked
        FROM league_invites AS li
        JOIN leagues AS l ON l.id = li.league_id
        WHERE li.league_id = ? AND li.revoked = 0
        ORDER BY li.created_at DESC
        """,
        (league_id,),
    ).fetchall()


def require_membership(conn: sqlite3.Connection, league_id: int, user_id: int) -> sqlite3.Row:
    membership = conn.execute(
        "SELECT id, league_id, user_id, role, joined_at FROM league_memberships WHERE league_id = ? AND user_id = ?",
        (league_id, user_id),
    ).fetchone()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="League membership required")
    return membership


def require_league_manager(conn: sqlite3.Connection, league_id: int, user_id: int) -> sqlite3.Row:
    membership = require_membership(conn, league_id, user_id)
    if membership["role"] not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="League manager access required")
    league = conn.execute("SELECT id, name FROM leagues WHERE id = ?", (league_id,)).fetchone()
    if league is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
    return league


def require_league_owner(conn: sqlite3.Connection, league_id: int, user_id: int) -> sqlite3.Row:
    membership = require_membership(conn, league_id, user_id)
    if membership["role"] != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="League owner access required")
    league = conn.execute("SELECT id, name FROM leagues WHERE id = ?", (league_id,)).fetchone()
    if league is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
    return league


def invite_preview_row(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            li.id,
            li.league_id,
            li.token,
            li.expires_at,
            li.max_uses,
            li.use_count,
            li.revoked,
            l.name AS league_name,
            l.football_type,
            l.goal_size,
            l.description,
            owner.username AS owner_username
        FROM league_invites AS li
        JOIN leagues AS l ON l.id = li.league_id
        JOIN users AS owner ON owner.id = l.owner_id
        WHERE li.token = ?
        """,
        (token,),
    ).fetchone()


app = FastAPI(title="RSTRating Accounts API", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    ensure_admin_account()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": utc_now_iso()}


@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterPayload) -> UserOut:
    if find_user_by_username(payload.username) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    normalized_email = normalize_email(payload.email)
    if find_user_by_email(normalized_email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    created_at = utc_now_iso()
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, email, name, surname, nicknames, display_name, role,
                               attendance, wins, goals, assists, global_rating, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'player', 0, 0, 0, 0, ?, ?, ?)
            """,
            (
                payload.username.strip(),
                hash_password(payload.password),
                normalized_email,
                payload.name.strip(),
                payload.surname.strip(),
                nicknames_to_db(payload.nicknames),
                payload.display_name.strip() if payload.display_name else None,
                DEFAULT_GLOBAL_RATING,
                created_at,
                created_at,
            ),
        )
        conn.commit()
        user_id = cursor.lastrowid
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create user")
    user = find_user_by_id(int(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create user")
    return serialize_user(user)


@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginPayload) -> TokenOut:
    user = find_user_by_username(payload.username)
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_access_token(subject=f"user:{user['id']}")
    return TokenOut(access_token=token, expires_in_minutes=ACCESS_TOKEN_EXPIRE_MINUTES)


@app.get("/auth/me", response_model=UserOut)
def me(current_user: sqlite3.Row = Depends(resolve_current_user)) -> UserOut:
    return serialize_user(current_user)


@app.patch("/auth/me", response_model=UserOut)
def update_me(payload: UpdateMePayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> UserOut:
    updates: list[str] = []
    params: list[str | None] = []
    if payload.display_name is not None:
        updates.append("display_name = ?")
        params.append(payload.display_name.strip() or None)
    if payload.new_password is not None:
        if payload.current_password is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password required")
        if not verify_password(payload.current_password, current_user["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is wrong")
        updates.append("password_hash = ?")
        params.append(hash_password(payload.new_password))
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update fields provided")
    updates.append("updated_at = ?")
    params.append(utc_now_iso())
    params.append(str(current_user["id"]))
    with get_conn() as conn:
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", tuple(params))
        conn.commit()
    updated_user = find_user_by_id(int(current_user["id"]))
    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User no longer exists")
    return serialize_user(updated_user)


@app.get("/backup/export", response_model=BackupExportData)
def export_backup(current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> BackupExportData:
    with get_conn() as conn:
        user_rows = conn.execute(
            """
            SELECT id, username, password_hash, email, name, surname, nicknames, display_name, role,
                   attendance, wins, goals, assists, global_rating, created_at, updated_at
            FROM users
            ORDER BY created_at
            """
        ).fetchall()
        league_rows = conn.execute(
            """
            SELECT l.id, l.name, l.football_type, l.goal_size, l.description,
                   l.owner_id AS owner_user_id, u.username AS owner_username, l.created_at, l.updated_at
            FROM leagues AS l
            JOIN users AS u ON u.id = l.owner_id
            ORDER BY l.created_at
            """
        ).fetchall()
        membership_rows = conn.execute(
            """
            SELECT lm.id, lm.league_id, lm.user_id, l.name AS league_name, u.username, lm.role, lm.joined_at
            FROM league_memberships AS lm
            JOIN leagues AS l ON l.id = lm.league_id
            JOIN users AS u ON u.id = lm.user_id
            ORDER BY lm.id
            """
        ).fetchall()
        invite_rows = conn.execute(
            """
            SELECT li.id, li.league_id, li.created_by_user_id, l.name AS league_name,
                   u.username AS created_by_username, li.token, li.created_at, li.expires_at,
                   li.max_uses, li.use_count, li.revoked
            FROM league_invites AS li
            JOIN leagues AS l ON l.id = li.league_id
            JOIN users AS u ON u.id = li.created_by_user_id
            ORDER BY li.id
            """
        ).fetchall()
        league_stats_rows = conn.execute(
            "SELECT id, league_id, user_id, attendance, wins, goals, assists, rating FROM league_player_stats ORDER BY id"
        ).fetchall()

    users = {
        str(row["id"]): BackupUserData(
            id=int(row["id"]),
            username=str(row["username"]),
            password_hash=str(row["password_hash"]),
            email=str(row["email"] or ""),
            name=str(row["name"] or ""),
            surname=str(row["surname"] or ""),
            nicknames=nicknames_from_db(row["nicknames"]),
            display_name=row["display_name"],
            role=str(row["role"]),
            attendance=int(row["attendance"]),
            wins=int(row["wins"]),
            goals=int(row["goals"]),
            assists=int(row["assists"]),
            global_rating=float(row["global_rating"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
        for row in user_rows
    }
    leagues = {
        str(row["id"]): BackupLeagueData(
            id=int(row["id"]),
            name=str(row["name"]),
            football_type=str(row["football_type"]),
            goal_size=str(row["goal_size"]),
            description=row["description"],
            owner_user_id=int(row["owner_user_id"]),
            owner_username=str(row["owner_username"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
        for row in league_rows
    }
    memberships = {
        str(row["id"]): BackupMembershipData(
            id=int(row["id"]),
            league_id=int(row["league_id"]),
            user_id=int(row["user_id"]),
            league_name=str(row["league_name"]),
            username=str(row["username"]),
            role=str(row["role"]),
            joined_at=str(row["joined_at"]),
        )
        for row in membership_rows
    }
    invites = {
        str(row["id"]): BackupInviteData(
            id=int(row["id"]),
            league_id=int(row["league_id"]),
            created_by_user_id=int(row["created_by_user_id"]),
            league_name=str(row["league_name"]),
            created_by_username=str(row["created_by_username"]),
            token=str(row["token"]),
            created_at=str(row["created_at"]),
            expires_at=row["expires_at"],
            max_uses=int(row["max_uses"]),
            use_count=int(row["use_count"]),
            revoked=int(row["revoked"]),
        )
        for row in invite_rows
    }
    league_player_stats = {
        str(row["id"]): BackupLeaguePlayerStatsData(
            id=int(row["id"]),
            league_id=int(row["league_id"]),
            user_id=int(row["user_id"]),
            attendance=int(row["attendance"]),
            wins=int(row["wins"]),
            goals=int(row["goals"]),
            assists=int(row["assists"]),
            rating=float(row["rating"]),
        )
        for row in league_stats_rows
    }
    return BackupExportData(
        update=utc_now().date().isoformat(),
        users=users,
        leagues=leagues,
        memberships=memberships,
        invites=invites,
        league_player_stats=league_player_stats,
    )


@app.post("/backup/import", response_model=MessageOut)
def import_backup(payload: BackupImportData, current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> MessageOut:
    imported_users = 0
    imported_leagues = 0
    imported_memberships = 0
    imported_invites = 0
    imported_league_stats = 0
    skipped = 0
    user_id_map: dict[int, int] = {}
    league_id_map: dict[int, int] = {}

    with get_conn() as conn:
        for backup_key, user_data in payload.users.items():
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ? OR lower(email) = ?",
                (user_data.username, normalize_email(user_data.email)),
            ).fetchone()
            if existing is not None:
                user_id_map[int(backup_key)] = int(existing["id"])
                skipped += 1
                continue
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, email, name, surname, nicknames, display_name, role,
                                   attendance, wins, goals, assists, global_rating, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_data.username,
                    user_data.password_hash,
                    normalize_email(user_data.email),
                    user_data.name,
                    user_data.surname,
                    nicknames_to_db(user_data.nicknames),
                    user_data.display_name,
                    user_data.role,
                    user_data.attendance,
                    user_data.wins,
                    user_data.goals,
                    user_data.assists,
                    user_data.global_rating,
                    user_data.created_at,
                    user_data.updated_at,
                ),
            )
            if cursor.lastrowid is not None:
                user_id_map[int(backup_key)] = int(cursor.lastrowid)
            imported_users += 1

        for backup_key, league_data in payload.leagues.items():
            owner_id = user_id_map.get(int(league_data.owner_user_id))
            if owner_id is None:
                owner_row = conn.execute("SELECT id FROM users WHERE username = ?", (league_data.owner_username,)).fetchone()
                owner_id = int(owner_row["id"]) if owner_row is not None else None
            if owner_id is None:
                skipped += 1
                continue
            existing = conn.execute(
                "SELECT id FROM leagues WHERE name = ? AND owner_id = ?",
                (league_data.name, owner_id),
            ).fetchone()
            if existing is not None:
                league_id_map[int(backup_key)] = int(existing["id"])
                skipped += 1
                continue
            cursor = conn.execute(
                """
                INSERT INTO leagues (name, football_type, goal_size, description, owner_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    league_data.name,
                    league_data.football_type,
                    league_data.goal_size,
                    league_data.description,
                    owner_id,
                    league_data.created_at,
                    league_data.updated_at,
                ),
            )
            if cursor.lastrowid is not None:
                league_id_map[int(backup_key)] = int(cursor.lastrowid)
            imported_leagues += 1

        for _, membership_data in payload.memberships.items():
            league_id = league_id_map.get(membership_data.league_id)
            user_id = user_id_map.get(membership_data.user_id)
            if league_id is None:
                league_row = conn.execute("SELECT id FROM leagues WHERE name = ?", (membership_data.league_name,)).fetchone()
                league_id = int(league_row["id"]) if league_row is not None else None
            if user_id is None:
                user_row = conn.execute("SELECT id FROM users WHERE username = ?", (membership_data.username,)).fetchone()
                user_id = int(user_row["id"]) if user_row is not None else None
            if league_id is None or user_id is None:
                skipped += 1
                continue
            existing = conn.execute(
                "SELECT id FROM league_memberships WHERE league_id = ? AND user_id = ?",
                (league_id, user_id),
            ).fetchone()
            if existing is not None:
                skipped += 1
                continue
            conn.execute(
                "INSERT INTO league_memberships (league_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
                (league_id, user_id, membership_data.role, membership_data.joined_at),
            )
            imported_memberships += 1

        for _, invite_data in payload.invites.items():
            league_id = league_id_map.get(invite_data.league_id)
            creator_id = user_id_map.get(invite_data.created_by_user_id)
            if league_id is None:
                league_row = conn.execute("SELECT id FROM leagues WHERE name = ?", (invite_data.league_name,)).fetchone()
                league_id = int(league_row["id"]) if league_row is not None else None
            if creator_id is None:
                user_row = conn.execute("SELECT id FROM users WHERE username = ?", (invite_data.created_by_username,)).fetchone()
                creator_id = int(user_row["id"]) if user_row is not None else None
            if league_id is None or creator_id is None:
                skipped += 1
                continue
            existing = conn.execute("SELECT id FROM league_invites WHERE token = ?", (invite_data.token,)).fetchone()
            if existing is not None:
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO league_invites (league_id, token, created_by_user_id, created_at, expires_at, max_uses, use_count, revoked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    league_id,
                    invite_data.token,
                    creator_id,
                    invite_data.created_at,
                    invite_data.expires_at,
                    invite_data.max_uses,
                    invite_data.use_count,
                    invite_data.revoked,
                ),
            )
            imported_invites += 1

        for _, stats_data in payload.league_player_stats.items():
            league_id = league_id_map.get(stats_data.league_id, stats_data.league_id)
            user_id = user_id_map.get(stats_data.user_id, stats_data.user_id)
            league_exists = conn.execute("SELECT id FROM leagues WHERE id = ?", (league_id,)).fetchone()
            user_exists = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if league_exists is None or user_exists is None:
                skipped += 1
                continue
            existing = conn.execute(
                "SELECT id FROM league_player_stats WHERE league_id = ? AND user_id = ?",
                (league_id, user_id),
            ).fetchone()
            if existing is not None:
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO league_player_stats (league_id, user_id, attendance, wins, goals, assists, rating)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    league_id,
                    user_id,
                    stats_data.attendance,
                    stats_data.wins,
                    stats_data.goals,
                    stats_data.assists,
                    stats_data.rating,
                ),
            )
            imported_league_stats += 1

        conn.commit()

    return MessageOut(detail=(
        f"Imported users: {imported_users}, leagues: {imported_leagues}, memberships: {imported_memberships}, "
        f"invites: {imported_invites}, league stats: {imported_league_stats}. Skipped: {skipped}."
    ))


@app.get("/admin/download-db", summary="Download raw SQLite database file (admin only)")
def download_db(current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> FileResponse:
    """Stream the live SQLite database file as a binary download.

    The downloaded file is a consistent snapshot because SQLite's
    file format is safe to copy while no write transaction is open.
    For a fully atomic snapshot use the JSON backup/export endpoint instead.
    """
    if not DB_PATH.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database file not found on server.")
    filename = f"rstrating_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
    return FileResponse(
        path=str(DB_PATH),
        media_type="application/octet-stream",
        filename=filename,
    )


@app.post("/auth/password-reset-request")
def request_password_reset(payload: PasswordResetRequestPayload) -> dict[str, str]:
    user = find_user_by_email(payload.email)
    if user is None:
        return {"detail": "If an account exists with this email, a reset link has been sent."}
    reset_token = secrets.token_urlsafe(32)
    expires_at = (utc_now() + timedelta(minutes=30)).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO password_reset_tokens (user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], reset_token, expires_at, utc_now_iso()),
        )
        conn.commit()
    return {
        "detail": "Password reset token generated. Use this token in the reset endpoint.",
        "token": reset_token,
        "note": "In production, this token would be sent via email.",
    }


@app.post("/auth/password-reset", response_model=MessageOut)
def reset_password(payload: PasswordResetPayload) -> MessageOut:
    user = find_user_by_email(payload.email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    with get_conn() as conn:
        token_row = conn.execute(
            "SELECT id, expires_at FROM password_reset_tokens WHERE user_id = ? AND token = ? ORDER BY created_at DESC LIMIT 1",
            (user["id"], payload.token),
        ).fetchone()
        if token_row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired reset token")
        expires_at = datetime.fromisoformat(str(token_row["expires_at"]))
        if utc_now() > expires_at:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reset token has expired")
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (hash_password(payload.new_password), utc_now_iso(), user["id"]),
        )
        conn.execute("DELETE FROM password_reset_tokens WHERE id = ?", (token_row["id"],))
        conn.commit()
    return MessageOut(detail="Password reset successfully. You can now log in with your new password.")


@app.get("/lobby", response_model=LobbyOut)
def get_lobby(current_user: sqlite3.Row = Depends(resolve_current_user)) -> LobbyOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        leagues = [serialize_league(row) for row in fetch_user_leagues(conn, user_id)]
        invites = [serialize_invite(row) for row in fetch_manageable_invites(conn, user_id)]
        league_player_stats = fetch_user_league_player_stats(conn, user_id)
    return LobbyOut(
        user=serialize_user(current_user),
        user_stats=serialize_user_stats(current_user),
        league_player_stats=league_player_stats,
        leagues=leagues,
        invites=invites,
    )


@app.post("/leagues", response_model=LeagueOut, status_code=status.HTTP_201_CREATED)
def create_league(payload: LeagueCreatePayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> LeagueOut:
    created_at = utc_now_iso()
    user_id = int(current_user["id"])
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO leagues (name, sport, football_type, goal_size, region, invite_code, description, owner_id, created_at, updated_at)
            VALUES (?, 'football', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name.strip(),
                payload.football_type,
                payload.goal_size,
                payload.region.strip(),
                secrets.token_hex(3).upper(),
                payload.description.strip() if payload.description else None,
                user_id,
                created_at,
                created_at,
            ),
        )
        league_id = cursor.lastrowid
        if league_id is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create league")

        conn.execute(
            "INSERT INTO league_memberships (league_id, user_id, role, joined_at) VALUES (?, ?, 'owner', ?)",
            (int(league_id), user_id, created_at),
        )
        conn.execute(
            "INSERT INTO league_player_stats (league_id, user_id, attendance, wins, goals, assists, rating) VALUES (?, ?, 0, 0, 0, 0, ?)",
            (int(league_id), user_id, float(current_user["global_rating"] or DEFAULT_GLOBAL_RATING)),
        )
        conn.commit()

        league_row = fetch_league_for_user(conn, int(league_id), user_id)
    if league_row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load league")
    return serialize_league(league_row)


@app.get("/leagues/{league_id}", response_model=LeagueDetailOut)
def get_league_detail(league_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> LeagueDetailOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        league_row = fetch_league_for_user(conn, league_id, user_id)
        if league_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
        members = [serialize_member(row) for row in fetch_league_members(conn, league_id)]
        membership = require_membership(conn, league_id, user_id)
        invites: list[LeagueInviteOut] = []
        if membership["role"] in {"owner", "admin"}:
            invites = [serialize_invite(row) for row in fetch_league_invites(conn, league_id)]
    return LeagueDetailOut(league=serialize_league(league_row), members=members, invites=invites)


@app.patch("/leagues/{league_id}/members/{member_user_id}", response_model=MessageOut)
def update_league_member_role(
    league_id: int,
    member_user_id: int,
    payload: LeagueMemberRolePayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    with get_conn() as conn:
        require_league_owner(conn, league_id, int(current_user["id"]))
        membership = conn.execute(
            "SELECT role FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, member_user_id),
        ).fetchone()
        if membership is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        if membership["role"] == "owner":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner role cannot be changed")
        conn.execute(
            "UPDATE league_memberships SET role = ? WHERE league_id = ? AND user_id = ?",
            (payload.role, league_id, member_user_id),
        )
        conn.commit()
    return MessageOut(detail="Member role updated.")


@app.post("/leagues/{league_id}/invites", response_model=LeagueInviteOut, status_code=status.HTTP_201_CREATED)
def create_league_invite(league_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> LeagueInviteOut:
    created_at = utc_now_iso()
    expires_at = (utc_now() + timedelta(days=LEAGUE_INVITE_EXPIRY_DAYS)).isoformat()
    token = secrets.token_urlsafe(18)
    with get_conn() as conn:
        league = require_league_manager(conn, league_id, int(current_user["id"]))
        cursor = conn.execute(
            """
            INSERT INTO league_invites (league_id, token, created_by_user_id, created_at, expires_at, max_uses, use_count, revoked)
            VALUES (?, ?, ?, ?, ?, 1, 0, 0)
            """,
            (league_id, token, int(current_user["id"]), created_at, expires_at),
        )
        invite_id = cursor.lastrowid
        conn.commit()
    if invite_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create invite")
    return LeagueInviteOut(
        id=int(invite_id),
        league_id=league_id,
        league_name=str(league["name"]),
        token=token,
        created_at=created_at,
        expires_at=expires_at,
        max_uses=1,
        use_count=0,
        revoked=0,
        invite_url=build_invite_url(token),
    )


@app.get("/league-invites/{token}", response_model=InvitePreviewOut)
def preview_league_invite(token: str) -> InvitePreviewOut:
    with get_conn() as conn:
        invite = invite_preview_row(conn, token.strip())
    if invite is None or int(invite["revoked"]) == 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    expires_at = invite["expires_at"]
    if expires_at is not None and utc_now() > datetime.fromisoformat(str(expires_at)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invite has expired")
    remaining_uses = max(int(invite["max_uses"]) - int(invite["use_count"]), 0)
    if remaining_uses < 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite has already been used")
    return InvitePreviewOut(
        league_id=int(invite["league_id"]),
        league_name=str(invite["league_name"]),
        football_type=str(invite["football_type"]),
        goal_size=str(invite["goal_size"]),
        description=invite["description"],
        owner_username=str(invite["owner_username"]),
        expires_at=expires_at,
        remaining_uses=remaining_uses,
    )


@app.post("/league-invites/accept", response_model=LeagueOut)
def accept_league_invite(payload: InviteAcceptPayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> LeagueOut:
    with get_conn() as conn:
        invite = invite_preview_row(conn, payload.token.strip())
        if invite is None or int(invite["revoked"]) == 1:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
        expires_at_raw = invite["expires_at"]
        if expires_at_raw is not None and utc_now() > datetime.fromisoformat(str(expires_at_raw)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invite has expired")
        if int(invite["use_count"]) >= int(invite["max_uses"]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite has already been used")

        league_id = int(invite["league_id"])
        user_id = int(current_user["id"])
        existing_membership = conn.execute(
            "SELECT role FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        if existing_membership is None:
            conn.execute(
                "INSERT INTO league_memberships (league_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
                (league_id, user_id, utc_now_iso()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO league_player_stats (league_id, user_id, attendance, wins, goals, assists, rating) VALUES (?, ?, 0, 0, 0, 0, ?)",
                (league_id, user_id, float(current_user["global_rating"] or DEFAULT_GLOBAL_RATING)),
            )
            conn.execute(
                "UPDATE league_invites SET use_count = use_count + 1 WHERE id = ?",
                (int(invite["id"]),),
            )
            conn.commit()

        league_row = fetch_league_for_user(conn, league_id, user_id)
    if league_row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not join league")
    return serialize_league(league_row)


# ============================================================
# ADMIN BACKDOOR
# ============================================================

class BackdoorPayload(BaseModel):
    pin: str = Field(min_length=1, max_length=128)


@app.post("/auth/backdoor", response_model=TokenOut)
def backdoor_login(payload: BackdoorPayload) -> TokenOut:
    if not hmac.compare_digest(payload.pin.encode(), BACKDOOR_PIN.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN")
    admin_user = find_user_by_username(ADMIN_USERNAME)
    if admin_user is None:
        ensure_admin_account()
        admin_user = find_user_by_username(ADMIN_USERNAME)
    if admin_user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Admin account not found")
    token = create_access_token(subject=f"user:{admin_user['id']}")
    return TokenOut(access_token=token, expires_in_minutes=ACCESS_TOKEN_EXPIRE_MINUTES)


def _serialize_join_request(row: sqlite3.Row) -> LeagueJoinRequestOut:
    return LeagueJoinRequestOut(
        id=int(row["id"]),
        league_id=int(row["league_id"]),
        user_id=int(row["user_id"]),
        username=str(row["username"]),
        display_name=row["display_name"],
        status=str(row["status"]),
        message=row["message"],
        requested_at=str(row["requested_at"]),
        decided_at=row["decided_at"],
        decided_by_user_id=row["decided_by_user_id"],
    )


@app.post("/leagues/join-by-code", response_model=LeagueOut)
def join_league_by_code(payload: JoinLeagueByCodePayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> LeagueOut:
    user_id = int(current_user["id"])
    invite_code = payload.invite_code.strip().upper()
    with get_conn() as conn:
        league = conn.execute(
            "SELECT id FROM leagues WHERE invite_code = ?",
            (invite_code,),
        ).fetchone()
        if league is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")

        league_id = int(league["id"])
        existing_membership = conn.execute(
            "SELECT id FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        if existing_membership is None:
            conn.execute(
                "INSERT INTO league_memberships (league_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
                (league_id, user_id, utc_now_iso()),
            )
            existing_stats = conn.execute(
                "SELECT id FROM league_player_stats WHERE league_id = ? AND user_id = ?",
                (league_id, user_id),
            ).fetchone()
            if existing_stats is None:
                conn.execute(
                    "INSERT INTO league_player_stats (league_id, user_id, attendance, wins, goals, assists, rating) VALUES (?, ?, 0, 0, 0, 0, ?)",
                    (league_id, user_id, float(current_user["global_rating"] or DEFAULT_GLOBAL_RATING)),
                )
        conn.execute(
            "DELETE FROM league_join_requests WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        )
        conn.commit()
        league_row = fetch_league_for_user(conn, league_id, user_id)
    if league_row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load league")
    return serialize_league(league_row)


@app.get("/leagues/discover")
def discover_leagues(
    region: str | None = None,
    q: str | None = None,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> list[dict]:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        params: list = [user_id]
        where_clauses = [
            "l.id NOT IN (SELECT league_id FROM league_memberships WHERE user_id = ?)",
        ]
        if region and region.strip():
            where_clauses.append("LOWER(l.region) = LOWER(?)")
            params.append(region.strip())
        if q and q.strip():
            where_clauses.append("(LOWER(l.name) LIKE LOWER(?) OR LOWER(COALESCE(l.description, '')) LIKE LOWER(?))")
            like_q = f"%{q.strip()}%"
            params.extend([like_q, like_q])

        query = f"""
            SELECT
                l.id,
                l.name,
                l.football_type,
                l.goal_size,
                l.region,
                l.description,
                owner.username AS owner_username,
                (
                    SELECT COUNT(*)
                    FROM league_memberships AS lm
                    WHERE lm.league_id = l.id
                ) AS member_count,
                (
                    SELECT status
                    FROM league_join_requests AS ljr
                    WHERE ljr.league_id = l.id AND ljr.user_id = ?
                ) AS my_request_status
            FROM leagues AS l
            JOIN users AS owner ON owner.id = l.owner_id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY l.created_at DESC
            LIMIT 100
        """
        # first placeholder is used in subquery my_request_status
        rows = conn.execute(query, [user_id] + params).fetchall()
    return [
        {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "football_type": str(row["football_type"]),
            "goal_size": str(row["goal_size"]),
            "region": str(row["region"] or "Unknown"),
            "description": row["description"],
            "owner_username": str(row["owner_username"]),
            "member_count": int(row["member_count"]),
            "my_request_status": row["my_request_status"],
        }
        for row in rows
    ]


@app.post("/leagues/{league_id}/join-requests", response_model=MessageOut)
def create_join_request(
    league_id: int,
    payload: LeagueJoinRequestCreatePayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        league_exists = conn.execute("SELECT id FROM leagues WHERE id = ?", (league_id,)).fetchone()
        if league_exists is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
        existing_member = conn.execute(
            "SELECT id FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        if existing_member is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You are already a league member")

        existing = conn.execute(
            "SELECT id, status FROM league_join_requests WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO league_join_requests (league_id, user_id, status, message, requested_at) VALUES (?, ?, 'pending', ?, ?)",
                (league_id, user_id, payload.message.strip() if payload.message else None, utc_now_iso()),
            )
        else:
            conn.execute(
                "UPDATE league_join_requests SET status = 'pending', message = ?, requested_at = ?, decided_at = NULL, decided_by_user_id = NULL WHERE id = ?",
                (payload.message.strip() if payload.message else None, utc_now_iso(), int(existing["id"])),
            )
        conn.commit()
    return MessageOut(detail="Join request submitted.")


@app.get("/leagues/{league_id}/join-requests", response_model=list[LeagueJoinRequestOut])
def list_join_requests(league_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> list[LeagueJoinRequestOut]:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        rows = conn.execute(
            """
            SELECT ljr.*, u.username, u.display_name
            FROM league_join_requests AS ljr
            JOIN users AS u ON u.id = ljr.user_id
            WHERE ljr.league_id = ? AND ljr.status = 'pending'
            ORDER BY ljr.requested_at ASC
            """,
            (league_id,),
        ).fetchall()
    return [_serialize_join_request(row) for row in rows]


@app.patch("/leagues/{league_id}/join-requests/{request_id}", response_model=MessageOut)
def decide_join_request(
    league_id: int,
    request_id: int,
    payload: LeagueJoinRequestDecisionPayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    manager_id = int(current_user["id"])
    with get_conn() as conn:
        require_league_manager(conn, league_id, manager_id)
        req = conn.execute(
            "SELECT id, user_id, status FROM league_join_requests WHERE id = ? AND league_id = ?",
            (request_id, league_id),
        ).fetchone()
        if req is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Join request not found")
        if str(req["status"]) != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Join request already processed")

        decision_status = "accepted" if payload.decision == "accept" else "rejected"
        conn.execute(
            "UPDATE league_join_requests SET status = ?, decided_at = ?, decided_by_user_id = ? WHERE id = ?",
            (decision_status, utc_now_iso(), manager_id, request_id),
        )

        if payload.decision == "accept":
            target_user_id = int(req["user_id"])
            member = conn.execute(
                "SELECT id FROM league_memberships WHERE league_id = ? AND user_id = ?",
                (league_id, target_user_id),
            ).fetchone()
            if member is None:
                conn.execute(
                    "INSERT INTO league_memberships (league_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
                    (league_id, target_user_id, utc_now_iso()),
                )
                lps = conn.execute(
                    "SELECT id FROM league_player_stats WHERE league_id = ? AND user_id = ?",
                    (league_id, target_user_id),
                ).fetchone()
                if lps is None:
                    user_row = conn.execute("SELECT global_rating FROM users WHERE id = ?", (target_user_id,)).fetchone()
                    base_rating = float(user_row["global_rating"] if user_row is not None else DEFAULT_GLOBAL_RATING)
                    conn.execute(
                        "INSERT INTO league_player_stats (league_id, user_id, attendance, wins, goals, assists, rating) VALUES (?, ?, 0, 0, 0, 0, ?)",
                        (league_id, target_user_id, base_rating),
                    )
        conn.commit()
    return MessageOut(detail=("Join request accepted." if payload.decision == "accept" else "Join request rejected."))


# ============================================================
# TEAM GENERATION (ported from TeamCalculator)
# ============================================================

def _generate_two_teams(player_ratings: list[tuple[int, float]]) -> tuple[list[int], list[int]]:
    """Balanced two-team split using exhaustive combinatorial search for n<=22 players."""
    if len(player_ratings) < 2:
        return [p for p, _ in player_ratings], []

    sorted_players = sorted(player_ratings, key=lambda x: x[1])
    odd_player_id: int | None = None

    if len(sorted_players) % 2 != 0:
        mid = len(sorted_players) // 2
        odd_player_id = sorted_players[mid][0]
        sorted_players.pop(mid)

    n = len(sorted_players)
    half = n // 2
    ratings = [r for _, r in sorted_players]
    ids = [pid for pid, _ in sorted_players]
    total = sum(ratings)

    best_diff = float("inf")
    best_weak_indices: list[int] = list(range(half))

    if n <= 22:
        for weak_idx in combinations(range(n), half):
            weak_rating = sum(ratings[i] for i in weak_idx)
            diff = abs(total - 2 * weak_rating)
            if diff < best_diff:
                best_diff = diff
                best_weak_indices = list(weak_idx)
    else:
        best_weak_indices = list(range(0, n, 2))[:half]

    team_a = [ids[i] for i in best_weak_indices]
    team_b = [ids[i] for i in range(n) if i not in set(best_weak_indices)]
    if odd_player_id is not None:
        team_b.append(odd_player_id)
    return team_a, team_b


# ============================================================
# RATING HELPERS
# ============================================================

def _elo_update(rating: float, opp_avg: float, won: bool, drew: bool = False, k: float = ELO_K) -> float:
    expected = 1.0 / (1.0 + 10 ** ((opp_avg - rating) / 400.0))
    actual = 0.5 if drew else (1.0 if won else 0.0)
    return round(rating + k * (actual - expected), 2)


def _recompute_global_rating(conn: sqlite3.Connection, user_id: int) -> None:
    """Recompute global_rating as attendance-weighted average of all league ratings."""
    rows = conn.execute(
        "SELECT rating, attendance FROM league_player_stats WHERE user_id = ? AND attendance > 0",
        (user_id,),
    ).fetchall()
    if not rows:
        return
    total_att = sum(int(r["attendance"]) for r in rows)
    if total_att == 0:
        return
    weighted = sum(float(r["rating"]) * int(r["attendance"]) for r in rows) / total_att
    conn.execute(
        "UPDATE users SET global_rating = ?, updated_at = ? WHERE id = ?",
        (round(weighted, 2), utc_now_iso(), user_id),
    )


def _create_notification(conn: sqlite3.Connection, user_id: int, notif_type: str, title: str, message: str, data: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO notifications (user_id, notif_type, title, message, data_json, read, created_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
        (user_id, notif_type, title, message, json.dumps(data or {}, ensure_ascii=False), utc_now_iso()),
    )


def _notify_league_members(conn: sqlite3.Connection, league_id: int, notif_type: str, title: str, message: str, data: dict | None = None, exclude_user_id: int | None = None) -> None:
    rows = conn.execute(
        "SELECT user_id FROM league_memberships WHERE league_id = ?",
        (league_id,),
    ).fetchall()
    for row in rows:
        uid = int(row["user_id"])
        if uid == exclude_user_id:
            continue
        _create_notification(conn, uid, notif_type, title, message, data)


def _advance_waitlist(conn: sqlite3.Connection, match_id: int) -> None:
    """Move next offered/waitlisted player into a vacant spot or send offer."""
    match = conn.execute("SELECT max_participants, status FROM matches WHERE id = ?", (match_id,)).fetchone()
    if match is None or str(match["status"]) not in {"registration_open", "upcoming"}:
        return

    registered_count = conn.execute(
        "SELECT COUNT(*) AS n FROM match_registrations WHERE match_id = ? AND status = 'registered'",
        (match_id,),
    ).fetchone()["n"]

    if int(registered_count) >= int(match["max_participants"]):
        return  # still full

    # Expire stale offers (>15 minutes old)
    cutoff = (utc_now() - timedelta(minutes=WAITLIST_OFFER_MINUTES)).isoformat()
    conn.execute(
        """
        UPDATE match_registrations
        SET status = 'waitlisted', offered_at = NULL
        WHERE match_id = ? AND status = 'offered' AND offered_at < ?
        """,
        (match_id, cutoff),
    )

    # Already has an active offer?
    active_offer = conn.execute(
        "SELECT id FROM match_registrations WHERE match_id = ? AND status = 'offered'",
        (match_id,),
    ).fetchone()
    if active_offer:
        return

    # Pick next in waitlist by earliest position
    next_wait = conn.execute(
        """
        SELECT mr.id, mr.user_id, mr.position
        FROM match_registrations AS mr
        WHERE mr.match_id = ? AND mr.status = 'waitlisted'
        ORDER BY mr.position
        LIMIT 1
        """,
        (match_id,),
    ).fetchone()
    if next_wait is None:
        return

    conn.execute(
        "UPDATE match_registrations SET status = 'offered', offered_at = ? WHERE id = ?",
        (utc_now_iso(), int(next_wait["id"])),
    )
    match_row = conn.execute(
        "SELECT title, scheduled_at FROM matches WHERE id = ?", (match_id,)
    ).fetchone()
    expires_str = (utc_now() + timedelta(minutes=WAITLIST_OFFER_MINUTES)).strftime("%H:%M")
    _create_notification(
        conn,
        int(next_wait["user_id"]),
        "waitlist_offer",
        "Spot available!",
        f"A spot opened up in '{match_row['title']}'. Register by {expires_str} or the next person will be offered.",
        {"match_id": match_id},
    )


def _apply_match_stats(conn: sqlite3.Connection, match_id: int) -> None:
    """Update league_player_stats and global ratings after match confirmation."""
    match = conn.execute(
        "SELECT league_id, team_a, team_b, score_a, score_b FROM matches WHERE id = ?",
        (match_id,),
    ).fetchone()
    if match is None:
        return

    team_a_ids: list[int] = json.loads(match["team_a"])
    team_b_ids: list[int] = json.loads(match["team_b"])
    score_a = int(match["score_a"])
    score_b = int(match["score_b"])
    league_id = int(match["league_id"])

    if not team_a_ids and not team_b_ids:
        return

    def avg_rating(ids: list[int]) -> float:
        if not ids:
            return DEFAULT_GLOBAL_RATING
        rows = conn.execute(
            f"SELECT rating FROM league_player_stats WHERE league_id = ? AND user_id IN ({','.join('?' * len(ids))})",
            [league_id] + ids,
        ).fetchall()
        ratings = [float(r["rating"]) for r in rows]
        return sum(ratings) / len(ratings) if ratings else DEFAULT_GLOBAL_RATING

    avg_a = avg_rating(team_a_ids)
    avg_b = avg_rating(team_b_ids)
    a_won = score_a > score_b
    b_won = score_b > score_a
    drew = score_a == score_b

    events = conn.execute(
        "SELECT event_type, user_id, team FROM match_events WHERE match_id = ? AND undone = 0",
        (match_id,),
    ).fetchall()

    goals_by_player: dict[int, int] = {}
    assists_by_player: dict[int, int] = {}
    for ev in events:
        uid = ev["user_id"]
        if uid is None:
            continue
        uid = int(uid)
        if ev["event_type"] == "goal":
            goals_by_player[uid] = goals_by_player.get(uid, 0) + 1
        elif ev["event_type"] == "assist":
            assists_by_player[uid] = assists_by_player.get(uid, 0) + 1

    all_participants = [(uid, "a") for uid in team_a_ids] + [(uid, "b") for uid in team_b_ids]

    for uid, team in all_participants:
        opp_avg = avg_b if team == "a" else avg_a
        won = (team == "a" and a_won) or (team == "b" and b_won)

        existing = conn.execute(
            "SELECT id, rating, attendance, wins, goals, assists FROM league_player_stats WHERE league_id = ? AND user_id = ?",
            (league_id, uid),
        ).fetchone()

        if existing is None:
            old_rating = DEFAULT_GLOBAL_RATING
            new_rating = _elo_update(old_rating, opp_avg, won, drew)
            conn.execute(
                """
                INSERT INTO league_player_stats (league_id, user_id, attendance, wins, goals, assists, rating)
                VALUES (?, ?, 1, ?, ?, ?, ?)
                """,
                (league_id, uid, 1 if won else 0, goals_by_player.get(uid, 0), assists_by_player.get(uid, 0), new_rating),
            )
        else:
            old_rating = float(existing["rating"])
            new_rating = _elo_update(old_rating, opp_avg, won, drew)
            conn.execute(
                """
                UPDATE league_player_stats
                SET attendance = attendance + 1,
                    wins = wins + ?,
                    goals = goals + ?,
                    assists = assists + ?,
                    rating = ?
                WHERE id = ?
                """,
                (1 if won else 0, goals_by_player.get(uid, 0), assists_by_player.get(uid, 0), new_rating, int(existing["id"])),
            )

        # Update global user stats too
        conn.execute(
            """
            UPDATE users SET
                attendance = attendance + 1,
                wins = wins + ?,
                goals = goals + ?,
                assists = assists + ?,
                updated_at = ?
            WHERE id = ?
            """,
            (1 if won else 0, goals_by_player.get(uid, 0), assists_by_player.get(uid, 0), utc_now_iso(), uid),
        )
        _recompute_global_rating(conn, uid)


# ============================================================
# MATCH SERIALIZERS
# ============================================================

def _serialize_match(row: sqlite3.Row, my_registration_status: str | None = None) -> MatchOut:
    return MatchOut(
        id=int(row["id"]),
        league_id=int(row["league_id"]),
        title=str(row["title"]),
        location=row["location"],
        scheduled_at=str(row["scheduled_at"]),
        registration_opens_at=row["registration_opens_at"],
        max_participants=int(row["max_participants"]),
        notes=row["notes"],
        status=str(row["status"]),
        registered_count=int(row["registered_count"]),
        waitlisted_count=int(row["waitlisted_count"]),
        my_registration_status=my_registration_status,
        team_a=json.loads(str(row["team_a"] or "[]")),
        team_b=json.loads(str(row["team_b"] or "[]")),
        score_a=int(row["score_a"]),
        score_b=int(row["score_b"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        created_by_username=str(row["created_by_username"]),
        created_at=str(row["created_at"]),
        preview_token=str(row["preview_token"] or ""),
    )


def _fetch_match_row(conn: sqlite3.Connection, match_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT m.*,
            u.username AS created_by_username,
            (SELECT COUNT(*) FROM match_registrations WHERE match_id = m.id AND status = 'registered') AS registered_count,
            (SELECT COUNT(*) FROM match_registrations WHERE match_id = m.id AND status IN ('waitlisted','offered')) AS waitlisted_count
        FROM matches AS m
        JOIN users AS u ON u.id = m.created_by
        WHERE m.id = ?
        """,
        (match_id,),
    ).fetchone()


def _fetch_league_matches(conn: sqlite3.Connection, league_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT m.*,
            u.username AS created_by_username,
            (SELECT COUNT(*) FROM match_registrations WHERE match_id = m.id AND status = 'registered') AS registered_count,
            (SELECT COUNT(*) FROM match_registrations WHERE match_id = m.id AND status IN ('waitlisted','offered')) AS waitlisted_count
        FROM matches AS m
        JOIN users AS u ON u.id = m.created_by
        WHERE m.league_id = ?
        ORDER BY m.scheduled_at DESC
        """,
        (league_id,),
    ).fetchall()


def _auto_open_registration(conn: sqlite3.Connection, match_id: int) -> None:
    """Auto-transition match to registration_open if reg time has passed."""
    match = conn.execute(
        "SELECT status, registration_opens_at FROM matches WHERE id = ?",
        (match_id,),
    ).fetchone()
    if match is None or str(match["status"]) != "upcoming":
        return
    reg_opens = match["registration_opens_at"]
    if reg_opens is None:
        return
    if utc_now() >= datetime.fromisoformat(str(reg_opens)):
        conn.execute(
            "UPDATE matches SET status = 'registration_open', updated_at = ? WHERE id = ?",
            (utc_now_iso(), match_id),
        )


def _match_registration_status(conn: sqlite3.Connection, match_id: int, user_id: int) -> str | None:
    row = conn.execute(
        "SELECT status FROM match_registrations WHERE match_id = ? AND user_id = ?",
        (match_id, user_id),
    ).fetchone()
    return str(row["status"]) if row else None


# ============================================================
# MATCH ENDPOINTS
# ============================================================

@app.post("/leagues/{league_id}/matches", response_model=MatchOut, status_code=status.HTTP_201_CREATED)
def create_match(league_id: int, payload: MatchCreatePayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchOut:
    created_at = utc_now_iso()
    user_id = int(current_user["id"])
    with get_conn() as conn:
        require_league_manager(conn, league_id, user_id)
        cursor = conn.execute(
            """
            INSERT INTO matches (league_id, title, location, scheduled_at, registration_opens_at,
                                 max_participants, notes, status, team_a, team_b, score_a, score_b,
                                 created_by, created_at, updated_at, preview_token)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'upcoming', '[]', '[]', 0, 0, ?, ?, ?, ?)
            """,
            (
                league_id,
                payload.title.strip(),
                payload.location.strip() if payload.location else None,
                payload.scheduled_at.strip(),
                payload.registration_opens_at.strip() if payload.registration_opens_at else None,
                payload.max_participants,
                payload.notes.strip() if payload.notes else None,
                user_id,
                created_at,
                created_at,
                secrets.token_urlsafe(16),
            ),
        )
        match_id = cursor.lastrowid
        conn.commit()

        # Notify all league members
        league = conn.execute("SELECT name FROM leagues WHERE id = ?", (league_id,)).fetchone()
        _notify_league_members(
            conn, league_id, "new_match",
            f"New match: {payload.title}",
            f"A new match has been scheduled in {league['name']}: {payload.title} at {payload.scheduled_at[:16].replace('T', ' ')}",
            {"match_id": match_id},
            exclude_user_id=user_id,
        )
        conn.commit()

        row = _fetch_match_row(conn, int(match_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load match")
    return _serialize_match(row)


@app.get("/leagues/{league_id}/matches", response_model=list[MatchOut])
def list_league_matches(league_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> list[MatchOut]:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        require_membership(conn, league_id, user_id)
        rows = _fetch_league_matches(conn, league_id)
        result = []
        for row in rows:
            _auto_open_registration(conn, int(row["id"]))
            _advance_waitlist(conn, int(row["id"]))
            my_status = _match_registration_status(conn, int(row["id"]), user_id)
            refreshed = _fetch_match_row(conn, int(row["id"]))
            if refreshed:
                result.append(_serialize_match(refreshed, my_status))
        conn.commit()
    return result


@app.get("/matches/{match_id}", response_model=MatchDetailOut)
def get_match_detail(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchDetailOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_membership(conn, int(row["league_id"]), user_id)
        _auto_open_registration(conn, match_id)
        _advance_waitlist(conn, match_id)
        conn.commit()
        row = _fetch_match_row(conn, match_id)
        my_status = _match_registration_status(conn, match_id, user_id)

        reg_rows = conn.execute(
            """
            SELECT mr.user_id, u.username, u.display_name, mr.status, mr.registered_at, mr.position
            FROM match_registrations AS mr
            JOIN users AS u ON u.id = mr.user_id
            WHERE mr.match_id = ? AND mr.status IN ('registered','waitlisted','offered')
            ORDER BY CASE mr.status WHEN 'registered' THEN 0 ELSE 1 END, mr.position
            """,
            (match_id,),
        ).fetchall()

        event_rows = conn.execute(
            """
            SELECT me.id, me.event_type, me.user_id, u.username, me.team, me.event_seconds, me.created_at, me.undone
            FROM match_events AS me
            LEFT JOIN users AS u ON u.id = me.user_id
            WHERE me.match_id = ?
            ORDER BY me.event_seconds, me.created_at
            """,
            (match_id,),
        ).fetchall()

    regs = [
        MatchRegistrationOut(
            user_id=int(r["user_id"]),
            username=str(r["username"]),
            display_name=r["display_name"],
            status=str(r["status"]),
            registered_at=str(r["registered_at"]),
            position=int(r["position"]),
        )
        for r in reg_rows
    ]
    events = [
        MatchEventOut(
            id=int(e["id"]),
            event_type=str(e["event_type"]),
            user_id=e["user_id"],
            username=e["username"],
            team=e["team"],
            event_seconds=int(e["event_seconds"]),
            created_at=str(e["created_at"]),
            undone=bool(int(e["undone"])),
        )
        for e in event_rows
    ]
    return MatchDetailOut(match=_serialize_match(row, my_status), registrations=regs, events=events)


@app.get("/preview/matches/{preview_token}", response_model=MatchDetailOut)
def get_match_detail_preview(preview_token: str) -> MatchDetailOut:
    """Public, read-only live preview for sharing match results/stats without auth."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT m.*,
                u.username AS created_by_username,
                (SELECT COUNT(*) FROM match_registrations WHERE match_id = m.id AND status = 'registered') AS registered_count,
                (SELECT COUNT(*) FROM match_registrations WHERE match_id = m.id AND status IN ('waitlisted','offered')) AS waitlisted_count
            FROM matches AS m
            JOIN users AS u ON u.id = m.created_by
            WHERE m.preview_token = ?
            """,
            (preview_token,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview link not found")

        match_id = int(row["id"])
        _auto_open_registration(conn, match_id)
        _advance_waitlist(conn, match_id)
        conn.commit()
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

        reg_rows = conn.execute(
            """
            SELECT mr.user_id, u.username, u.display_name, mr.status, mr.registered_at, mr.position
            FROM match_registrations AS mr
            JOIN users AS u ON u.id = mr.user_id
            WHERE mr.match_id = ? AND mr.status IN ('registered','waitlisted','offered')
            ORDER BY CASE mr.status WHEN 'registered' THEN 0 ELSE 1 END, mr.position
            """,
            (match_id,),
        ).fetchall()

        event_rows = conn.execute(
            """
            SELECT me.id, me.event_type, me.user_id, u.username, me.team, me.event_seconds, me.created_at, me.undone
            FROM match_events AS me
            LEFT JOIN users AS u ON u.id = me.user_id
            WHERE me.match_id = ?
            ORDER BY me.event_seconds, me.created_at
            """,
            (match_id,),
        ).fetchall()

    regs = [
        MatchRegistrationOut(
            user_id=int(r["user_id"]),
            username=str(r["username"]),
            display_name=r["display_name"],
            status=str(r["status"]),
            registered_at=str(r["registered_at"]),
            position=int(r["position"]),
        )
        for r in reg_rows
    ]
    events = [
        MatchEventOut(
            id=int(e["id"]),
            event_type=str(e["event_type"]),
            user_id=e["user_id"],
            username=e["username"],
            team=e["team"],
            event_seconds=int(e["event_seconds"]),
            created_at=str(e["created_at"]),
            undone=bool(int(e["undone"])),
        )
        for e in event_rows
    ]
    return MatchDetailOut(match=_serialize_match(row, None), registrations=regs, events=events)


@app.post("/matches/{match_id}/open-registration", response_model=MessageOut)
def open_match_registration(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        if str(row["status"]) not in {"upcoming"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match is not in upcoming state")
        conn.execute(
            "UPDATE matches SET status = 'registration_open', updated_at = ? WHERE id = ?",
            (utc_now_iso(), match_id),
        )
        conn.commit()
    return MessageOut(detail="Registration opened.")


@app.post("/matches/{match_id}/register", response_model=MessageOut)
def register_for_match(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_membership(conn, int(row["league_id"]), user_id)
        _auto_open_registration(conn, match_id)
        row = _fetch_match_row(conn, match_id)
        if str(row["status"]) not in {"registration_open"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registration is not open")

        existing = conn.execute(
            "SELECT id, status FROM match_registrations WHERE match_id = ? AND user_id = ?",
            (match_id, user_id),
        ).fetchone()

        if existing is not None:
            if str(existing["status"]) in {"registered", "offered"}:
                # Accepting an offer promotes to registered
                conn.execute(
                    "UPDATE match_registrations SET status = 'registered', offered_at = NULL WHERE id = ?",
                    (int(existing["id"]),),
                )
                conn.commit()
                return MessageOut(detail="You are now registered for the match.")
            elif str(existing["status"]) == "waitlisted":
                return MessageOut(detail="You are already on the waiting list.")
            elif str(existing["status"]) == "cancelled":
                pass  # re-register below
            else:
                return MessageOut(detail="Already registered.")

        registered_count = int(row["registered_count"])
        now_iso = utc_now_iso()

        if registered_count < int(row["max_participants"]):
            if existing is not None:
                conn.execute("UPDATE match_registrations SET status = 'registered', registered_at = ? WHERE id = ?", (now_iso, int(existing["id"])))
            else:
                pos = registered_count + 1
                conn.execute(
                    "INSERT INTO match_registrations (match_id, user_id, status, position, registered_at) VALUES (?, ?, 'registered', ?, ?)",
                    (match_id, user_id, pos, now_iso),
                )
            conn.commit()
            return MessageOut(detail="You are registered for the match.")
        else:
            waitlisted_count = int(row["waitlisted_count"])
            pos = int(row["max_participants"]) + waitlisted_count + 1
            if existing is not None:
                conn.execute("UPDATE match_registrations SET status = 'waitlisted', registered_at = ?, position = ?, offered_at = NULL WHERE id = ?", (now_iso, pos, int(existing["id"])))
            else:
                conn.execute(
                    "INSERT INTO match_registrations (match_id, user_id, status, position, registered_at) VALUES (?, ?, 'waitlisted', ?, ?)",
                    (match_id, user_id, pos, now_iso),
                )
            conn.commit()
            return MessageOut(detail=f"Match is full. You are on the waiting list at position {waitlisted_count + 1}.")


@app.delete("/matches/{match_id}/register", response_model=MessageOut)
def cancel_match_registration(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_membership(conn, int(row["league_id"]), user_id)

        # Enforce 1-hour cutoff
        scheduled = datetime.fromisoformat(str(row["scheduled_at"]))
        if utc_now() > scheduled - timedelta(hours=1):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registration cannot be cancelled within 1 hour of match start")

        existing = conn.execute(
            "SELECT id, status FROM match_registrations WHERE match_id = ? AND user_id = ?",
            (match_id, user_id),
        ).fetchone()
        if existing is None or str(existing["status"]) == "cancelled":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active registration found")

        was_registered = str(existing["status"]) == "registered"
        conn.execute("UPDATE match_registrations SET status = 'cancelled' WHERE id = ?", (int(existing["id"]),))
        conn.commit()

        if was_registered:
            _advance_waitlist(conn, match_id)
            conn.commit()

    return MessageOut(detail="Registration cancelled.")


@app.post("/matches/{match_id}/generate-teams", response_model=MatchDetailOut)
def generate_match_teams(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchDetailOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        if str(row["status"]) not in {"registration_open", "upcoming"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Teams can only be generated before match starts")

        registered = conn.execute(
            "SELECT user_id FROM match_registrations WHERE match_id = ? AND status = 'registered'",
            (match_id,),
        ).fetchall()
        participant_ids = [int(r["user_id"]) for r in registered]

        league_id = int(row["league_id"])
        player_ratings: list[tuple[int, float]] = []
        for pid in participant_ids:
            lps = conn.execute(
                "SELECT rating FROM league_player_stats WHERE league_id = ? AND user_id = ?",
                (league_id, pid),
            ).fetchone()
            rating = float(lps["rating"]) if lps else DEFAULT_GLOBAL_RATING
            player_ratings.append((pid, rating))

        team_a, team_b = _generate_two_teams(player_ratings)
        conn.execute(
            "UPDATE matches SET team_a = ?, team_b = ?, updated_at = ? WHERE id = ?",
            (json.dumps(team_a), json.dumps(team_b), utc_now_iso(), match_id),
        )
        conn.commit()

    return get_match_detail(match_id, current_user)


@app.post("/matches/{match_id}/start", response_model=MatchDetailOut)
def start_match(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchDetailOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        if str(row["status"]) not in {"registration_open", "upcoming"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match cannot be started in its current state")

        # Auto-generate teams if not yet done
        team_a = json.loads(str(row["team_a"] or "[]"))
        team_b = json.loads(str(row["team_b"] or "[]"))
        if not team_a and not team_b:
            registered = conn.execute(
                "SELECT user_id FROM match_registrations WHERE match_id = ? AND status = 'registered'",
                (match_id,),
            ).fetchall()
            participant_ids = [int(r["user_id"]) for r in registered]
            league_id = int(row["league_id"])
            player_ratings: list[tuple[int, float]] = []
            for pid in participant_ids:
                lps = conn.execute(
                    "SELECT rating FROM league_player_stats WHERE league_id = ? AND user_id = ?",
                    (league_id, pid),
                ).fetchone()
                rating = float(lps["rating"]) if lps else DEFAULT_GLOBAL_RATING
                player_ratings.append((pid, rating))
            team_a, team_b = _generate_two_teams(player_ratings)

        conn.execute(
            "UPDATE matches SET status = 'live', team_a = ?, team_b = ?, started_at = ?, updated_at = ? WHERE id = ?",
            (json.dumps(team_a), json.dumps(team_b), utc_now_iso(), utc_now_iso(), match_id),
        )
        conn.commit()

    return get_match_detail(match_id, current_user)


@app.post("/matches/{match_id}/events", response_model=MatchEventOut, status_code=status.HTTP_201_CREATED)
def add_match_goal(match_id: int, payload: GoalEventPayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchEventOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        if str(row["status"]) != "live":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match is not live")

        started_at = row["started_at"]
        if started_at is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match has no start time")
        elapsed_seconds = int((utc_now() - datetime.fromisoformat(str(started_at))).total_seconds())
        now_iso = utc_now_iso()

        # Add goal
        cursor = conn.execute(
            "INSERT INTO match_events (match_id, event_type, user_id, team, event_seconds, created_at, undone) VALUES (?, 'goal', ?, ?, ?, ?, 0)",
            (match_id, payload.scorer_user_id, payload.team, elapsed_seconds, now_iso),
        )
        goal_event_id = cursor.lastrowid

        # Update score
        if payload.team == "a":
            conn.execute("UPDATE matches SET score_a = score_a + 1, updated_at = ? WHERE id = ?", (now_iso, match_id))
        else:
            conn.execute("UPDATE matches SET score_b = score_b + 1, updated_at = ? WHERE id = ?", (now_iso, match_id))

        # Add assist if provided
        if payload.assist_user_id is not None:
            conn.execute(
                "INSERT INTO match_events (match_id, event_type, user_id, team, event_seconds, created_at, undone) VALUES (?, 'assist', ?, ?, ?, ?, 0)",
                (match_id, payload.assist_user_id, payload.team, elapsed_seconds, now_iso),
            )

        conn.commit()

        scorer_username = conn.execute("SELECT username FROM users WHERE id = ?", (payload.scorer_user_id,)).fetchone()
        return MatchEventOut(
            id=int(goal_event_id),
            event_type="goal",
            user_id=payload.scorer_user_id,
            username=scorer_username["username"] if scorer_username else None,
            team=payload.team,
            event_seconds=elapsed_seconds,
            created_at=now_iso,
            undone=False,
        )


@app.delete("/matches/{match_id}/events/{event_id}", response_model=MessageOut)
def undo_match_event(match_id: int, event_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)

        event = conn.execute(
            "SELECT id, event_type, team, created_at, undone FROM match_events WHERE id = ? AND match_id = ?",
            (event_id, match_id),
        ).fetchone()
        if event is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if int(event["undone"]) == 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Event already undone")

        created_dt = datetime.fromisoformat(str(event["created_at"]))
        if (utc_now() - created_dt).total_seconds() > UNDO_WINDOW_SECONDS:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Undo window has passed (30 seconds)")

        conn.execute("UPDATE match_events SET undone = 1 WHERE id = ?", (event_id,))
        if str(event["event_type"]) == "goal":
            if str(event["team"]) == "a":
                conn.execute("UPDATE matches SET score_a = MAX(0, score_a - 1) WHERE id = ?", (match_id,))
            else:
                conn.execute("UPDATE matches SET score_b = MAX(0, score_b - 1) WHERE id = ?", (match_id,))
        conn.commit()
    return MessageOut(detail="Event undone.")


@app.post("/matches/{match_id}/finish", response_model=MatchDetailOut)
def finish_match(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchDetailOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        if str(row["status"]) != "live":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match is not live")
        conn.execute(
            "UPDATE matches SET status = 'finished', ended_at = ?, updated_at = ? WHERE id = ?",
            (utc_now_iso(), utc_now_iso(), match_id),
        )
        conn.commit()
    return get_match_detail(match_id, current_user)


@app.post("/matches/{match_id}/confirm", response_model=MessageOut)
def confirm_match(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        if str(row["status"]) != "finished":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match must be in finished state to confirm")

        _apply_match_stats(conn, match_id)
        conn.execute(
            "UPDATE matches SET status = 'completed', updated_at = ? WHERE id = ?",
            (utc_now_iso(), match_id),
        )

        match_title = str(row["title"])
        score_a = int(row["score_a"])
        score_b = int(row["score_b"])
        _notify_league_members(
            conn, int(row["league_id"]), "match_result",
            f"Match result: {match_title}",
            f"The match '{match_title}' has ended: Team A {score_a} – {score_b} Team B. Ratings updated.",
            {"match_id": match_id},
        )
        conn.commit()
    return MessageOut(detail="Match confirmed. Stats and ratings updated.")


@app.post("/matches/{match_id}/cancel", response_model=MessageOut)
def cancel_match(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        if str(row["status"]) in {"completed"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed matches cannot be cancelled")
        conn.execute(
            "UPDATE matches SET status = 'cancelled', updated_at = ? WHERE id = ?",
            (utc_now_iso(), match_id),
        )
        _notify_league_members(
            conn, int(row["league_id"]), "match_cancelled",
            f"Match cancelled: {row['title']}",
            f"The match '{row['title']}' has been cancelled.",
            {"match_id": match_id},
            exclude_user_id=user_id,
        )
        conn.commit()
    return MessageOut(detail="Match cancelled.")


# ============================================================
# NOTIFICATION ENDPOINTS
# ============================================================

@app.get("/notifications", response_model=list[NotificationOut])
def get_notifications(current_user: sqlite3.Row = Depends(resolve_current_user)) -> list[NotificationOut]:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, notif_type, title, message, data_json, read, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        ).fetchall()
    return [
        NotificationOut(
            id=int(r["id"]),
            notif_type=str(r["notif_type"]),
            title=str(r["title"]),
            message=str(r["message"]),
            data=json.loads(str(r["data_json"] or "{}")),
            read=bool(int(r["read"])),
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


@app.get("/notifications/unread-count")
def get_unread_count(current_user: sqlite3.Row = Depends(resolve_current_user)) -> dict[str, int]:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND read = 0",
            (user_id,),
        ).fetchone()["n"]
    return {"count": int(count)}


@app.patch("/notifications/read-all", response_model=MessageOut)
def mark_notifications_read(current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        conn.execute("UPDATE notifications SET read = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    return MessageOut(detail="All notifications marked as read.")
