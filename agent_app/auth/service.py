"""Transactional email verification, account migration and opaque sessions.

SQLite is shared by workers. Legacy JSON is imported once, without changing
user IDs or password hashes. Neither verification codes nor session tokens
are persisted in plaintext.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .mailer import send_code

ITERATIONS = 600_000
CODE_TTL = 600
RESEND_SECONDS = 60
SESSION_TTL = 7 * 24 * 3600
LEGACY_PATH = Path(__file__).with_name('users.json')
USERNAME_RE = re.compile(r"[A-Za-z0-9_\u4e00-\u9fa5.\-]{2,32}")
EMAIL_RE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+")


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400, retry_after: int = 0):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email) or len(email.split('@')[0]) > 64:
        raise AuthError("请输入有效的邮箱地址")
    return email


def validate_password(password: str) -> None:
    if not 8 <= len(password) <= 128 or not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        raise AuthError("密码需为 8–128 个字符，且包含字母和数字")


def validate_registration_password(password: str) -> None:
    """Apply the new policy only when creating an account."""
    if not (
        8 <= len(password) <= 128
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"[0-9]", password)
        and re.search(r"[\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]", password)
    ):
        raise AuthError("注册密码需为 8–128 个字符，且包含大写字母、小写字母、数字和特殊字符（如 !@#）")


def password_hash(password: str, salt: str, iterations: int = ITERATIONS) -> str:
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), iterations).hex()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _connect() -> sqlite3.Connection:
    path = Path(os.getenv('AUTH_DB_PATH', str(Path(__file__).with_name('auth.sqlite3'))))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY, username TEXT NOT NULL, username_key TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE, password_salt TEXT NOT NULL, password_hash TEXT NOT NULL,
            iterations INTEGER NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id), expires_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS challenges (
            email TEXT NOT NULL, purpose TEXT NOT NULL, owner TEXT NOT NULL,
            salt TEXT NOT NULL, code_hash TEXT NOT NULL, created_at REAL NOT NULL,
            expires_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(email, purpose)
        );
        CREATE TABLE IF NOT EXISTS rate_events (scope TEXT NOT NULL, created_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS rate_events_scope ON rate_events(scope, created_at);
    ''')
    try:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT 1 FROM meta WHERE key='legacy_imported'").fetchone():
            legacy = LEGACY_PATH
            if legacy.exists():
                # Fail closed on malformed legacy data; never silently lose accounts.
                users = json.loads(legacy.read_text(encoding='utf-8'))['users']
                for user in users.values():
                    db.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?,?)', (
                        user['user_id'], user['username'], user['username'].strip().lower(),
                        None, user['password_salt'], user['password_hash'], 120_000, user['created_at'],
                    ))
            db.execute("INSERT INTO meta VALUES ('legacy_imported', '1')")
        db.commit()
    except Exception:
        db.rollback()
        db.close()
        raise
    return db


@contextmanager
def transaction():
    db = _connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        now = time.time()
        db.execute('DELETE FROM sessions WHERE expires_at<=?', (now,))
        db.execute('DELETE FROM rate_events WHERE created_at<=?', (now - 3600,))
        db.execute('DELETE FROM challenges WHERE created_at<=?', (now - 3600,))
        yield db
        db.commit()
    except AuthError:
        # Failed code guesses / throttling must be durable, too.
        db.commit()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def rate_limit(db, scope: str, limit: int, window: int):
    scope = digest(scope)
    now = time.time()
    row = db.execute('SELECT COUNT(*) AS n, MIN(created_at) AS oldest FROM rate_events WHERE scope=? AND created_at>?', (scope, now - window)).fetchone()
    if row['n'] >= limit:
        wait = max(1, int(row['oldest'] + window - now) + 1)
        raise AuthError('操作过于频繁，请稍后重试', 429, wait)
    db.execute('INSERT INTO rate_events VALUES (?,?)', (scope, now))


def public_user(user) -> dict:
    return {key: user[key] for key in ('user_id', 'username', 'email')}


def _new_session(db, user) -> dict:
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + SESSION_TTL
    db.execute('INSERT INTO sessions VALUES (?,?,?)', (digest(token), user['user_id'], expires_at))
    return dict(success=True, **public_user(user), access_token=token, expires_at=expires_at)


def session_user(token: str) -> dict | None:
    if not token or len(token) > 256:
        return None
    with transaction() as db:
        user = db.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.user_id WHERE s.token_hash=? AND s.expires_at>?', (digest(token), time.time())).fetchone()
        return public_user(user) if user else None


def logout(token: str):
    with transaction() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?', (digest(token),))


def login(identifier: str, password: str, ip: str) -> dict:
    key = identifier.strip().lower()
    with transaction() as db:
        rate_limit(db, 'login-ip:' + ip, 30, 900)
        user = db.execute('SELECT * FROM users WHERE username_key=? OR email=?', (key, key)).fetchone()
        rate_limit(db, 'login-account:' + (user['user_id'] if user else key), 10, 900)
        expected = user['password_hash'] if user else '0' * 64
        actual = password_hash(password, user['password_salt'] if user else '0' * 32, user['iterations'] if user else ITERATIONS)
        if not hmac.compare_digest(actual, expected):
            raise AuthError('账户或密码错误', 401)
        if user['iterations'] < ITERATIONS:
            salt = secrets.token_hex(16)
            db.execute('UPDATE users SET password_salt=?, password_hash=?, iterations=? WHERE user_id=?', (salt, password_hash(password, salt), ITERATIONS, user['user_id']))
        return _new_session(db, user)


def request_code(email: str, purpose: str, ip: str, owner: str = '') -> dict:
    email = normalize_email(email)
    if purpose not in ('register', 'reset_password', 'bind_email'):
        raise AuthError('验证码用途不正确')
    if purpose == 'bind_email' and not owner:
        raise AuthError('请先登录', 401)
    code, salt = f'{secrets.randbelow(1_000_000):06d}', secrets.token_hex(16)
    with transaction() as db:
        rate_limit(db, 'send-ip:' + ip, 20, 3600)
        rate_limit(db, 'send-email:' + email, 5, 3600)
        previous = db.execute('SELECT created_at FROM challenges WHERE email=? AND purpose=?', (email, purpose)).fetchone()
        if previous and previous['created_at'] + RESEND_SECONDS > time.time():
            wait = int(previous['created_at'] + RESEND_SECONDS - time.time()) + 1
            raise AuthError(f'请在 {wait} 秒后重新获取验证码', 429, wait)
        existing = db.execute('SELECT user_id FROM users WHERE email=?', (email,)).fetchone()
        if purpose == 'bind_email':
            user = db.execute('SELECT email FROM users WHERE user_id=?', (owner,)).fetchone()
            if not user or user['email']:
                raise AuthError('当前账户已绑定邮箱')
        deliver = bool(existing) if purpose == 'reset_password' else not existing
        now = time.time()
        db.execute('INSERT OR REPLACE INTO challenges VALUES (?,?,?,?,?,?,?,0,0)', (email, purpose, owner, salt, password_hash(code, salt, 120_000), now, now + CODE_TTL))
    # The same response is returned for unknown reset addresses / used addresses.
    # Delivery runs as a background task so response timing does not reveal accounts.
    return {'email': email, 'purpose': purpose, 'code': code, 'salt': salt, 'deliver': deliver}


def deliver_code(challenge: dict):
    from .mailer import MailDeliveryError
    try:
        if challenge['deliver']:
            send_code(challenge['email'], challenge['code'], challenge['purpose'])
        with transaction() as db:
            db.execute('UPDATE challenges SET active=? WHERE email=? AND purpose=? AND salt=?', (int(challenge['deliver']), challenge['email'], challenge['purpose'], challenge['salt']))
        import logging
        logging.getLogger(__name__).info(
            'Verification email %s; purpose=%s',
            'accepted by SMTP' if challenge['deliver'] else 'skipped (email not eligible)',
            challenge['purpose'],
        )
    except MailDeliveryError as exc:
        import logging
        logging.getLogger(__name__).warning(
            'Verification email delivery failed: category=%s stage=%s exception_type=%s errno=%s smtp_status=%s; %s',
            exc.category, exc.stage, exc.exception_type, exc.error_number, exc.smtp_status, exc,
        )
        with transaction() as db:
            db.execute('DELETE FROM challenges WHERE email=? AND purpose=? AND salt=?', (challenge['email'], challenge['purpose'], challenge['salt']))


def _verify_code(db, email: str, purpose: str, code: str, owner: str = ''):
    row = db.execute('SELECT * FROM challenges WHERE email=? AND purpose=?', (email, purpose)).fetchone()
    if not row or not row['active'] or row['expires_at'] <= time.time() or row['attempts'] >= 5 or row['owner'] != owner:
        raise AuthError('验证码错误或已失效，请重新获取')
    db.execute('UPDATE challenges SET attempts=attempts+1 WHERE email=? AND purpose=?', (email, purpose))
    if not re.fullmatch(r'[0-9]{6}', code) or not hmac.compare_digest(password_hash(code, row['salt'], 120_000), row['code_hash']):
        raise AuthError('验证码错误或已失效，请重新获取')


def register(username: str, password: str, email: str, code: str, ip: str) -> dict:
    username = username.strip()
    if not USERNAME_RE.fullmatch(username) or len(username.encode()) > 32:
        raise AuthError('用户名需为 2–32 个字符且不超过 32 字节，支持中文、字母、数字、下划线、点和短横线')
    validate_registration_password(password)
    email = normalize_email(email)
    with transaction() as db:
        rate_limit(db, 'verify-ip:' + ip, 30, 900)
        if db.execute('SELECT 1 FROM users WHERE username_key=? OR email=?', (username.lower(), email)).fetchone():
            raise AuthError('用户名或邮箱已被使用')
        _verify_code(db, email, 'register', code)
        salt = secrets.token_hex(16)
        user_id = 'user_' + secrets.token_hex(16)
        db.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?,?)', (user_id, username, username.lower(), email, salt, password_hash(password, salt), ITERATIONS, str(time.time())))
        db.execute("DELETE FROM challenges WHERE email=? AND purpose='register'", (email,))
        return _new_session(db, db.execute('SELECT * FROM users WHERE user_id=?', (user_id,)).fetchone())


def reset_password(email: str, code: str, password: str, ip: str):
    email = normalize_email(email)
    validate_password(password)
    with transaction() as db:
        rate_limit(db, 'verify-ip:' + ip, 30, 900)
        _verify_code(db, email, 'reset_password', code)
        user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        if not user:
            raise AuthError('验证码错误或已失效，请重新获取')
        salt = secrets.token_hex(16)
        db.execute('UPDATE users SET password_salt=?, password_hash=?, iterations=? WHERE user_id=?', (salt, password_hash(password, salt), ITERATIONS, user['user_id']))
        db.execute('DELETE FROM sessions WHERE user_id=?', (user['user_id'],))
        db.execute('DELETE FROM challenges WHERE email=?', (email,))


def bind_email(user_id: str, email: str, code: str, password: str, ip: str) -> dict:
    email = normalize_email(email)
    with transaction() as db:
        rate_limit(db, 'bind:' + user_id, 10, 900)
        rate_limit(db, 'verify-ip:' + ip, 30, 900)
        user = db.execute('SELECT * FROM users WHERE user_id=?', (user_id,)).fetchone()
        if not user or not hmac.compare_digest(password_hash(password, user['password_salt'], user['iterations']), user['password_hash']):
            raise AuthError('当前密码不正确')
        if user['email'] or db.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
            raise AuthError('当前账户或邮箱已绑定')
        _verify_code(db, email, 'bind_email', code, user_id)
        db.execute('UPDATE users SET email=? WHERE user_id=?', (email, user_id))
        db.execute("DELETE FROM challenges WHERE email=? AND purpose='bind_email'", (email,))
        return dict(success=True, **public_user(db.execute('SELECT * FROM users WHERE user_id=?', (user_id,)).fetchone()))
