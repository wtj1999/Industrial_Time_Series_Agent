/**
 * Top-level React error boundary.
 *
 * Why this exists
 * ---------------
 * Without an error boundary, *any* exception thrown during render
 * (most commonly: a chart component reading `undefined.foo` when the
 * backend payload is missing a field) unmounts the entire React tree
 * and leaves a blank white page. The error is logged to the browser
 * DevTools Console only — never to the Vite dev-server terminal — so
 * it looks like "the page just died silently".
 *
 * Wrapping `<App />` with this boundary turns that white-screen into
 * a visible error card with the message, the component stack, and a
 * "reload" button. The original error is still forwarded to
 * `console.error` so DevTools remains the source of truth for debugging.
 *
 * Granularity
 * -----------
 * This is intentionally the *root* boundary — a single safety net for
 * the whole app. If you later want a broken chart to degrade inline
 * (instead of taking over the whole screen), wrap individual chart
 * cards with their own `<ErrorBoundary>` instance; this component is
 * reusable via the optional `fallback` prop.
 */

import { Component, Fragment, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** Optional custom fallback. Receives the captured error + a reset
   *  callback that clears the boundary and attempts a re-render. */
  fallback?: (error: Error, errorInfo: ErrorInfo | null, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
  errorInfo: ErrorInfo | null;
  /** Monotonically increasing key. When the user hits "reset" we bump
   *  this so children remount from scratch — otherwise clearing `error`
   *  alone would re-run the same broken render and crash again. */
  resetKey: number;
}

export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null, errorInfo: null, resetKey: 0 };

  static getDerivedStateFromError(error: Error): Partial<State> {
    // Called during the render phase — keep it side-effect free.
    return { error };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Mirror to devtools console so the stack stays discoverable even
    // when callers swallow the default React error log downstream.
    console.error('[ErrorBoundary] captured render error:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  private reset = (): void => {
    this.setState((prev) => ({
      error: null,
      errorInfo: null,
      resetKey: prev.resetKey + 1,
    }));
  };

  private reload = (): void => {
    window.location.reload();
  };

  private copyError = async (): Promise<void> => {
    const { error, errorInfo } = this.state;
    if (!error) return;
    const text = [
      `${error.name}: ${error.message}`,
      '',
      'Component stack:',
      errorInfo?.componentStack?.trim() ?? '(unavailable)',
    ].join('\n');
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* clipboard may be blocked / unavailable — ignore */
    }
  };

  override render(): ReactNode {
    const { error, errorInfo, resetKey } = this.state;
    const { children, fallback } = this.props;

    if (!error) {
      // Render children untouched — NO wrapper DOM node. The app's root
      // layout relies on a direct parent chain (`#root` → AppLayout)
      // for `h-full` / sticky sidebar behaviour; an intermediate <div>
      // here would break that chain and make the sidebar scroll with
      // the page. Fragment with a key still gives us remount-on-reset.
      return <Fragment key={resetKey}>{children}</Fragment>;
    }

    if (fallback) {
      return fallback(error, errorInfo, this.reset);
    }

    return (
      <div className="min-h-full flex items-center justify-center p-6">
        <div className="max-w-2xl w-full rounded-2xl border border-red-200 bg-white shadow-lg p-6">
          <div className="flex items-start gap-3">
            <div className="text-2xl leading-none">⚠️</div>
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-semibold text-red-700">页面渲染出错</h1>
              <p className="mt-1 text-sm text-gray-600">
                某个组件在渲染时抛出了未捕获的异常。详细堆栈已写入浏览器 Console
                （DevTools → Console）。你可以复制错误信息反馈，或直接重新加载页面。
              </p>
            </div>
          </div>

          <div className="mt-4 rounded-lg bg-gray-50 border border-gray-200 p-3">
            <div className="text-xs font-mono text-red-700 break-all">
              {error.name}: {error.message}
            </div>
            {errorInfo?.componentStack && (
              <details className="mt-2 group">
                <summary className="text-xs text-gray-500 cursor-pointer select-none">
                  组件堆栈（点击展开）
                </summary>
                <pre className="mt-2 text-xs font-mono text-gray-700 whitespace-pre-wrap break-all max-h-64 overflow-auto">
                  {errorInfo.componentStack}
                </pre>
              </details>
            )}
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={this.reload}
              className="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              重新加载页面
            </button>
            <button
              type="button"
              onClick={this.copyError}
              className="px-3 py-1.5 text-sm rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              复制错误信息
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
