import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { AuthForm } from './AuthForm';
import './AuthPage.css';

/** Old accounts can add recovery email without changing their identity/assets. */
export function AccountSecurityNotice({ onBindEmail }: { onBindEmail: () => void }) {
  const { user } = useAuth();
  if (!user || user.email) return null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-brand-200 bg-brand-50 px-4 py-2 text-xs text-brand-800">
      <span>您的账户尚未绑定邮箱，绑定后可通过邮箱验证码找回密码。</span>
      <button type="button" aria-haspopup="dialog" className="font-semibold underline underline-offset-4" onClick={onBindEmail}>
        绑定安全邮箱
      </button>
    </div>
  );
}

export function BindEmailDialog({ onClose }: { onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);

  function close() {
    dialog.current?.close();
    onClose();
  }

  return createPortal(
    <dialog ref={dialog} className="auth-dialog" aria-labelledby="auth-dialog-title" onCancel={event => { event.preventDefault(); if (!busy) close(); }}>
      <button type="button" className="auth-dialog-close" disabled={busy} aria-label="关闭绑定邮箱窗口" onClick={close}><X size={19} aria-hidden="true" /></button>
      <AuthForm initialMode="bind" onBusyChange={setBusy} onBound={close} />
    </dialog>,
    document.body,
  );
}
