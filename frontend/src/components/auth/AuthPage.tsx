import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Eye, EyeOff, KeyRound, User, AudioLines, ScanLine, ChartNoAxesCombined, GitFork, ShieldCheck, X, MoveUpRight } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/Button';
import './AuthPage.css';
import { AuthShowcase } from './AuthShowcase';

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
  const [insight, setInsight] = useState(0);
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
    <main className="industrial-auth">
      <header className="auth-header">
        <a className="auth-brand" href="#" aria-label="工业时序智能体首页">
          <span className="auth-brand-symbol"><AudioLines size={25} strokeWidth={1.5} /></span>
          <span><strong>工业时序智能体</strong><small>Industrial Time Series Agent</small></span>
        </a>
        <nav className="auth-site-nav" aria-label="页面导航"><a href="#agent-scenes">应用场景</a></nav>
        <button className="auth-header-login" onClick={openAuth}>登录工作台 <MoveUpRight size={14} /></button>
      </header>

      <section className="auth-experience" aria-labelledby="auth-headline">
        <div className="auth-intro">
          <p className="auth-intro-caption">从时序信号，走向工业洞见</p>
          <h1 id="auth-headline">洞见工业脉搏，预见运行未来</h1>
          <p className="auth-intro-description">连接设备、工艺与生产数据，以自然语言探索异常、趋势与成因。</p>
          <button className="auth-explore" onClick={openAuth}>开启分析 <MoveUpRight size={15} /></button>
        </div>

        <div className="auth-landscape">
          <SignalLandscape insight={insight} paused={reducedMotion || authOpen} />
          <div className="auth-landscape-tools" aria-hidden="true">
            <div className="auth-signal-console">
              <span className="auth-console-label"><i /> SIGNAL INPUT</span>
              <strong>多源信号同步</strong>
            </div>
          </div>
          <div key={`mobile-insight-${insight}`} className="auth-insight-note auth-mobile-insight-note" aria-live="polite">
            <span className="auth-note-dot" />
            <span className="auth-note-copy"><small>{INSIGHTS[insight].code}</small><strong>{INSIGHTS[insight].note}</strong></span>
            <span className="auth-note-scan" aria-hidden="true" />
          </div>
          <div className="auth-landscape-axis"><span>数据感知</span><span>智能分析</span><span>决策支持</span></div>
        </div>

        <div className="auth-capabilities" role="group" aria-label="探索分析能力">
          {INSIGHTS.map((item, index) => {
            const Icon = item.icon;
            return <button key={item.title} className={insight === index ? 'auth-capability is-active' : 'auth-capability'} aria-pressed={insight === index} onClick={() => setInsight(index)}>
              <span className="auth-capability-icon"><Icon size={19} strokeWidth={1.4} /><span className="auth-capability-motion" aria-hidden="true"><i /><i /><i /></span></span><span><strong>{item.title}</strong><small>{item.description}</small></span><span className="auth-capability-indicator" />
            </button>;
          })}
        </div>
      </section>
      <AuthShowcase onLogin={openAuth} />
      <footer className="auth-footer"><span>工业时序智能体平台</span><span>数据有序，洞见有源</span><span>数据 · 模型 · 智能体</span></footer>

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

const INSIGHTS = [
  { code: 'ANOMALY SCAN', title: '异常检测', description: '识别偏离，捕捉潜在风险', note: '从连续信号中，识别不寻常的波动', icon: ScanLine },
  { code: 'TREND FORECAST', title: '趋势预测', description: '理解规律，预见未来趋势', note: '沿着历史规律，推演未来变化', icon: ChartNoAxesCombined },
  { code: 'CAUSE ANALYSIS', title: '归因分析', description: '关联变量，追溯问题成因', note: '连接多维变量，追溯波动的来源', icon: GitFork },
];

