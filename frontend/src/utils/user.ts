/**
 * Persisted user identity for the authenticated session.
 *
 * The backend namespaces uploads + trained-model artifacts by ``user_id``
 * (read from the ``X-User-Id`` header on every request) so that user A
 * never sees user B's data. The ``user_id`` is minted ONCE at
 * registration time by ``agent_app/auth/user_store.py`` as
 * ``user_<32-hex>`` and never changes for a given account, so a user's
 * accumulated assets stay reachable from any browser they log in from.
 *
 * This module is the single source of truth for the {user_id, username}
 * pair in the browser. AuthContext drives the lifecycle (set on login /
 * register, cleared on logout); :func:`getUserId` is kept as a thin
 * accessor for the ``X-User-Id`` header that ``services/api.ts`` injects
 * on every request.
 *
 * NOTE: This is real authentication (server-validated username+password),
 * NOT the previous anonymous-id scheme. Clearing browser storage (or
 * logging out via the UI) returns the user to the login page.
 */

export interface StoredUser {
  user_id: string;
  username: string;
}

const STORAGE_KEY = 'industrial_ts_user';

/**
 * Read the persisted user, or ``null`` when no session is stored
 * (first visit, after logout, or in private-browsing modes where
 * localStorage is thrown away on tab close).
 */
export function getStoredUser(): StoredUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredUser> | null;
    if (
      parsed &&
      typeof parsed.user_id === 'string' && parsed.user_id.trim() &&
      typeof parsed.username === 'string' && parsed.username.trim()
    ) {
      return { user_id: parsed.user_id, username: parsed.username };
    }
  } catch {
    // Corrupt JSON, disabled storage, quota errors — treat as logged-out.
  }
  return null;
}

/** Persist the authenticated identity. Called by AuthContext after a
 *  successful login / register / `GET /api/auth/me` round-trip. */
export function setStoredUser(user: StoredUser): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  } catch {
    /* swallow — in-memory copy in AuthContext still works for this tab */
  }
}

/** Clear the persisted identity. Called on logout and when `getMe`
 *  rejects the stored id (e.g. the account was deleted server-side). */
export function clearStoredUser(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* swallow */
  }
}

/**
 * Return the current user_id for the ``X-User-Id`` header.
 *
 * Returns an empty string when no session is stored. The app gates all
 * authenticated UI behind :class:`AuthProvider`, so this is only called
 * after a session exists; the empty-string fallback is purely defensive
 * (e.g. a stray API call during logout racing with state teardown).
 */
export function getUserId(): string {
  return getStoredUser()?.user_id ?? '';
}
