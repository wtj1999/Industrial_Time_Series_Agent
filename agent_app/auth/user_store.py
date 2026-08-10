"""File-based user store for lightweight authentication.

Users are stored in a JSON file (``agent_app/auth/users.json``) keyed by
lowercased username. Passwords are hashed with PBKDF2-SHA256 + per-user
random salt — we deliberately avoid adding a bcrypt/passlib dependency
since :mod:`hashlib` ships with the standard library and is strong
enough for an internal/lab deployment.

The ``user_id`` is generated ONCE at registration time as
``user_<32-char-hex>`` and is the stable identity that namespaces
uploads + model artifacts. Logging in from any browser with the same
account always returns the same user_id, so a user's accumulated data
and trained models are always reachable.

Concurrency
-----------
All read/write paths are guarded by a process-wide :class:`threading.Lock`
and writes are atomic (temp-file + ``os.replace``), so concurrent
registrations inside a single uvicorn worker are safe. Cross-worker
races are extremely unlikely for an internal tool; if that ever matters,
swap the JSON file for SQLite without touching the public surface.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Storage paths + concurrency
# ----------------------------------------------------------------------

_STORE_PATH: Path = Path(__file__).resolve().parent / "users.json"
_LOCK = threading.Lock()

# ----------------------------------------------------------------------
# Validation constants
# ----------------------------------------------------------------------

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fa5.\-]{2,32}$")
_USERNAME_BYTES_MAX = 32
_PASSWORD_MIN = 4
_PASSWORD_MAX = 128
_PBKDF2_ITERATIONS = 120_000


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _load() -> Dict[str, Any]:
    """Load the user store from disk, returning an empty structure on
    any error (missing file, corrupt JSON, ...)."""
    if not _STORE_PATH.exists():
        return {"users": {}}
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("users"), dict):
            return {"users": {}}
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("user store load failed, starting empty: %s", exc)
        return {"users": {}}


def _save(data: Dict[str, Any]) -> None:
    """Atomically write the user store (temp-file + ``os.replace``)."""
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _STORE_PATH)


def _hash_password(password: str, salt_hex: str) -> str:
    """PBKDF2-HMAC-SHA256 hash of ``password`` using the hex-encoded salt."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        _PBKDF2_ITERATIONS,
    ).hex()


def _gen_user_id() -> str:
    """Generate a fresh ``user_<32-hex>`` id (16 bytes of entropy)."""
    return "user_" + secrets.token_hex(16)


def _public_user(user: Dict[str, Any]) -> Dict[str, str]:
    """Project a stored user record down to the public shape we return
    to the API layer (never leaks the salt/hash)."""
    return {
        "user_id": user["user_id"],
        "username": user["username"],
    }


def _validate_credentials(username: str, password: str) -> Optional[str]:
    """Return ``None`` if credentials are valid, else an error message."""
    username = (username or "").strip()
    if not username:
        return "用户名不能为空"
    if len(username.encode("utf-8")) > _USERNAME_BYTES_MAX or not _USERNAME_RE.match(username):
        return "用户名需为 2-32 个字符（字母、数字、下划线、中文、点、短横线）"
    if not password:
        return "密码不能为空"
    if len(password) < _PASSWORD_MIN:
        return "密码至少 %d 个字符" % _PASSWORD_MIN
    if len(password) > _PASSWORD_MAX:
        return "密码不能超过 %d 个字符" % _PASSWORD_MAX
    return None


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def register(username: str, password: str) -> Optional[Dict[str, str]]:
    """Create a new user.

    Returns ``{"user_id", "username"}`` on success, or ``None`` if the
    credentials are invalid or the username is already taken.
    """
    err = _validate_credentials(username, password)
    if err:
        return None
    username_norm = username.strip()
    key = username_norm.lower()

    with _LOCK:
        data = _load()
        users = data.setdefault("users", {})
        if key in users:
            return None  # already exists

        salt_hex = secrets.token_hex(16)
        user = {
            "username": username_norm,
            "password_salt": salt_hex,
            "password_hash": _hash_password(password, salt_hex),
            "user_id": _gen_user_id(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        users[key] = user
        try:
            _save(data)
        except OSError as exc:
            logger.error("user store save failed: %s", exc)
            return None
        logger.info("registered new user: %s (user_id=%s)", username_norm, user["user_id"])
        return _public_user(user)


def authenticate(username: str, password: str) -> Optional[Dict[str, str]]:
    """Validate credentials.

    Returns ``{"user_id", "username"}`` on success, or ``None`` if the
    username doesn't exist or the password is wrong.
    """
    username = (username or "").strip()
    if not username or not password:
        return None
    key = username.lower()

    with _LOCK:
        data = _load()
        user = data.get("users", {}).get(key)
        if not user:
            return None
        if _hash_password(password, user["password_salt"]) != user["password_hash"]:
            return None
        return _public_user(user)


def get_by_user_id(user_id: str) -> Optional[Dict[str, str]]:
    """Look up a user by their stable user_id.

    Used by ``GET /api/auth/me`` to validate a stored session on page
    reload. Returns ``None`` when the user_id doesn't match any account
    (e.g. stale localStorage from the old anonymous-id scheme).
    """
    if not user_id:
        return None
    with _LOCK:
        data = _load()
        for user in data.get("users", {}).values():
            if user.get("user_id") == user_id:
                return _public_user(user)
        return None
