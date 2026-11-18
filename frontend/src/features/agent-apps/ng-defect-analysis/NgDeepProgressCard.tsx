import { useEffect, useId, useRef, useState } from 'react';
import { Check, ChevronDown, CircleAlert, LoaderCircle } from 'lucide-react';
import type { DeepProgress } from './deepTypes';
import { cn } from '@/utils/cn';

export function NgDeepProgressCard({ progress, history }: { progress: DeepProgress; history: DeepProgress[] }) {
  const done = ['completed', 'failed', 'cancelled'].includes(progress.stage);
  const [expanded, setExpanded] = useState(false);
  const previousDone = useRef(done);
  const log = useRef<HTMLDivElement>(null);
  const id = useId();
  const [elapsed, setElapsed] = useState(progress.elapsed_seconds);
  useEffect(() => {
    if (!previousDone.current && done) setExpanded(false);
    previousDone.current = done;
  }, [done]);
  useEffect(() => {
    setElapsed(progress.elapsed_seconds);
    if (done) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(progress.elapsed_seconds + (Date.now() - started) / 1000), 1000);
    return () => clearInterval(timer);
  }, [progress.elapsed_seconds, done]);
  useEffect(() => {
    if (expanded && log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [expanded, progress.sequence]);
  return <div className="text-steel-400" aria-label="深度分析实时取数进度">
    <button type="button" className="group flex w-full items-center gap-2 py-1 text-left text-xs transition-colors hover:text-steel-600"
      aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded(value => !value)}>
      {progress.stage === 'completed' ? <Check className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
        : done ? <CircleAlert className="h-3.5 w-3.5 shrink-0" /> : <LoaderCircle className="h-3.5 w-3.5 shrink-0 animate-spin" />}
      <span key={progress.sequence} aria-live="polite" className="min-w-0 flex-1 truncate animate-fade-in" title={progress.message}>{progress.message}</span>
      <span className="shrink-0 font-mono text-[10px] tabular-nums">{elapsed.toFixed(1)}s</span>
      <ChevronDown className={cn('h-3.5 w-3.5 shrink-0 transition-transform duration-200', expanded && 'rotate-180')} />
    </button>
    <div id={id} hidden={!expanded} className="ml-1.5 border-l border-steel-200 pb-1 pl-4 pt-2">
      <div ref={log} className="max-h-36 space-y-1.5 overflow-y-auto pr-2 text-[11px] leading-5">
        {history.map(entry => <p key={entry.sequence} className="break-words"><span className="mr-2 font-mono text-[10px]">{entry.elapsed_seconds.toFixed(1)}s</span>{entry.message}</p>)}
      </div>
    </div>
  </div>;
}
