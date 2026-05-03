import hashlib
import hmac
import json
import math
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

try:
    import numpy as np
except Exception:
    np = None


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
        "http://localhost:8000,http://127.0.0.1:8000,https://xeroxandarian.github.io,null",
    ).split(",")
    if origin.strip()
]

# Initial admin account seed. Change these via environment variables in production.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "rstadmin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@rstrating.local")
BACKDOOR_PIN = os.getenv("BACKDOOR_PIN", "rst2024")
ENABLE_SAMPLE_MATCHES = os.getenv("ENABLE_SAMPLE_MATCHES", "0") == "1"

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
    recovery_id: str | None = None
    recovery_token: str | None = None
    role: str
    is_active: bool = True
    terminated_at: str | None = None
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
    email: str | None = Field(default=None, max_length=255)
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
    email: str | None = Field(default=None, max_length=255)
    recovery_id: str | None = Field(default=None, min_length=6, max_length=32)
    recovery_token: str | None = Field(default=None, min_length=19, max_length=19)


class PasswordResetPayload(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    recovery_id: str | None = Field(default=None, min_length=6, max_length=32)
    recovery_token: str | None = Field(default=None, min_length=19, max_length=19)
    token: str = Field(min_length=32, max_length=128)
    new_password: str = Field(min_length=6, max_length=200)


class AdminPasswordResetPayload(BaseModel):
    new_password: str | None = Field(default=None, min_length=6, max_length=200)


class AdminPasswordResetOut(BaseModel):
    detail: str
    password: str


class LeagueApprovalPayload(BaseModel):
    status: str = Field(pattern=r"^(approved|rejected)$")
    note: str | None = Field(default=None, max_length=300)


class AdminUserOut(BaseModel):
    id: int
    username: str
    email: str
    display_name: str | None
    role: str
    recovery_id: str | None
    recovery_token: str | None
    is_active: bool
    terminated_at: str | None
    created_at: str
    updated_at: str
    attendance: int
    wins: int
    goals: int
    assists: int
    global_rating: float
    league_count: int
    owned_league_count: int


class AdminLeagueOut(BaseModel):
    id: int
    name: str
    football_type: str
    goal_size: str
    region: str
    description: str | None
    owner_id: int
    owner_username: str
    member_count: int
    approval_status: str
    approved_at: str | None
    approval_note: str | None
    terminated_until: str | None
    is_terminated: bool
    created_at: str
    updated_at: str


class AdminLeagueTemporaryTerminatePayload(BaseModel):
    until: str = Field(description="ISO datetime when temporary termination ends")
    note: str | None = Field(default=None, max_length=300)


class AdminLeaguePermanentTerminatePayload(BaseModel):
    confirm: bool = Field(default=False)


class AdminSettingsOut(BaseModel):
    auto_approve_leagues: bool


class AdminSettingsPatchPayload(BaseModel):
    auto_approve_leagues: bool | None = None


class PlayerSettingsOut(BaseModel):
    profile_visibility: str
    friend_request_policy: str


class PlayerSettingsPatchPayload(BaseModel):
    profile_visibility: str | None = Field(default=None, pattern=r"^(public|friends|private)$")
    friend_request_policy: str | None = Field(default=None, pattern=r"^(everyone|shared_leagues|nobody)$")


class PlayerSearchOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    global_rating: float
    is_friend: bool
    has_pending_outgoing_request: bool
    has_pending_incoming_request: bool
    is_following: bool


class PlayerLeagueStatsOut(BaseModel):
    league_id: int
    league_name: str
    attendance: int
    wins: int
    goals: int
    assists: int
    rating: float


class PlayerProfileOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    global_rating: float
    global_position: int
    attendance: int
    wins: int
    goals: int
    assists: int
    profile_visibility: str
    can_view_stats: bool
    is_friend: bool
    is_following: bool
    can_send_friend_request: bool
    has_pending_outgoing_request: bool
    has_pending_incoming_request: bool
    league_stats: list[PlayerLeagueStatsOut]


class FriendRequestCreatePayload(BaseModel):
    message: str | None = Field(default=None, max_length=300)


class FriendRequestOut(BaseModel):
    id: int
    from_user_id: int
    from_username: str
    from_display_name: str | None
    to_user_id: int
    to_username: str
    to_display_name: str | None
    status: str
    message: str | None
    created_at: str
    updated_at: str


class FriendRequestsResponseOut(BaseModel):
    incoming: list[FriendRequestOut]
    outgoing: list[FriendRequestOut]


class FollowStateOut(BaseModel):
    following: bool


class FanclubMemberOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    global_rating: float


class LeagueCreatePayload(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    football_type: str = Field(pattern=r"^(outdoor|indoor)$")
    goal_size: str = Field(pattern=r"^(small|medium|large)$")
    region: str = Field(min_length=2, max_length=64)
    league_visibility: str = Field(default="public", pattern=r"^(public|private)$")
    discover_visible: bool = Field(default=True)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    description: str | None = Field(default=None, max_length=300)
    fee_type: str = Field(default="none", pattern=r"^(none|yearly|monthly|per_attendance)$")
    fee_value: float | None = Field(default=None, ge=0)
    match_presets: list[dict] = Field(default_factory=list)
    rating_config: dict = Field(default_factory=dict)


class LeagueSettingsPayload(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    region: str | None = Field(default=None, min_length=2, max_length=64)
    league_visibility: str | None = Field(default=None, pattern=r"^(public|private)$")
    discover_visible: bool | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    football_type: str | None = Field(default=None, pattern=r"^(outdoor|indoor)$")
    goal_size: str | None = Field(default=None, pattern=r"^(small|medium|large)$")
    auto_accept_members: bool | None = None
    fee_type: str | None = Field(default=None, pattern=r"^(none|yearly|monthly|per_attendance)$")
    fee_value: float | None = Field(default=None, ge=0)
    match_presets: list[dict] | None = None
    rating_config: dict | None = None


class LeagueBanPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class UpdateProfilePayload(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=100)
    surname: str | None = Field(default=None, max_length=100)


class LeaguePenaltyPayload(BaseModel):
    until: str = Field(description="ISO datetime when penalty expires")
    reason: str | None = Field(default=None, max_length=300)


class LeagueMemberStatusOut(BaseModel):
    user_id: int
    username: str
    display_name: str | None = None
    is_banned: bool
    penalty_until: str | None
    penalty_reason: str | None


class LeagueDisciplineHistoryOut(BaseModel):
    id: int
    user_id: int
    action: str
    reason: str | None
    penalty_until: str | None
    created_at: str
    actor_username: str | None
    actor_display_name: str | None


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
    league_visibility: str
    discover_visible: bool
    latitude: float | None
    longitude: float | None
    invite_code: str
    description: str | None
    owner_id: int
    owner_username: str
    member_role: str
    member_count: int
    created_at: str
    auto_accept_members: bool
    fee_type: str
    fee_value: float
    match_presets: list[dict]
    rating_config: dict
    approval_status: str = "approved"
    approved_at: str | None = None
    approval_note: str | None = None


class LeagueInviteOut(BaseModel):
    id: int
    league_id: int
    league_name: str
    token: str
    creator_username: str | None = None
    accepted_by_username: str | None = None
    created_at: str
    expires_at: str | None
    max_uses: int
    use_count: int
    revoked: int
    expired: bool = False
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
    penalty_until: str | None = None
    penalty_reason: str | None = None


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


class PasswordResetRequestOut(BaseModel):
    detail: str
    token: str
    expires_at: str
    note: str


# ====================== MATCH MANAGEMENT MODELS ======================

MATCH_STATUS = frozenset({"upcoming", "registration_open", "registration_closed", "live", "finished", "completed", "cancelled"})
ELO_K = 32.0
WAITLIST_OFFER_MINUTES = 15
TEMP_LMMR_MATCH_LIMIT = 10
UNDO_WINDOW_SECONDS = 30
DEFAULT_RATING_CONFIG = {
    "sr_start_points": 1000.0,
    "sr_goal_points": 10.0,
    "sr_assist_points": 6.0,
    "sr_own_goal_points": -2.0,
    "sr_win_points": 20.0,
    "sr_draw_points": 0.0,
    "sr_loss_points": -20.0,
}


class MatchCreatePayload(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    scheduled_at: str = Field(min_length=10, max_length=40)
    registration_opens_at: str | None = Field(default=None, max_length=40)
    max_participants: int = Field(default=20, ge=2, le=200)
    notes: str | None = Field(default=None, max_length=1000)
    visibility: str = Field(default="public", pattern=r"^(public|private)$")
    cards_enabled: bool = Field(default=True)
    offsides_enabled: bool = Field(default=False)
    corners_enabled: bool = Field(default=False)
    fouls_enabled: bool = Field(default=False)


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
    team_a_name: str
    team_b_name: str
    teams_confirmed: bool
    score_a: int
    score_b: int
    started_at: str | None
    ended_at: str | None
    created_by_username: str
    created_at: str
    preview_token: str
    visibility: str
    cards_enabled: bool
    offsides_enabled: bool
    corners_enabled: bool
    fouls_enabled: bool


class MatchRegistrationOut(BaseModel):
    user_id: int
    username: str
    display_name: str | None
    status: str
    registered_at: str
    position: int
    seasonal_rating: float
    global_rating: float


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


class MatchLiveEventPayload(BaseModel):
    event_type: str = Field(default="goal", pattern=r"^(goal|own_goal|injury|yellow_card|red_card|pause|resume|offside|corner|foul)$")
    team: str | None = Field(default=None, pattern=r"^[ab]$")
    scorer_user_id: int | None = None
    assist_user_id: int | None = None
    own_goal_user_id: int | None = None
    player_user_id: int | None = None
    event_seconds: int | None = Field(default=None, ge=0)


class MatchVisibilityPayload(BaseModel):
    visibility: str = Field(pattern=r"^(public|private)$")


class MatchTeamsDraftPayload(BaseModel):
    team_a: list[int]
    team_b: list[int]
    team_a_name: str | None = Field(default=None, min_length=1, max_length=60)
    team_b_name: str | None = Field(default=None, min_length=1, max_length=60)


class NotificationOut(BaseModel):
    id: int
    notif_type: str
    title: str
    message: str
    data: dict
    read: bool
    created_at: str


class LeagueSeasonOut(BaseModel):
    id: int
    league_id: int
    name: str
    description: str | None = None
    is_active: bool
    start_at: str | None = None
    end_at: str | None = None
    created_at: str


class LeagueSeasonCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    activate: bool = Field(default=False)
    start_at: str | None = Field(default=None, max_length=40)
    end_at: str | None = Field(default=None, max_length=40)


class LeaguePlayerStatsTabRow(BaseModel):
    user_id: int
    username: str
    display_name: str | None
    attendance: int
    wins: int
    goals: int
    own_goals: int
    assists: int
    lmmr: float
    sr_points: float


class LeaguePlayerStatsTabOut(BaseModel):
    key: str
    label: str
    rows: list[LeaguePlayerStatsTabRow]


class LeagueLmmrPlacementResolvePayload(BaseModel):
    final_rating: float = Field(ge=0, le=5000)
    note: str | None = Field(default=None, max_length=300)


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
    if "github.io" in base_origin:
        return f"{base_origin}/RSTRating/invite.html?token={token}"
    return f"{base_origin}/invite.html?token={token}"


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


def get_app_setting(conn: sqlite3.Connection, key: str, default: str) -> str:
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    return str(row["value"])


def set_app_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, utc_now_iso()),
    )


def get_bool_app_setting(conn: sqlite3.Connection, key: str, default: bool = False) -> bool:
    raw = get_app_setting(conn, key, "1" if default else "0")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def infer_football_type(old_sport: str | None) -> str:
    if old_sport is None:
        return "outdoor"
    sport = old_sport.strip().lower()
    if "indoor" in sport:
        return "indoor"
    return "outdoor"


def _generate_recovery_id(conn: sqlite3.Connection) -> str:
    while True:
        digits = "".join(str(secrets.randbelow(10)) for _ in range(16))
        candidate = f"{digits[:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:16]}"
        row = conn.execute("SELECT 1 FROM users WHERE recovery_id = ?", (candidate,)).fetchone()
        if row is None:
            return candidate


def _is_valid_recovery_token(value: str | None) -> bool:
    if not value:
        return False
    s = str(value).strip()
    if len(s) != 19:
        return False
    parts = s.split("-")
    return len(parts) == 4 and all(len(p) == 4 and p.isdigit() for p in parts)


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        set_app_setting(
            conn,
            "auto_approve_leagues",
            get_app_setting(conn, "auto_approve_leagues", "0"),
        )

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
        ensure_column(conn, "users", "recovery_id", "TEXT")
        ensure_column(conn, "users", "is_active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "users", "terminated_at", "TEXT")
        ensure_column(conn, "users", "attendance", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "users", "wins", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "users", "goals", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "users", "assists", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "users", "global_rating", "REAL NOT NULL DEFAULT 1000")
        ensure_column(conn, "users", "profile_visibility", "TEXT NOT NULL DEFAULT 'public'")
        ensure_column(conn, "users", "friend_request_policy", "TEXT NOT NULL DEFAULT 'everyone'")
        conn.execute("UPDATE users SET profile_visibility = 'public' WHERE profile_visibility IS NULL OR profile_visibility = ''")
        conn.execute("UPDATE users SET friend_request_policy = 'everyone' WHERE friend_request_policy IS NULL OR friend_request_policy = ''")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email) WHERE email IS NOT NULL")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_recovery_id_unique ON users(recovery_id) WHERE recovery_id IS NOT NULL")

        users_without_recovery = conn.execute(
            "SELECT id, recovery_id FROM users"
        ).fetchall()
        for row in users_without_recovery:
            rid = str(row["recovery_id"] or "").strip()
            if _is_valid_recovery_token(rid):
                continue
            conn.execute(
                "UPDATE users SET recovery_id = ? WHERE id = ?",
                (_generate_recovery_id(conn), int(row["id"])),
            )

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
                fee_type TEXT NOT NULL DEFAULT 'none',
                fee_value REAL NOT NULL DEFAULT 0,
                match_presets_json TEXT NOT NULL DEFAULT '[]',
                rating_config_json TEXT NOT NULL DEFAULT '{}',
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
        ensure_column(conn, "leagues", "fee_type", "TEXT NOT NULL DEFAULT 'none'")
        ensure_column(conn, "leagues", "fee_value", "REAL NOT NULL DEFAULT 0")
        ensure_column(conn, "leagues", "match_presets_json", "TEXT NOT NULL DEFAULT '[]'")
        ensure_column(conn, "leagues", "rating_config_json", "TEXT NOT NULL DEFAULT '{}' ")
        ensure_column(conn, "leagues", "approval_status", "TEXT NOT NULL DEFAULT 'approved'")
        ensure_column(conn, "leagues", "approved_at", "TEXT")
        ensure_column(conn, "leagues", "approved_by_user_id", "INTEGER")
        ensure_column(conn, "leagues", "approval_note", "TEXT")
        ensure_column(conn, "leagues", "terminated_until", "TEXT")
        ensure_column(conn, "leagues", "termination_note", "TEXT")
        ensure_column(conn, "leagues", "terminated_by_user_id", "INTEGER")
        ensure_column(conn, "leagues", "league_visibility", "TEXT NOT NULL DEFAULT 'public'")
        ensure_column(conn, "leagues", "discover_visible", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "leagues", "latitude", "REAL")
        ensure_column(conn, "leagues", "longitude", "REAL")

        conn.execute("UPDATE leagues SET approval_status = 'approved' WHERE approval_status IS NULL OR approval_status = ''")
        conn.execute("UPDATE leagues SET league_visibility = 'public' WHERE league_visibility IS NULL OR league_visibility = ''")
        conn.execute("UPDATE leagues SET discover_visible = 1 WHERE discover_visible IS NULL")

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

        leagues_missing_cfg = conn.execute(
            "SELECT id, rating_config_json FROM leagues"
        ).fetchall()
        for row in leagues_missing_cfg:
            try:
                parsed = json.loads(str(row["rating_config_json"] or "{}"))
                if not isinstance(parsed, dict):
                    parsed = {}
            except Exception:
                parsed = {}
            merged_cfg = dict(DEFAULT_RATING_CONFIG)
            merged_cfg.update(parsed)
            conn.execute(
                "UPDATE leagues SET rating_config_json = ? WHERE id = ?",
                (json.dumps(merged_cfg), int(row["id"])),
            )

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
        ensure_column(conn, "league_invites", "accepted_by_user_id", "INTEGER")

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
                is_temporary_lmmr INTEGER NOT NULL DEFAULT 0,
                temporary_lmmr_match_limit INTEGER NOT NULL DEFAULT 10,
                UNIQUE(league_id, user_id),
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        ensure_column(conn, "league_player_stats", "is_temporary_lmmr", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "league_player_stats", "temporary_lmmr_match_limit", "INTEGER NOT NULL DEFAULT 10")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS league_lmmr_placements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reason TEXT,
                suggested_rating REAL,
                final_rating REAL,
                note TEXT,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by_user_id INTEGER,
                UNIQUE(league_id, user_id),
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(resolved_by_user_id) REFERENCES users(id) ON DELETE SET NULL
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
        ensure_column(conn, "matches", "team_a_name", "TEXT NOT NULL DEFAULT 'Team A'")
        ensure_column(conn, "matches", "team_b_name", "TEXT NOT NULL DEFAULT 'Team B'")
        ensure_column(conn, "matches", "teams_confirmed", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "matches", "visibility", "TEXT NOT NULL DEFAULT 'public'")
        ensure_column(conn, "matches", "cards_enabled", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "matches", "offsides_enabled", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "matches", "corners_enabled", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "matches", "fouls_enabled", "INTEGER NOT NULL DEFAULT 0")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS league_seasons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 0,
                start_at TEXT,
                end_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE
            )
            """
        )
        ensure_column(conn, "league_seasons", "start_at", "TEXT")
        ensure_column(conn, "league_seasons", "end_at", "TEXT")
        ensure_column(conn, "league_seasons", "description", "TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS league_season_player_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                attendance INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                goals INTEGER NOT NULL DEFAULT 0,
                assists INTEGER NOT NULL DEFAULT 0,
                own_goals INTEGER NOT NULL DEFAULT 0,
                points REAL NOT NULL DEFAULT 1000,
                UNIQUE(season_id, user_id),
                FOREIGN KEY(season_id) REFERENCES league_seasons(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

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
                rating_snapshot_lmmr REAL,
                rating_snapshot_gmmr REAL,
                UNIQUE(match_id, user_id),
                FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        ensure_column(conn, "match_registrations", "rating_snapshot_lmmr", "REAL")
        ensure_column(conn, "match_registrations", "rating_snapshot_gmmr", "REAL")

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

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS friendships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                friend_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, friend_user_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(friend_user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS friend_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(from_user_id, to_user_id),
                FOREIGN KEY(from_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(to_user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_follows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                follower_user_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(follower_user_id, target_user_id),
                FOREIGN KEY(follower_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(target_user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        # auto_accept_members flag on leagues
        ensure_column(conn, "leagues", "auto_accept_members", "INTEGER NOT NULL DEFAULT 1")

        leagues = conn.execute("SELECT id FROM leagues").fetchall()
        for league in leagues:
            existing_active = conn.execute(
                "SELECT id FROM league_seasons WHERE league_id = ? AND is_active = 1 LIMIT 1",
                (int(league["id"]),),
            ).fetchone()
            if existing_active is None:
                conn.execute(
                    "INSERT INTO league_seasons (league_id, name, is_active, start_at, end_at, created_at) VALUES (?, 'Season 1', 1, ?, NULL, ?)",
                    (int(league["id"]), utc_now_iso(), utc_now_iso()),
                )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS league_bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                banned_by INTEGER NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(league_id, user_id),
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(banned_by) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS league_penalties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                penalty_until TEXT NOT NULL,
                reason TEXT,
                imposed_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(league_id, user_id),
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(imposed_by) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS league_discipline_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                penalty_until TEXT,
                actor_user_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(league_id) REFERENCES leagues(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(actor_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )

        conn.commit()


def ensure_admin_account() -> None:
    with get_conn() as conn:
        existing_admin = conn.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        if existing_admin is not None:
            conn.execute(
                "UPDATE users SET is_active = 1, terminated_at = NULL WHERE id = ?",
                (int(existing_admin["id"]),),
            )
            conn.commit()
            return

        existing_username = conn.execute("SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
        created_at = utc_now_iso()
        if existing_username is not None:
            conn.execute(
                """
                UPDATE users
                SET role = 'admin', email = COALESCE(email, ?), name = COALESCE(name, 'Admin'),
                    surname = COALESCE(surname, 'User'), display_name = COALESCE(display_name, 'Administrator'),
                    recovery_id = COALESCE(recovery_id, ?), is_active = 1, terminated_at = NULL, updated_at = ?
                WHERE id = ?
                """,
                (normalize_email(ADMIN_EMAIL), _generate_recovery_id(conn), created_at, existing_username["id"]),
            )
            conn.commit()
            return

        conn.execute(
            """
            INSERT INTO users (username, password_hash, email, name, surname, nicknames, display_name, role,
                               recovery_id, is_active, terminated_at, attendance, wins, goals, assists, global_rating, created_at, updated_at)
            VALUES (?, ?, ?, 'Admin', 'User', '[]', 'Administrator', 'admin',
                    ?, 1, NULL, 0, 0, 0, 0, ?, ?, ?)
            """,
            (
                ADMIN_USERNAME,
                hash_password(ADMIN_PASSWORD),
                normalize_email(ADMIN_EMAIL),
                _generate_recovery_id(conn),
                DEFAULT_GLOBAL_RATING,
                created_at,
                created_at,
            ),
        )
        conn.commit()


def ensure_sample_matches() -> None:
    """Seed richer demo matches and registrations for demo leagues.

    Rules:
    - Demo leagues (with demo% members) should have at least 6 matches.
    - Seeded matches include both past (completed) and future (upcoming/registration_open).
    - Every demo user should be registered for at least one match.
    """
    with get_conn() as conn:
        leagues = conn.execute(
            """
            SELECT l.id, l.name, l.owner_id
            FROM leagues AS l
            WHERE EXISTS (
                SELECT 1
                FROM league_memberships AS lm
                JOIN users AS u ON u.id = lm.user_id
                WHERE lm.league_id = l.id
                  AND LOWER(u.username) LIKE 'demo%'
            )
            ORDER BY l.id
            """
        ).fetchall()
        if not leagues:
            return

        now = utc_now()
        created_at = utc_now_iso()
        seeded_matches = 0

        def create_match(
            league_id: int,
            owner_id: int,
            title: str,
            scheduled_at: str,
            registration_opens_at: str | None,
            status: str,
            score_a: int,
            score_b: int,
            started_at: str | None,
            ended_at: str | None,
            notes: str,
        ) -> int:
            cursor = conn.execute(
                """
                INSERT INTO matches (
                    league_id, title, location, scheduled_at, registration_opens_at,
                    max_participants, notes, status, team_a, team_b, score_a, score_b,
                    started_at, ended_at, created_by, created_at, updated_at, preview_token
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    league_id,
                    title,
                    "Main field",
                    scheduled_at,
                    registration_opens_at,
                    14,
                    notes,
                    status,
                    int(score_a),
                    int(score_b),
                    started_at,
                    ended_at,
                    owner_id,
                    created_at,
                    created_at,
                    secrets.token_urlsafe(16),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Could not create sample match")
            return int(cursor.lastrowid)

        for league in leagues:
            league_id = int(league["id"])
            owner_id = int(league["owner_id"])
            league_name = str(league["name"])

            existing_count = int(
                conn.execute("SELECT COUNT(*) FROM matches WHERE league_id = ?", (league_id,)).fetchone()[0]
            )
            target_count = 6
            to_create = max(0, target_count - existing_count)
            if to_create <= 0:
                continue

            templates = [
                {
                    "title": f"{league_name} Weekly Friendly",
                    "scheduled_at": (now - timedelta(days=10)).isoformat(),
                    "registration_opens_at": (now - timedelta(days=13)).isoformat(),
                    "status": "completed",
                    "score_a": 3,
                    "score_b": 2,
                    "started_at": (now - timedelta(days=10, hours=-1)).isoformat(),
                    "ended_at": (now - timedelta(days=10, hours=-2)).isoformat(),
                    "notes": "Sample past match",
                },
                {
                    "title": f"{league_name} Midweek Match",
                    "scheduled_at": (now - timedelta(days=4)).isoformat(),
                    "registration_opens_at": (now - timedelta(days=7)).isoformat(),
                    "status": "completed",
                    "score_a": 1,
                    "score_b": 1,
                    "started_at": (now - timedelta(days=4, hours=-1)).isoformat(),
                    "ended_at": (now - timedelta(days=4, hours=-2)).isoformat(),
                    "notes": "Sample completed draw",
                },
                {
                    "title": f"{league_name} Weekend Fixture",
                    "scheduled_at": (now + timedelta(days=3)).isoformat(),
                    "registration_opens_at": (now + timedelta(days=1)).isoformat(),
                    "status": "registration_open",
                    "score_a": 0,
                    "score_b": 0,
                    "started_at": None,
                    "ended_at": None,
                    "notes": "Sample upcoming match (registration open)",
                },
                {
                    "title": f"{league_name} Next Week Clash",
                    "scheduled_at": (now + timedelta(days=8)).isoformat(),
                    "registration_opens_at": (now + timedelta(days=6)).isoformat(),
                    "status": "upcoming",
                    "score_a": 0,
                    "score_b": 0,
                    "started_at": None,
                    "ended_at": None,
                    "notes": "Sample scheduled match",
                },
                {
                    "title": f"{league_name} Sunday Cup",
                    "scheduled_at": (now + timedelta(days=12)).isoformat(),
                    "registration_opens_at": (now + timedelta(days=9)).isoformat(),
                    "status": "upcoming",
                    "score_a": 0,
                    "score_b": 0,
                    "started_at": None,
                    "ended_at": None,
                    "notes": "Sample scheduled cup fixture",
                },
                {
                    "title": f"{league_name} Last Sunday Replay",
                    "scheduled_at": (now - timedelta(days=17)).isoformat(),
                    "registration_opens_at": (now - timedelta(days=20)).isoformat(),
                    "status": "completed",
                    "score_a": 4,
                    "score_b": 3,
                    "started_at": (now - timedelta(days=17, hours=-1)).isoformat(),
                    "ended_at": (now - timedelta(days=17, hours=-2)).isoformat(),
                    "notes": "Sample classic match",
                },
            ]

            for i in range(to_create):
                item = templates[i % len(templates)]
                create_match(
                    league_id=league_id,
                    owner_id=owner_id,
                    title=item["title"],
                    scheduled_at=item["scheduled_at"],
                    registration_opens_at=item["registration_opens_at"],
                    status=item["status"],
                    score_a=int(item["score_a"]),
                    score_b=int(item["score_b"]),
                    started_at=item["started_at"],
                    ended_at=item["ended_at"],
                    notes=item["notes"],
                )
                seeded_matches += 1

        # Ensure demo users appear in at least one match registration.
        demo_users = conn.execute(
            "SELECT id FROM users WHERE LOWER(username) LIKE 'demo%' ORDER BY id"
        ).fetchall()

        for user in demo_users:
            user_id = int(user["id"])
            has_any = conn.execute(
                """
                SELECT 1
                FROM match_registrations AS mr
                JOIN matches AS m ON m.id = mr.match_id
                JOIN league_memberships AS lm ON lm.league_id = m.league_id AND lm.user_id = mr.user_id
                WHERE mr.user_id = ?
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if has_any is not None:
                continue

            league_row = conn.execute(
                "SELECT league_id FROM league_memberships WHERE user_id = ? ORDER BY league_id LIMIT 1",
                (user_id,),
            ).fetchone()
            if league_row is None:
                continue
            league_id = int(league_row["league_id"])

            match_row = conn.execute(
                "SELECT id FROM matches WHERE league_id = ? ORDER BY scheduled_at ASC LIMIT 1",
                (league_id,),
            ).fetchone()
            if match_row is None:
                continue
            match_id = int(match_row["id"])

            existing_reg = conn.execute(
                "SELECT 1 FROM match_registrations WHERE match_id = ? AND user_id = ?",
                (match_id, user_id),
            ).fetchone()
            if existing_reg is not None:
                continue

            position = int(
                conn.execute(
                    "SELECT COUNT(*) FROM match_registrations WHERE match_id = ?",
                    (match_id,),
                ).fetchone()[0]
            ) + 1
            conn.execute(
                """
                INSERT INTO match_registrations (match_id, user_id, status, position, registered_at, offered_at)
                VALUES (?, ?, 'registered', ?, ?, NULL)
                """,
                (match_id, user_id, position, created_at),
            )

        # Also register demo members into upcoming/open matches they belong to (up to max participants).
        candidate_matches = conn.execute(
            """
            SELECT id, league_id, max_participants
            FROM matches
            WHERE status IN ('upcoming', 'registration_open')
            ORDER BY scheduled_at ASC
            """
        ).fetchall()
        for m in candidate_matches:
            match_id = int(m["id"])
            league_id = int(m["league_id"])
            max_participants = int(m["max_participants"])
            current_registered = int(
                conn.execute(
                    "SELECT COUNT(*) FROM match_registrations WHERE match_id = ? AND status = 'registered'",
                    (match_id,),
                ).fetchone()[0]
            )
            if current_registered >= max_participants:
                continue

            demo_members = conn.execute(
                """
                SELECT lm.user_id
                FROM league_memberships AS lm
                JOIN users AS u ON u.id = lm.user_id
                WHERE lm.league_id = ? AND LOWER(u.username) LIKE 'demo%'
                ORDER BY lm.user_id
                """,
                (league_id,),
            ).fetchall()
            for member in demo_members:
                if current_registered >= max_participants:
                    break
                user_id = int(member["user_id"])
                already = conn.execute(
                    "SELECT 1 FROM match_registrations WHERE match_id = ? AND user_id = ?",
                    (match_id, user_id),
                ).fetchone()
                if already is not None:
                    continue
                position = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM match_registrations WHERE match_id = ?",
                        (match_id,),
                    ).fetchone()[0]
                ) + 1
                conn.execute(
                    """
                    INSERT INTO match_registrations (match_id, user_id, status, position, registered_at, offered_at)
                    VALUES (?, ?, 'registered', ?, ?, NULL)
                    """,
                    (match_id, user_id, position, created_at),
                )
                current_registered += 1

        if seeded_matches or demo_users:
            conn.commit()


def remove_seeded_sample_matches() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM match_events WHERE match_id IN (SELECT id FROM matches WHERE notes LIKE 'Sample %')")
        conn.execute("DELETE FROM match_registrations WHERE match_id IN (SELECT id FROM matches WHERE notes LIKE 'Sample %')")
        conn.execute("DELETE FROM matches WHERE notes LIKE 'Sample %'")
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
            SELECT id, username, password_hash, email, name, surname, nicknames, display_name, recovery_id, role,
                   is_active, terminated_at, attendance, wins, goals, assists, global_rating, created_at, updated_at
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()


def find_user_by_id(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT id, username, password_hash, email, name, surname, nicknames, display_name, recovery_id, role,
                   is_active, terminated_at, attendance, wins, goals, assists, global_rating, created_at, updated_at
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
            SELECT id, username, password_hash, email, name, surname, nicknames, display_name, recovery_id, role,
                   is_active, terminated_at, attendance, wins, goals, assists, global_rating, created_at, updated_at
            FROM users
            WHERE lower(email) = ?
            """,
            (normalized_email,),
        ).fetchone()


def find_user_by_recovery_id(recovery_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT id, username, password_hash, email, name, surname, nicknames, display_name, recovery_id, role,
                   is_active, terminated_at, attendance, wins, goals, assists, global_rating, created_at, updated_at
            FROM users
            WHERE recovery_id = ?
            """,
            (recovery_id.strip(),),
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
        recovery_id=(str(row["recovery_id"]) if "recovery_id" in row.keys() and row["recovery_id"] is not None else None),
        recovery_token=(str(row["recovery_id"]) if "recovery_id" in row.keys() and row["recovery_id"] is not None else None),
        role=str(row["role"]),
        is_active=bool(int(row["is_active"] or 0)) if "is_active" in row.keys() else True,
        terminated_at=(str(row["terminated_at"]) if "terminated_at" in row.keys() and row["terminated_at"] is not None else None),
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
    raw_presets = row["match_presets_json"] if "match_presets_json" in row.keys() else "[]"
    try:
        match_presets = json.loads(str(raw_presets or "[]"))
        if not isinstance(match_presets, list):
            match_presets = []
    except (ValueError, TypeError):
        match_presets = []

    raw_cfg = row["rating_config_json"] if "rating_config_json" in row.keys() else "{}"
    try:
        rating_config = json.loads(str(raw_cfg or "{}"))
        if not isinstance(rating_config, dict):
            rating_config = {}
    except (ValueError, TypeError):
        rating_config = {}
    merged_cfg = dict(DEFAULT_RATING_CONFIG)
    merged_cfg.update(rating_config)

    return LeagueOut(
        id=int(row["id"]),
        name=str(row["name"]),
        football_type=str(row["football_type"]),
        goal_size=str(row["goal_size"]),
        region=str(row["region"] or "Unknown"),
        league_visibility=str(row["league_visibility"] or "public") if "league_visibility" in row.keys() else "public",
        discover_visible=bool(int(row["discover_visible"])) if "discover_visible" in row.keys() and row["discover_visible"] is not None else True,
        latitude=(float(row["latitude"]) if "latitude" in row.keys() and row["latitude"] is not None else None),
        longitude=(float(row["longitude"]) if "longitude" in row.keys() and row["longitude"] is not None else None),
        invite_code=str(row["invite_code"] or ""),
        description=row["description"],
        owner_id=int(row["owner_id"]),
        owner_username=str(row["owner_username"]),
        member_role=str(row["member_role"]),
        member_count=int(row["member_count"]),
        created_at=str(row["created_at"]),
        auto_accept_members=bool(row["auto_accept_members"]) if row["auto_accept_members"] is not None else True,
        fee_type=str(row["fee_type"] or "none"),
        fee_value=float(row["fee_value"] or 0),
        match_presets=match_presets,
        rating_config=merged_cfg,
        approval_status=str(row["approval_status"] or "approved") if "approval_status" in row.keys() else "approved",
        approved_at=(str(row["approved_at"]) if "approved_at" in row.keys() and row["approved_at"] is not None else None),
        approval_note=(str(row["approval_note"]) if "approval_note" in row.keys() and row["approval_note"] is not None else None),
    )


def serialize_invite(row: sqlite3.Row) -> LeagueInviteOut:
    token = str(row["token"])
    expires_at_raw = row["expires_at"]
    expired = False
    if expires_at_raw:
        try:
            expires_dt = datetime.fromisoformat(str(expires_at_raw))
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            expired = utc_now() > expires_dt
        except ValueError:
            expired = False
    return LeagueInviteOut(
        id=int(row["id"]),
        league_id=int(row["league_id"]),
        league_name=str(row["league_name"]),
        token=token,
        creator_username=(str(row["creator_username"]) if "creator_username" in row.keys() and row["creator_username"] is not None else None),
        accepted_by_username=(str(row["accepted_by_username"]) if "accepted_by_username" in row.keys() and row["accepted_by_username"] is not None else None),
        created_at=str(row["created_at"]),
        expires_at=expires_at_raw,
        max_uses=int(row["max_uses"]),
        use_count=int(row["use_count"]),
        revoked=int(row["revoked"]),
        expired=expired,
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
        penalty_until=(str(row["penalty_until"]) if "penalty_until" in row.keys() and row["penalty_until"] is not None else None),
        penalty_reason=(str(row["penalty_reason"]) if "penalty_reason" in row.keys() and row["penalty_reason"] is not None else None),
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
    if not bool(int(user["is_active"] or 0)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is temporarily blocked")
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
            l.league_visibility,
            l.discover_visible,
            l.latitude,
            l.longitude,
            l.invite_code,
            l.description,
            l.fee_type,
            l.fee_value,
            l.match_presets_json,
            l.rating_config_json,
            l.approval_status,
            l.approved_at,
            l.approval_note,
            l.owner_id,
            l.created_at,
            l.auto_accept_members,
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
            l.league_visibility,
            l.discover_visible,
            l.latitude,
            l.longitude,
            l.invite_code,
            l.description,
            l.fee_type,
            l.fee_value,
            l.match_presets_json,
            l.rating_config_json,
            l.approval_status,
            l.approved_at,
            l.approval_note,
            l.owner_id,
            l.created_at,
            l.auto_accept_members,
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
            creator.username AS creator_username,
            accepted.username AS accepted_by_username,
            li.created_at,
            li.expires_at,
            li.max_uses,
            li.use_count,
            li.revoked
        FROM league_invites AS li
        JOIN leagues AS l ON l.id = li.league_id
        JOIN users AS creator ON creator.id = li.created_by_user_id
        LEFT JOIN users AS accepted ON accepted.id = li.accepted_by_user_id
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
            COALESCE(lps.rating, 1000) AS rating,
            lp.penalty_until,
            lp.reason AS penalty_reason
        FROM league_memberships AS lm
        JOIN users AS u ON u.id = lm.user_id
        LEFT JOIN league_player_stats AS lps ON lps.league_id = lm.league_id AND lps.user_id = lm.user_id
        LEFT JOIN league_penalties AS lp
            ON lp.league_id = lm.league_id
           AND lp.user_id = lm.user_id
           AND datetime(lp.penalty_until) > datetime('now')
        WHERE lm.league_id = ?
        ORDER BY CASE lm.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, u.username
        """,
        (league_id,),
    ).fetchall()


def fetch_league_invites(conn: sqlite3.Connection, league_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            li.id,
            li.league_id,
            l.name AS league_name,
            li.token,
            creator.username AS creator_username,
            accepted.username AS accepted_by_username,
            li.created_at,
            li.expires_at,
            li.max_uses,
            li.use_count,
            li.revoked
        FROM league_invites AS li
        JOIN leagues AS l ON l.id = li.league_id
        JOIN users AS creator ON creator.id = li.created_by_user_id
        LEFT JOIN users AS accepted ON accepted.id = li.accepted_by_user_id
        WHERE li.league_id = ? AND li.revoked = 0
        ORDER BY li.created_at DESC
        """,
        (league_id,),
    ).fetchall()


def _has_league_membership(conn: sqlite3.Connection, league_id: int, user_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM league_memberships WHERE league_id = ? AND user_id = ?",
        (league_id, user_id),
    ).fetchone() is not None


def _is_league_public(conn: sqlite3.Connection, league_id: int) -> bool:
    row = conn.execute(
        "SELECT league_visibility FROM leagues WHERE id = ?",
        (league_id,),
    ).fetchone()
    if row is None:
        return False
    return str(row["league_visibility"] or "public") == "public"


def _can_view_league_stats(conn: sqlite3.Connection, league_id: int, user_id: int) -> bool:
    return _has_league_membership(conn, league_id, user_id) or _is_league_public(conn, league_id)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _estimate_temporary_lmmr_from_global(conn: sqlite3.Connection, league_id: int, user_id: int) -> float:
    user_row = conn.execute("SELECT global_rating FROM users WHERE id = ?", (user_id,)).fetchone()
    user_global = float(user_row["global_rating"] if user_row is not None and user_row["global_rating"] is not None else DEFAULT_GLOBAL_RATING)

    peer_rows = conn.execute(
        """
        SELECT COALESCE(u.global_rating, ?) AS global_rating, COALESCE(lps.rating, ?) AS lmmr
        FROM league_memberships lm
        JOIN users u ON u.id = lm.user_id
        LEFT JOIN league_player_stats lps ON lps.league_id = lm.league_id AND lps.user_id = lm.user_id
        WHERE lm.league_id = ? AND lm.user_id != ?
        """,
        (DEFAULT_GLOBAL_RATING, DEFAULT_GLOBAL_RATING, league_id, user_id),
    ).fetchall()

    if not peer_rows:
        return round(user_global, 2)

    peer_globals = sorted(float(r["global_rating"] or DEFAULT_GLOBAL_RATING) for r in peer_rows)
    peer_lmmr = sorted(float(r["lmmr"] or DEFAULT_GLOBAL_RATING) for r in peer_rows)
    if not peer_lmmr:
        return round(user_global, 2)

    count = len(peer_globals)
    less_or_equal = sum(1 for g in peer_globals if g <= user_global)
    p = (less_or_equal - 1) / max(1, count - 1) if count > 1 else 0.5
    p = max(0.0, min(1.0, p))

    idx = p * (len(peer_lmmr) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return round(peer_lmmr[lo], 2)
    frac = idx - lo
    return round(peer_lmmr[lo] * (1.0 - frac) + peer_lmmr[hi] * frac, 2)


def _is_completely_new_player(conn: sqlite3.Connection, user_id: int) -> bool:
    row = conn.execute(
        "SELECT attendance, wins, goals, assists, global_rating FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return False
    return (
        int(row["attendance"] or 0) == 0
        and int(row["wins"] or 0) == 0
        and int(row["goals"] or 0) == 0
        and int(row["assists"] or 0) == 0
        and abs(float(row["global_rating"] or DEFAULT_GLOBAL_RATING) - DEFAULT_GLOBAL_RATING) <= 0.01
    )


def _enqueue_lmmr_placement_if_needed(conn: sqlite3.Connection, league_id: int, user_id: int, suggested_rating: float) -> None:
    if not _is_completely_new_player(conn, user_id):
        return

    now_iso = utc_now_iso()
    conn.execute(
        """
        INSERT INTO league_lmmr_placements (league_id, user_id, status, reason, suggested_rating, created_at)
        VALUES (?, ?, 'pending', ?, ?, ?)
        ON CONFLICT(league_id, user_id) DO UPDATE SET
            status = 'pending',
            reason = excluded.reason,
            suggested_rating = excluded.suggested_rating,
            created_at = excluded.created_at,
            resolved_at = NULL,
            resolved_by_user_id = NULL,
            final_rating = NULL,
            note = NULL
        """,
        (league_id, user_id, "new_player_needs_manual_seed", float(suggested_rating), now_iso),
    )

    target = conn.execute("SELECT username, display_name FROM users WHERE id = ?", (user_id,)).fetchone()
    label = str(target["display_name"] or target["username"] or f"User {user_id}") if target is not None else f"User {user_id}"
    managers = conn.execute(
        "SELECT user_id FROM league_memberships WHERE league_id = ? AND role IN ('owner', 'admin')",
        (league_id,),
    ).fetchall()
    for m in managers:
        _create_notification(
            conn,
            int(m["user_id"]),
            "lmmr_placement_needed",
            "LMMR placement needed",
            f"Please place {label} on your league rating scale.",
            {"league_id": league_id, "user_id": user_id},
        )


def _ensure_member_lps_with_temp_rating(conn: sqlite3.Connection, league_id: int, user_id: int) -> None:
    existing_stats = conn.execute(
        "SELECT id FROM league_player_stats WHERE league_id = ? AND user_id = ?",
        (league_id, user_id),
    ).fetchone()
    if existing_stats is not None:
        return

    suggested = _estimate_temporary_lmmr_from_global(conn, league_id, user_id)
    conn.execute(
        """
        INSERT INTO league_player_stats (
            league_id,
            user_id,
            attendance,
            wins,
            goals,
            assists,
            rating,
            is_temporary_lmmr,
            temporary_lmmr_match_limit
        ) VALUES (?, ?, 0, 0, 0, 0, ?, 1, ?)
        """,
        (league_id, user_id, float(suggested), TEMP_LMMR_MATCH_LIMIT),
    )
    _enqueue_lmmr_placement_if_needed(conn, league_id, user_id, suggested)


def add_discipline_history(
    conn: sqlite3.Connection,
    league_id: int,
    user_id: int,
    action: str,
    actor_user_id: int | None,
    reason: str | None = None,
    penalty_until: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO league_discipline_history (league_id, user_id, action, reason, penalty_until, actor_user_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (league_id, user_id, action, reason, penalty_until, actor_user_id, utc_now_iso()),
    )


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


def require_league_approved(conn: sqlite3.Connection, league_id: int) -> sqlite3.Row:
    league = conn.execute(
        "SELECT id, name, approval_status, terminated_until FROM leagues WHERE id = ?",
        (league_id,),
    ).fetchone()
    if league is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
    if str(league["approval_status"] or "approved") != "approved":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="League is awaiting admin approval")
    terminated_until_raw = league["terminated_until"]
    if terminated_until_raw:
        terminated_until = datetime.fromisoformat(str(terminated_until_raw))
        if terminated_until.tzinfo is None:
            terminated_until = terminated_until.replace(tzinfo=timezone.utc)
        if utc_now() < terminated_until:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"League is temporarily terminated until {terminated_until.isoformat()}")
    return league


def _are_friends(conn: sqlite3.Connection, user_a: int, user_b: int) -> bool:
    if user_a == user_b:
        return True
    row = conn.execute(
        "SELECT 1 FROM friendships WHERE user_id = ? AND friend_user_id = ?",
        (user_a, user_b),
    ).fetchone()
    return row is not None


def _share_league(conn: sqlite3.Connection, user_a: int, user_b: int) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM league_memberships AS a
        JOIN league_memberships AS b ON b.league_id = a.league_id
        WHERE a.user_id = ? AND b.user_id = ?
        LIMIT 1
        """,
        (user_a, user_b),
    ).fetchone()
    return row is not None


def _can_send_friend_request(conn: sqlite3.Connection, from_user_id: int, target_row: sqlite3.Row) -> bool:
    if int(target_row["id"]) == from_user_id:
        return False
    policy = str(target_row["friend_request_policy"] or "everyone")
    if policy == "nobody":
        return False
    if policy == "shared_leagues" and not _share_league(conn, from_user_id, int(target_row["id"])):
        return False
    return True


def _can_view_player_stats(conn: sqlite3.Connection, viewer_user_id: int | None, target_row: sqlite3.Row) -> bool:
    target_id = int(target_row["id"])
    if viewer_user_id is not None and viewer_user_id == target_id:
        return True
    visibility = str(target_row["profile_visibility"] or "public")
    if visibility == "public":
        return True
    if visibility == "private":
        return False
    if viewer_user_id is None:
        return False
    return _are_friends(conn, viewer_user_id, target_id)


def _player_global_position(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute(
        "SELECT 1 + COUNT(*) AS pos FROM users WHERE COALESCE(global_rating, ?) > COALESCE((SELECT global_rating FROM users WHERE id = ?), ?)",
        (DEFAULT_GLOBAL_RATING, user_id, DEFAULT_GLOBAL_RATING),
    ).fetchone()
    return int(row["pos"] if row is not None else 1)


def _serialize_friend_request(row: sqlite3.Row) -> FriendRequestOut:
    return FriendRequestOut(
        id=int(row["id"]),
        from_user_id=int(row["from_user_id"]),
        from_username=str(row["from_username"]),
        from_display_name=row["from_display_name"],
        to_user_id=int(row["to_user_id"]),
        to_username=str(row["to_username"]),
        to_display_name=row["to_display_name"],
        status=str(row["status"]),
        message=row["message"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _notify_player_fans(
    conn: sqlite3.Connection,
    *,
    player_user_id: int,
    league_id: int,
    notif_type: str,
    title: str,
    message: str,
    data: dict,
    exclude_user_ids: set[int] | None = None,
) -> None:
    exclude = exclude_user_ids or set()
    rows = conn.execute(
        """
        SELECT pf.follower_user_id
        FROM player_follows AS pf
        JOIN league_memberships AS lm ON lm.user_id = pf.follower_user_id AND lm.league_id = ?
        WHERE pf.target_user_id = ?
        """,
        (league_id, player_user_id),
    ).fetchall()
    for row in rows:
        follower_id = int(row["follower_user_id"])
        if follower_id in exclude:
            continue
        _create_notification(conn, follower_id, notif_type, title, message, data)


def _find_password_reset_user(email: str | None, recovery_id: str | None, recovery_token: str | None) -> sqlite3.Row | None:
    if recovery_token is not None and recovery_token.strip():
        return find_user_by_recovery_id(recovery_token)
    if recovery_id is not None and recovery_id.strip():
        return find_user_by_recovery_id(recovery_id)
    if email is not None and email.strip():
        return find_user_by_email(email)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Provide either recovery_token or recovery_id",
    )


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
            l.approval_status,
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
    if ENABLE_SAMPLE_MATCHES:
        ensure_sample_matches()
    else:
        remove_seeded_sample_matches()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": utc_now_iso()}


@app.get("/public/stats")
def public_stats() -> dict[str, int]:
    """No-auth endpoint returning aggregate platform counts for the login page."""
    with get_conn() as conn:
        users = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        leagues = int(conn.execute("SELECT COUNT(*) FROM leagues").fetchone()[0])
        matches = int(conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0])
    return {"users": users, "leagues": leagues, "matches": matches}


@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterPayload) -> UserOut:
    if find_user_by_username(payload.username) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    normalized_email = normalize_email(payload.email)
    if find_user_by_email(normalized_email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    created_at = utc_now_iso()
    with get_conn() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, email, name, surname, nicknames, display_name, role,
                                   recovery_id, is_active, terminated_at, attendance, wins, goals, assists, global_rating, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'player', ?, 1, NULL, 0, 0, 0, 0, ?, ?, ?)
                """,
                (
                    payload.username.strip(),
                    hash_password(payload.password),
                    normalized_email,
                    payload.name.strip(),
                    payload.surname.strip(),
                    nicknames_to_db(payload.nicknames),
                    payload.display_name.strip() if payload.display_name else None,
                    _generate_recovery_id(conn),
                    DEFAULT_GLOBAL_RATING,
                    created_at,
                    created_at,
                ),
            )
            conn.commit()
            user_id = cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "users.email" in message or "idx_users_email_unique" in message:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists") from exc
            if "users.username" in message:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from exc
            raise
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
    if not bool(int(user["is_active"] or 0)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is temporarily blocked")
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
    if payload.email is not None:
        normalized_email = normalize_email(payload.email)
        if not normalized_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email cannot be empty")
        existing_email_user = find_user_by_email(normalized_email)
        if existing_email_user is not None and int(existing_email_user["id"]) != int(current_user["id"]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
        if payload.current_password is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password required")
        if not verify_password(payload.current_password, current_user["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is wrong")
        updates.append("email = ?")
        params.append(normalized_email)
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
        try:
            conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", tuple(params))
            conn.commit()
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "users.email" in message or "idx_users_email_unique" in message:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists") from exc
            raise
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


@app.post("/auth/password-reset-request", response_model=PasswordResetRequestOut)
def request_password_reset(payload: PasswordResetRequestPayload) -> PasswordResetRequestOut:
    user = _find_password_reset_user(payload.email, payload.recovery_id, payload.recovery_token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not bool(int(user["is_active"] or 0)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is temporarily blocked")
    reset_token = secrets.token_urlsafe(32)
    expires_at = (utc_now() + timedelta(minutes=30)).isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (int(user["id"]),))
        conn.execute(
            "INSERT INTO password_reset_tokens (user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], reset_token, expires_at, utc_now_iso()),
        )
        conn.commit()
    return PasswordResetRequestOut(
        detail="Password reset token generated. Use this token in the reset endpoint.",
        token=reset_token,
        expires_at=expires_at,
        note="In production, this token would be sent by email or another verified recovery channel.",
    )


@app.post("/auth/password-reset", response_model=MessageOut)
def reset_password(payload: PasswordResetPayload) -> MessageOut:
    user = _find_password_reset_user(payload.email, payload.recovery_id, payload.recovery_token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not bool(int(user["is_active"] or 0)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is temporarily blocked")
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
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (int(user["id"]),))
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


@app.patch("/users/me", response_model=MessageOut)
def update_own_profile(
    payload: UpdateProfilePayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    updates: list[str] = []
    params: list = []
    if payload.display_name is not None:
        updates.append("display_name = ?")
        params.append(payload.display_name.strip() or None)
    if payload.name is not None:
        updates.append("name = ?")
        params.append(payload.name.strip())
    if payload.surname is not None:
        updates.append("surname = ?")
        params.append(payload.surname.strip())
    if not updates:
        return MessageOut(detail="Nothing to update.")
    params.append(int(current_user["id"]))
    with get_conn() as conn:
        conn.execute(f"UPDATE users SET {', '.join(updates)}, updated_at = ? WHERE id = ?",
                     [*params[:-1], utc_now_iso(), params[-1]])
        conn.commit()
    return MessageOut(detail="Profile updated.")


@app.get("/players/me/settings", response_model=PlayerSettingsOut)
def get_player_settings(current_user: sqlite3.Row = Depends(resolve_current_user)) -> PlayerSettingsOut:
    return PlayerSettingsOut(
        profile_visibility=str(current_user["profile_visibility"] or "public"),
        friend_request_policy=str(current_user["friend_request_policy"] or "everyone"),
    )


@app.patch("/players/me/settings", response_model=PlayerSettingsOut)
def patch_player_settings(
    payload: PlayerSettingsPatchPayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> PlayerSettingsOut:
    updates: list[str] = []
    params: list = []
    if payload.profile_visibility is not None:
        updates.append("profile_visibility = ?")
        params.append(payload.profile_visibility)
    if payload.friend_request_policy is not None:
        updates.append("friend_request_policy = ?")
        params.append(payload.friend_request_policy)
    if not updates:
        return PlayerSettingsOut(
            profile_visibility=str(current_user["profile_visibility"] or "public"),
            friend_request_policy=str(current_user["friend_request_policy"] or "everyone"),
        )
    params.extend([utc_now_iso(), int(current_user["id"])])
    with get_conn() as conn:
        conn.execute(f"UPDATE users SET {', '.join(updates)}, updated_at = ? WHERE id = ?", params)
        conn.commit()
        row = conn.execute(
            "SELECT profile_visibility, friend_request_policy FROM users WHERE id = ?",
            (int(current_user["id"]),),
        ).fetchone()
    return PlayerSettingsOut(
        profile_visibility=str(row["profile_visibility"] if row is not None else "public"),
        friend_request_policy=str(row["friend_request_policy"] if row is not None else "everyone"),
    )


@app.get("/players/search", response_model=list[PlayerSearchOut])
def player_search(
    q: str | None = None,
    limit: int = 20,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> list[PlayerSearchOut]:
    user_id = int(current_user["id"])
    safe_limit = max(1, min(int(limit), 100))
    with get_conn() as conn:
        where_params: list = [user_id]
        where = ["u.id != ?"]
        if q and q.strip():
            like_q = f"%{q.strip()}%"
            where.append("(LOWER(u.username) LIKE LOWER(?) OR LOWER(COALESCE(u.display_name, '')) LIKE LOWER(?))")
            where_params.extend([like_q, like_q])

        rows = conn.execute(
            f"""
            SELECT u.id, u.username, u.display_name, COALESCE(u.global_rating, ?) AS global_rating,
                   EXISTS(SELECT 1 FROM friendships f WHERE f.user_id = ? AND f.friend_user_id = u.id) AS is_friend,
                   EXISTS(SELECT 1 FROM friend_requests fr WHERE fr.from_user_id = ? AND fr.to_user_id = u.id AND fr.status = 'pending') AS has_pending_outgoing,
                   EXISTS(SELECT 1 FROM friend_requests fr WHERE fr.from_user_id = u.id AND fr.to_user_id = ? AND fr.status = 'pending') AS has_pending_incoming,
                   EXISTS(SELECT 1 FROM player_follows pf WHERE pf.follower_user_id = ? AND pf.target_user_id = u.id) AS is_following
            FROM users u
            WHERE {' AND '.join(where)}
            ORDER BY u.global_rating DESC, u.username ASC
            LIMIT ?
            """,
            [DEFAULT_GLOBAL_RATING, user_id, user_id, user_id, user_id, *where_params, safe_limit],
        ).fetchall()
    return [
        PlayerSearchOut(
            id=int(r["id"]),
            username=str(r["username"]),
            display_name=r["display_name"],
            global_rating=float(r["global_rating"] or DEFAULT_GLOBAL_RATING),
            is_friend=bool(int(r["is_friend"] or 0)),
            has_pending_outgoing_request=bool(int(r["has_pending_outgoing"] or 0)),
            has_pending_incoming_request=bool(int(r["has_pending_incoming"] or 0)),
            is_following=bool(int(r["is_following"] or 0)),
        )
        for r in rows
    ]


@app.get("/players/{user_id}", response_model=PlayerProfileOut)
def get_player_profile(
    user_id: int,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> PlayerProfileOut:
    viewer_id: int | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        try:
            payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            subject = str(payload.get("sub", ""))
            if subject.startswith("user:"):
                viewer_id = int(subject.split(":", 1)[1])
        except Exception:
            viewer_id = None

    with get_conn() as conn:
        target = conn.execute(
            "SELECT id, username, display_name, attendance, wins, goals, assists, global_rating, profile_visibility, friend_request_policy FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

        viewer_is_admin = False
        if viewer_id is not None:
            viewer_row = conn.execute("SELECT role FROM users WHERE id = ?", (viewer_id,)).fetchone()
            viewer_is_admin = viewer_row is not None and str(viewer_row["role"] or "") == "admin"
        can_view = True if viewer_is_admin else _can_view_player_stats(conn, viewer_id, target)
        is_friend = viewer_id is not None and _are_friends(conn, viewer_id, int(target["id"]))
        is_following = False
        has_pending_out = False
        has_pending_in = False
        can_send_request = False
        if viewer_id is not None and viewer_id != int(target["id"]):
            is_following = conn.execute(
                "SELECT 1 FROM player_follows WHERE follower_user_id = ? AND target_user_id = ?",
                (viewer_id, int(target["id"])),
            ).fetchone() is not None
            has_pending_out = conn.execute(
                "SELECT 1 FROM friend_requests WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'",
                (viewer_id, int(target["id"])),
            ).fetchone() is not None
            has_pending_in = conn.execute(
                "SELECT 1 FROM friend_requests WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'",
                (int(target["id"]), viewer_id),
            ).fetchone() is not None
            can_send_request = (not is_friend) and (not has_pending_out) and _can_send_friend_request(conn, viewer_id, target)

        league_stats: list[PlayerLeagueStatsOut] = []
        if can_view:
            rows = conn.execute(
                """
                SELECT l.id AS league_id, l.name AS league_name,
                       COALESCE(lps.attendance, 0) AS attendance,
                       COALESCE(lps.wins, 0) AS wins,
                       COALESCE(lps.goals, 0) AS goals,
                       COALESCE(lps.assists, 0) AS assists,
                       COALESCE(lps.rating, ?) AS rating
                FROM league_player_stats lps
                JOIN leagues l ON l.id = lps.league_id
                WHERE lps.user_id = ?
                ORDER BY l.name ASC
                """,
                (DEFAULT_GLOBAL_RATING, int(target["id"])),
            ).fetchall()
            league_stats = [
                PlayerLeagueStatsOut(
                    league_id=int(r["league_id"]),
                    league_name=str(r["league_name"]),
                    attendance=int(r["attendance"] or 0),
                    wins=int(r["wins"] or 0),
                    goals=int(r["goals"] or 0),
                    assists=int(r["assists"] or 0),
                    rating=float(r["rating"] or DEFAULT_GLOBAL_RATING),
                )
                for r in rows
            ]

        return PlayerProfileOut(
            id=int(target["id"]),
            username=str(target["username"]),
            display_name=target["display_name"],
            global_rating=float(target["global_rating"] or DEFAULT_GLOBAL_RATING) if can_view else 0.0,
            global_position=_player_global_position(conn, int(target["id"])) if can_view else 0,
            attendance=int(target["attendance"] or 0) if can_view else 0,
            wins=int(target["wins"] or 0) if can_view else 0,
            goals=int(target["goals"] or 0) if can_view else 0,
            assists=int(target["assists"] or 0) if can_view else 0,
            profile_visibility=str(target["profile_visibility"] or "public"),
            can_view_stats=can_view,
            is_friend=bool(is_friend),
            is_following=bool(is_following),
            can_send_friend_request=bool(can_send_request),
            has_pending_outgoing_request=bool(has_pending_out),
            has_pending_incoming_request=bool(has_pending_in),
            league_stats=league_stats,
        )


@app.post("/players/{target_user_id}/friend-requests", response_model=MessageOut)
def send_friend_request(
    target_user_id: int,
    payload: FriendRequestCreatePayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    from_user_id = int(current_user["id"])
    sender_name = str(current_user["display_name"] or current_user["username"])
    with get_conn() as conn:
        target = conn.execute(
            "SELECT id, username, friend_request_policy FROM users WHERE id = ?",
            (target_user_id,),
        ).fetchone()
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
        if from_user_id == target_user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot send a friend request to yourself")
        if _are_friends(conn, from_user_id, target_user_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You are already friends")
        if not _can_send_friend_request(conn, from_user_id, target):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This player is not accepting your friend requests")

        reciprocal = conn.execute(
            "SELECT id FROM friend_requests WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'",
            (target_user_id, from_user_id),
        ).fetchone()
        if reciprocal is not None:
            now_iso = utc_now_iso()
            conn.execute(
                "INSERT OR IGNORE INTO friendships (user_id, friend_user_id, created_at) VALUES (?, ?, ?)",
                (from_user_id, target_user_id, now_iso),
            )
            conn.execute(
                "INSERT OR IGNORE INTO friendships (user_id, friend_user_id, created_at) VALUES (?, ?, ?)",
                (target_user_id, from_user_id, now_iso),
            )
            conn.execute(
                "UPDATE friend_requests SET status = 'accepted', updated_at = ? WHERE id = ?",
                (now_iso, int(reciprocal["id"])),
            )
            conn.commit()
            return MessageOut(detail="Friend request accepted. You are now friends.")

        existing = conn.execute(
            "SELECT id, status FROM friend_requests WHERE from_user_id = ? AND to_user_id = ?",
            (from_user_id, target_user_id),
        ).fetchone()
        now_iso = utc_now_iso()
        if existing is None:
            conn.execute(
                "INSERT INTO friend_requests (from_user_id, to_user_id, status, message, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?, ?)",
                (from_user_id, target_user_id, payload.message, now_iso, now_iso),
            )
        else:
            if str(existing["status"]) == "pending":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Friend request already pending")
            conn.execute(
                "UPDATE friend_requests SET status = 'pending', message = ?, updated_at = ? WHERE id = ?",
                (payload.message, now_iso, int(existing["id"])),
            )
        _create_notification(
            conn,
            target_user_id,
            "friend_request",
            "New friend request",
            f"{sender_name} sent you a friend request.",
            {"from_user_id": from_user_id},
        )
        conn.commit()
    return MessageOut(detail="Friend request sent.")


@app.get("/players/me/friend-requests", response_model=FriendRequestsResponseOut)
def list_my_friend_requests(current_user: sqlite3.Row = Depends(resolve_current_user)) -> FriendRequestsResponseOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        incoming_rows = conn.execute(
            """
            SELECT fr.id, fr.from_user_id, fu.username AS from_username, fu.display_name AS from_display_name,
                   fr.to_user_id, tu.username AS to_username, tu.display_name AS to_display_name,
                   fr.status, fr.message, fr.created_at, fr.updated_at
            FROM friend_requests fr
            JOIN users fu ON fu.id = fr.from_user_id
            JOIN users tu ON tu.id = fr.to_user_id
            WHERE fr.to_user_id = ? AND fr.status = 'pending'
            ORDER BY fr.updated_at DESC
            """,
            (user_id,),
        ).fetchall()
        outgoing_rows = conn.execute(
            """
            SELECT fr.id, fr.from_user_id, fu.username AS from_username, fu.display_name AS from_display_name,
                   fr.to_user_id, tu.username AS to_username, tu.display_name AS to_display_name,
                   fr.status, fr.message, fr.created_at, fr.updated_at
            FROM friend_requests fr
            JOIN users fu ON fu.id = fr.from_user_id
            JOIN users tu ON tu.id = fr.to_user_id
            WHERE fr.from_user_id = ? AND fr.status = 'pending'
            ORDER BY fr.updated_at DESC
            """,
            (user_id,),
        ).fetchall()
    return FriendRequestsResponseOut(
        incoming=[_serialize_friend_request(r) for r in incoming_rows],
        outgoing=[_serialize_friend_request(r) for r in outgoing_rows],
    )


@app.post("/friend-requests/{request_id}/accept", response_model=MessageOut)
def accept_friend_request(request_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    accepter_name = str(current_user["display_name"] or current_user["username"])
    with get_conn() as conn:
        req = conn.execute(
            "SELECT id, from_user_id, to_user_id, status FROM friend_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if req is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Friend request not found")
        if int(req["to_user_id"]) != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your friend request")
        if str(req["status"]) != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Friend request already handled")

        now_iso = utc_now_iso()
        from_user_id = int(req["from_user_id"])
        conn.execute(
            "INSERT OR IGNORE INTO friendships (user_id, friend_user_id, created_at) VALUES (?, ?, ?)",
            (from_user_id, user_id, now_iso),
        )
        conn.execute(
            "INSERT OR IGNORE INTO friendships (user_id, friend_user_id, created_at) VALUES (?, ?, ?)",
            (user_id, from_user_id, now_iso),
        )
        conn.execute("UPDATE friend_requests SET status = 'accepted', updated_at = ? WHERE id = ?", (now_iso, request_id))
        _create_notification(
            conn,
            from_user_id,
            "friend_request_accepted",
            "Friend request accepted",
            f"{accepter_name} accepted your friend request.",
            {"user_id": user_id},
        )
        conn.commit()
    return MessageOut(detail="Friend request accepted.")


@app.post("/friend-requests/{request_id}/reject", response_model=MessageOut)
def reject_friend_request(request_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        req = conn.execute(
            "SELECT id, to_user_id, status FROM friend_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if req is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Friend request not found")
        if int(req["to_user_id"]) != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your friend request")
        if str(req["status"]) != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Friend request already handled")
        conn.execute("UPDATE friend_requests SET status = 'rejected', updated_at = ? WHERE id = ?", (utc_now_iso(), request_id))
        conn.commit()
    return MessageOut(detail="Friend request rejected.")


@app.get("/players/me/friends", response_model=list[PlayerSearchOut])
def get_my_friends(current_user: sqlite3.Row = Depends(resolve_current_user)) -> list[PlayerSearchOut]:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.display_name, COALESCE(u.global_rating, 1000.0) AS global_rating
            FROM friendships f
            JOIN users u ON u.id = f.friend_user_id
            WHERE f.user_id = ?
            ORDER BY u.username
            """,
            (user_id,),
        ).fetchall()
        result = []
        for r in rows:
            result.append(PlayerSearchOut(
                id=int(r["id"]),
                username=str(r["username"]),
                display_name=r["display_name"],
                global_rating=float(r["global_rating"]),
                is_friend=True,
                has_pending_outgoing_request=False,
                has_pending_incoming_request=False,
                is_following=False,
            ))
    return result


