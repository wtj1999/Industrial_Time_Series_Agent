import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, LoaderCircle } from 'lucide-react';
import type { AnomalyTrainingProgress, PredictionFinetuningProgress } from '@/types';
import { cn } from '@/utils/cn';

type TrainingProgress = AnomalyTrainingProgress | PredictionFinetuningProgress;

const stageLabels: Record<TrainingProgress['stage'], string> = {
  preparing: '准备训练数据与模型',
  training: '训练模型',
  evaluating: '回测基础模型与微调模型',
  scoring: '计算异常分数',
  saving: '保存模型与元数据',
  completed: '执行完成',
  failed: '执行失败',
};

interface Props {
  progress: TrainingProgress;
  history: TrainingProgress[];
}

export function TrainingProgressCard({ progress, history }: Props) {
  const done = progress.stage === 'completed' || progress.stage === 'failed';
  const displayName = 'detector_name' in progress ? progress.detector_name : progress.model_name;
  const [expanded, setExpanded] = useState(!done);
  const wasDoneRef = useRef(done);
  const logRef = useRef<HTMLDivElement>(null);

  // Only the transition from running -> completed triggers auto-collapse.
  // A user's later click is therefore never overridden by a render.
  useEffect(() => {
    if (!wasDoneRef.current && done) setExpanded(false);
    wasDoneRef.current = done;
  }, [done]);

  useEffect(() => {
    if (!expanded || done) return;
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [expanded, done, history.length]);

  const percent = Math.max(0, Math.min(100, progress.percent ?? (done ? 100 : 0)));
  const epoch = progress.total && progress.current !== undefined
    ? `${progress.current}/${progress.total}`
    : null;

  return (
    <div className="ml-11 max-w-[78%] animate-fade-in text-steel-400">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
        className="group flex w-full items-center gap-2 py-1 text-left text-xs transition-colors hover:text-steel-600"
      >
        {done ? (
          <Check className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
        ) : (
          <LoaderCircle className="h-3.5 w-3.5 shrink-0 animate-spin text-brand-400" />
        )}
        <span className="min-w-0 flex-1 truncate">
          {done
            ? `${displayName} · 执行过程`
            : `${displayName} · ${stageLabels[progress.stage]}`}
        </span>
        {!done && epoch && <span className="font-mono text-[10px] text-steel-400">{epoch}</span>}
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 shrink-0 transition-transform duration-200',
            expanded && 'rotate-180',
          )}
        />
      </button>

      <div
        className={cn(
          'grid transition-[grid-template-rows,opacity] duration-200 ease-out',
          expanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
        )}
      >
        <div className="overflow-hidden">
          <div className="ml-1.5 border-l border-steel-200 pb-1 pl-4 pt-2">
            {!done && (
              <div className="mb-3 h-0.5 overflow-hidden rounded-full bg-steel-100">
                <div
                  className="h-full rounded-full bg-brand-300 transition-[width] duration-300 ease-out"
                  style={{ width: `${percent}%` }}
                />
              </div>
            )}
            <div
              ref={logRef}
              className="max-h-44 space-y-1.5 overflow-y-auto pr-2 text-[11px] leading-5"
            >
              {history.map((entry, index) => (
                <ProgressLine key={`${entry.stage}-${entry.current ?? index}-${index}`} entry={entry} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProgressLine({ entry }: { entry: TrainingProgress }) {
  const metrics = Object.entries(entry.metrics ?? {});
  const epoch = entry.total && entry.current !== undefined
    ? ` ${entry.current}/${entry.total}`
    : '';

  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
      <span className="shrink-0 text-steel-500">
        {stageLabels[entry.stage]}{epoch}
      </span>
      {metrics.length > 0 && (
        <span className="flex min-w-0 flex-wrap gap-x-2.5 gap-y-0 font-mono text-[10px] text-steel-400/90">
          {metrics.map(([name, value]) => (
            <span key={name} title={name}>
              {metricLabel(name)} {formatMetric(name, value)}
            </span>
          ))}
        </span>
      )}
    </div>
  );
}

const metricLabels: Record<string, string> = {
  loss: 'Loss',
  best_loss: 'Best',
  change_pct: 'Change',
  learning_rate: 'LR',
  epoch_seconds: 'Time',
  throughput_per_second: 'Throughput',
};

function metricLabel(name: string): string {
  return metricLabels[name] ?? name;
}

function formatMetric(name: string, value: number): string {
  if (!Number.isFinite(value)) return '—';
  if (name.endsWith('_pct')) return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  if (name === 'epoch_seconds') return `${value.toFixed(2)}s`;
  if (name.endsWith('_per_second')) return `${value.toFixed(1)}/s`;
  if (name === 'learning_rate') return value.toExponential(1);
  const magnitude = Math.abs(value);
  if (magnitude !== 0 && (magnitude >= 10_000 || magnitude < 0.001)) {
    return value.toExponential(3);
  }
  return value.toFixed(magnitude >= 100 ? 2 : 4);
}
