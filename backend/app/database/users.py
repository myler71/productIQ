"""User storage + session signing for ProductIQ.
SQLite via raw sqlite3 (no ORM). Passwords hashed with bcrypt.
Session identity carried in a signed httponly cookie (itsdangerous).
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import bcrypt
from itsdangerous import URLSafeSerializer

from app.core.config import ADMIN_PASSWORD, ADMIN_USERNAME, COOKIE_SECRET, SQLITE_DIR

signer = URLSafeSerializer(COOKIE_SECRET, salt="productiq-auth")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False

DB_PATH = SQLITE_DIR / "productiq.db"
AUTH_COOKIE = "productiq_user"


def _connect() -> sqlite3.Connection:
    SQLITE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def create_user(username: str, password: str) -> bool:
    """Create a user. Returns False if username exists."""
    init_db()
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, _hash_password(password), datetime.utcnow().isoformat()),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username: str, password: str) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return False
    return _verify_password(password, row["password_hash"])


def seed_admin() -> None:
    """Seed the admin user from env on first boot. Loud warning on defaults."""
    init_db()
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if count == 0:
        create_user(ADMIN_USERNAME, ADMIN_PASSWORD)
        print(f"[ProductIQ] Seeded admin user '{ADMIN_USERNAME}'.")
        if ADMIN_USERNAME == "admin" and ADMIN_PASSWORD == "admin123":
            print("⚠️  [ProductIQ] WARNING: default admin credentials in use — "
                  "change ADMIN_USERNAME / ADMIN_PASSWORD in .env immediately!")


def sign_username(username: str) -> str:
    return signer.dumps({"u": username})


def unsign_cookie(value: str) -> str | None:
    try:
        data = signer.loads(value)
        return data.get("u")
    except Exception:
        return None
