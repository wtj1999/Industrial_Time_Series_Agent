import { useState } from 'react';
import {
  ArrowRight,
  BadgeCheck,
  CircleCheck,
  Crosshair,
  Gauge,
  Layers,
  ListTree,
  Sparkles,
  Target,
  Zap,
} from 'lucide-react';
import type { TechPath, TechPathStep, ChooseTechPathInterruptData } from '@/types';
import { useSession } from '@/context/SessionContext';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { cn } from '@/utils/cn';
import { taskLabel } from '@/utils/format';

interface Props {
  interrupt: ChooseTechPathInterruptData & { type?: string };
}

export function TechPathSelector({ interrupt }: Props) {
  const { resumeQuery, streaming } = useSession();
  const [selected, setSelected] = useState<string | null>(null);
  const paths = interrupt.paths ?? [];

  const handleSubmit = () => {
    if (!selected) return;
    // Backend `_node_choose_path` reads `selected.get("path_id")` — the key
    // must be "path_id" to match.
    void resumeQuery({ path_id: selected });
  };

  return (
    <div className="space-y-4">
      {/* Intro */}
      <div className="flex items-start gap-2.5 rounded-xl border border-brand-200 bg-gradient-to-r from-brand-50 to-white px-4 py-3">
        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-steel-800">
            智能体已为你规划 {paths.length} 条候选技术方案
          </p>
          <p className="mt-0.5 text-xs leading-5 text-steel-600">
            {interrupt.message ?? '请选择一条执行路径，确认后将进入参数解析与字段映射阶段。'}
          </p>
        </div>
      </div>

      {/* Path cards */}
      <div className="space-y-3">
        {paths.map((p, idx) => (
          <PathCard
            key={p.path_id ?? idx}
            path={p}
            index={idx}
            isSelected={selected === p.path_id}
            onSelect={() => setSelected(p.path_id)}
          />
        ))}
      </div>

      {/* Footer actions */}
      <div className="flex items-center justify-between gap-3 border-t border-steel-100 pt-3">
        <p className="inline-flex items-center gap-1.5 text-[11px] text-steel-500">
          <CircleCheck className="h-3.5 w-3.5" />
          选择后将进入参数解析 / 字段确认阶段
        </p>
        <Button
          onClick={handleSubmit}
          disabled={!selected || streaming}
          loading={streaming}
        >
          <ArrowRight className="h-4 w-4" />
          确认选择
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Single path card
 * ------------------------------------------------------------------ */

function PathCard({
  path,
  index,
  isSelected,
  onSelect,
}: {
  path: TechPath;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect();
        }
      }}
      className={cn(
        'group relative overflow-hidden rounded-2xl border bg-white transition-all duration-200',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400',
        isSelected
          ? 'border-brand-500 shadow-glow ring-1 ring-brand-200'
          : 'border-steel-200 hover:border-brand-300 hover:shadow-soft',
      )}
    >
      {/* Left accent strip */}
      <div
        className={cn(
          'absolute inset-y-0 left-0 w-1.5 transition-colors',
          isSelected ? 'bg-brand-500' : 'bg-steel-200 group-hover:bg-brand-300',
        )}
        aria-hidden
      />

      <div className="pl-5 pr-4 py-4">
        <PathHeader path={path} index={index} isSelected={isSelected} />
        <PathSummary path={path} />

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <TargetObjects path={path} />
          <ExpectedEffect path={path} />
        </div>

        <PathSteps path={path} />
      </div>
    </div>
  );
}

function PathHeader({
  path,
  index,
  isSelected,
}: {
  path: TechPath;
  index: number;
  isSelected: boolean;
}) {
  return (
    <div className="flex items-start gap-3">
      <div
        className={cn(
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-semibold shadow-sm transition-colors',
          isSelected
            ? 'bg-brand-600 text-white'
            : 'bg-steel-100 text-steel-600 group-hover:bg-brand-100 group-hover:text-brand-700',
        )}
      >
        {String(index + 1).padStart(2, '0')}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-base font-semibold leading-tight text-steel-900">
            {path.title || `技术方案 ${index + 1}`}
          </h4>
          {path.model_type && (
            <Badge tone="brand" dot>
              <Gauge className="mr-0.5 h-3 w-3" />
              {taskLabel(path.model_type)}
            </Badge>
          )}
          {isSelected && (
            <Badge tone="success">
              <BadgeCheck className="mr-0.5 h-3 w-3" />
              已选中
            </Badge>
          )}
        </div>
        {path.path_id && (
          <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-steel-400">
            {path.path_id}
          </p>
        )}
      </div>

      {/* Radio-style selection indicator */}
      <span
        className={cn(
          'mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-all',
          isSelected
            ? 'border-brand-500 bg-brand-500 text-white'
            : 'border-steel-300 text-transparent group-hover:border-brand-400',
        )}
        aria-hidden
      >
        <CircleCheck className="h-3.5 w-3.5" strokeWidth={3} />
      </span>
    </div>
  );
}

