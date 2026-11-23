export function AccountAvatar({ username }: { username: string }) {
  const initial = Array.from(username.trim())[0]?.toUpperCase() || '·';
  return <span className="account-avatar" aria-hidden="true">{initial}</span>;
}
