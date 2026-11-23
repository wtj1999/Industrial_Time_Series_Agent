import { useEffect, useId, useRef, useState } from 'react';
import { ChevronRight, ChevronsUpDown, LogOut, UserRound } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { AccountAvatar } from './AccountAvatar';
import './Account.css';

export function AccountMenu({ onOpenProfile, compact = false }: {
  onOpenProfile: () => void;
  compact?: boolean;
}) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  const menuId = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    function closeFromOutside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      trigger.current?.focus();
      setOpen(false);
    }
    document.addEventListener('pointerdown', closeFromOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeFromOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open]);

  if (!user) return null;

  function closeToTrigger() {
    trigger.current?.focus();
    setOpen(false);
  }

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError('');
    try {
      await logout();
    } catch (error) {
      setLogoutError(error instanceof Error ? error.message : '退出失败，请重试');
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <div
      ref={root}
      className="account-menu"
      data-compact={compact || undefined}
      onBlur={event => {
        if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <button
        ref={trigger}
        type="button"
        className="account-menu-trigger"
        aria-label={`${user.username}的账号菜单`}
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen(!open)}
      >
        <AccountAvatar username={user.username} />
        {!compact && (
          <>
            <span className="account-identity">
              <strong>{user.username}</strong>
              <span>{user.email || '邮箱未绑定'}</span>
            </span>
            <ChevronsUpDown size={15} aria-hidden="true" className="account-menu-chevron" />
          </>
        )}
      </button>
      <div id={menuId} className="account-menu-panel" hidden={!open}>
        <div className="account-menu-header account-identity">
          <strong>{user.username}</strong>
          <span>{user.email || '邮箱未绑定'}</span>
        </div>
        <div className="account-menu-actions">
          <button type="button" aria-haspopup="dialog" onClick={() => {
            closeToTrigger();
            onOpenProfile();
          }}>
            <UserRound size={16} aria-hidden="true" />
            <span>个人资料</span>
            <ChevronRight size={14} aria-hidden="true" />
          </button>
          <button type="button" className="account-menu-logout" aria-disabled={loggingOut} onClick={() => void handleLogout()}>
            <LogOut size={16} aria-hidden="true" />
            <span>{loggingOut ? '正在退出…' : '退出登录'}</span>
          </button>
          {logoutError && <p className="account-menu-error" role="alert">{logoutError}</p>}
        </div>
      </div>
    </div>
  );
}
