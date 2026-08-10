"""Lightweight user authentication for the Industrial Time Series Agent.

Exports a small surface from :mod:`auth.user_store`:

- :func:`register` — create a new (username, password) → user_id mapping.
- :func:`authenticate` — validate credentials and return the user_id.
- :func:`get_by_user_id` — look up a user by their stable user_id.

The user_id is the identity that namespaces uploads + model artifacts,
so it must be **stable for the same account** and **unguessable** by
others. We generate it once at registration time as
``user_<random_hex>`` and never change it.
"""

from .user_store import authenticate, get_by_user_id, register

__all__ = ["register", "authenticate", "get_by_user_id"]
