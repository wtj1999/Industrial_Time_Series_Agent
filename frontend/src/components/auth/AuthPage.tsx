/**
 * Login / registration page shown when no session is active.
 *
 * Two-column layout: a brand showcase on the left (hidden on small
 * screens) and a form card on the right with login/register tabs.
 * Matches the validation rules in ``agent_app/auth/user_store.py`` so
 * the user gets immediate feedback without a round-trip.
 */

import { useEffect, useState, type FormEvent } from 'react';
import { Activity, Eye, EyeOff, KeyRound, User } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/Button';
import { cn } from '@/utils/cn';

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
  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  // Clear form errors when the user edits anything or switches modes.
  useEffect(() => {
    setLocalError(null);
  }, [mode]);
  useEffect(() => {
    setLocalError(null);
    clearError();
  }, [username, password, clearError]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
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
    <div className="flex min-h-screen bg-gradient-to-br from-steel-50 via-white to-brand-50/40">
      {/* Brand showcase */}
      <aside className="relative hidden lg:flex lg:w-1/2 flex-col justify-between overflow-hidden bg-gradient-to-br from-brand-700 via-brand-800 to-steel-900 p-12 text-white">
        <div className="absolute inset-0 opacity-20" aria-hidden>
          <svg width="100%" height="100%" viewBox="0 0 400 400" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M0 250 Q50 200 100 230 T200 220 T300 180 T400 200" stroke="white" strokeWidth="1.5" fill="none" />
            <path d="M0 300 Q50 260 100 280 T200 270 T300 240 T400 260" stroke="white" strokeWidth="1.5" fill="none" opacity="0.6" />
            <path d="M0 350 Q50 320 100 335 T200 325 T300 300 T400 320" stroke="white" strokeWidth="1.5" fill="none" opacity="0.4" />
          </svg>
        </div>

        <div className="relative flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15 backdrop-blur-sm">
            <Activity className="h-5 w-5" strokeWidth={2.4} />
          </div>
          <div className="leading-tight">
            <div className="text-base font-semibold">工业时序智能体</div>
            <div className="text-xs text-white/70">Industrial Time Series Agent</div>
          </div>
        </div>

        <div className="relative max-w-md space-y-4">
          <h1 className="text-3xl font-bold leading-tight">
            工业时序智能体平台
          </h1>
          <p className="text-sm leading-relaxed text-white/75">
            面向工业时序数据的智能分析与决策支持，自然语言驱动异常检测、趋势预测与相关性分析，全流程可解释、可干预。
          </p>
          <ul className="space-y-2 pt-2 text-sm text-white/80">
            {[
              '异常检测 · 趋势预测 · 统计分析',
              '自然语言交互 · Human-in-the-loop 工作流',
              '多源数据接入 · 可解释分析报告',
            ].map((line) => (
              <li key={line} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-300" />
                {line}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative text-xs text-white/50">
          LangGraph · FastAPI · React
        </div>
      </aside>

      {/* Form column */}
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-sm">
          {/* Mobile-only header (the aside is hidden below lg) */}
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-600 to-brand-800 text-white shadow-sm">
              <Activity className="h-4 w-4" strokeWidth={2.4} />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold text-steel-900">工业时序智能体</div>
              <div className="text-[11px] text-steel-500">Industrial Time Series Agent</div>
            </div>
          </div>

          {/* Tabs */}
          <div className="mb-6 inline-flex w-full rounded-xl bg-steel-100 p-1">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={cn(
                  'flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-all',
                  mode === m
                    ? 'bg-white text-steel-900 shadow-sm'
                    : 'text-steel-500 hover:text-steel-700',
                )}
              >
                {m === 'login' ? '登录' : '注册'}
              </button>
            ))}
          </div>

          <div className="mb-6">
            <h2 className="text-xl font-semibold text-steel-900">
              {mode === 'login' ? '欢迎回来' : '创建账户'}
            </h2>
            <p className="mt-1 text-xs text-steel-500">
              {mode === 'login'
                ? '登录账户以继续你的分析工作。'
                : '注册后即可上传数据并训练模型，资产绑定到账户。'}
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <Field
              id="auth-username"
              label="用户名"
              icon={<User className="h-4 w-4" />}
            >
              <input
                id="auth-username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="2-32 个字符"
                maxLength={64}
                className="w-full bg-transparent pl-10 pr-3 py-2.5 text-sm text-steel-900 placeholder:text-steel-400 focus:outline-none"
              />
            </Field>

            <Field
              id="auth-password"
              label="密码"
              icon={<KeyRound className="h-4 w-4" />}
            >
              <input
                id="auth-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 4 个字符"
                className="w-full bg-transparent pl-10 pr-10 py-2.5 text-sm text-steel-900 placeholder:text-steel-400 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-steel-400 hover:text-steel-600"
                tabIndex={-1}
                aria-label={showPassword ? '隐藏密码' : '显示密码'}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </Field>

            {shownError && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                {shownError}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={submitting}
              className="w-full"
            >
              {mode === 'login' ? '登录' : '注册并登录'}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-steel-500">
            {mode === 'login' ? (
              <>
                还没有账户？
                <button
                  type="button"
                  onClick={() => setMode('register')}
                  className="ml-1 font-medium text-brand-600 hover:text-brand-700"
                >
                  立即注册
                </button>
              </>
            ) : (
              <>
                已有账户？
                <button
                  type="button"
                  onClick={() => setMode('login')}
                  className="ml-1 font-medium text-brand-600 hover:text-brand-700"
                >
                  返回登录
                </button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}

function Field({
  id,
  label,
  icon,
  children,
}: {
  id: string;
  label: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-xs font-medium text-steel-700">
        {label}
      </label>
      <div className="relative flex items-center rounded-xl border border-steel-200 bg-white/70 transition-colors focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100">
        <span className="pointer-events-none absolute left-3 text-steel-400">{icon}</span>
        {children}
      </div>
    </div>
  );
}