function PathSummary({ path }: { path: TechPath }) {
  if (!path.short_summary) return null;
  return (
    <div className="mt-3 flex items-start gap-2 rounded-lg border border-steel-100 bg-steel-50/60 px-3 py-2">
      <Layers className="mt-0.5 h-3.5 w-3.5 shrink-0 text-steel-500" />
      <p className="text-[13px] leading-6 text-steel-700">{path.short_summary}</p>
    </div>
  );
}

function TargetObjects({ path }: { path: TechPath }) {
  const targets = path.target_objects ?? [];
  if (targets.length === 0) return null;
  return (
    <div className="rounded-lg border border-sky-200 bg-sky-50/40 px-3 py-2.5">
      <SectionLabel icon={Target} tone="sky">
        关注对象
      </SectionLabel>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {targets.map((t, i) => (
          <span
            key={i}
            className="inline-flex items-center rounded-md bg-white px-2 py-0.5 text-[11px] font-medium text-sky-700 border border-sky-200 shadow-sm"
          >
            <Crosshair className="mr-1 h-3 w-3" />
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

function ExpectedEffect({ path }: { path: TechPath }) {
  if (!path.expected_effect) return null;
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50/40 px-3 py-2.5">
      <SectionLabel icon={Zap} tone="amber">
        预期效果
      </SectionLabel>
      <p className="mt-1.5 text-[12px] leading-5 text-amber-900/90">
        {path.expected_effect}
      </p>
    </div>
  );
}

function PathSteps({ path }: { path: TechPath }) {
  const steps = path.steps ?? [];
  if (steps.length === 0) return null;
  return (
    <div className="mt-3">
      <SectionLabel icon={ListTree} tone="steel">
        执行步骤
        <span className="ml-1 text-steel-400">({steps.length})</span>
      </SectionLabel>

      <ol className="relative mt-2 space-y-2.5 border-l border-dashed border-steel-200 pl-4">
        {steps.map((step, i) => (
          <StepItem key={i} step={step} index={i} />
        ))}
      </ol>
    </div>
  );
}

function StepItem({ step, index }: { step: TechPathStep; index: number }) {
  // Tolerate malformed LLM output that returns a plain string instead of an object
  const title = step?.step_title ?? `步骤 ${index + 1}`;
  const content = step?.content ?? '';

  return (
    <li className="relative">
      {/* Node marker on the timeline */}
      <span
        className="absolute -left-[21px] top-1 flex h-4 w-4 items-center justify-center rounded-full bg-white ring-2 ring-brand-400"
        aria-hidden
      >
        <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
      </span>

      <div className="rounded-lg border border-steel-100 bg-white px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-md bg-brand-50 text-[10px] font-bold text-brand-700">
            {index + 1}
          </span>
          <p className="text-[13px] font-semibold text-steel-800">{title}</p>
        </div>
        {content && (
          <p className="mt-1 pl-7 text-[12px] leading-5 text-steel-600 whitespace-pre-wrap">
            {content}
          </p>
        )}
      </div>
    </li>
  );
}

/* ------------------------------------------------------------------ */

function SectionLabel({
  icon: Icon,
  tone,
  children,
}: {
  icon: typeof Target;
  tone: 'sky' | 'amber' | 'steel';
  children: React.ReactNode;
}) {
  const toneCls =
    tone === 'sky'
      ? 'text-sky-700'
      : tone === 'amber'
      ? 'text-amber-700'
      : 'text-steel-600';
  return (
    <div
      className={cn(
        'flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider',
        toneCls,
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {children}
    </div>
  );
}
