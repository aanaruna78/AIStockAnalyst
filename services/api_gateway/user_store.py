"""
JSON-file-backed user store.
Survives container restarts when the data directory is volume-mounted.

Usage:
    from user_store import user_store
    user_store.save(user)          # upsert by email
    user = user_store.get(email)   # returns User | None
    all_users = user_store.all()   # list[User]
    user_store.delete(email)       # remove
"""

import json
import os
import threading
import logging
from typing import Optional

from shared.models import User

logger = logging.getLogger("user_store")

DATA_DIR = os.environ.get("USER_DATA_DIR", "/app/data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")


class UserStore:
    """Thread-safe, JSON-file-backed user store."""

    def __init__(self, filepath: str = USERS_FILE):
        self._filepath = filepath
        self._lock = threading.Lock()
        self._users: dict[str, User] = {}
        self._load()

    # ── Public API ────────────────────────────────────────────────

    def get(self, email: str) -> Optional[User]:
        """Get user by email."""
        with self._lock:
            return self._users.get(email)

    def save(self, user: User) -> None:
        """Insert or update a user (keyed by email). Persists to disk."""
        with self._lock:
            self._users[user.email] = user
            self._persist()

    def delete(self, email: str) -> bool:
        """Remove user. Returns True if existed."""
        with self._lock:
            if email in self._users:
                del self._users[email]
                self._persist()
                return True
            return False

    def all(self) -> list[User]:
        """Return all users."""
        with self._lock:
            return list(self._users.values())

    def exists(self, email: str) -> bool:
        with self._lock:
            return email in self._users

    def find_by_google_id(self, google_id: str) -> Optional[User]:
        """Find a user by Google ID."""
        with self._lock:
            for u in self._users.values():
                if u.google_id == google_id:
                    return u
            return None

    def find_by_email_or_google(self, email: str, google_id: str) -> Optional[User]:
        """Find user by email OR google_id (for SSO merge)."""
        with self._lock:
            for u in self._users.values():
                if u.google_id == google_id or u.email == email:
                    return u
            return None

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._users)

    # ── Internal ──────────────────────────────────────────────────

    def _load(self) -> None:
        """Load users from JSON file on startup."""
        if not os.path.exists(self._filepath):
            logger.info(f"No existing user file at {self._filepath}, starting fresh")
            return
        try:
            with open(self._filepath, "r") as f:
                data = json.load(f)
            for email, udict in data.items():
                self._users[email] = User(**udict)
            logger.info(f"Loaded {len(self._users)} users from {self._filepath}")
        except Exception as e:
            logger.error(f"Failed to load users from {self._filepath}: {e}")

    def _persist(self) -> None:
        """Write all users to JSON file."""
        try:
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            data = {email: u.model_dump() for email, u in self._users.items()}
            # Write to temp file first, then rename (atomic on POSIX)
            tmp = self._filepath + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp, self._filepath)
        except Exception as e:
            logger.error(f"Failed to persist users to {self._filepath}: {e}")


# ── Singleton ─────────────────────────────────────────────────────
user_store = UserStore()
