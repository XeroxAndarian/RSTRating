import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
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

bearer_scheme = HTTPBearer(auto_error=False)
PBKDF2_ITERATIONS = 210000
LEAGUE_INVITE_EXPIRY_DAYS = 7


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
    created_at: str
    updated_at: str


class BackupLeagueData(BaseModel):
    id: int
    name: str
    sport: str
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


class BackupExportData(BaseModel):
    update: str
    users: dict[str, BackupUserData]
    leagues: dict[str, BackupLeagueData]
    memberships: dict[str, BackupMembershipData]
    invites: dict[str, BackupInviteData]


class BackupImportData(BaseModel):
    users: dict[str, BackupUserData]
    leagues: dict[str, BackupLeagueData] = Field(default_factory=dict)
    memberships: dict[str, BackupMembershipData] = Field(default_factory=dict)
    invites: dict[str, BackupInviteData] = Field(default_factory=dict)


class PasswordResetRequestPayload(BaseModel):
    email: str = Field(max_length=255)


class PasswordResetPayload(BaseModel):
    email: str = Field(max_length=255)
    token: str = Field(min_length=32, max_length=128)
    new_password: str = Field(min_length=6, max_length=200)


class LeagueCreatePayload(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    sport: str = Field(default="football", min_length=3, max_length=40)
    description: str | None = Field(default=None, max_length=300)


class InviteAcceptPayload(BaseModel):
    token: str = Field(min_length=8, max_length=128)


class LeagueMemberRolePayload(BaseModel):
    role: str = Field(pattern=r"^(member|admin)$")


class LeagueOut(BaseModel):
    id: int
    name: str
    sport: str
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


class LeagueDetailOut(BaseModel):
    league: LeagueOut
    members: list[LeagueMemberOut]
    invites: list[LeagueInviteOut]


class LobbyOut(BaseModel):
    user: UserOut
    leagues: list[LeagueOut]
    invites: list[LeagueInviteOut]


class InvitePreviewOut(BaseModel):
    league_id: int
    league_name: str
    sport: str
    description: str | None
    owner_username: str
    expires_at: str | None
    remaining_uses: int
    requires_login: bool = True


class MessageOut(BaseModel):
    detail: str


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
                sport TEXT NOT NULL DEFAULT 'football',
                description TEXT,
                owner_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
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
            "SELECT id, username, password_hash, email, name, surname, nicknames, display_name, role, created_at, updated_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()


def find_user_by_id(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, username, password_hash, email, name, surname, nicknames, display_name, role, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def find_user_by_email(email: str) -> sqlite3.Row | None:
    normalized_email = normalize_email(email)
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, username, password_hash, email, name, surname, nicknames, display_name, role, created_at, updated_at FROM users WHERE lower(email) = ?",
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


def serialize_league(row: sqlite3.Row) -> LeagueOut:
    return LeagueOut(
        id=int(row["id"]),
        name=str(row["name"]),
        sport=str(row["sport"]),
        description=row["description"],
        owner_id=int(row["owner_id"]),
        owner_username=str(row["owner_username"]),
        member_role=str(row["member_role"]),
        member_count=int(row["member_count"]),
        created_at=str(row["created_at"]),
    )


def serialize_invite(row: sqlite3.Row) -> LeagueInviteOut:
    return LeagueInviteOut(
        id=int(row["id"]),
        league_id=int(row["league_id"]),
        league_name=str(row["league_name"]),
        token=str(row["token"]),
        created_at=str(row["created_at"]),
        expires_at=row["expires_at"],
        max_uses=int(row["max_uses"]),
        use_count=int(row["use_count"]),
        revoked=int(row["revoked"]),
        invite_url=build_invite_url(str(row["token"])),
    )


def serialize_member(row: sqlite3.Row) -> LeagueMemberOut:
    return LeagueMemberOut(
        user_id=int(row["user_id"]),
        username=str(row["username"]),
        display_name=row["display_name"],
        role=str(row["role"]),
        joined_at=str(row["joined_at"]),
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


def fetch_league_for_user(conn: sqlite3.Connection, league_id: int, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            l.id,
            l.name,
            l.sport,
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
            l.sport,
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
            lm.joined_at
        FROM league_memberships AS lm
        JOIN users AS u ON u.id = lm.user_id
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
            l.sport,
            l.description,
            owner.username AS owner_username
        FROM league_invites AS li
        JOIN leagues AS l ON l.id = li.league_id
        JOIN users AS owner ON owner.id = l.owner_id
        WHERE li.token = ?
        """,
        (token,),
    ).fetchone()


app = FastAPI(title="RSTRating Accounts API", version="0.3.0")

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
            INSERT INTO users (username, password_hash, email, name, surname, nicknames, display_name, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'player', ?, ?)
            """,
            (
                payload.username.strip(),
                hash_password(payload.password),
                normalized_email,
                payload.name.strip(),
                payload.surname.strip(),
                nicknames_to_db(payload.nicknames),
                payload.display_name.strip() if payload.display_name else None,
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
def export_backup(current_user: sqlite3.Row = Depends(resolve_current_user)) -> BackupExportData:
    with get_conn() as conn:
        user_rows = conn.execute(
            "SELECT id, username, password_hash, email, name, surname, nicknames, display_name, role, created_at, updated_at FROM users ORDER BY created_at"
        ).fetchall()
        league_rows = conn.execute(
            "SELECT l.id, l.name, l.sport, l.description, l.owner_id AS owner_user_id, u.username AS owner_username, l.created_at, l.updated_at FROM leagues AS l JOIN users AS u ON u.id = l.owner_id ORDER BY l.created_at"
        ).fetchall()
        membership_rows = conn.execute(
            "SELECT lm.id, lm.league_id, lm.user_id, l.name AS league_name, u.username, lm.role, lm.joined_at FROM league_memberships AS lm JOIN leagues AS l ON l.id = lm.league_id JOIN users AS u ON u.id = lm.user_id ORDER BY lm.id"
        ).fetchall()
        invite_rows = conn.execute(
            "SELECT li.id, li.league_id, li.created_by_user_id, l.name AS league_name, u.username AS created_by_username, li.token, li.created_at, li.expires_at, li.max_uses, li.use_count, li.revoked FROM league_invites AS li JOIN leagues AS l ON l.id = li.league_id JOIN users AS u ON u.id = li.created_by_user_id ORDER BY li.id"
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
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
        for row in user_rows
    }
    leagues = {
        str(row["id"]): BackupLeagueData(
            id=int(row["id"]),
            name=str(row["name"]),
            sport=str(row["sport"]),
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
    return BackupExportData(update=utc_now().date().isoformat(), users=users, leagues=leagues, memberships=memberships, invites=invites)


@app.post("/backup/import", response_model=MessageOut)
def import_backup(payload: BackupImportData, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
    imported_users = 0
    imported_leagues = 0
    imported_memberships = 0
    imported_invites = 0
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
                INSERT INTO users (username, password_hash, email, name, surname, nicknames, display_name, role, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                "INSERT INTO leagues (name, sport, description, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (league_data.name, league_data.sport, league_data.description, owner_id, league_data.created_at, league_data.updated_at),
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

        conn.commit()

    return MessageOut(detail=(
        f"Imported users: {imported_users}, leagues: {imported_leagues}, memberships: {imported_memberships}, "
        f"invites: {imported_invites}. Skipped: {skipped}."
    ))


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
    with get_conn() as conn:
        leagues = [serialize_league(row) for row in fetch_user_leagues(conn, int(current_user["id"]))]
        invites = [serialize_invite(row) for row in fetch_manageable_invites(conn, int(current_user["id"]))]
    return LobbyOut(user=serialize_user(current_user), leagues=leagues, invites=invites)


@app.post("/leagues", response_model=LeagueOut, status_code=status.HTTP_201_CREATED)
def create_league(payload: LeagueCreatePayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> LeagueOut:
    created_at = utc_now_iso()
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO leagues (name, sport, description, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                payload.name.strip(),
                payload.sport.strip().lower(),
                payload.description.strip() if payload.description else None,
                int(current_user["id"]),
                created_at,
                created_at,
            ),
        )
        league_id = cursor.lastrowid
        if league_id is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create league")
        conn.execute(
            "INSERT INTO league_memberships (league_id, user_id, role, joined_at) VALUES (?, ?, 'owner', ?)",
            (int(league_id), int(current_user["id"]), created_at),
        )
        conn.commit()
        league_row = fetch_league_for_user(conn, int(league_id), int(current_user["id"]))
    if league_row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load league")
    return serialize_league(league_row)


@app.get("/leagues/{league_id}", response_model=LeagueDetailOut)
def get_league_detail(league_id: int, current_user: sqlite3.Row = Depends(resolve_current_user)) -> LeagueDetailOut:
    with get_conn() as conn:
        league_row = fetch_league_for_user(conn, league_id, int(current_user["id"]))
        if league_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
        members = [serialize_member(row) for row in fetch_league_members(conn, league_id)]
        membership = require_membership(conn, league_id, int(current_user["id"]))
        invites: list[LeagueInviteOut] = []
        if membership["role"] in {"owner", "admin"}:
            invites = [serialize_invite(row) for row in fetch_league_invites(conn, league_id)]
    return LeagueDetailOut(league=serialize_league(league_row), members=members, invites=invites)


@app.patch("/leagues/{league_id}/members/{member_user_id}", response_model=MessageOut)
def update_league_member_role(league_id: int, member_user_id: int, payload: LeagueMemberRolePayload, current_user: sqlite3.Row = Depends(resolve_current_user)) -> MessageOut:
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
            "INSERT INTO league_invites (league_id, token, created_by_user_id, created_at, expires_at, max_uses, use_count, revoked) VALUES (?, ?, ?, ?, ?, 1, 0, 0)",
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
        sport=str(invite["sport"]),
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
        existing_membership = conn.execute(
            "SELECT role FROM league_memberships WHERE league_id = ? AND user_id = ?",
            (int(invite["league_id"]), int(current_user["id"])),
        ).fetchone()
        if existing_membership is None:
            conn.execute(
                "INSERT INTO league_memberships (league_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
                (int(invite["league_id"]), int(current_user["id"]), utc_now_iso()),
            )
            conn.execute(
                "UPDATE league_invites SET use_count = use_count + 1 WHERE id = ?",
                (int(invite["id"]),),
            )
            conn.commit()
        league_row = fetch_league_for_user(conn, int(invite["league_id"]), int(current_user["id"]))
    if league_row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not join league")
    return serialize_league(league_row)
