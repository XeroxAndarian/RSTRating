import os
import sqlite3
import hashlib
import hmac
import secrets
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


class RegisterPayload(BaseModel):
    username: str = Field(min_length=3, max_length=24, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=6, max_length=200)
    email: str = Field(max_length=255)
    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    nicknames: str | None = Field(default=None, max_length=500)
    display_name: str | None = Field(default=None, max_length=100)


class LoginPayload(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    name: str | None
    surname: str | None
    nicknames: str | None
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
    email: str | None
    name: str | None
    surname: str | None
    nicknames: str | None
    display_name: str | None
    role: str
    created_at: str
    updated_at: str


class BackupExportData(BaseModel):
    update: str
    users: dict[str, BackupUserData]


class BackupImportData(BaseModel):
    users: dict[str, BackupUserData]


class PasswordResetRequestPayload(BaseModel):
    email: str = Field(max_length=255)


class PasswordResetPayload(BaseModel):
    email: str = Field(max_length=255)
    token: str = Field(min_length=32, max_length=64)
    new_password: str = Field(min_length=6, max_length=200)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


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
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": int(expires.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
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
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, username, password_hash, email, name, surname, nicknames, display_name, role, created_at, updated_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()


def serialize_user(row: sqlite3.Row) -> UserOut:
    return UserOut(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        name=row["name"],
        surname=row["surname"],
        nicknames=row["nicknames"],
        display_name=row["display_name"],
        role=row["role"],
        created_at=row["created_at"],
    )


def resolve_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> sqlite3.Row:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    sub = payload.get("sub", "")
    if not sub.startswith("user:"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    try:
        user_id = int(sub.split(":", 1)[1])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc

    user = find_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


app = FastAPI(title="RSTRating Accounts API", version="0.1.0")

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

    created_at = utc_now_iso()
    password_hash = hash_password(payload.password)

    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, email, name, surname, nicknames, display_name, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'player', ?, ?)
            """,
            (payload.username, password_hash, payload.email, payload.name, payload.surname, payload.nicknames, payload.display_name, created_at, created_at),
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
    params: list[str] = []

    if payload.display_name is not None:
        updates.append("display_name = ?")
        params.append(payload.display_name)

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
    """Export all user accounts as JSON backup (requires authentication)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, password_hash, email, name, surname, nicknames, display_name, role, created_at, updated_at FROM users ORDER BY created_at"
        ).fetchall()

    users_dict = {}
    for row in rows:
        user_id_str = str(row["id"])
        users_dict[user_id_str] = BackupUserData(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            email=row["email"],
            name=row["name"],
            surname=row["surname"],
            nicknames=row["nicknames"],
            display_name=row["display_name"],
            role=row["role"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    return BackupExportData(
        update=utc_now_iso().split("T")[0],
        users=users_dict,
    )


@app.post("/backup/import")
def import_backup(payload: BackupImportData, current_user: sqlite3.Row = Depends(resolve_current_user)) -> dict[str, str]:
    """Import user accounts from a JSON backup file (requires authentication). Skips existing usernames."""
    imported_count = 0
    skipped_count = 0

    with get_conn() as conn:
        for user_id_key, user_data in payload.users.items():
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (user_data.username,),
            ).fetchone()

            if existing is not None:
                skipped_count += 1
                continue

            conn.execute(
                """
                INSERT INTO users (username, password_hash, email, name, surname, nicknames, display_name, role, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_data.username,
                    user_data.password_hash,
                    user_data.email,
                    user_data.name,
                    user_data.surname,
                    user_data.nicknames,
                    user_data.display_name,
                    user_data.role,
                    user_data.created_at,
                    user_data.updated_at,
                ),
            )
            imported_count += 1

        conn.commit()

    return {
        "detail": f"Imported {imported_count} user(s), skipped {skipped_count} existing account(s)."
    }


@app.post("/auth/password-reset-request")
def request_password_reset(payload: PasswordResetRequestPayload) -> dict[str, str]:
    """Request a password reset token via email. Returns reset token (for development/email setup)."""
    user = find_user_by_email(payload.email)
    if user is None:
        # Don't reveal that email doesn't exist (security best practice)
        return {"detail": "If an account exists with this email, a reset link has been sent."}

    reset_token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user["id"], reset_token, expires_at, utc_now_iso()),
        )
        conn.commit()

    return {
        "detail": "Password reset token generated. Use this token in the reset endpoint.",
        "token": reset_token,
        "note": "In production, this token would be sent via email."
    }


@app.post("/auth/password-reset")
def reset_password(payload: PasswordResetPayload) -> dict[str, str]:
    """Reset password using email and reset token."""
    user = find_user_by_email(payload.email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    with get_conn() as conn:
        token_row = conn.execute(
            """
            SELECT id, expires_at FROM password_reset_tokens
            WHERE user_id = ? AND token = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (user["id"], payload.token),
        ).fetchone()

        if token_row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired reset token")

        expires_at = datetime.fromisoformat(token_row["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reset token has expired")

        # Update password
        new_password_hash = hash_password(payload.new_password)
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (new_password_hash, utc_now_iso(), user["id"]),
        )

        # Delete used token
        conn.execute(
            "DELETE FROM password_reset_tokens WHERE id = ?",
            (token_row["id"],),
        )

        conn.commit()

    return {"detail": "Password reset successfully. You can now log in with your new password."}
