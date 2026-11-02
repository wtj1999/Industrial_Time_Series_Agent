/** Identity is for display; only the server-issued token authenticates requests. */
export interface StoredUser {
  user_id: string;
  username: string;
  email?: string | null;
  access_token: string;
  expires_at?: number;
}
const STORAGE_KEY = 'industrial_ts_user';
let memoryUser: StoredUser | null = null;

export function getStoredUser(): StoredUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return memoryUser;
    const parsed = JSON.parse(raw) as Partial<StoredUser> | null;
    if (parsed && typeof parsed.user_id === 'string' && typeof parsed.username === 'string' &&
      typeof parsed.access_token === 'string' && parsed.access_token &&
      (!parsed.expires_at || parsed.expires_at > Date.now() / 1000)) return parsed as StoredUser;
  } catch { return memoryUser; }
  return null;
}
export function setStoredUser(user: StoredUser): void {
  memoryUser = user;
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(user)); } catch { /* Memory works when storage is disabled. */ }
}
export function clearStoredUser(): void {
  memoryUser = null;
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* Storage may be disabled. */ }
}
export function getUserId(): string { return getStoredUser()?.user_id ?? ''; }
export function getAuthHeaders(): Record<string, string> {
  const user = getStoredUser();
  return user ? { Authorization: `Bearer ${user.access_token}` } : {};
}
export function handleUnauthorized(response: Response): void {
  if (response.status === 401) {
    clearStoredUser();
    window.dispatchEvent(new Event('auth:expired'));
  }
}
