"""Compatibility entry points backed by the transactional account database.

The legacy users.json is imported once by service.py and is never written.
Registration requires a verified email; a user_id alone is not a session.
"""
from . import service


def register(username: str, password: str, email: str, code: str):
    return service.register(username, password, email, code, 'internal')


def authenticate(username: str, password: str):
    return service.login(username, password, 'internal')


def get_by_user_id(user_id: str):
    """Account lookup only; use session_user to authenticate a request."""
    with service.transaction() as db:
        user = db.execute('SELECT * FROM users WHERE user_id=?', (user_id,)).fetchone()
        return service.public_user(user) if user else None
