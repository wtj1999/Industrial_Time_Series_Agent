import { useEffect, useRef, useState } from 'react';
import { AudioLines, X, MoveUpRight } from 'lucide-react';
import { AuthForm } from './AuthForm';
import './AuthPage.css';
import { SignalCore } from './SignalCore';
import './AuthExperience.css';

export function AuthPage() {
  const [busy, setBusy] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setReducedMotion(preference.matches);
    sync();
    preference.addEventListener('change', sync);
    return () => preference.removeEventListener('change', sync);
  }, []);
  useEffect(() => {
    if (!authOpen) return;
    const dialog = dialogRef.current;
    const previousOverflow = document.body.style.overflow;
    dialog?.showModal();
    dialog?.querySelector<HTMLInputElement>('#auth-username')?.focus();
    document.body.style.overflow = 'hidden';
    return () => {
      dialog?.close();
      document.body.style.overflow = previousOverflow;
    };
  }, [authOpen]);

  function openAuth() { setAuthOpen(true); }
  function closeAuth() { if (!busy) setAuthOpen(false); }

  return (
    <main className="industrial-auth signal-experience" id="auth-top">
      <header className="auth-header">
        <a className="auth-brand" href="#auth-top" aria-label="工业时序智能体首页">
          <span className="auth-brand-symbol"><AudioLines size={25} strokeWidth={1.5} /></span>
          <span><strong>工业时序智能体</strong><small>Industrial Time Series Agent</small></span>
        </a>
        <span className="auth-room-label">数据 · 模型 · 智能体</span>
        <button className="auth-header-login" onClick={openAuth}>登录工作台 <MoveUpRight size={14} /></button>
      </header>

      <SignalCore paused={authOpen} reducedMotion={reducedMotion} onLogin={openAuth} />

      <dialog ref={dialogRef} className="auth-dialog" aria-labelledby="auth-dialog-title" onCancel={event => { event.preventDefault(); closeAuth(); }} onClick={event => { if (event.target === event.currentTarget) { const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeAuth(); } }}>
        <button type="button" className="auth-dialog-close" onClick={closeAuth} disabled={busy} aria-label="关闭登录窗口"><X size={19} /></button>
        {authOpen && <AuthForm onBusyChange={setBusy} />}
      </dialog>
    </main>
  );
}