/** Deterministic, illustrative signal surface; no production telemetry. */
function SignalLandscape({ insight, paused }: { insight: number; paused: boolean }) {
  const surfaceRef = useRef<SVGSVGElement>(null);
  const phaseRef = useRef(0);
  function point(t: number, row: number, phase = 0) {
    const ridge = Math.exp(-Math.pow((t - .49) / .19, 2));
    const envelope = Math.sin(t * Math.PI);
    const wave = Math.sin(t * 22 - row * .19 + phase) * 17 + Math.sin(t * 43 + row * .13 + phase * .7) * 7;
    const height = (ridge * (76 + 20 * Math.sin(row * .18)) + wave * envelope);
    return [65 + t * 860 + row * 4.6, 245 + row * 3.2 - height - row * 1.7];
  }
  function line(row: number, phase = 0) {
    return Array.from({ length: 161 }, (_, i) => {
      const [x, y] = point(i / 160, row, phase);
      return `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(' ');
  }
  useEffect(() => {
    const surface = surfaceRef.current;
    if (!surface || paused) return;
    const waves = Array.from(surface.querySelectorAll<SVGPathElement>('[data-wave-row]'));
    const marker = surface.querySelector<SVGGElement>('.auth-surface-marker');
    const t = insight === 1 ? .73 : .49;
    const origin = point(t, 20);
    let frame = 0;
    let last = 0;
    let visible = false;
    const tick = (now: number) => {
      if (now - last >= 45) {
        phaseRef.current += last ? Math.min(now - last, 80) * .00055 : 0;
        last = now;
        for (const wave of waves) wave.setAttribute('d', line(Number(wave.dataset.waveRow), phaseRef.current));
        const current = point(t, 20, phaseRef.current);
        marker?.setAttribute('transform', `translate(0 ${current[1] - origin[1]})`);
      }
      frame = requestAnimationFrame(tick);
    };
    const sync = () => {
      cancelAnimationFrame(frame);
      last = 0;
      if (visible && !document.hidden) frame = requestAnimationFrame(tick);
    };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); });
    observer.observe(surface);
    document.addEventListener('visibilitychange', sync);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); document.removeEventListener('visibilitychange', sync); };
  }, [paused, insight]);
  const [nodeX, nodeY] = point(insight === 1 ? .73 : .49, 20);
  return <svg ref={surfaceRef} className="auth-surface" viewBox="0 0 1100 365" fill="none" role="img" aria-label={`${INSIGHTS[insight].title}概念图：多维工业时序信号构成连续的数据曲面`}>
    <defs>
      <linearGradient id="auth-surface-stroke" x1="50" y1="0" x2="1050" y2="0" gradientUnits="userSpaceOnUse"><stop stopColor="var(--auth-wave-light)" stopOpacity="0" /><stop offset=".2" stopColor="var(--auth-wave-mid)" /><stop offset=".5" stopColor="var(--auth-wave-strong)" /><stop offset=".8" stopColor="var(--auth-wave-mid)" /><stop offset="1" stopColor="var(--auth-wave-light)" stopOpacity="0" /></linearGradient>
      <radialGradient id="auth-surface-shadow"><stop stopColor="var(--auth-wave-shadow)" stopOpacity=".14" /><stop offset="1" stopColor="var(--auth-wave-shadow)" stopOpacity="0" /></radialGradient>
    </defs>
    <ellipse cx="560" cy="285" rx="450" ry="72" fill="url(#auth-surface-shadow)" />
    <g stroke="var(--auth-wave-grid)" strokeOpacity=".16" strokeWidth=".6">
      {Array.from({ length: 9 }, (_, i) => <path key={i} d={`M${80 + i * 110} 306 l155 -160`} />)}
      {Array.from({ length: 5 }, (_, i) => <path key={i} d={`M${80 + i * 33} ${306 - i * 34} h875`} />)}
    </g>
    <g aria-hidden="true" stroke="var(--auth-wave-grid)" strokeWidth=".7">
      {Array.from({ length: 61 }, (_, i) => <path key={i} opacity={i % 5 === 0 ? .4 : .2} d={`M${100 + i * 15} 329 v${i % 5 === 0 ? 7 : 3}`} />)}
      <path d="M100 323 h900" strokeOpacity=".12" />
    </g>
    {Array.from({ length: 38 }, (_, row) => <path key={row} data-wave-row={row} d={line(row)} stroke="url(#auth-surface-stroke)" strokeWidth={row === 20 ? 1.8 : .8} opacity={row === 20 ? 1 : .22 + row / 80} />)}
    <path data-wave-row={20} d={line(20)} stroke={insight === 0 ? 'var(--auth-wave-strong)' : 'var(--auth-wave-mid)'} strokeWidth="1.4" opacity=".85" strokeDasharray={insight === 1 ? '4 5' : undefined} />
    <g className="auth-surface-marker" key={insight}>
      <path d={`M${nodeX} ${nodeY - 8} v-54 h18`} stroke="var(--auth-wave-grid)" strokeWidth=".8" />
      <circle cx={nodeX} cy={nodeY} r="10" fill="var(--auth-wave-shadow)" fillOpacity=".12" /><circle cx={nodeX} cy={nodeY} r="3.5" fill="var(--auth-wave-strong)" stroke="var(--auth-wave-surface)" strokeWidth="1.5" />
      <foreignObject className="auth-surface-insight-object" x={nodeX + 18} y={nodeY - 88} width="276" height="62">
        <div className="auth-insight-note auth-surface-insight" role="status">
          <span className="auth-note-dot" />
          <span className="auth-note-copy"><small>{INSIGHTS[insight].code}</small><strong>{INSIGHTS[insight].note}</strong></span>
          <span className="auth-note-scan" aria-hidden="true" />
        </div>
      </foreignObject>
    </g>
  </svg>;
}

function Field({ id, label, icon, children }: { id: string; label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <div className="auth-field"><label htmlFor={id}>{label}</label><div className="auth-input-wrap"><span className="auth-input-icon">{icon}</span>{children}</div></div>;
}

