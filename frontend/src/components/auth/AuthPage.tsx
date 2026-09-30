import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Eye, EyeOff, KeyRound, User, AudioLines, ShieldCheck, X, MoveUpRight } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/Button';
import './AuthPage.css';
import { SignalCore } from './SignalCore';
import './AuthExperience.css';

type Mode = 'login' | 'register';

const USERNAME_RE = /^[A-Za-z0-9_\u4e00-\u9fa5.\-]{2,32}$/;

/** Mirror of the backend credential rules so we can give instant
 *  feedback. Returns ``null`` when valid. */
function validateUsername(username: string): string | null {
  const trimmed = username.trim();
  if (!trimmed) return '请输入用户名';
  if (new TextEncoder().encode(trimmed).length > 32) {
    return '用户名不能超过 32 字节';
  }
  if (!USERNAME_RE.test(trimmed)) {
    return '用户名需为 2-32 个字符（字母、数字、下划线、中文、点、短横线）';
  }
  return null;
}

function validatePassword(password: string): string | null {
  if (!password) return '请输入密码';
  if (password.length < 4) return '密码至少 4 个字符';
  if (password.length > 128) return '密码不能超过 128 个字符';
  return null;
}

export function AuthPage() {
  const { login, register, error, submitting, clearError } = useAuth();
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
  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

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

  function openAuth() {
    setMode('login');
    setLocalError(null);
    clearError();
    setAuthOpen(true);
  }

  function closeAuth() {
    if (submitting) return;
    setAuthOpen(false);
    setPassword('');
    setShowPassword(false);
    setLocalError(null);
    clearError();
  }

  // Clear form errors when the user edits anything or switches modes.
  useEffect(() => {
    setLocalError(null);
    clearError();
  }, [mode, clearError]);
  useEffect(() => {
    setLocalError(null);
    clearError();
  }, [username, password, clearError]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    const uErr = validateUsername(username);
    if (uErr) {
      setLocalError(uErr);
      return;
    }
    const pErr = validatePassword(password);
    if (pErr) {
      setLocalError(pErr);
      return;
    }
    if (mode === 'login') {
      await login(username.trim(), password);
    } else {
      await register(username.trim(), password);
    }
  };

  const shownError = localError ?? error;

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
        <button type="button" className="auth-dialog-close" onClick={closeAuth} disabled={submitting} aria-label="关闭登录窗口"><X size={19} /></button>
        <div className="auth-form-wrap">
          <div className="auth-form-symbol"><AudioLines size={28} strokeWidth={1.5} /></div>
          <h2 id="auth-dialog-title">{mode === 'login' ? '欢迎回来' : '开启智能分析之旅'}</h2>
          <p className="auth-form-intro">{mode === 'login' ? '登录工作台，继续探索数据的下一种可能。' : '创建账户，让每一份工业数据释放价值。'}</p>
          <div className="auth-mode-switch" role="group" aria-label="账户操作">
            {(['login', 'register'] as const).map(m => (
              <button key={m} type="button" disabled={submitting} aria-pressed={mode === m} onClick={() => setMode(m)} className={mode === m ? 'is-active' : ''}>{m === 'login' ? '账户登录' : '注册账户'}</button>
            ))}
          </div>
          <form onSubmit={onSubmit} noValidate aria-busy={submitting}>
            <Field id="auth-username" label="用户名" icon={<User size={17} />}>
              <input id="auth-username" autoFocus type="text" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} placeholder="请输入用户名" maxLength={64} disabled={submitting} aria-describedby={shownError ? 'auth-error' : undefined} />
            </Field>
            <Field id="auth-password" label="密码" icon={<KeyRound size={17} />}>
              <input id="auth-password" type={showPassword ? 'text' : 'password'} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={e => setPassword(e.target.value)} placeholder={mode === 'login' ? '请输入密码' : '设置密码，至少 4 个字符'} disabled={submitting} aria-describedby={shownError ? 'auth-error' : undefined} />
              <button type="button" className="auth-password-toggle" onClick={() => setShowPassword(s => !s)} aria-label={showPassword ? '隐藏密码' : '显示密码'} aria-pressed={showPassword}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button>
            </Field>
            {mode === 'register' && <p className="auth-register-hint">用户名支持中文、字母、数字、下划线、点和短横线，长度为 2–32 个字符，且不超过 32 字节。</p>}
            {shownError && <div id="auth-error" role="alert" className="auth-error">{shownError}</div>}
            <Button type="submit" variant="primary" size="lg" loading={submitting} className="auth-submit">{mode === 'login' ? '登录工作台' : '创建账户并登录'}</Button>
          </form>
          <p className="auth-switch-copy">{mode === 'login' ? '还没有账户？' : '已有账户？'}<button type="button" disabled={submitting} onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? '立即注册' : '返回登录'}</button></p>
          <div className="auth-workspace-note"><ShieldCheck size={16} /><span>在专属工作空间中管理数据、模型与智能体</span></div>
        </div>
      </dialog>
    </main>
  );
}

function Field({ id, label, icon, children }: { id: string; label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <div className="auth-field"><label htmlFor={id}>{label}</label><div className="auth-input-wrap"><span className="auth-input-icon">{icon}</span>{children}</div></div>;
}