@app.delete("/players/{friend_user_id}/friendship", response_model=MessageOut)
def remove_friendship(friend_user_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM friendships WHERE (user_id = ? AND friend_user_id = ?) OR (user_id = ? AND friend_user_id = ?)",
            (user_id, friend_user_id, friend_user_id, user_id),
        )
        conn.execute(
            """UPDATE friend_requests SET status = 'removed', updated_at = ?
               WHERE ((from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?))
               AND status = 'accepted'""",
            (utc_now_iso(), user_id, friend_user_id, friend_user_id, user_id),
        )
        conn.commit()
    return MessageOut(detail="Friendship removed.")


@app.post("/players/{target_user_id}/follow", response_model=FollowStateOut)
def follow_player(target_user_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> FollowStateOut:
    follower_id = int(current_user["id"])
    if follower_id == target_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself")
    with get_conn() as conn:
        target = conn.execute("SELECT id FROM users WHERE id = ?", (target_user_id,)).fetchone()
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
        conn.execute(
            "INSERT OR IGNORE INTO player_follows (follower_user_id, target_user_id, created_at) VALUES (?, ?, ?)",
            (follower_id, target_user_id, utc_now_iso()),
        )
        conn.commit()
    return FollowStateOut(following=True)


@app.delete("/players/{target_user_id}/follow", response_model=FollowStateOut)
def unfollow_player(target_user_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> FollowStateOut:
    follower_id = int(current_user["id"])
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM player_follows WHERE follower_user_id = ? AND target_user_id = ?",
            (follower_id, target_user_id),
        )
        conn.commit()
    return FollowStateOut(following=False)


@app.get("/players/{target_user_id}/fanclub", response_model=list[FanclubMemberOut])
def get_player_fanclub(target_user_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> list[FanclubMemberOut]:
    with get_conn() as conn:
        target = conn.execute("SELECT id FROM users WHERE id = ?", (target_user_id,)).fetchone()
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

        rows = conn.execute(
            """
            SELECT u.id, u.username, u.display_name, COALESCE(u.global_rating, ?) AS global_rating
            FROM player_follows pf
            JOIN users u ON u.id = pf.follower_user_id
            WHERE pf.target_user_id = ?
            ORDER BY COALESCE(u.global_rating, ?) DESC, u.username ASC
            """,
            (DEFAULT_GLOBAL_RATING, target_user_id, DEFAULT_GLOBAL_RATING),
        ).fetchall()

    return [
        FanclubMemberOut(
            id=int(r["id"]),
            username=str(r["username"]),
            display_name=r["display_name"],
            global_rating=float(r["global_rating"] or DEFAULT_GLOBAL_RATING),
        )
        for r in rows
    ]


@app.post("/leagues/{league_id}/leave", response_model=MessageOut)
def leave_league(
    league_id: int,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        membership = conn.execute(
            "SELECT role FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        if membership is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not in this league.")
        if membership["role"] == "owner":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owners cannot leave their own league. Transfer ownership or delete the league.",
            )
        conn.execute(
            "DELETE FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        )
        conn.commit()
    return MessageOut(detail="You have left the league.")


@app.post("/leagues", response_model=LeagueOut, status_code=status.HTTP_201_CREATED)
def create_league(payload: LeagueCreatePayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> LeagueOut:
    created_at = utc_now_iso()
    user_id = int(current_user["id"])
    is_admin_creator = str(current_user["role"] or "") == "admin"
    with get_conn() as conn:
        auto_approve_leagues = get_bool_app_setting(conn, "auto_approve_leagues", default=False)
        should_auto_approve = is_admin_creator or auto_approve_leagues
        approval_status = "approved" if should_auto_approve else "pending"
        approved_at = created_at if should_auto_approve else None

        cursor = conn.execute(
            """
            INSERT INTO leagues (name, sport, football_type, goal_size, region, league_visibility, discover_visible, latitude, longitude, invite_code, description, fee_type, fee_value, match_presets_json, rating_config_json, approval_status, approved_at, approved_by_user_id, approval_note, owner_id, created_at, updated_at)
            VALUES (?, 'football', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name.strip(),
                payload.football_type,
                payload.goal_size,
                payload.region.strip(),
                payload.league_visibility,
                1 if payload.discover_visible else 0,
                payload.latitude,
                payload.longitude,
                secrets.token_hex(3).upper(),
                payload.description.strip() if payload.description else None,
                payload.fee_type,
                float(payload.fee_value or 0),
                json.dumps(payload.match_presets or []),
                json.dumps({**DEFAULT_RATING_CONFIG, **(payload.rating_config or {})}),
                approval_status,
                approved_at,
                user_id if is_admin_creator else None,
                None,
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
        conn.execute(
            "INSERT INTO league_seasons (league_id, name, is_active, created_at) VALUES (?, 'Season 1', 1, ?)",
            (int(league_id), created_at),
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
        is_member = _has_league_membership(conn, league_id, user_id)
        can_view_public = _is_league_public(conn, league_id)
        league_row = fetch_league_for_user(conn, league_id, user_id) if is_member else None

        if league_row is None and str(current_user["role"] or "") == "admin":
            league_row = conn.execute(
                """
                SELECT
                    l.id,
                    l.name,
                    l.football_type,
                    l.goal_size,
                    l.region,
                    l.league_visibility,
                    l.discover_visible,
                    l.latitude,
                    l.longitude,
                    l.invite_code,
                    l.description,
                    l.fee_type,
                    l.fee_value,
                    l.match_presets_json,
                    l.rating_config_json,
                    l.approval_status,
                    l.approved_at,
                    l.approval_note,
                    l.owner_id,
                    l.created_at,
                    l.auto_accept_members,
                    'admin' AS member_role,
                    owner.username AS owner_username,
                    (SELECT COUNT(*) FROM league_memberships AS member_count_source WHERE member_count_source.league_id = l.id) AS member_count
                FROM leagues AS l
                JOIN users AS owner ON owner.id = l.owner_id
                WHERE l.id = ?
                """,
                (league_id,),
            ).fetchone()

        if league_row is None and can_view_public:
            league_row = conn.execute(
                """
                SELECT
                    l.id,
                    l.name,
                    l.football_type,
                    l.goal_size,
                    l.region,
                    l.league_visibility,
                    l.discover_visible,
                    l.latitude,
                    l.longitude,
                    l.invite_code,
                    l.description,
                    l.fee_type,
                    l.fee_value,
                    l.match_presets_json,
                    l.rating_config_json,
                    l.approval_status,
                    l.approved_at,
                    l.approval_note,
                    l.owner_id,
                    l.created_at,
                    l.auto_accept_members,
                    'viewer' AS member_role,
                    owner.username AS owner_username,
                    (SELECT COUNT(*) FROM league_memberships AS member_count_source WHERE member_count_source.league_id = l.id) AS member_count
                FROM leagues AS l
                JOIN users AS owner ON owner.id = l.owner_id
                WHERE l.id = ?
                  AND COALESCE(l.approval_status, 'approved') = 'approved'
                  AND (l.terminated_until IS NULL OR datetime(l.terminated_until) <= datetime('now'))
                  AND COALESCE(l.league_visibility, 'public') = 'public'
                """,
                (league_id,),
            ).fetchone()

        if league_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
        members = [serialize_member(row) for row in fetch_league_members(conn, league_id)]
        membership = conn.execute("SELECT role FROM league_memberships WHERE league_id = ? AND user_id = ?", (league_id, user_id)).fetchone()
        invites: list[LeagueInviteOut] = []
        if (membership is not None and membership["role"] in {"owner", "admin"}) or str(current_user["role"] or "") == "admin":
            invites = [serialize_invite(row) for row in fetch_league_invites(conn, league_id)]
    return LeagueDetailOut(league=serialize_league(league_row), members=members, invites=invites)


@app.patch("/leagues/{league_id}/settings", response_model=MessageOut)
def update_league_settings(
    league_id: int,
    payload: LeagueSettingsPayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        updates: list[str] = []
        params: list = []
        if payload.name is not None:
            updates.append("name = ?")
            params.append(payload.name)
        if payload.description is not None:
            updates.append("description = ?")
            params.append(payload.description)
        if payload.region is not None:
            updates.append("region = ?")
            params.append(payload.region)
        if payload.league_visibility is not None:
            updates.append("league_visibility = ?")
            params.append(payload.league_visibility)
        if payload.discover_visible is not None:
            updates.append("discover_visible = ?")
            params.append(1 if payload.discover_visible else 0)
        if payload.latitude is not None:
            updates.append("latitude = ?")
            params.append(float(payload.latitude))
        if payload.longitude is not None:
            updates.append("longitude = ?")
            params.append(float(payload.longitude))
        if payload.football_type is not None:
            updates.append("football_type = ?")
            params.append(payload.football_type)
        if payload.goal_size is not None:
            updates.append("goal_size = ?")
            params.append(payload.goal_size)
        if payload.auto_accept_members is not None:
            updates.append("auto_accept_members = ?")
            params.append(1 if payload.auto_accept_members else 0)
        if payload.fee_type is not None:
            updates.append("fee_type = ?")
            params.append(payload.fee_type)
        if payload.fee_value is not None:
            updates.append("fee_value = ?")
            params.append(float(payload.fee_value))
        if payload.match_presets is not None:
            updates.append("match_presets_json = ?")
            params.append(json.dumps(payload.match_presets))
        if payload.rating_config is not None:
            merged_cfg = dict(DEFAULT_RATING_CONFIG)
            merged_cfg.update(payload.rating_config)
            updates.append("rating_config_json = ?")
            params.append(json.dumps(merged_cfg))
        if not updates:
            return MessageOut(detail="Nothing to update.")
        params.append(league_id)
        conn.execute(f"UPDATE leagues SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    return MessageOut(detail="League settings updated.")


@app.post("/leagues/{league_id}/seasons", response_model=LeagueSeasonOut, status_code=status.HTTP_201_CREATED)
def create_league_season(
    league_id: int,
    payload: LeagueSeasonCreatePayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> LeagueSeasonOut:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        start_at_iso = _parse_optional_utc_iso(payload.start_at, "start_at")
        end_at_iso = _parse_optional_utc_iso(payload.end_at, "end_at")
        _validate_season_window(start_at_iso, end_at_iso)
        if start_at_iso is not None:
            conn.execute(
                """
                UPDATE league_seasons
                SET end_at = ?
                WHERE league_id = ?
                  AND end_at IS NULL
                  AND id IN (
                    SELECT id FROM league_seasons
                    WHERE league_id = ?
                      AND COALESCE(start_at, created_at) < ?
                  )
                """,
                (start_at_iso, league_id, league_id, start_at_iso),
            )
        _assert_season_window_available(conn, league_id, start_at_iso, end_at_iso)

        auto_active = _season_is_active_at(start_at_iso, end_at_iso, utc_now())
        should_activate = bool(payload.activate or auto_active)
        if should_activate and not auto_active and (start_at_iso is not None or end_at_iso is not None):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot activate a season outside its scheduled start/end window",
            )

        if should_activate:
            conn.execute("UPDATE league_seasons SET is_active = 0 WHERE league_id = ?", (league_id,))

        created_at = utc_now_iso()
        cursor = conn.execute(
            "INSERT INTO league_seasons (league_id, name, description, is_active, start_at, end_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (league_id, payload.name.strip(), payload.description.strip() if payload.description else None, 1 if should_activate else 0, start_at_iso, end_at_iso, created_at),
        )
        season_id = cursor.lastrowid
        if season_id is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create season")
        _sync_league_season_activation(conn, league_id)
        conn.commit()
    return LeagueSeasonOut(
        id=int(season_id),
        league_id=league_id,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        is_active=bool(should_activate),
        start_at=start_at_iso,
        end_at=end_at_iso,
        created_at=created_at,
    )


@app.get("/leagues/{league_id}/seasons", response_model=list[LeagueSeasonOut])
def list_league_seasons(league_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> list[LeagueSeasonOut]:
    with get_conn() as conn:
        if not _can_view_league_stats(conn, league_id, int(current_user["id"])):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="League stats are private")
        _sync_league_season_activation(conn, league_id)
        rows = conn.execute(
            "SELECT id, league_id, name, description, is_active, start_at, end_at, created_at FROM league_seasons WHERE league_id = ? ORDER BY COALESCE(start_at, created_at) DESC, id DESC",
            (league_id,),
        ).fetchall()
        conn.commit()
    return [
        LeagueSeasonOut(
            id=int(r["id"]),
            league_id=int(r["league_id"]),
            name=str(r["name"]),
            description=str(r["description"]) if r["description"] else None,
            is_active=bool(int(r["is_active"] or 0)),
            start_at=str(r["start_at"]) if r["start_at"] else None,
            end_at=str(r["end_at"]) if r["end_at"] else None,
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


@app.post("/leagues/{league_id}/seasons/{season_id}/activate", response_model=MessageOut)
def activate_league_season(league_id: int, season_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        row = conn.execute(
            "SELECT id, start_at, end_at FROM league_seasons WHERE id = ? AND league_id = ?",
            (season_id, league_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
        if not _season_is_active_at(row["start_at"], row["end_at"], utc_now()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Season cannot be activated outside its scheduled window",
            )
        conn.execute("UPDATE league_seasons SET is_active = 0 WHERE league_id = ?", (league_id,))
        conn.execute("UPDATE league_seasons SET is_active = 1 WHERE id = ?", (season_id,))
        _sync_league_season_activation(conn, league_id)
        conn.commit()
    return MessageOut(detail="Season activated.")


@app.post("/admin/recompute-gmmr", response_model=MessageOut)
def admin_recompute_gmmr(current_user: sqlite3.Row = Depends(resolve_current_admin)) -> MessageOut:
    with get_conn() as conn:
        updated = _maybe_run_hierarchical_gmmr_recompute(conn, force=True)
        conn.commit()
    return MessageOut(detail=f"Hierarchical GMMR recompute finished. Updated {updated} players.")


@app.get("/leagues/{league_id}/player-stats-tabs", response_model=list[LeaguePlayerStatsTabOut])
def get_league_player_stats_tabs(league_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> list[LeaguePlayerStatsTabOut]:
    with get_conn() as conn:
        if not _can_view_league_stats(conn, league_id, int(current_user["id"])):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="League stats are private")
        _sync_league_season_activation(conn, league_id)

        general_rows = conn.execute(
            """
            SELECT u.id AS user_id, u.username, u.display_name,
                   COALESCE(lps.attendance, 0) AS attendance,
                   COALESCE(lps.wins, 0) AS wins,
                   COALESCE(lps.goals, 0) AS goals,
                 COALESCE(lps.own_goals, 0) AS own_goals,
                   COALESCE(lps.assists, 0) AS assists,
                   COALESCE(lps.rating, ?) AS lmmr
            FROM league_memberships AS lm
            JOIN users AS u ON u.id = lm.user_id
            LEFT JOIN league_player_stats AS lps ON lps.league_id = lm.league_id AND lps.user_id = lm.user_id
            WHERE lm.league_id = ?
            ORDER BY lmmr DESC, u.username
            """,
            (DEFAULT_GLOBAL_RATING, league_id),
        ).fetchall()

        tabs: list[LeaguePlayerStatsTabOut] = [
            LeaguePlayerStatsTabOut(
                key="general",
                label="General",
                rows=[
                    LeaguePlayerStatsTabRow(
                        user_id=int(r["user_id"]),
                        username=str(r["username"]),
                        display_name=r["display_name"],
                        attendance=int(r["attendance"]),
                        wins=int(r["wins"]),
                        goals=int(r["goals"]),
                        own_goals=int(r["own_goals"]),
                        assists=int(r["assists"]),
                        lmmr=float(r["lmmr"]),
                        sr_points=0.0,
                    )
                    for r in general_rows
                ],
            )
        ]

        seasons = conn.execute(
            "SELECT id, name, is_active, start_at, end_at FROM league_seasons WHERE league_id = ? ORDER BY COALESCE(start_at, created_at) DESC, id DESC",
            (league_id,),
        ).fetchall()

        for season in seasons:
            rows = conn.execute(
                """
                SELECT u.id AS user_id, u.username, u.display_name,
                       COALESCE(ss.attendance, 0) AS attendance,
                       COALESCE(ss.wins, 0) AS wins,
                       COALESCE(ss.goals, 0) AS goals,
                      COALESCE(ss.own_goals, 0) AS own_goals,
                       COALESCE(ss.assists, 0) AS assists,
                       COALESCE(lps.rating, ?) AS lmmr,
                       COALESCE(ss.points, ?) AS sr_points
                FROM league_memberships AS lm
                JOIN users AS u ON u.id = lm.user_id
                LEFT JOIN league_player_stats AS lps ON lps.league_id = lm.league_id AND lps.user_id = lm.user_id
                LEFT JOIN league_season_player_stats AS ss ON ss.season_id = ? AND ss.user_id = lm.user_id
                WHERE lm.league_id = ?
                ORDER BY sr_points DESC, lmmr DESC, u.username
                """,
                (DEFAULT_GLOBAL_RATING, DEFAULT_RATING_CONFIG["sr_start_points"], int(season["id"]), league_id),
            ).fetchall()
            label = str(season["name"])
            if season["start_at"] or season["end_at"]:
                start_lbl = str(season["start_at"] or "?")[:10]
                end_lbl = str(season["end_at"] or "...")[:10]
                label += f" ({start_lbl} to {end_lbl})"
            if int(season["is_active"] or 0):
                label += " (Current)"
            tabs.append(
                LeaguePlayerStatsTabOut(
                    key=f"season-{int(season['id'])}",
                    label=label,
                    rows=[
                        LeaguePlayerStatsTabRow(
                            user_id=int(r["user_id"]),
                            username=str(r["username"]),
                            display_name=r["display_name"],
                            attendance=int(r["attendance"]),
                            wins=int(r["wins"]),
                            goals=int(r["goals"]),
                            own_goals=int(r["own_goals"]),
                            assists=int(r["assists"]),
                            lmmr=float(r["lmmr"]),
                            sr_points=float(r["sr_points"]),
                        )
                        for r in rows
                    ],
                )
            )

            conn.commit()

    return tabs


@app.post("/leagues/{league_id}/members/{member_user_id}/ban", response_model=MessageOut)
def ban_member(
    league_id: int,
    member_user_id: int,
    payload: LeagueBanPayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        target = conn.execute(
            "SELECT role FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, member_user_id),
        ).fetchone()
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        if target["role"] == "owner":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot ban the owner")
        # kick first
        conn.execute(
            "DELETE FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, member_user_id),
        )
        # blacklist
        conn.execute(
            """
            INSERT INTO league_bans(league_id, user_id, banned_by, reason, created_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(league_id, user_id) DO UPDATE SET
                banned_by=excluded.banned_by,
                reason=excluded.reason,
                created_at=excluded.created_at
            """,
            (league_id, member_user_id, int(current_user["id"]), payload.reason, utc_now_iso()),
        )
        add_discipline_history(
            conn,
            league_id=league_id,
            user_id=member_user_id,
            action="ban",
            actor_user_id=int(current_user["id"]),
            reason=payload.reason,
        )
        conn.commit()
    return MessageOut(detail="Member banned and removed from the league.")


@app.delete("/leagues/{league_id}/bans/{user_id}", response_model=MessageOut)
def unban_member(
    league_id: int,
    user_id: int,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        result = conn.execute(
            "DELETE FROM league_bans WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        )
        if result.rowcount == 0:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No ban found for this user.")
        add_discipline_history(
            conn,
            league_id=league_id,
            user_id=user_id,
            action="unban",
            actor_user_id=int(current_user["id"]),
            reason=None,
        )
        conn.commit()
    return MessageOut(detail="User unbanned.")


@app.post("/leagues/{league_id}/members/{member_user_id}/penalty", response_model=MessageOut)
def set_member_penalty(
    league_id: int,
    member_user_id: int,
    payload: LeaguePenaltyPayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    try:
        until_dt = datetime.fromisoformat(payload.until)
        if until_dt.tzinfo is None:
            until_dt = until_dt.replace(tzinfo=timezone.utc)
        if until_dt <= utc_now():
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'until' must be a future ISO datetime.")
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        target = conn.execute(
            "SELECT role FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, member_user_id),
        ).fetchone()
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        conn.execute(
            """
            INSERT INTO league_penalties(league_id, user_id, penalty_until, reason, imposed_by, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(league_id, user_id) DO UPDATE SET
                penalty_until=excluded.penalty_until,
                reason=excluded.reason,
                imposed_by=excluded.imposed_by,
                created_at=excluded.created_at
            """,
            (league_id, member_user_id, until_dt.isoformat(), payload.reason, int(current_user["id"]), utc_now_iso()),
        )
        add_discipline_history(
            conn,
            league_id=league_id,
            user_id=member_user_id,
            action="penalty_set",
            actor_user_id=int(current_user["id"]),
            reason=payload.reason,
            penalty_until=until_dt.isoformat(),
        )
        conn.commit()
    return MessageOut(detail="Penalty applied.")


@app.delete("/leagues/{league_id}/members/{member_user_id}/penalty", response_model=MessageOut)
def remove_member_penalty(
    league_id: int,
    member_user_id: int,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        existing = conn.execute(
            "SELECT penalty_until, reason FROM league_penalties WHERE league_id = ? AND user_id = ?",
            (league_id, member_user_id),
        ).fetchone()
        conn.execute(
            "DELETE FROM league_penalties WHERE league_id = ? AND user_id = ?",
            (league_id, member_user_id),
        )
        if existing is not None:
            add_discipline_history(
                conn,
                league_id=league_id,
                user_id=member_user_id,
                action="penalty_removed",
                actor_user_id=int(current_user["id"]),
                reason=existing["reason"],
                penalty_until=existing["penalty_until"],
            )
        conn.commit()
    return MessageOut(detail="Penalty removed.")


@app.get("/leagues/{league_id}/members/{member_user_id}/discipline-history", response_model=list[LeagueDisciplineHistoryOut])
def member_discipline_history(
    league_id: int,
    member_user_id: int,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> list[LeagueDisciplineHistoryOut]:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        rows = conn.execute(
            """
            SELECT
                h.id,
                h.user_id,
                h.action,
                h.reason,
                h.penalty_until,
                h.created_at,
                actor.username AS actor_username,
                actor.display_name AS actor_display_name
            FROM league_discipline_history h
            LEFT JOIN users AS actor ON actor.id = h.actor_user_id
            WHERE h.league_id = ? AND h.user_id = ?
            ORDER BY h.created_at DESC, h.id DESC
            """,
            (league_id, member_user_id),
        ).fetchall()
    return [
        LeagueDisciplineHistoryOut(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            action=str(r["action"]),
            reason=r["reason"],
            penalty_until=r["penalty_until"],
            created_at=str(r["created_at"]),
            actor_username=(str(r["actor_username"]) if r["actor_username"] is not None else None),
            actor_display_name=(str(r["actor_display_name"]) if r["actor_display_name"] is not None else None),
        )
        for r in rows
    ]


@app.get("/leagues/{league_id}/bans", response_model=list[LeagueMemberStatusOut])
def list_bans(
    league_id: int,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> list[LeagueMemberStatusOut]:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        rows = conn.execute(
            """
            SELECT u.id AS user_id, u.username, u.display_name,
                   1 AS is_banned, NULL AS penalty_until, lb.reason AS penalty_reason
            FROM league_bans lb
            JOIN users u ON u.id = lb.user_id
            WHERE lb.league_id = ?
            ORDER BY lb.created_at DESC
            """,
            (league_id,),
        ).fetchall()
    return [
        LeagueMemberStatusOut(
            user_id=r["user_id"],
            username=r["username"],
            display_name=r["display_name"],
            is_banned=True,
            penalty_until=None,
            penalty_reason=r["penalty_reason"],
        )
        for r in rows
    ]


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
def create_league_invite(
    league_id: int,
    max_uses: int = 1,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> LeagueInviteOut:
    if max_uses < 1 or max_uses > 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="max_uses must be between 1 and 200")
    created_at = utc_now_iso()
    expires_at = (utc_now() + timedelta(days=LEAGUE_INVITE_EXPIRY_DAYS)).isoformat()
    token = secrets.token_urlsafe(18)
    with get_conn() as conn:
        league = require_league_manager(conn, league_id, int(current_user["id"]))
        require_league_approved(conn, league_id)
        cursor = conn.execute(
            """
            INSERT INTO league_invites (league_id, token, created_by_user_id, created_at, expires_at, max_uses, use_count, revoked)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (league_id, token, int(current_user["id"]), created_at, expires_at, max_uses),
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
        creator_username=str(current_user["username"]),
        accepted_by_username=None,
        created_at=created_at,
        expires_at=expires_at,
        max_uses=max_uses,
        use_count=0,
        revoked=0,
        expired=False,
        invite_url=build_invite_url(token),
    )


@app.get("/leagues/{league_id}/invites", response_model=list[LeagueInviteOut])
def list_league_invites(
    league_id: int,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> list[LeagueInviteOut]:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        rows = fetch_league_invites(conn, league_id)
    return [serialize_invite(row) for row in rows]


@app.delete("/leagues/{league_id}/invites/{invite_id}", response_model=MessageOut)
def cancel_league_invite(
    league_id: int,
    invite_id: int,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        result = conn.execute(
            "UPDATE league_invites SET revoked = 1 WHERE id = ? AND league_id = ? AND revoked = 0",
            (invite_id, league_id),
        )
        conn.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    return MessageOut(detail="Invite cancelled.")


@app.get("/league-invites/{token}", response_model=InvitePreviewOut)
def preview_league_invite(token: str) -> InvitePreviewOut:
    with get_conn() as conn:
        invite = invite_preview_row(conn, token.strip())
    if invite is None or int(invite["revoked"]) == 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if str(invite["approval_status"] or "approved") != "approved":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="League is awaiting admin approval")
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
        require_league_approved(conn, league_id)
        user_id = int(current_user["id"])
        # Check if user is banned from this league
        ban = conn.execute(
            "SELECT id FROM league_bans WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        if ban is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are banned from this league.")
        existing_membership = conn.execute(
            "SELECT role FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        if existing_membership is None:
            conn.execute(
                "INSERT INTO league_memberships (league_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
                (league_id, user_id, utc_now_iso()),
            )
            _ensure_member_lps_with_temp_rating(conn, league_id, user_id)
            conn.execute(
                "UPDATE league_invites SET use_count = use_count + 1, accepted_by_user_id = ? WHERE id = ?",
                (user_id, int(invite["id"])),
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


@app.get("/admin/overview")
def admin_overview(current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> dict[str, int]:
    with get_conn() as conn:
        users_total = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        users_active = int(conn.execute("SELECT COUNT(*) FROM users WHERE COALESCE(is_active, 1) = 1").fetchone()[0])
        leagues_total = int(conn.execute("SELECT COUNT(*) FROM leagues").fetchone()[0])
        leagues_pending = int(conn.execute("SELECT COUNT(*) FROM leagues WHERE COALESCE(approval_status, 'approved') = 'pending'").fetchone()[0])
        leagues_rejected = int(conn.execute("SELECT COUNT(*) FROM leagues WHERE COALESCE(approval_status, 'approved') = 'rejected'").fetchone()[0])
    return {
        "users_total": users_total,
        "users_active": users_active,
        "leagues_total": leagues_total,
        "leagues_pending": leagues_pending,
        "leagues_rejected": leagues_rejected,
    }


@app.get("/admin/settings", response_model=AdminSettingsOut)
def admin_get_settings(current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> AdminSettingsOut:
    with get_conn() as conn:
        return AdminSettingsOut(
            auto_approve_leagues=get_bool_app_setting(conn, "auto_approve_leagues", default=False),
        )


@app.patch("/admin/settings", response_model=AdminSettingsOut)
def admin_patch_settings(
    payload: AdminSettingsPatchPayload,
    current_admin: sqlite3.Row = Depends(resolve_current_admin),
) -> AdminSettingsOut:
    with get_conn() as conn:
        if payload.auto_approve_leagues is not None:
            set_app_setting(conn, "auto_approve_leagues", "1" if payload.auto_approve_leagues else "0")
        conn.commit()
        return AdminSettingsOut(
            auto_approve_leagues=get_bool_app_setting(conn, "auto_approve_leagues", default=False),
        )


@app.get("/admin/users", response_model=list[AdminUserOut])
def admin_list_users(current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> list[AdminUserOut]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.email, u.display_name, u.role, u.recovery_id, u.is_active, u.terminated_at,
                   u.created_at, u.updated_at, u.attendance, u.wins, u.goals, u.assists, u.global_rating,
                   (SELECT COUNT(*) FROM league_memberships AS lm WHERE lm.user_id = u.id) AS league_count,
                   (SELECT COUNT(*) FROM leagues AS l WHERE l.owner_id = u.id) AS owned_league_count
            FROM users AS u
            ORDER BY COALESCE(u.is_active, 1) DESC, u.created_at DESC, u.id DESC
            """
        ).fetchall()
    return [
        AdminUserOut(
            id=int(r["id"]),
            username=str(r["username"]),
            email=str(r["email"] or ""),
            display_name=r["display_name"],
            role=str(r["role"]),
            recovery_id=(str(r["recovery_id"]) if r["recovery_id"] is not None else None),
            recovery_token=(str(r["recovery_id"]) if r["recovery_id"] is not None else None),
            is_active=bool(int(r["is_active"] or 0)),
            terminated_at=(str(r["terminated_at"]) if r["terminated_at"] is not None else None),
            created_at=str(r["created_at"]),
            updated_at=str(r["updated_at"]),
            attendance=int(r["attendance"] or 0),
            wins=int(r["wins"] or 0),
            goals=int(r["goals"] or 0),
            assists=int(r["assists"] or 0),
            global_rating=float(r["global_rating"] or DEFAULT_GLOBAL_RATING),
            league_count=int(r["league_count"] or 0),
            owned_league_count=int(r["owned_league_count"] or 0),
        )
        for r in rows
    ]


@app.get("/admin/leagues", response_model=list[AdminLeagueOut])
def admin_list_leagues(current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> list[AdminLeagueOut]:
    with get_conn() as conn:
        rows = conn.execute(
            """
                 SELECT l.id, l.name, l.football_type, l.goal_size, l.region, l.description,
                   l.owner_id, owner.username AS owner_username,
                     l.approval_status, l.approved_at, l.approval_note,
                     l.terminated_until, l.created_at, l.updated_at,
                   (SELECT COUNT(*) FROM league_memberships AS lm WHERE lm.league_id = l.id) AS member_count
            FROM leagues AS l
            JOIN users AS owner ON owner.id = l.owner_id
            ORDER BY CASE COALESCE(l.approval_status, 'approved') WHEN 'pending' THEN 0 WHEN 'rejected' THEN 1 ELSE 2 END,
                     l.created_at DESC, l.id DESC
            """
        ).fetchall()
    out: list[AdminLeagueOut] = []
    now = utc_now()
    for r in rows:
        terminated_until_text = str(r["terminated_until"]) if r["terminated_until"] is not None else None
        is_terminated = False
        if terminated_until_text:
            try:
                term_dt = datetime.fromisoformat(terminated_until_text)
                if term_dt.tzinfo is None:
                    term_dt = term_dt.replace(tzinfo=timezone.utc)
                is_terminated = now < term_dt
            except Exception:
                is_terminated = False
        out.append(
            AdminLeagueOut(
                id=int(r["id"]),
                name=str(r["name"]),
                football_type=str(r["football_type"]),
                goal_size=str(r["goal_size"]),
                region=str(r["region"] or "Unknown"),
                description=r["description"],
                owner_id=int(r["owner_id"]),
                owner_username=str(r["owner_username"]),
                member_count=int(r["member_count"] or 0),
                approval_status=str(r["approval_status"] or "approved"),
                approved_at=(str(r["approved_at"]) if r["approved_at"] is not None else None),
                approval_note=(str(r["approval_note"]) if r["approval_note"] is not None else None),
                terminated_until=terminated_until_text,
                is_terminated=is_terminated,
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
            )
        )
    return out


@app.patch("/admin/leagues/{league_id}/approval", response_model=MessageOut)
def admin_update_league_approval(
    league_id: int,
    payload: LeagueApprovalPayload,
    current_admin: sqlite3.Row = Depends(resolve_current_admin),
) -> MessageOut:
    with get_conn() as conn:
        league = conn.execute("SELECT id, name FROM leagues WHERE id = ?", (league_id,)).fetchone()
        if league is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
        approved_at = utc_now_iso() if payload.status == "approved" else None
        conn.execute(
            """
            UPDATE leagues
            SET approval_status = ?, approved_at = ?, approved_by_user_id = ?, approval_note = ?, updated_at = ?
            WHERE id = ?
            """,
            (payload.status, approved_at, int(current_admin["id"]), payload.note, utc_now_iso(), league_id),
        )
        conn.commit()
    return MessageOut(detail=f"League '{league['name']}' marked as {payload.status}.")


@app.post("/admin/leagues/{league_id}/terminate-temporary", response_model=MessageOut)
def admin_temporarily_terminate_league(
    league_id: int,
    payload: AdminLeagueTemporaryTerminatePayload,
    current_admin: sqlite3.Row = Depends(resolve_current_admin),
) -> MessageOut:
    try:
        until_dt = datetime.fromisoformat(payload.until)
        if until_dt.tzinfo is None:
            until_dt = until_dt.replace(tzinfo=timezone.utc)
        if until_dt <= utc_now():
            raise ValueError
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="until must be a future ISO datetime")

    with get_conn() as conn:
        league = conn.execute("SELECT id, name FROM leagues WHERE id = ?", (league_id,)).fetchone()
        if league is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
        conn.execute(
            "UPDATE leagues SET terminated_until = ?, termination_note = ?, terminated_by_user_id = ?, updated_at = ? WHERE id = ?",
            (until_dt.isoformat(), payload.note, int(current_admin["id"]), utc_now_iso(), league_id),
        )
        conn.commit()
    return MessageOut(detail=f"League '{league['name']}' terminated until {until_dt.isoformat()}.")


@app.post("/admin/leagues/{league_id}/unterminate", response_model=MessageOut)
def admin_unterminate_league(
    league_id: int,
    current_admin: sqlite3.Row = Depends(resolve_current_admin),
) -> MessageOut:
    with get_conn() as conn:
        league = conn.execute("SELECT id, name FROM leagues WHERE id = ?", (league_id,)).fetchone()
        if league is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
        conn.execute(
            "UPDATE leagues SET terminated_until = NULL, termination_note = NULL, terminated_by_user_id = NULL, updated_at = ? WHERE id = ?",
            (utc_now_iso(), league_id),
        )
        conn.commit()
    return MessageOut(detail=f"League '{league['name']}' is active again.")


@app.delete("/admin/leagues/{league_id}/terminate-permanent", response_model=MessageOut)
def admin_permanently_terminate_league(
    league_id: int,
    payload: AdminLeaguePermanentTerminatePayload,
    current_admin: sqlite3.Row = Depends(resolve_current_admin),
) -> MessageOut:
    if not payload.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confirm=true is required for permanent termination")
    with get_conn() as conn:
        league = conn.execute("SELECT id, name FROM leagues WHERE id = ?", (league_id,)).fetchone()
        if league is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
        conn.execute("DELETE FROM leagues WHERE id = ?", (league_id,))
        conn.commit()
    return MessageOut(detail=f"League '{league['name']}' permanently deleted.")


@app.post("/admin/users/{user_id}/force-password-reset", response_model=AdminPasswordResetOut)
def admin_force_password_reset(
    user_id: int,
    payload: AdminPasswordResetPayload,
    current_admin: sqlite3.Row = Depends(resolve_current_admin),
) -> AdminPasswordResetOut:
    with get_conn() as conn:
        user = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if int(user["id"]) == int(current_admin["id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use the account settings page to change your own password")
        new_password = payload.new_password or secrets.token_urlsafe(9)
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (hash_password(new_password), utc_now_iso(), user_id),
        )
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
        conn.commit()
    return AdminPasswordResetOut(detail=f"Password reset for {user['username']}.", password=new_password)


@app.post("/admin/users/{user_id}/reset-password", response_model=AdminPasswordResetOut)
def admin_reset_password_alias(
    user_id: int,
    payload: AdminPasswordResetPayload,
    current_admin: sqlite3.Row = Depends(resolve_current_admin),
) -> AdminPasswordResetOut:
    return admin_force_password_reset(user_id, payload, current_admin)


@app.post("/admin/users/{user_id}/block", response_model=MessageOut)
def admin_block_user(user_id: int, current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> MessageOut:
    with get_conn() as conn:
        user = conn.execute("SELECT id, username, role, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if int(user["id"]) == int(current_admin["id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot block the current account")
        if not bool(int(user["is_active"] or 0)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account is already blocked")
        conn.execute(
            "UPDATE users SET is_active = 0, terminated_at = ?, updated_at = ? WHERE id = ?",
            (utc_now_iso(), utc_now_iso(), user_id),
        )
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
        conn.commit()
    return MessageOut(detail=f"Account '{user['username']}' blocked.")


@app.post("/admin/users/{user_id}/unblock", response_model=MessageOut)
def admin_unblock_user(user_id: int, current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> MessageOut:
    with get_conn() as conn:
        user = conn.execute("SELECT id, username, role, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if bool(int(user["is_active"] or 0)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account is already active")
        conn.execute(
            "UPDATE users SET is_active = 1, terminated_at = NULL, updated_at = ? WHERE id = ?",
            (utc_now_iso(), user_id),
        )
        conn.commit()
    return MessageOut(detail=f"Account '{user['username']}' unblocked.")


@app.post("/admin/users/{user_id}/promote", response_model=MessageOut)
def admin_promote_user(user_id: int, current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> MessageOut:
    with get_conn() as conn:
        user = conn.execute("SELECT id, username, role, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if str(user["role"] or "") == "admin":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already an admin")

        conn.execute(
            "UPDATE users SET role = 'admin', is_active = 1, terminated_at = NULL, updated_at = ? WHERE id = ?",
            (utc_now_iso(), user_id),
        )
        conn.commit()
    return MessageOut(detail=f"User '{user['username']}' promoted to admin.")


@app.post("/admin/users/{user_id}/terminate", response_model=MessageOut)
def admin_terminate_user(user_id: int, current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> MessageOut:
    return admin_block_user(user_id, current_admin)


@app.post("/admin/hard-reset", response_model=MessageOut)
def admin_hard_reset(current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> MessageOut:
    """Delete all match / event / season data, clear all stats back to defaults, and wipe notifications and social connections."""
    admin_id = int(current_admin["id"])
    with get_conn() as conn:
        conn.execute("DELETE FROM match_events")
        conn.execute("DELETE FROM match_registrations")
        conn.execute("DELETE FROM matches")
        conn.execute("DELETE FROM league_season_player_stats")
        conn.execute("DELETE FROM league_seasons")
        conn.execute("DELETE FROM league_penalties")
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM friendships")
        conn.execute("DELETE FROM player_follows")
        conn.execute("UPDATE league_player_stats SET attendance=0, wins=0, goals=0, own_goals=0, assists=0, rating=1000")
        conn.execute("UPDATE users SET global_rating=1000, attendance=0, wins=0, goals=0, assists=0 WHERE role != 'admin'")
        conn.commit()
    return MessageOut(detail="Hard reset complete. All match data, stats, notifications, and social connections have been cleared.")


class AdminMatchOut(BaseModel):
    id: int
    league_id: int
    league_name: str
    title: str
    status: str
    scheduled_at: str
    score_a: int
    score_b: int
    created_by_username: str
    participant_count: int


@app.get("/admin/matches", response_model=list[AdminMatchOut])
def admin_list_matches(current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> list[AdminMatchOut]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT m.id, m.league_id, l.name AS league_name, m.title, m.status,
                   m.scheduled_at, COALESCE(m.score_a, 0) AS score_a, COALESCE(m.score_b, 0) AS score_b,
                   u.username AS created_by_username,
                   (SELECT COUNT(*) FROM match_registrations mr WHERE mr.match_id = m.id AND mr.status = 'registered') AS participant_count
            FROM matches m
            JOIN leagues l ON l.id = m.league_id
            JOIN users u ON u.id = m.created_by
            ORDER BY m.scheduled_at DESC
            LIMIT 500
        """).fetchall()
    return [AdminMatchOut(
        id=int(r["id"]), league_id=int(r["league_id"]), league_name=str(r["league_name"]),
        title=str(r["title"]), status=str(r["status"]), scheduled_at=str(r["scheduled_at"]),
        score_a=int(r["score_a"]), score_b=int(r["score_b"]),
        created_by_username=str(r["created_by_username"]),
        participant_count=int(r["participant_count"]),
    ) for r in rows]


@app.delete("/admin/matches/{match_id}", response_model=MessageOut)
def admin_delete_match(match_id: int, current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> MessageOut:
    with get_conn() as conn:
        if not conn.execute("SELECT id FROM matches WHERE id = ?", (match_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Match not found.")
        conn.execute("DELETE FROM match_events WHERE match_id = ?", (match_id,))
        conn.execute("DELETE FROM match_registrations WHERE match_id = ?", (match_id,))
        conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))
        conn.commit()
    return MessageOut(detail="Match deleted.")


@app.delete("/admin/users/{user_id}", response_model=MessageOut)
def admin_delete_user(user_id: int, current_admin: sqlite3.Row = Depends(resolve_current_admin)) -> MessageOut:
    admin_id = int(current_admin["id"])
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account.")
    with get_conn() as conn:
        row = conn.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        if str(row["role"]) == "admin":
            raise HTTPException(status_code=400, detail="Cannot delete admin accounts.")
        conn.execute("DELETE FROM notifications WHERE user_id = ? OR actor_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM friendships WHERE user_id = ? OR friend_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM player_follows WHERE follower_id = ? OR followed_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM match_registrations WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM league_player_stats WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM league_season_player_stats WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM league_memberships WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM league_join_requests WHERE user_id = ?", (user_id,))
        # Cascade-delete leagues owned by this user
        owned = conn.execute("SELECT id FROM leagues WHERE owner_id = ?", (user_id,)).fetchall()
        for lg in owned:
            lid = int(lg["id"])
            conn.execute("DELETE FROM match_events WHERE match_id IN (SELECT id FROM matches WHERE league_id = ?)", (lid,))
            conn.execute("DELETE FROM match_registrations WHERE match_id IN (SELECT id FROM matches WHERE league_id = ?)", (lid,))
            conn.execute("DELETE FROM matches WHERE league_id = ?", (lid,))
            conn.execute("DELETE FROM league_player_stats WHERE league_id = ?", (lid,))
            conn.execute("DELETE FROM league_season_player_stats WHERE league_id = ?", (lid,))
            conn.execute("DELETE FROM league_memberships WHERE league_id = ?", (lid,))
            conn.execute("DELETE FROM league_join_requests WHERE league_id = ?", (lid,))
            conn.execute("DELETE FROM league_seasons WHERE league_id = ?", (lid,))
            conn.execute("DELETE FROM league_penalties WHERE league_id = ?", (lid,))
            conn.execute("DELETE FROM leagues WHERE id = ?", (lid,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    return MessageOut(detail="User and all associated data deleted.")


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
        require_league_approved(conn, league_id)
        # Check if user is banned from this league
        ban = conn.execute(
            "SELECT id FROM league_bans WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        if ban is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are banned from this league.")
        existing_membership = conn.execute(
            "SELECT id FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        if existing_membership is None:
            conn.execute(
                "INSERT INTO league_memberships (league_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
                (league_id, user_id, utc_now_iso()),
            )
            _ensure_member_lps_with_temp_rating(conn, league_id, user_id)
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
    latitude: float | None = None,
    longitude: float | None = None,
    max_km: float | None = None,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> list[dict]:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        params: list = [user_id]
        where_clauses = [
            "l.id NOT IN (SELECT league_id FROM league_memberships WHERE user_id = ?)",
            "COALESCE(l.approval_status, 'approved') = 'approved'",
            "COALESCE(l.discover_visible, 1) = 1",
            "(l.terminated_until IS NULL OR datetime(l.terminated_until) <= datetime('now'))",
        ]
        if region and region.strip():
            where_clauses.append("LOWER(l.region) LIKE LOWER(?)")
            params.append(f"%{region.strip()}%")
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
                l.latitude,
                l.longitude,
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

    items: list[dict] = []
    for row in rows:
        lat = float(row["latitude"]) if row["latitude"] is not None else None
        lon = float(row["longitude"]) if row["longitude"] is not None else None
        distance_km: float | None = None
        if latitude is not None and longitude is not None and lat is not None and lon is not None:
            distance_km = _haversine_km(float(latitude), float(longitude), lat, lon)
        if max_km is not None and distance_km is not None and distance_km > float(max_km):
            continue
        items.append(
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "football_type": str(row["football_type"]),
                "goal_size": str(row["goal_size"]),
                "region": str(row["region"] or "Unknown"),
                "latitude": lat,
                "longitude": lon,
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
                "description": row["description"],
                "owner_username": str(row["owner_username"]),
                "member_count": int(row["member_count"]),
                "my_request_status": row["my_request_status"],
            }
        )

    if latitude is not None and longitude is not None:
        items.sort(key=lambda item: (item["distance_km"] is None, item["distance_km"] if item["distance_km"] is not None else 1e12, item["name"].lower()))
    return items


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
        require_league_approved(conn, league_id)
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
                    _ensure_member_lps_with_temp_rating(conn, league_id, target_user_id)
        conn.commit()
    return MessageOut(detail=("Join request accepted." if payload.decision == "accept" else "Join request rejected."))


@app.get("/leagues/{league_id}/lmmr-placements/pending")
def list_pending_lmmr_placements(league_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> list[dict]:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        rows = conn.execute(
            """
            SELECT p.user_id, p.reason, p.suggested_rating, p.created_at, u.username, u.display_name, COALESCE(u.global_rating, ?) AS global_rating
            FROM league_lmmr_placements p
            JOIN users u ON u.id = p.user_id
            WHERE p.league_id = ? AND p.status = 'pending'
            ORDER BY p.created_at ASC
            """,
            (DEFAULT_GLOBAL_RATING, league_id),
        ).fetchall()
    return [
        {
            "user_id": int(r["user_id"]),
            "username": str(r["username"]),
            "display_name": r["display_name"],
            "global_rating": float(r["global_rating"] or DEFAULT_GLOBAL_RATING),
            "reason": str(r["reason"] or "new_player_needs_manual_seed"),
            "suggested_rating": float(r["suggested_rating"] or DEFAULT_GLOBAL_RATING),
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]


@app.get("/leagues/{league_id}/lmmr-placements/{user_id}/candidates")
def get_lmmr_placement_candidates(league_id: int, user_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> dict:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        pending = conn.execute(
            "SELECT suggested_rating, reason, created_at FROM league_lmmr_placements WHERE league_id = ? AND user_id = ? AND status = 'pending'",
            (league_id, user_id),
        ).fetchone()
        if pending is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending placement for this player")

        target = conn.execute(
            "SELECT id, username, display_name, COALESCE(global_rating, ?) AS global_rating FROM users WHERE id = ?",
            (DEFAULT_GLOBAL_RATING, user_id),
        ).fetchone()
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        rows = conn.execute(
            """
            SELECT lm.user_id, u.username, u.display_name, COALESCE(lps.rating, ?) AS rating
            FROM league_memberships lm
            JOIN users u ON u.id = lm.user_id
            LEFT JOIN league_player_stats lps ON lps.league_id = lm.league_id AND lps.user_id = lm.user_id
            WHERE lm.league_id = ? AND lm.user_id != ?
            ORDER BY rating ASC, u.username ASC
            """,
            (DEFAULT_GLOBAL_RATING, league_id, user_id),
        ).fetchall()

    return {
        "target": {
            "user_id": int(target["id"]),
            "username": str(target["username"]),
            "display_name": target["display_name"],
            "global_rating": float(target["global_rating"] or DEFAULT_GLOBAL_RATING),
        },
        "reason": str(pending["reason"] or "new_player_needs_manual_seed"),
        "suggested_rating": float(pending["suggested_rating"] or DEFAULT_GLOBAL_RATING),
        "created_at": str(pending["created_at"]),
        "candidates": [
            {
                "user_id": int(r["user_id"]),
                "username": str(r["username"]),
                "display_name": r["display_name"],
                "rating": float(r["rating"] or DEFAULT_GLOBAL_RATING),
            }
            for r in rows
        ],
    }


@app.post("/leagues/{league_id}/lmmr-placements/{user_id}/resolve", response_model=MessageOut)
def resolve_lmmr_placement(
    league_id: int,
    user_id: int,
    payload: LeagueLmmrPlacementResolvePayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MessageOut:
    manager_id = int(current_user["id"])
    with get_conn() as conn:
        require_league_manager(conn, league_id, manager_id)
        pending = conn.execute(
            "SELECT id FROM league_lmmr_placements WHERE league_id = ? AND user_id = ? AND status = 'pending'",
            (league_id, user_id),
        ).fetchone()
        if pending is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending placement for this player")

        lps = conn.execute(
            "SELECT id FROM league_player_stats WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        if lps is None:
            conn.execute(
                """
                INSERT INTO league_player_stats (
                    league_id,
                    user_id,
                    attendance,
                    wins,
                    goals,
                    assists,
                    rating,
                    is_temporary_lmmr,
                    temporary_lmmr_match_limit
                ) VALUES (?, ?, 0, 0, 0, 0, ?, 1, ?)
                """,
                (league_id, user_id, float(payload.final_rating), TEMP_LMMR_MATCH_LIMIT),
            )
        else:
            conn.execute(
                """
                UPDATE league_player_stats
                SET rating = ?,
                    is_temporary_lmmr = CASE WHEN attendance < ? THEN 1 ELSE 0 END,
                    temporary_lmmr_match_limit = ?
                WHERE league_id = ? AND user_id = ?
                """,
                (float(payload.final_rating), TEMP_LMMR_MATCH_LIMIT, TEMP_LMMR_MATCH_LIMIT, league_id, user_id),
            )

        conn.execute(
            """
            UPDATE league_lmmr_placements
            SET status = 'resolved', final_rating = ?, note = ?, resolved_at = ?, resolved_by_user_id = ?
            WHERE league_id = ? AND user_id = ?
            """,
            (float(payload.final_rating), payload.note.strip() if payload.note else None, utc_now_iso(), manager_id, league_id, user_id),
        )

        _create_notification(
            conn,
            user_id,
            "lmmr_placement_resolved",
            "Your temporary LMMR was placed",
            "A league manager placed your initial league rating.",
            {"league_id": league_id, "final_rating": float(payload.final_rating)},
        )
        conn.commit()
    return MessageOut(detail="Placement saved.")


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


def _expected_win_probability(team_avg: float, opp_avg: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opp_avg - team_avg) / 400.0))


def _load_league_rating_config(conn: sqlite3.Connection, league_id: int) -> dict:
    row = conn.execute("SELECT rating_config_json FROM leagues WHERE id = ?", (league_id,)).fetchone()
    cfg = dict(DEFAULT_RATING_CONFIG)
    if row is None:
        return cfg
    try:
        raw = json.loads(str(row["rating_config_json"] or "{}"))
        if isinstance(raw, dict):
            cfg.update(raw)
    except Exception:
        pass
    return cfg


def _fit_hierarchical_map_backend(
    y: list[float],
    league_idx: list[int],
    mu_global: float = 1500.0,
    sigma_obs: float = 50.0,
    sigma_player: float = 200.0,
    sigma_league: float = 100.0,
) -> list[float]:
    if np is None or not y:
        return y

    y_arr = np.asarray(y, dtype=float)
    idx_arr = np.asarray(league_idx, dtype=int)
    n = len(y_arr)
    leagues = np.unique(idx_arr)
    g_count = len(leagues)

    league_map = {old: new for new, old in enumerate(leagues)}
    mapped = np.array([league_map[v] for v in idx_arr], dtype=int)
    n_g = np.bincount(mapped, minlength=g_count)

    p_obs = 1.0 / (sigma_obs ** 2)
    p_player = 1.0 / (sigma_player ** 2)
    p_league = 1.0 / (sigma_league ** 2)

    size = n + g_count
    A = np.zeros((size, size), dtype=float)
    b = np.zeros(size, dtype=float)

    for i in range(n):
        g = mapped[i]
        A[i, i] = p_obs + p_player
        A[i, n + g] = -p_player
        b[i] = p_obs * y_arr[i]

    for g in range(g_count):
        rows = np.where(mapped == g)[0]
        for i in rows:
            A[n + g, i] = -p_player
        A[n + g, n + g] = n_g[g] * p_player + p_league
        b[n + g] = p_league * mu_global

    try:
        sol = np.linalg.solve(A, b)
    except Exception:
        sol = np.linalg.pinv(A) @ b

    theta_map = sol[:n]
    return [float(v) for v in theta_map]


def _recompute_global_rating_hierarchical(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT user_id, league_id, rating, attendance FROM league_player_stats WHERE attendance > 0"
    ).fetchall()
    if not rows:
        return 0

    y: list[float] = []
    leagues: list[int] = []
    user_ids: list[int] = []
    weights: list[int] = []
    for r in rows:
        y.append(float(r["rating"] or DEFAULT_GLOBAL_RATING))
        leagues.append(int(r["league_id"]))
        user_ids.append(int(r["user_id"]))
        weights.append(max(1, int(r["attendance"] or 0)))

    theta = _fit_hierarchical_map_backend(
        y,
        leagues,
        mu_global=DEFAULT_GLOBAL_RATING,
        sigma_obs=60.0,
        sigma_player=180.0,
        sigma_league=120.0,
    )

    agg_sum: dict[int, float] = {}
    agg_w: dict[int, int] = {}
    for i, uid in enumerate(user_ids):
        w = weights[i]
        agg_sum[uid] = agg_sum.get(uid, 0.0) + theta[i] * w
        agg_w[uid] = agg_w.get(uid, 0) + w

    now_iso = utc_now_iso()
    count = 0
    for uid, total in agg_sum.items():
        w = agg_w[uid]
        if w <= 0:
            continue
        gmmr = round(total / w, 2)
        conn.execute(
            "UPDATE users SET global_rating = ?, updated_at = ? WHERE id = ?",
            (gmmr, now_iso, uid),
        )
        count += 1
    return count


def _maybe_run_hierarchical_gmmr_recompute(conn: sqlite3.Connection, force: bool = False) -> int:
    interval_minutes = 30
    meta_key = "last_hierarchical_gmmr_recompute_at"
    if not force:
        last_row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (meta_key,)).fetchone()
        if last_row is not None:
            try:
                last_dt = datetime.fromisoformat(str(last_row["value"]))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if utc_now() - last_dt < timedelta(minutes=interval_minutes):
                    return 0
            except Exception:
                pass

    updated = _recompute_global_rating_hierarchical(conn)
    conn.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (meta_key, utc_now_iso()),
    )
    return updated


def _parse_optional_utc_iso(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}. Expected ISO datetime",
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _validate_season_window(start_at_iso: str | None, end_at_iso: str | None) -> None:
    if start_at_iso is None or end_at_iso is None:
        return
    start_dt = datetime.fromisoformat(start_at_iso)
    end_dt = datetime.fromisoformat(end_at_iso)
    if end_dt <= start_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Season end_at must be after start_at",
        )


def _season_is_active_at(start_at_raw: str | None, end_at_raw: str | None, at_dt: datetime) -> bool:
    start_dt = datetime.fromisoformat(str(start_at_raw)) if start_at_raw else None
    end_dt = datetime.fromisoformat(str(end_at_raw)) if end_at_raw else None
    if start_dt is not None and at_dt < start_dt:
        return False
    if end_dt is not None and at_dt >= end_dt:
        return False
    return True


def _windows_overlap(
    start_a_raw: str | None,
    end_a_raw: str | None,
    start_b_raw: str | None,
    end_b_raw: str | None,
) -> bool:
    start_a = datetime.fromisoformat(str(start_a_raw)) if start_a_raw else datetime.min.replace(tzinfo=timezone.utc)
    end_a = datetime.fromisoformat(str(end_a_raw)) if end_a_raw else datetime.max.replace(tzinfo=timezone.utc)
    start_b = datetime.fromisoformat(str(start_b_raw)) if start_b_raw else datetime.min.replace(tzinfo=timezone.utc)
    end_b = datetime.fromisoformat(str(end_b_raw)) if end_b_raw else datetime.max.replace(tzinfo=timezone.utc)
    return start_a < end_b and start_b < end_a


def _assert_season_window_available(
    conn: sqlite3.Connection,
    league_id: int,
    start_at_iso: str | None,
    end_at_iso: str | None,
) -> None:
    rows = conn.execute(
        "SELECT id, name, start_at, end_at FROM league_seasons WHERE league_id = ?",
        (league_id,),
    ).fetchall()
    for row in rows:
        if _windows_overlap(start_at_iso, end_at_iso, row["start_at"], row["end_at"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Season window overlaps with '{row['name']}'",
            )


def _sync_league_season_activation(conn: sqlite3.Connection, league_id: int) -> int | None:
    rows = conn.execute(
        "SELECT id, start_at, end_at FROM league_seasons WHERE league_id = ? ORDER BY COALESCE(start_at, created_at), id",
        (league_id,),
    ).fetchall()
    now_dt = utc_now()
    eligible = [r for r in rows if _season_is_active_at(r["start_at"], r["end_at"], now_dt)]
    active_id = int(eligible[-1]["id"]) if eligible else None

    conn.execute("UPDATE league_seasons SET is_active = 0 WHERE league_id = ?", (league_id,))
    if active_id is not None:
        conn.execute("UPDATE league_seasons SET is_active = 1 WHERE id = ?", (active_id,))
    return active_id


def _ensure_active_season(conn: sqlite3.Connection, league_id: int) -> int:
    active_id = _sync_league_season_activation(conn, league_id)
    if active_id is not None:
        return active_id

    now_iso = utc_now_iso()
    cursor = conn.execute(
        "INSERT INTO league_seasons (league_id, name, is_active, start_at, end_at, created_at) VALUES (?, ?, 1, ?, NULL, ?)",
        (league_id, "Season 1", now_iso, now_iso),
    )
    season_id = cursor.lastrowid
    if season_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create active season")
    return int(season_id)


def _match_active_elapsed_seconds(conn: sqlite3.Connection, match_id: int, started_at_iso: str) -> int:
    started_at = datetime.fromisoformat(str(started_at_iso))
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    absolute_elapsed = int((utc_now() - started_at).total_seconds())
    absolute_elapsed = max(0, absolute_elapsed)

    markers = conn.execute(
        "SELECT event_type, event_seconds FROM match_events WHERE match_id = ? AND undone = 0 AND event_type IN ('pause','resume') ORDER BY event_seconds, created_at",
        (match_id,),
    ).fetchall()

    paused_total = 0
    paused_from: int | None = None
    for marker in markers:
        ev_type = str(marker["event_type"])
        ev_sec = int(marker["event_seconds"])
        if ev_type == "pause":
            paused_from = ev_sec
        elif ev_type == "resume" and paused_from is not None:
            paused_total += max(0, ev_sec - paused_from)
            paused_from = None

    if paused_from is not None:
        paused_total += max(0, absolute_elapsed - paused_from)

    return max(0, absolute_elapsed - paused_total)


def _recompute_global_rating(conn: sqlite3.Connection, user_id: int) -> None:
    """Recompute global_rating as attendance-weighted average with Bayesian shrinkage to prior."""
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
    prior_weight = 10.0
    weighted = ((weighted * total_att) + (DEFAULT_GLOBAL_RATING * prior_weight)) / (total_att + prior_weight)
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
    season_id = _ensure_active_season(conn, league_id)
    cfg = _load_league_rating_config(conn, league_id)

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
    expected_a = _expected_win_probability(avg_a, avg_b)
    expected_b = 1.0 - expected_a
    a_won = score_a > score_b
    b_won = score_b > score_a
    drew = score_a == score_b

    # Build score progression to detect comebacks (winner was trailing during match).
    scoring_events = conn.execute(
        """
        SELECT team, event_seconds, created_at, id
        FROM match_events
        WHERE match_id = ? AND undone = 0 AND event_type IN ('goal', 'own_goal') AND team IN ('a', 'b')
        ORDER BY event_seconds ASC, created_at ASC, id ASC
        """,
        (match_id,),
    ).fetchall()
    run_a = 0
    run_b = 0
    max_deficit_a = 0
    max_deficit_b = 0
    max_deficit_time_a = 0
    max_deficit_time_b = 0
    for ev in scoring_events:
        team_now = str(ev["team"])
        ev_sec = int(ev["event_seconds"] or 0)
        if team_now == "a":
            run_a += 1
        elif team_now == "b":
            run_b += 1
        lead = run_a - run_b
        if lead < 0:
            deficit = -lead
            if deficit > max_deficit_a:
                max_deficit_a = deficit
                max_deficit_time_a = ev_sec
        elif lead > 0:
            deficit = lead
            if deficit > max_deficit_b:
                max_deficit_b = deficit
                max_deficit_time_b = ev_sec

    max_event_seconds = max((int(ev["event_seconds"] or 0) for ev in scoring_events), default=1)

    def avg_form(ids: list[int]) -> float:
        if not ids:
            return 0.5
        rows = conn.execute(
            f"SELECT attendance, wins FROM users WHERE id IN ({','.join('?' * len(ids))})",
            ids,
        ).fetchall()
        values: list[float] = []
        for r in rows:
            att = int(r["attendance"] or 0)
            if att <= 0:
                continue
            values.append(float(r["wins"] or 0) / att)
        if not values:
            return 0.5
        return max(0.0, min(1.0, sum(values) / len(values)))

    form_a = avg_form(team_a_ids)
    form_b = avg_form(team_b_ids)

    events = conn.execute(
        "SELECT event_type, user_id, team FROM match_events WHERE match_id = ? AND undone = 0",
        (match_id,),
    ).fetchall()

    goals_by_player: dict[int, int] = {}
    own_goals_by_player: dict[int, int] = {}
    assists_by_player: dict[int, int] = {}
    for ev in events:
        uid = ev["user_id"]
        if uid is None:
            continue
        uid = int(uid)
        if ev["event_type"] == "goal":
            goals_by_player[uid] = goals_by_player.get(uid, 0) + 1
        elif ev["event_type"] == "own_goal":
            own_goals_by_player[uid] = own_goals_by_player.get(uid, 0) + 1
        elif ev["event_type"] == "assist":
            assists_by_player[uid] = assists_by_player.get(uid, 0) + 1

    all_participants = [(uid, "a") for uid in team_a_ids] + [(uid, "b") for uid in team_b_ids]

    for uid, team in all_participants:
        opp_avg = avg_b if team == "a" else avg_a
        won = (team == "a" and a_won) or (team == "b" and b_won)

        existing = conn.execute(
            "SELECT id, rating, attendance, wins, goals, assists, is_temporary_lmmr, temporary_lmmr_match_limit FROM league_player_stats WHERE league_id = ? AND user_id = ?",
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
            prev_attendance = int(existing["attendance"] or 0)
            temp_limit = int(existing["temporary_lmmr_match_limit"] or TEMP_LMMR_MATCH_LIMIT)
            temp_active = bool(int(existing["is_temporary_lmmr"] or 0)) and prev_attendance < temp_limit
            new_rating = old_rating if temp_active else _elo_update(old_rating, opp_avg, won, drew)
            should_disable_temp = bool(int(existing["is_temporary_lmmr"] or 0)) and (prev_attendance + 1) >= temp_limit
            conn.execute(
                """
                UPDATE league_player_stats
                SET attendance = attendance + 1,
                    wins = wins + ?,
                    goals = goals + ?,
                    assists = assists + ?,
                    rating = ?,
                    is_temporary_lmmr = CASE WHEN ? THEN 0 ELSE is_temporary_lmmr END
                WHERE id = ?
                """,
                (1 if won else 0, goals_by_player.get(uid, 0), assists_by_player.get(uid, 0), new_rating, 1 if should_disable_temp else 0, int(existing["id"])),
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

        # Seasonal SR points and seasonal-only counters
        season_row = conn.execute(
            "SELECT id, attendance, wins, goals, assists, own_goals, points FROM league_season_player_stats WHERE season_id = ? AND user_id = ?",
            (season_id, uid),
        ).fetchone()
        base_result_points = float(cfg["sr_win_points"]) if won else (float(cfg["sr_draw_points"]) if drew else float(cfg["sr_loss_points"]))
        win_base = abs(float(cfg["sr_win_points"]))
        loss_base = abs(float(cfg["sr_loss_points"]))
        draw_cap_basis = max(win_base, loss_base)
        expected = expected_a if team == "a" else expected_b
        team_form = form_a if team == "a" else form_b
        opp_form = form_b if team == "a" else form_a
        form_component = max(-1.0, min(1.0, (opp_form - team_form) / 0.35))
        goal_diff = abs(score_a - score_b)
        close_game_component = max(-1.0, min(1.0, (2.0 - float(goal_diff)) / 2.0))
        team_deficit = max_deficit_a if team == "a" else max_deficit_b
        team_deficit_time = max_deficit_time_a if team == "a" else max_deficit_time_b
        comeback_depth = min(1.0, float(team_deficit) / 3.0)
        comeback_late_factor = 0.5 + 0.5 * min(1.0, float(team_deficit_time) / max(1.0, float(max_event_seconds)))
        comeback_component = max(0.0, min(1.0, comeback_depth * comeback_late_factor))

        # Cap dynamic weighting to ±25%.
        adjustment_cap = 0.25

        if drew:
            difficulty_component = (0.5 - expected) * 2.0
            combined_component = max(
                -1.0,
                min(1.0, difficulty_component + 0.45 * comeback_component + 0.30 * form_component),
            )
            draw_adjustment = draw_cap_basis * adjustment_cap * combined_component
            won_bonus = float(cfg["sr_draw_points"]) + draw_adjustment
        elif base_result_points == 0.0:
            won_bonus = 0.0
        elif won:
            # Underdog wins, bigger/later comebacks, and stronger-opponent form increase reward.
            difficulty_component = (0.5 - expected) * 2.0
            combined_component = max(
                -1.0,
                min(1.0, difficulty_component + 0.45 * comeback_component + 0.25 * close_game_component + 0.30 * form_component),
            )
            base_magnitude = abs(base_result_points)
            adjusted_magnitude = base_magnitude * (1.0 + adjustment_cap * combined_component)
            won_bonus = adjusted_magnitude
        else:
            # Expected losses are softened; upset losses are penalized more.
            difficulty_component = (expected - 0.5) * 2.0
            combined_component = max(
                -1.0,
                min(1.0, difficulty_component + 0.25 * close_game_component + 0.30 * form_component),
            )
            base_magnitude = abs(base_result_points)
            adjusted_magnitude = base_magnitude * (1.0 + adjustment_cap * combined_component)
            won_bonus = -adjusted_magnitude

        delta_points = (
            goals_by_player.get(uid, 0) * float(cfg["sr_goal_points"])
            + assists_by_player.get(uid, 0) * float(cfg["sr_assist_points"])
            + own_goals_by_player.get(uid, 0) * float(cfg["sr_own_goal_points"])
            + won_bonus
        )
        if season_row is None:
            start_points = float(cfg["sr_start_points"])
            conn.execute(
                """
                INSERT INTO league_season_player_stats (season_id, user_id, attendance, wins, goals, assists, own_goals, points)
                VALUES (?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    season_id,
                    uid,
                    1 if won else 0,
                    goals_by_player.get(uid, 0),
                    assists_by_player.get(uid, 0),
                    own_goals_by_player.get(uid, 0),
                    round(start_points + delta_points, 2),
                ),
            )
        else:
            conn.execute(
                """
                UPDATE league_season_player_stats
                SET attendance = attendance + 1,
                    wins = wins + ?,
                    goals = goals + ?,
                    assists = assists + ?,
                    own_goals = own_goals + ?,
                    points = points + ?
                WHERE id = ?
                """,
                (
                    1 if won else 0,
                    goals_by_player.get(uid, 0),
                    assists_by_player.get(uid, 0),
                    own_goals_by_player.get(uid, 0),
                    round(delta_points, 2),
                    int(season_row["id"]),
                ),
            )


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
        team_a_name=str(row["team_a_name"] or "Team A"),
        team_b_name=str(row["team_b_name"] or "Team B"),
        teams_confirmed=bool(int(row["teams_confirmed"] or 0)),
        score_a=int(row["score_a"]),
        score_b=int(row["score_b"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        created_by_username=str(row["created_by_username"]),
        created_at=str(row["created_at"]),
        preview_token=str(row["preview_token"] or ""),
        visibility=str(row["visibility"] if row["visibility"] else "public"),
        cards_enabled=bool(int(row["cards_enabled"]) if row["cards_enabled"] is not None else 1),
        offsides_enabled=bool(int(row["offsides_enabled"]) if row["offsides_enabled"] is not None else 0),
        corners_enabled=bool(int(row["corners_enabled"]) if row["corners_enabled"] is not None else 0),
        fouls_enabled=bool(int(row["fouls_enabled"]) if row["fouls_enabled"] is not None else 0),
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


def _auto_sync_registration_state(conn: sqlite3.Connection, match_id: int) -> None:
    """Auto-transition registration state (open by configured time, close 15 min before kickoff)."""
    match = conn.execute(
        "SELECT status, registration_opens_at, scheduled_at FROM matches WHERE id = ?",
        (match_id,),
    ).fetchone()
    if match is None:
        return

    status_now = str(match["status"])
    reg_opens = match["registration_opens_at"]
    scheduled = datetime.fromisoformat(str(match["scheduled_at"]))
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    now = utc_now()
    close_at = scheduled - timedelta(minutes=15)

    if status_now == "upcoming" and reg_opens is not None:
        reg_dt = datetime.fromisoformat(str(reg_opens))
        if reg_dt.tzinfo is None:
            reg_dt = reg_dt.replace(tzinfo=timezone.utc)
        if now >= reg_dt:
            conn.execute(
                "UPDATE matches SET status = 'registration_open', updated_at = ? WHERE id = ?",
                (utc_now_iso(), match_id),
            )
            match_row = conn.execute("SELECT league_id, title FROM matches WHERE id = ?", (match_id,)).fetchone()
            if match_row is not None:
                _notify_league_members(
                    conn,
                    int(match_row["league_id"]),
                    "registration_open",
                    f"Registration open: {match_row['title']}",
                    f"Registration is now open for '{match_row['title']}'.",
                    {"match_id": match_id},
                )

    current = conn.execute("SELECT status FROM matches WHERE id = ?", (match_id,)).fetchone()
    current_status = str(current["status"]) if current is not None else status_now

    # Auto-cancel stale matches that were never started within 6 hours after kickoff.
    if current_status in {"upcoming", "registration_open", "registration_closed"} and now >= (scheduled + timedelta(hours=6)):
        conn.execute(
            "UPDATE matches SET status = 'cancelled', updated_at = ? WHERE id = ?",
            (utc_now_iso(), match_id),
        )
        return

    # Close registration 15 min before kickoff
    if current_status == "registration_open" and now >= close_at:
        conn.execute(
            "UPDATE matches SET status = 'registration_closed', updated_at = ? WHERE id = ?",
            (utc_now_iso(), match_id),
        )
    # Additionally, if match is still upcoming/open at exact kickoff time, force close
    elif current_status in {"upcoming", "registration_open"} and now >= scheduled:
        conn.execute(
            "UPDATE matches SET status = 'registration_closed', updated_at = ? WHERE id = ?",
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
        require_league_approved(conn, league_id)
        cursor = conn.execute(
            """
            INSERT INTO matches (league_id, title, location, scheduled_at, registration_opens_at,
                                 max_participants, notes, status, team_a, team_b, score_a, score_b,
                                 team_a_name, team_b_name, teams_confirmed,
                                 visibility, cards_enabled, offsides_enabled, corners_enabled, fouls_enabled,
                                 created_by, created_at, updated_at, preview_token)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'upcoming', '[]', '[]', 0, 0, 'Team A', 'Team B', 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                league_id,
                payload.title.strip(),
                payload.location.strip() if payload.location else None,
                payload.scheduled_at.strip(),
                payload.registration_opens_at.strip() if payload.registration_opens_at else None,
                payload.max_participants,
                payload.notes.strip() if payload.notes else None,
                payload.visibility,
                int(payload.cards_enabled),
                int(payload.offsides_enabled),
                int(payload.corners_enabled),
                int(payload.fouls_enabled),
                user_id,
                created_at,
                created_at,
                secrets.token_urlsafe(16),
            ),
        )
        match_id = cursor.lastrowid
        if match_id is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create match")
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
        if not _can_view_league_stats(conn, league_id, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="League stats are private")
        is_member = _has_league_membership(conn, league_id, user_id)
        rows = _fetch_league_matches(conn, league_id)
        result = []
        for row in rows:
            _auto_sync_registration_state(conn, int(row["id"]))
            _advance_waitlist(conn, int(row["id"]))
            my_status = _match_registration_status(conn, int(row["id"]), user_id) if is_member else None
            refreshed = _fetch_match_row(conn, int(row["id"]))
            if refreshed:
                result.append(_serialize_match(refreshed, my_status))
        conn.commit()
    return result


@app.get("/leagues/{league_id}/match-history")
def list_league_match_history(league_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> list[dict]:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        if not _can_view_league_stats(conn, league_id, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="League stats are private")
        rows = _fetch_league_matches(conn, league_id)
        out: list[dict] = []
        for row in rows:
            _auto_sync_registration_state(conn, int(row["id"]))
            refreshed = _fetch_match_row(conn, int(row["id"]))
            if refreshed is None:
                continue
            status_now = str(refreshed["status"])
            if status_now not in {"completed", "finished", "cancelled"}:
                continue
            out.append({
                "match": _serialize_match(refreshed),
                "league_name": conn.execute("SELECT name FROM leagues WHERE id = ?", (league_id,)).fetchone()["name"],
            })
        conn.commit()
    out.sort(key=lambda x: str(x["match"].scheduled_at), reverse=True)
    return out


@app.get("/matches/history/me")
def list_my_match_history(current_user: sqlite3.Row = Depends(resolve_current_user)) -> list[dict]:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.id
            FROM matches m
            JOIN league_memberships lm ON lm.league_id = m.league_id AND lm.user_id = ?
            WHERE m.status IN ('completed', 'finished', 'cancelled')
            ORDER BY m.scheduled_at DESC
            """,
            (user_id,),
        ).fetchall()
        out: list[dict] = []
        for row in rows:
            match_row = _fetch_match_row(conn, int(row["id"]))
            if match_row is None:
                continue
            out.append(
                {
                    "match": _serialize_match(match_row),
                    "league_name": conn.execute("SELECT name FROM leagues WHERE id = ?", (int(match_row["league_id"]),)).fetchone()["name"],
                }
            )
    return out


@app.get("/matches/{match_id}", response_model=MatchDetailOut)
def get_match_detail(match_id: int, credentials: HTTPAuthorizationCredentials | sqlite3.Row | None = Depends(bearer_scheme)) -> MatchDetailOut:
    # Resolve optional user - allow unauthenticated for public matches
    user_id: int | None = None
    if isinstance(credentials, sqlite3.Row):
        user_id = int(credentials["id"])
    elif credentials is not None and credentials.scheme.lower() == "bearer":
        try:
            payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            subject = str(payload.get("sub", ""))
            if subject.startswith("user:"):
                user_id = int(subject.split(":", 1)[1])
        except (JWTError, ValueError):
            pass

    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        visibility = str(row["visibility"] if row["visibility"] else "public")
        league_id = int(row["league_id"])
        is_member = user_id is not None and conn.execute(
            "SELECT 1 FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone() is not None
        _auto_sync_registration_state(conn, match_id)
        _advance_waitlist(conn, match_id)
        conn.commit()
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        my_status = _match_registration_status(conn, match_id, user_id) if user_id is not None else None

        reg_rows = conn.execute(
            """
            SELECT mr.user_id, u.username, u.display_name, mr.status, mr.registered_at, mr.position,
                 COALESCE(mr.rating_snapshot_lmmr, lps.rating, ?) AS seasonal_rating,
                 COALESCE(mr.rating_snapshot_gmmr, u.global_rating, ?) AS global_rating
            FROM match_registrations AS mr
            JOIN users AS u ON u.id = mr.user_id
            LEFT JOIN league_player_stats AS lps ON lps.league_id = ? AND lps.user_id = mr.user_id
            WHERE mr.match_id = ? AND mr.status IN ('registered','waitlisted','offered')
            ORDER BY CASE mr.status WHEN 'registered' THEN 0 ELSE 1 END, mr.position
            """,
            (DEFAULT_GLOBAL_RATING, DEFAULT_GLOBAL_RATING, int(row["league_id"]), match_id),
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
            seasonal_rating=float(r["seasonal_rating"]),
            global_rating=float(r["global_rating"]),
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
        _auto_sync_registration_state(conn, match_id)
        _advance_waitlist(conn, match_id)
        conn.commit()
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

        reg_rows = conn.execute(
            """
            SELECT mr.user_id, u.username, u.display_name, mr.status, mr.registered_at, mr.position,
                 COALESCE(mr.rating_snapshot_lmmr, lps.rating, ?) AS seasonal_rating,
                 COALESCE(mr.rating_snapshot_gmmr, u.global_rating, ?) AS global_rating
            FROM match_registrations AS mr
            JOIN users AS u ON u.id = mr.user_id
            LEFT JOIN league_player_stats AS lps ON lps.league_id = ? AND lps.user_id = mr.user_id
            WHERE mr.match_id = ? AND mr.status IN ('registered','waitlisted','offered')
            ORDER BY CASE mr.status WHEN 'registered' THEN 0 ELSE 1 END, mr.position
            """,
            (DEFAULT_GLOBAL_RATING, DEFAULT_GLOBAL_RATING, int(row["league_id"]), match_id),
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
            seasonal_rating=float(r["seasonal_rating"]),
            global_rating=float(r["global_rating"]),
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
        if str(row["status"]) not in {"upcoming", "registration_closed"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match is not in upcoming state")
        conn.execute(
            "UPDATE matches SET status = 'registration_open', updated_at = ? WHERE id = ?",
            (utc_now_iso(), match_id),
        )
        _notify_league_members(
            conn,
            int(row["league_id"]),
            "registration_open",
            f"Registration open: {row['title']}",
            f"Registration is now open for '{row['title']}'.",
            {"match_id": match_id},
            exclude_user_id=user_id,
        )
        conn.commit()
    return MessageOut(detail="Registration opened.")


@app.post("/matches/{match_id}/close-registration", response_model=MessageOut)
def close_match_registration(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        _auto_sync_registration_state(conn, match_id)
        row = _fetch_match_row(conn, match_id)
        if row is None or str(row["status"]) != "registration_open":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registration is not open")
        conn.execute(
            "UPDATE matches SET status = 'registration_closed', updated_at = ? WHERE id = ?",
            (utc_now_iso(), match_id),
        )
        conn.commit()
    return MessageOut(detail="Registration closed.")


@app.post("/matches/{match_id}/register", response_model=MessageOut)
def register_for_match(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_membership(conn, int(row["league_id"]), user_id)
        # Check active penalty
        penalty = conn.execute(
            "SELECT penalty_until FROM league_penalties WHERE league_id = ? AND user_id = ?",
            (int(row["league_id"]), user_id),
        ).fetchone()
        if penalty is not None:
            until_dt = datetime.fromisoformat(str(penalty["penalty_until"]))
            if until_dt.tzinfo is None:
                until_dt = until_dt.replace(tzinfo=timezone.utc)
            if utc_now() < until_dt:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You are under penalty until {str(penalty['penalty_until'])}.",
                )
        _auto_sync_registration_state(conn, match_id)
        row = _fetch_match_row(conn, match_id)
        if row is None or str(row["status"]) not in {"registration_open"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registration is not open")

        scheduled = datetime.fromisoformat(str(row["scheduled_at"]))
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        if utc_now() >= scheduled - timedelta(minutes=15):
            conn.execute(
                "UPDATE matches SET status = 'registration_closed', updated_at = ? WHERE id = ?",
                (utc_now_iso(), match_id),
            )
            conn.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registration closes 15 minutes before kickoff")

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
            _notify_player_fans(
                conn,
                player_user_id=user_id,
                league_id=int(row["league_id"]),
                notif_type="fan_player_registered",
                title="Followed player registered",
                message=f"{str(current_user['display_name'] or current_user['username'])} registered for '{row['title']}'.",
                data={"match_id": match_id, "league_id": int(row["league_id"]), "player_user_id": user_id},
                exclude_user_ids={user_id},
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

        _auto_sync_registration_state(conn, match_id)
        row = _fetch_match_row(conn, match_id)
        if row is None or str(row["status"]) != "registration_open":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registration is not open")

        # Enforce 1-hour cutoff
        scheduled = datetime.fromisoformat(str(row["scheduled_at"]))
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)
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
        _auto_sync_registration_state(conn, match_id)
        row = _fetch_match_row(conn, match_id)
        if row is None or str(row["status"]) != "registration_closed":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Teams can only be generated after registrations are closed")
        if bool(int(row["teams_confirmed"] or 0)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Teams are locked after confirmation")

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
            "UPDATE matches SET team_a = ?, team_b = ?, teams_confirmed = 0, updated_at = ? WHERE id = ?",
            (json.dumps(team_a), json.dumps(team_b), utc_now_iso(), match_id),
        )
        conn.commit()

    return get_match_detail(match_id, current_user)


@app.patch("/matches/{match_id}/teams", response_model=MatchDetailOut)
def update_match_teams(match_id: int, payload: MatchTeamsDraftPayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchDetailOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        if str(row["status"]) != "registration_closed":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Teams can only be edited while registration is closed")
        if bool(int(row["teams_confirmed"] or 0)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Teams are locked after confirmation")

        a_ids = [int(x) for x in payload.team_a]
        b_ids = [int(x) for x in payload.team_b]
        if set(a_ids).intersection(set(b_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A player cannot be in both teams")

        valid_users = conn.execute(
            "SELECT user_id FROM match_registrations WHERE match_id = ? AND status = 'registered'",
            (match_id,),
        ).fetchall()
        valid_set = {int(r["user_id"]) for r in valid_users}
        if set(a_ids).union(set(b_ids)) != valid_set:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All registered players must be assigned to exactly one team")

        team_a_name = (payload.team_a_name or str(row["team_a_name"] or "Team A")).strip() or "Team A"
        team_b_name = (payload.team_b_name or str(row["team_b_name"] or "Team B")).strip() or "Team B"

        conn.execute(
            "UPDATE matches SET team_a = ?, team_b = ?, team_a_name = ?, team_b_name = ?, teams_confirmed = 0, updated_at = ? WHERE id = ?",
            (json.dumps(a_ids), json.dumps(b_ids), team_a_name, team_b_name, utc_now_iso(), match_id),
        )
        conn.commit()
    return get_match_detail(match_id, current_user)


@app.post("/matches/{match_id}/confirm-teams", response_model=MatchDetailOut)
def confirm_match_teams(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchDetailOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        if str(row["status"]) != "registration_closed":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Teams can only be confirmed after registration closes")
        team_a = json.loads(str(row["team_a"] or "[]"))
        team_b = json.loads(str(row["team_b"] or "[]"))
        if not team_a and not team_b:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Generate or set teams before confirming")
        conn.execute(
            "UPDATE matches SET teams_confirmed = 1, updated_at = ? WHERE id = ?",
            (utc_now_iso(), match_id),
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
        _auto_sync_registration_state(conn, match_id)
        row = _fetch_match_row(conn, match_id)
        if row is None or str(row["status"]) != "registration_closed":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match can only start after registrations are closed")
        if not bool(int(row["teams_confirmed"] or 0)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Confirm teams before starting the match")

        team_a = json.loads(str(row["team_a"] or "[]"))
        team_b = json.loads(str(row["team_b"] or "[]"))
        if not team_a and not team_b:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Teams are missing")

        conn.execute(
            "UPDATE matches SET status = 'live', team_a = ?, team_b = ?, started_at = ?, updated_at = ? WHERE id = ?",
            (json.dumps(team_a), json.dumps(team_b), utc_now_iso(), utc_now_iso(), match_id),
        )
        conn.execute(
            """
            UPDATE match_registrations
            SET rating_snapshot_lmmr = (
                    SELECT COALESCE(lps.rating, ?)
                    FROM league_player_stats AS lps
                    WHERE lps.league_id = ? AND lps.user_id = match_registrations.user_id
                ),
                rating_snapshot_gmmr = (
                    SELECT COALESCE(u.global_rating, ?)
                    FROM users AS u
                    WHERE u.id = match_registrations.user_id
                )
            WHERE match_id = ? AND status IN ('registered','waitlisted','offered')
            """,
            (DEFAULT_GLOBAL_RATING, int(row["league_id"]), DEFAULT_GLOBAL_RATING, match_id),
        )

        participant_ids = {int(uid) for uid in team_a + team_b}
        for pid in participant_ids:
            player_row = conn.execute("SELECT username, display_name FROM users WHERE id = ?", (pid,)).fetchone()
            player_name = str(player_row["display_name"] or player_row["username"]) if player_row is not None else f"Player {pid}"
            _notify_player_fans(
                conn,
                player_user_id=pid,
                league_id=int(row["league_id"]),
                notif_type="fan_player_started_match",
                title="Followed player started a match",
                message=f"{player_name} is now live in '{row['title']}'.",
                data={"match_id": match_id, "league_id": int(row["league_id"]), "player_user_id": pid},
                exclude_user_ids=participant_ids,
            )
        conn.commit()

    return get_match_detail(match_id, current_user)


@app.post("/matches/{match_id}/events", response_model=MatchEventOut, status_code=status.HTTP_201_CREATED)
def add_match_goal(match_id: int, payload: MatchLiveEventPayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchEventOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        if str(row["status"]) not in {"live", "finished"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Events can only be edited while match is live or finished")
        if str(row["status"]) == "live":
            last_marker = conn.execute(
                "SELECT event_type FROM match_events WHERE match_id = ? AND event_type IN ('pause','resume') AND undone = 0 ORDER BY event_seconds DESC, created_at DESC LIMIT 1",
                (match_id,),
            ).fetchone()
            if last_marker is not None and str(last_marker["event_type"]) == "pause":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot log events while match is paused")

        started_at = row["started_at"]
        if payload.event_seconds is not None:
            elapsed_seconds = int(payload.event_seconds)
        else:
            if started_at is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match has no start time")
            elapsed_seconds = _match_active_elapsed_seconds(conn, match_id, str(started_at))
        now_iso = utc_now_iso()

        team_a = {int(uid) for uid in json.loads(str(row["team_a"] or "[]"))}
        team_b = {int(uid) for uid in json.loads(str(row["team_b"] or "[]"))}
        scoring_team_players = team_a if payload.team == "a" else team_b
        opposite_team_players = team_b if payload.team == "a" else team_a

        event_type = str(payload.event_type)
        actor_user_id: int | None = None
        score_team: str | None = None

        if event_type in {"goal", "own_goal", "injury", "yellow_card", "red_card", "offside", "corner", "foul"} and payload.team not in {"a", "b"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team must be 'a' or 'b' for this event")

        if event_type == "goal":
            if payload.scorer_user_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scorer_user_id is required for goal")
            if int(payload.scorer_user_id) not in scoring_team_players:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Goal scorer must belong to scoring team")
            actor_user_id = int(payload.scorer_user_id)
            score_team = payload.team

        elif event_type == "own_goal":
            own_goal_user_id = payload.own_goal_user_id or payload.player_user_id
            if own_goal_user_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="own_goal_user_id is required for own_goal")
            if int(own_goal_user_id) not in opposite_team_players:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Own-goal scorer must belong to opposite team")
            actor_user_id = int(own_goal_user_id)
            score_team = payload.team

        elif event_type in {"injury", "yellow_card", "red_card", "foul"}:
            card_user_id = payload.player_user_id or payload.scorer_user_id
            if card_user_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="player_user_id is required for this event")
            if int(card_user_id) not in scoring_team_players:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected player must belong to the selected team")
            actor_user_id = int(card_user_id)
            score_team = payload.team

        elif event_type == "corner":
            actor_user_id = None
            score_team = payload.team

        elif event_type in {"pause", "resume"}:
            actor_user_id = None
            score_team = None

        elif event_type == "offside":
            offside_user_id = payload.player_user_id or payload.scorer_user_id
            if offside_user_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="player_user_id is required for offside")
            actor_user_id = int(offside_user_id)
            score_team = payload.team

        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported event type")

        # Add goal/own-goal event
        cursor = conn.execute(
            "INSERT INTO match_events (match_id, event_type, user_id, team, event_seconds, created_at, undone) VALUES (?, ?, ?, ?, ?, ?, 0)",
            (match_id, event_type, actor_user_id, score_team, elapsed_seconds, now_iso),
        )
        goal_event_id = cursor.lastrowid
        if goal_event_id is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create event")

        # Update score
        if event_type in {"goal", "own_goal"} and score_team is not None:
            if score_team == "a":
                conn.execute("UPDATE matches SET score_a = score_a + 1, updated_at = ? WHERE id = ?", (now_iso, match_id))
            else:
                conn.execute("UPDATE matches SET score_b = score_b + 1, updated_at = ? WHERE id = ?", (now_iso, match_id))

        # Add assist if provided
        if event_type == "goal" and payload.assist_user_id is not None:
            if int(payload.assist_user_id) not in scoring_team_players:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assist player must belong to scoring team")
            conn.execute(
                "INSERT INTO match_events (match_id, event_type, user_id, team, event_seconds, created_at, undone) VALUES (?, 'assist', ?, ?, ?, ?, 0)",
                (match_id, payload.assist_user_id, payload.team, elapsed_seconds, now_iso),
            )

        if event_type == "yellow_card" and actor_user_id is not None:
            yellow_count_row = conn.execute(
                "SELECT COUNT(*) AS c FROM match_events WHERE match_id = ? AND user_id = ? AND event_type = 'yellow_card' AND undone = 0",
                (match_id, actor_user_id),
            ).fetchone()
            yellow_count = int(yellow_count_row["c"] or 0) if yellow_count_row is not None else 0
            if yellow_count >= 2:
                conn.execute(
                    "INSERT INTO match_events (match_id, event_type, user_id, team, event_seconds, created_at, undone) VALUES (?, 'red_card', ?, ?, ?, ?, 0)",
                    (match_id, actor_user_id, score_team, elapsed_seconds, now_iso),
                )

        if actor_user_id is not None and event_type not in {"pause", "resume"}:
            actor_row = conn.execute("SELECT username, display_name FROM users WHERE id = ?", (actor_user_id,)).fetchone()
            actor_name = str(actor_row["display_name"] or actor_row["username"]) if actor_row is not None else f"Player {actor_user_id}"
            _notify_player_fans(
                conn,
                player_user_id=actor_user_id,
                league_id=int(row["league_id"]),
                notif_type="fan_player_match_event",
                title="Followed player had a match event",
                message=f"{actor_name}: {event_type.replace('_', ' ')} in '{row['title']}'.",
                data={"match_id": match_id, "league_id": int(row["league_id"]), "player_user_id": actor_user_id, "event_type": event_type},
                exclude_user_ids={actor_user_id},
            )

        conn.commit()

        scorer_username = conn.execute("SELECT username FROM users WHERE id = ?", (actor_user_id,)).fetchone() if actor_user_id is not None else None
        return MatchEventOut(
            id=int(goal_event_id),
            event_type=event_type,
            user_id=actor_user_id,
            username=scorer_username["username"] if scorer_username else None,
            team=score_team,
            event_seconds=elapsed_seconds,
            created_at=now_iso,
            undone=False,
        )


@app.post("/matches/{match_id}/pause", response_model=MatchEventOut, status_code=status.HTTP_201_CREATED)
def pause_match(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchEventOut:
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

        last_marker = conn.execute(
            "SELECT event_type FROM match_events WHERE match_id = ? AND event_type IN ('pause','resume') AND undone = 0 ORDER BY event_seconds DESC, created_at DESC LIMIT 1",
            (match_id,),
        ).fetchone()
        if last_marker is not None and str(last_marker["event_type"]) == "pause":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match is already paused")

        elapsed_seconds = _match_active_elapsed_seconds(conn, match_id, str(started_at))
        now_iso = utc_now_iso()
        cursor = conn.execute(
            "INSERT INTO match_events (match_id, event_type, user_id, team, event_seconds, created_at, undone) VALUES (?, 'pause', NULL, NULL, ?, ?, 0)",
            (match_id, elapsed_seconds, now_iso),
        )
        event_id = cursor.lastrowid
        if event_id is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create pause event")
        conn.commit()

    return MatchEventOut(
        id=int(event_id),
        event_type="pause",
        user_id=None,
        username=None,
        team=None,
        event_seconds=elapsed_seconds,
        created_at=now_iso,
        undone=False,
    )


@app.patch("/matches/{match_id}/visibility", response_model=MatchDetailOut)
def update_match_visibility(
    match_id: int,
    payload: MatchVisibilityPayload,
    current_user: sqlite3.Row = Depends(resolve_current_user),
) -> MatchDetailOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = _fetch_match_row(conn, match_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        require_league_manager(conn, int(row["league_id"]), user_id)
        conn.execute(
            "UPDATE matches SET visibility = ?, updated_at = ? WHERE id = ?",
            (payload.visibility, utc_now_iso(), match_id),
        )
        conn.commit()
    return get_match_detail(match_id, current_user)


@app.post("/matches/{match_id}/resume", response_model=MatchEventOut, status_code=status.HTTP_201_CREATED)
def resume_match(match_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MatchEventOut:
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

        last_marker = conn.execute(
            "SELECT event_type FROM match_events WHERE match_id = ? AND event_type IN ('pause','resume') AND undone = 0 ORDER BY event_seconds DESC, created_at DESC LIMIT 1",
            (match_id,),
        ).fetchone()
        if last_marker is None or str(last_marker["event_type"]) != "pause":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match is not paused")

        elapsed_seconds = _match_active_elapsed_seconds(conn, match_id, str(started_at))
        now_iso = utc_now_iso()
        cursor = conn.execute(
            "INSERT INTO match_events (match_id, event_type, user_id, team, event_seconds, created_at, undone) VALUES (?, 'resume', NULL, NULL, ?, ?, 0)",
            (match_id, elapsed_seconds, now_iso),
        )
        event_id = cursor.lastrowid
        if event_id is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create resume event")
        conn.commit()

    return MatchEventOut(
        id=int(event_id),
        event_type="resume",
        user_id=None,
        username=None,
        team=None,
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

        match_status = str(row["status"])
        if match_status == "live":
            created_dt = datetime.fromisoformat(str(event["created_at"]))
            if (utc_now() - created_dt).total_seconds() > UNDO_WINDOW_SECONDS:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Undo window has passed (30 seconds)")
        elif match_status != "finished":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Events can only be removed while match is live or finished")

        conn.execute("UPDATE match_events SET undone = 1 WHERE id = ?", (event_id,))
        if str(event["event_type"]) in {"goal", "own_goal"}:
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
        _maybe_run_hierarchical_gmmr_recompute(conn, force=True)
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


@app.patch("/notifications/{notification_id}/read", response_model=MessageOut)
def mark_notification_read(notification_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    user_id = int(current_user["id"])
    with get_conn() as conn:
        row = conn.execute("SELECT id, user_id FROM notifications WHERE id = ?", (notification_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        if int(row["user_id"]) != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your notification")
        conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notification_id,))
        conn.commit()
    return MessageOut(detail="Notification marked as read.")


class LeaderboardPlayerOut(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    global_rating: float
    rank: int


@app.get("/players/leaderboard", response_model=list[LeaderboardPlayerOut])
def get_players_leaderboard(
    q: str = "",
    page: int = 1,
    limit: int = 50,
) -> list[LeaderboardPlayerOut]:
    page = max(1, page)
    limit = min(100, max(1, limit))
    offset = (page - 1) * limit
    with get_conn() as conn:
        if q.strip():
            rows = conn.execute(
                """SELECT id, username, display_name, COALESCE(global_rating, 1000.0) AS global_rating,
                   ROW_NUMBER() OVER (ORDER BY COALESCE(global_rating,1000.0) DESC) AS rank
                   FROM users WHERE is_active = 1 AND role != 'admin'
                   AND (LOWER(username) LIKE ? OR LOWER(COALESCE(display_name,'')) LIKE ?)
                   ORDER BY global_rating DESC LIMIT ? OFFSET ?""",
                (f"%{q.lower()}%", f"%{q.lower()}%", limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, username, display_name, COALESCE(global_rating, 1000.0) AS global_rating,
                   ROW_NUMBER() OVER (ORDER BY COALESCE(global_rating,1000.0) DESC) AS rank
                   FROM users WHERE is_active = 1 AND role != 'admin'
                   ORDER BY global_rating DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
    return [
        LeaderboardPlayerOut(
            id=int(r["id"]),
            username=str(r["username"]),
            display_name=r["display_name"],
            global_rating=float(r["global_rating"]),
            rank=int(r["rank"]),
        )
        for r in rows
    ]


@app.post("/leagues/{league_id}/seasons/{season_id}/close", response_model=MessageOut)
def close_league_season(league_id: int, season_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    with get_conn() as conn:
        require_league_manager(conn, league_id, int(current_user["id"]))
        row = conn.execute(
            "SELECT id, is_active FROM league_seasons WHERE id = ? AND league_id = ?",
            (season_id, league_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
        conn.execute(
            "UPDATE league_seasons SET is_active = 0, end_at = COALESCE(end_at, ?) WHERE id = ?",
            (utc_now_iso(), season_id),
        )
        conn.commit()
    return MessageOut(detail="Season closed.")

