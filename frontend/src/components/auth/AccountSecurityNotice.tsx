import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { AuthForm } from './AuthForm';
import './AuthPage.css';

/** Old accounts can add recovery email without changing their identity/assets. */
export function AccountSecurityNotice() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loggingOut, setLoggingOut] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!open) return;
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, [open]);
  return <>
    <div className={`${user?.email ? 'lg:hidden' : ''} flex flex-wrap items-center justify-between gap-2 border-b border-brand-200 bg-brand-50 px-4 py-2 text-xs text-brand-800`}>
      <span>{user?.email ? `当前账户：${user.username}` : '您的账户尚未绑定邮箱，绑定后可通过邮箱验证码找回密码。'}</span>
      <div className="flex items-center gap-4">
        {!user?.email && <button type="button" className="font-semibold underline underline-offset-4" onClick={() => setOpen(true)}>绑定安全邮箱</button>}
        <button type="button" className="lg:hidden" disabled={loggingOut} onClick={async () => {
          setLoggingOut(true); setError('');
          try { await logout(); } catch (err) { setError(err instanceof Error ? err.message : '退出失败，请重试'); }
          finally { setLoggingOut(false); }
        }}>{loggingOut ? '正在退出…' : '退出登录'}</button>
      </div>
      {error && <span role="alert">{error}</span>}
    </div>
    <dialog ref={dialog} className="auth-dialog" aria-labelledby="auth-dialog-title" onCancel={e => { e.preventDefault(); if (!busy) setOpen(false); }}>
      <button type="button" className="auth-dialog-close" disabled={busy} aria-label="关闭绑定邮箱窗口" onClick={() => setOpen(false)}><X size={19} /></button>
      {open && <AuthForm initialMode="bind" onBusyChange={setBusy} onBound={() => setOpen(false)} />}
    </dialog>
  </>;
}
