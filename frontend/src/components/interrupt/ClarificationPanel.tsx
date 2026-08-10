import { useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, Columns3, Info, Plus, Save, Trash2 } from 'lucide-react';
import type {
  ClarificationInterruptData,
  ClarificationResume,
  ColumnMapping,
  MappingStatus,
} from '@/types';
import { useSession } from '@/context/SessionContext';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { cn } from '@/utils/cn';
import { mappingStatusMeta } from '@/utils/format';

interface Props {
  interrupt: ClarificationInterruptData & { type?: string };
}

export function ClarificationPanel({ interrupt }: Props) {
  const { resumeQuery, streaming } = useSession();

  const initialTargets = interrupt.target_columns ?? [];
  const initialFeatures = interrupt.feature_columns ?? [];
  const candidates = interrupt.candidate_columns ?? [];

  const [targets, setTargets] = useState<ColumnMapping[]>(() => clone(initialTargets));
  const [features, setFeatures] = useState<ColumnMapping[]>(() => clone(initialFeatures));
  const [tab, setTab] = useState<'targets' | 'features'>(
    initialTargets.length > 0 ? 'targets' : 'features',
  );

  // 新增的空名字行不参与计数 / 提交时会被过滤掉
  const validTargets = targets.filter((m) => m.semantic_name.trim() !== '');
  const validFeatures = features.filter((m) => m.semantic_name.trim() !== '');
  const total = validTargets.length + validFeatures.length;
  const confirmedCount = useMemo(
    () =>
      validTargets.filter((m) => m.status === 'mapped').length +
      validFeatures.filter((m) => m.status === 'mapped').length,
    [validTargets, validFeatures],
  );
  const allConfirmed = total > 0 && confirmedCount === total;
  const hasEmptyName =
    targets.some((m) => m.semantic_name.trim() === '') ||
    features.some((m) => m.semantic_name.trim() === '');

  const updateMapping = (group: 'targets' | 'features', idx: number, patch: Partial<ColumnMapping>) => {
    const setter = group === 'targets' ? setTargets : setFeatures;
    setter((prev) =>
      prev.map((m, i) =>
        i === idx
          ? {
              ...m,
              ...patch,
              status: patch.status ?? deriveStatus(m, patch),
            }
          : m,
      ),
    );
  };

  const addMapping = (group: 'targets' | 'features') => {
    const setter = group === 'targets' ? setTargets : setFeatures;
    setter((prev) => [
      ...prev,
      { semantic_name: '', csv_column: null, status: 'unmapped' },
    ]);
    setTab(group);
  };

  const deleteMapping = (group: 'targets' | 'features', idx: number) => {
    const setter = group === 'targets' ? setTargets : setFeatures;
    setter((prev) => prev.filter((_, i) => i !== idx));
  };

  const markAllConfirmed = () => {
    setTargets((prev) => prev.map((m) => ({ ...m, status: 'mapped' as MappingStatus })));
    setFeatures((prev) => prev.map((m) => ({ ...m, status: 'mapped' as MappingStatus })));
  };

  const handleSubmit = () => {
    const payload: ClarificationResume = {
      target_columns: validTargets,
      feature_columns: validFeatures,
    };
    void resumeQuery(payload);
  };

  // 目标列必填且必须映射到 csv_column：目标列没有条目、或任意一条 csv_column 为空，都不能提交
  const hasUnmappedTarget = validTargets.some((m) => !m.csv_column);
  const submitDisabled =
    streaming || validTargets.length === 0 || hasUnmappedTarget || hasEmptyName;

  return (
    <div className="space-y-4">
      {/* Intro */}
      <div className="flex items-start gap-2 rounded-xl bg-sky-50 border border-sky-200 px-3 py-2.5">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-sky-600" />
        <div className="text-xs text-sky-800 leading-5">
          <p>
            {interrupt.message ??
              '智能体已根据你的需求与数据画像，推断出业务语义字段与 CSV 列的映射关系。'}
          </p>
          <p className="mt-0.5 text-sky-700/80">
            请逐项确认或调整下拉框；可以新增字段映射，也可以删除不需要的项。
          </p>
        </div>
      </div>

      {/* Progress */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-steel-600">确认进度</span>
          <Badge tone={allConfirmed ? 'success' : 'warning'} dot>
            {confirmedCount}/{total}
          </Badge>
        </div>
        <button
          onClick={markAllConfirmed}
          disabled={streaming || total === 0}
          className="text-[11px] text-brand-700 hover:underline disabled:opacity-50"
        >
          全部标记为已确认
        </button>
      </div>

      {/* Tabs */}
      {(targets.length > 0 || features.length > 0) && (
        <div className="flex items-center gap-1 rounded-lg bg-steel-100 p-1">
          <TabButton active={tab === 'targets'} onClick={() => setTab('targets')}>
            目标列 · {validTargets.length}
          </TabButton>
          <TabButton active={tab === 'features'} onClick={() => setTab('features')}>
            特征列 · {validFeatures.length}
          </TabButton>
        </div>
      )}

      {/* Target columns */}
      {(tab === 'targets' || features.length === 0) && (
        <ColumnMappingGroup
          title="目标列（需要预测 / 检测的核心变量）"
          icon={Columns3}
          mappings={targets}
          candidates={candidates}
          onChange={(i, patch) => updateMapping('targets', i, patch)}
          onAdd={() => addMapping('targets')}
          onDelete={(i) => deleteMapping('targets', i)}
        />
      )}

      {/* Feature columns */}
      {(tab === 'features' || targets.length === 0) && (
        <ColumnMappingGroup
          title="特征列（输入维度 / 上下文变量）"
          icon={Columns3}
          mappings={features}
          candidates={candidates}
          onChange={(i, patch) => updateMapping('features', i, patch)}
          onAdd={() => addMapping('features')}
          onDelete={(i) => deleteMapping('features', i)}
        />
      )}

      {/* Actions */}
      <div className="flex items-center justify-between gap-3 border-t border-steel-100 pt-3">
        <p className="text-[11px] text-steel-500">
          {hasEmptyName
            ? '请补全新增行的业务字段名，或将其删除。'
            : validTargets.length === 0
              ? '目标列至少需要一条映射才能提交。'
              : hasUnmappedTarget
                ? '目标列存在未映射的字段，请为每个目标列选择对应的 CSV 列。'
                : '确认无误后点击「提交确认」，智能体将执行分析任务。'}
        </p>
        <div className="flex gap-2">
          <Button
            onClick={handleSubmit}
            disabled={submitDisabled}
            loading={streaming}
          >
            {allConfirmed ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
            提交确认
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function ColumnMappingGroup({
  title,
  icon: Icon,
  mappings,
  candidates,
  onChange,
  onAdd,
  onDelete,
}: {
  title: string;
  icon: typeof Columns3;
  mappings: ColumnMapping[];
  candidates: string[];
  onChange: (idx: number, patch: Partial<ColumnMapping>) => void;
  onAdd: () => void;
  onDelete: (idx: number) => void;
}) {
  return (
    <section className="space-y-2">
      <h4 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-steel-500">
        <Icon className="h-3.5 w-3.5" />
        {title}
      </h4>
      <div className="space-y-2">
        {mappings.map((m, i) => (
          <ColumnMappingRow
            key={i}
            mapping={m}
            candidates={candidates}
            onChange={(patch) => onChange(i, patch)}
            onDelete={() => onDelete(i)}
          />
        ))}
      </div>
      <button
        type="button"
        onClick={onAdd}
        className="w-full rounded-xl border border-dashed border-steel-300 px-3 py-2 text-xs text-steel-500 hover:border-brand-400 hover:bg-brand-50/30 hover:text-brand-700 transition-colors flex items-center justify-center gap-1.5"
      >
        <Plus className="h-3.5 w-3.5" />
        添加字段映射
      </button>
    </section>
  );
}

function ColumnMappingRow({
  mapping,
  candidates,
  onChange,
  onDelete,
}: {
  mapping: ColumnMapping;
  candidates: string[];
  onChange: (patch: Partial<ColumnMapping>) => void;
  onDelete: () => void;
}) {
  const meta = mappingStatusMeta(mapping.status);

  // Provide the union of current value + candidates without duplicates
  const options = Array.from(new Set([...candidates, mapping.csv_column].filter(Boolean) as string[]));
  const isEmpty = !mapping.semantic_name.trim();

  return (
    <div
      className={cn(
        'flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 rounded-xl border bg-white px-3 py-2.5',
        isEmpty ? 'border-amber-300 bg-amber-50/30' : 'border-steel-200',
      )}
    >
      <div className="flex items-center gap-2 sm:w-56 shrink-0">
        <span className={cn('h-2 w-2 rounded-full shrink-0', meta.dot)} />
        <input
          type="text"
          value={mapping.semantic_name}
          placeholder="业务字段名（如：温度）"
          autoFocus={isEmpty}
          onChange={(e) => onChange({ semantic_name: e.target.value })}
          className={cn(
            'flex-1 min-w-0 rounded-md px-2 py-1 text-sm text-steel-800 placeholder:text-steel-400 focus:outline-none focus:ring-2 focus:ring-brand-100',
            isEmpty
              ? 'border border-steel-200 bg-white focus:border-brand-400'
              : 'border border-transparent bg-transparent font-medium hover:border-steel-200 focus:border-brand-400 focus:bg-white',
          )}
        />
      </div>

      <div className="hidden sm:flex items-center text-steel-300">
        <ArrowRight className="h-3.5 w-3.5" />
      </div>

      <div className="flex-1">
        <select
          value={mapping.csv_column ?? ''}
          onChange={(e) => onChange({ csv_column: e.target.value || null })}
          className={cn(
            'block w-full rounded-lg border bg-white px-2.5 py-1.5 text-sm text-steel-800',
            'border-steel-200 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100',
          )}
        >
          <option value="">— 未映射 —</option>
          {options.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-1">
        <StatusButton
          label={mappingStatusMeta('mapped').label}
          active={mapping.status === 'mapped'}
          tone="success"
          onClick={() => onChange({ status: 'mapped' })}
        />
        <StatusButton
          label={mappingStatusMeta('uncertain').label}
          active={mapping.status === 'uncertain'}
          tone="warning"
          onClick={() => onChange({ status: 'uncertain' })}
        />
        <StatusButton
          label={mappingStatusMeta('unmapped').label}
          active={mapping.status === 'unmapped'}
          tone="danger"
          onClick={() => onChange({ status: 'unmapped', csv_column: null })}
        />
        <button
          type="button"
          onClick={onDelete}
          aria-label="删除该映射"
          title="删除该映射"
          className="ml-1 rounded-md border border-steel-200 bg-white p-1.5 text-steel-500 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600 transition-colors"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function StatusButton({
  label,
  active,
  tone,
  onClick,
}: {
  label: string;
  active: boolean;
  tone: 'success' | 'warning' | 'danger';
  onClick: () => void;
}) {
  const meta = mappingStatusMeta(
    tone === 'success' ? 'mapped' : tone === 'warning' ? 'uncertain' : 'unmapped',
  );
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-md border px-2 py-1 text-[11px] font-medium transition-all',
        active
          ? `${meta.cls} shadow-sm`
          : 'border-steel-200 bg-white text-steel-500 hover:bg-steel-50',
      )}
    >
      {label}
    </button>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
        active
          ? 'bg-white text-steel-900 shadow-sm'
          : 'text-steel-500 hover:text-steel-700',
      )}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */

function clone<T>(arr: T[]): T[] {
  return arr.map((x) => ({ ...(x as object) }) as unknown as T);
}

function deriveStatus(m: ColumnMapping, patch: Partial<ColumnMapping>): MappingStatus {
  const next: ColumnMapping = { ...m, ...patch };
  if (next.status !== 'mapped' && next.csv_column) return 'mapped';
  if (next.status === 'mapped' && !next.csv_column) return 'unmapped';
  return next.status;
}
