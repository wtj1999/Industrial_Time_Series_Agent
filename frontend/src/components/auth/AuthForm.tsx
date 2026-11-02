import { useEffect, useState, type FormEvent } from 'react';
import { AudioLines, Eye, EyeOff, KeyRound, Mail, ShieldCheck, User } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { ApiError, bindEmail, resetPassword, sendEmailCode, type CodePurpose } from '@/services/api';
import { Button } from '@/components/ui/Button';

type Mode = 'login' | 'register' | 'reset' | 'bind';
const CODE_KEY = 'industrial_ts_code_deadlines';
const emailValid = (value: string) => /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/.test(value) && value.length <= 254 && value.split('@')[0].length <= 64;
const passwordValid = (value: string) => value.length >= 8 && value.length <= 128 && /[A-Za-z]/.test(value) && /[0-9]/.test(value);

export function AuthForm({ initialMode = 'login', onBusyChange, onBound }: {
  initialMode?: Mode; onBusyChange?: (busy: boolean) => void; onBound?: () => void;
}) {
  const { login, register, error, submitting, clearError, refreshUser } = useAuth();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [working, setWorking] = useState(false);
  const [sending, setSending] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [now, setNow] = useState(Date.now());
  const [deadlines, setDeadlines] = useState<Record<string, number>>(() => {
    try {
      const parsed = JSON.parse(sessionStorage.getItem(CODE_KEY) ?? '{}');
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
      return Object.fromEntries(Object.entries(parsed).filter((entry): entry is [string, number] => typeof entry[1] === 'number' && Number.isFinite(entry[1]) && entry[1] > Date.now()));
    } catch { return {}; }
  });
  const busy = submitting || working || sending;
  const normalizedEmail = email.trim().toLowerCase();
  const purpose: CodePurpose = mode === 'register' ? 'register' : mode === 'bind' ? 'bind_email' : 'reset_password';
  const deadlineKey = `${purpose}:${normalizedEmail}`;
  const remaining = Math.max(0, Math.ceil(((deadlines[deadlineKey] ?? 0) - now) / 1000));

  useEffect(() => { onBusyChange?.(busy); }, [busy, onBusyChange]);
  useEffect(() => {
    if (!remaining) return;
    const interval = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(interval);
  }, [remaining]);
  useEffect(() => { setLocalError(null); clearError(); }, [username, email, code, password, confirm, clearError]);

  function switchMode(next: Mode) {
    setMode(next); setPassword(''); setConfirm(''); setCode(''); setShowPassword(false);
    setLocalError(null); setNotice(''); clearError();
  }
  function startCooldown(seconds: number) {
    const next = { ...deadlines, [deadlineKey]: Date.now() + seconds * 1000 };
    setNow(Date.now()); setDeadlines(next);
    try { sessionStorage.setItem(CODE_KEY, JSON.stringify(next)); } catch { /* Optional persistence. */ }
  }
  async function sendCode() {
    if (busy || remaining) return;
    if (!emailValid(normalizedEmail)) { setLocalError('请输入有效的邮箱地址'); return; }
    setSending(true); setLocalError(null); setNotice(''); setCode(''); clearError();
    try {
      const response = await sendEmailCode(normalizedEmail, purpose);
      startCooldown(response.retry_after);
      setNotice(`${response.message} 验证码 10 分钟内有效。`);
    } catch (err) {
      if (err instanceof ApiError && err.retryAfter) startCooldown(err.retryAfter);
      setLocalError(err instanceof Error ? err.message : '验证码发送失败，请重试');
    } finally { setSending(false); }
  }
  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setLocalError(null); setNotice(''); clearError();
    if (mode === 'login') {
      if (!username.trim() || !password) { setLocalError('请输入用户名或邮箱及密码'); return; }
      await login(username.trim(), password);
      return;
    }
    if (mode === 'register' && (!/^[A-Za-z0-9_\u4e00-\u9fa5.\-]{2,32}$/.test(username.trim()) || new TextEncoder().encode(username.trim()).length > 32)) {
      setLocalError('用户名需为 2–32 个字符且不超过 32 字节，支持中文、字母、数字、下划线、点和短横线'); return;
    }
    if (!emailValid(normalizedEmail)) { setLocalError('请输入有效的邮箱地址'); return; }
    if (!/^[0-9]{6}$/.test(code)) { setLocalError('请输入邮件中的 6 位验证码'); return; }
    if (mode === 'bind' ? !password : !passwordValid(password)) {
      setLocalError(mode === 'bind' ? '请输入当前密码' : '密码需为 8–128 个字符，且包含字母和数字'); return;
    }
    if (mode !== 'bind' && password !== confirm) { setLocalError('两次输入的密码不一致'); return; }
    if (mode === 'register') { await register(username.trim(), password, normalizedEmail, code); return; }
    setWorking(true);
    try {
      if (mode === 'bind') {
        await bindEmail(normalizedEmail, code, password);
        await refreshUser();
        onBound?.();
      } else {
        await resetPassword(normalizedEmail, code, password);
        switchMode('login'); setUsername(normalizedEmail);
        setNotice('密码已重置，旧登录会话已失效。请使用新密码登录。');
      }
    } catch (err) { setLocalError(err instanceof Error ? err.message : '操作失败，请稍后重试'); }
    finally { setWorking(false); }
  }

  const shownError = localError ?? error;
  return <div className="auth-form-wrap">
    <div className="auth-form-symbol"><AudioLines size={28} strokeWidth={1.5} /></div>
    <h2 id="auth-dialog-title">{{ login: '欢迎回来', register: '创建账户', reset: '找回密码', bind: '绑定安全邮箱' }[mode]}</h2>
    <p className="auth-form-intro">{{ login: '登录工作台，继续探索数据的下一种可能。', register: '验证邮箱后，开启您的专属工作空间。', reset: '验证注册邮箱，设置新的登录密码。', bind: '验证邮箱并确认当前密码，以后可用邮箱找回账户。' }[mode]}</p>
    {(mode === 'login' || mode === 'register') && <div className="auth-mode-switch" role="group" aria-label="账户操作">
      {(['login', 'register'] as const).map(value => <button key={value} type="button" disabled={busy} aria-pressed={mode === value} className={mode === value ? 'is-active' : ''} onClick={() => switchMode(value)}>{value === 'login' ? '账户登录' : '注册账户'}</button>)}
    </div>}
    <form onSubmit={onSubmit} noValidate aria-busy={busy}>
      {(mode === 'login' || mode === 'register') && <Field id="auth-username" label={mode === 'login' ? '用户名或邮箱' : '用户名'} icon={<User size={17} />}>
        <input id="auth-username" autoFocus autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} placeholder={mode === 'login' ? '请输入用户名或邮箱' : '设置用户名'} maxLength={mode === 'login' ? 254 : 32} disabled={busy} />
      </Field>}
      {mode !== 'login' && <>
        <Field id="auth-email" label="邮箱" icon={<Mail size={17} />}>
          <input id="auth-email" type="email" autoFocus={mode === 'reset' || mode === 'bind'} autoComplete="email" value={email} onChange={e => { setEmail(e.target.value); setCode(''); setNotice(''); }} placeholder="请输入邮箱地址" maxLength={254} disabled={busy} />
        </Field>
        <div className="auth-code-row">
          <Field id="auth-code" label="邮箱验证码" icon={<ShieldCheck size={17} />}>
            <input id="auth-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="6 位验证码" maxLength={6} disabled={busy} />
          </Field>
          <button className="auth-send-code" type="button" onClick={() => void sendCode()} disabled={busy || remaining > 0 || !normalizedEmail}>{sending ? '发送中…' : remaining > 0 ? `${remaining} 秒后重发` : '获取验证码'}</button>
        </div>
      </>}
      <Field id="auth-password" label={mode === 'bind' ? '当前密码' : mode === 'reset' ? '新密码' : '密码'} icon={<KeyRound size={17} />}>
        <input id="auth-password" type={showPassword ? 'text' : 'password'} autoComplete={mode === 'login' || mode === 'bind' ? 'current-password' : 'new-password'} value={password} onChange={e => setPassword(e.target.value)} placeholder={mode === 'login' || mode === 'bind' ? '请输入密码' : '8–128 个字符，包含字母和数字'} maxLength={128} disabled={busy} aria-describedby={shownError ? 'auth-error' : undefined} />
        <button className="auth-password-toggle" type="button" onClick={() => setShowPassword(value => !value)} disabled={busy} aria-label={showPassword ? '隐藏密码' : '显示密码'} aria-pressed={showPassword}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button>
      </Field>
      {(mode === 'register' || mode === 'reset') && <Field id="auth-confirm" label="确认密码" icon={<KeyRound size={17} />}>
        <input id="auth-confirm" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="再次输入密码" maxLength={128} disabled={busy} />
      </Field>}
      {mode === 'login' && <div className="auth-forgot"><button type="button" disabled={busy} onClick={() => switchMode('reset')}>忘记密码？</button></div>}
      {mode === 'register' && <p className="auth-register-hint">用户名支持中文、字母、数字、下划线、点和短横线，长度为 2–32 个字符，且不超过 32 字节。</p>}
      {mode === 'reset' && <p className="auth-register-hint">旧账户若尚未绑定邮箱，请先用原用户名和密码登录，再绑定安全邮箱；忘记原密码请联系管理员核验身份。</p>}
      {shownError && <div id="auth-error" role="alert" className="auth-error">{shownError}</div>}
      {notice && <div role="status" className="auth-notice">{notice}</div>}
      <Button type="submit" variant="primary" size="lg" loading={submitting || working} disabled={busy} className="auth-submit">{{ login: '登录工作台', register: '创建账户并登录', reset: '重置密码', bind: '验证并绑定邮箱' }[mode]}</Button>
    </form>
    {mode !== 'bind' && <p className="auth-switch-copy">{mode === 'login' ? '还没有账户？' : '已有账户？'}<button type="button" disabled={busy} onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? '立即注册' : '返回登录'}</button></p>}
    <div className="auth-workspace-note"><ShieldCheck size={16} /><span>在专属工作空间中管理数据、模型与智能体</span></div>
  </div>;
}

function Field({ id, label, icon, children }: { id: string; label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <div className="auth-field"><label htmlFor={id}>{label}</label><div className="auth-input-wrap"><span className="auth-input-icon">{icon}</span>{children}</div></div>;
}
