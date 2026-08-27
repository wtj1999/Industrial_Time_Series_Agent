import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react';
import { BatteryWarning, Database, FileUp, Loader2, Play } from 'lucide-react';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatView } from '@/components/chat/ChatView';
import { Button } from '@/components/ui/Button';
import { useSession } from '@/context/SessionContext';
import * as api from '@/services/api';
import type { DatasetEntry } from '@/types';
import { cn } from '@/utils/cn';
import {
  CELL_CAPACITY_ROOT_CAUSE_AGENT,
  DEFAULT_ROOT_CAUSE_REQUIREMENTS,
  FEATURE_SCOPES,
  buildCellCapacityRootCauseQuery,
  type CellCapacityRootCauseTask,
} from './config';

const MAX_FILE_MB = 100;
const fieldClass = 'h-10 w-full rounded-xl border border-steel-200 bg-white px-3 text-xs text-steel-700 outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100';

export function CellCapacityRootCauseApp() {
  const { items, streaming, sendQuery, sendAgentTask, stop } = useSession();
  const [datasets, setDatasets] = useState<DatasetEntry[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [datasetError, setDatasetError] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState('');
  const [upload, setUpload] = useState<File | null>(null);
  const [started, setStarted] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [task, setTask] = useState<CellCapacityRootCauseTask>({
    featureScopes: ['全部可用工艺参数'],
    trainRatio: 0.7,
    validationRatio: 0.1,
    testRatio: 0.2,
    splitStrategy: 'chronological',
    iterations: 500,
    learningRate: 0.05,
    depth: 6,
    additionalRequirements: DEFAULT_ROOT_CAUSE_REQUIREMENTS,
  });

  useEffect(() => {
    let alive = true;
    api.listDatasets()
      .then((response) => { if (alive) setDatasets(response.datasets ?? []); })
      .catch((error: unknown) => { if (alive) setDatasetError(error instanceof Error ? error.message : '获取数据列表失败'); })
      .finally(() => { if (alive) setDatasetsLoading(false); });
    return () => { alive = false; };
  }, []);

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.file_name === selectedFileName),
    [datasets, selectedFileName],
  );

  const handleUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    event.target.value = '';
    if (!file) return;
    if (file.name.split('.').pop()?.toLowerCase() !== 'csv') {
      setFormError('分容容量根因分析当前仅支持 CSV 文件');
      return;
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      setFormError(`文件大小不能超过 ${MAX_FILE_MB}MB`);
      return;
    }
    setFormError(null);
    setUpload(file);
    setSelectedFileName('');
  };

  const toggleScope = (scope: string) => {
    setTask((current) => {
      const exclusive = scope === '全部可用工艺参数';
      if (exclusive) return { ...current, featureScopes: [scope] };
      const withoutAll = current.featureScopes.filter((item) => item !== '全部可用工艺参数');
      const next = withoutAll.includes(scope)
        ? withoutAll.filter((item) => item !== scope)
        : [...withoutAll, scope];
      return { ...current, featureScopes: next };
    });
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!upload && !selectedFileName) return setFormError('请从“我的数据”选择文件，或上传一个新文件');
    if (task.featureScopes.length === 0) return setFormError('请至少选择一个候选特征范围');
    const ratioSum = task.trainRatio + task.validationRatio + task.testRatio;
    if (Math.abs(ratioSum - 1) > 1e-8 || [task.trainRatio, task.validationRatio, task.testRatio].some((value) => value <= 0)) {
      return setFormError('训练集、验证集和测试集比例必须均大于 0，且总和为 1');
    }
    setFormError(null);
    setStarted(true);
    void sendAgentTask(
      CELL_CAPACITY_ROOT_CAUSE_AGENT.id,
      {
        feature_scopes: task.featureScopes,
        train_ratio: task.trainRatio,
        validation_ratio: task.validationRatio,
        test_ratio: task.testRatio,
        split_strategy: task.splitStrategy,
        iterations: task.iterations,
        learning_rate: task.learningRate,
        depth: task.depth,
        additional_requirements: task.additionalRequirements,
      },
      buildCellCapacityRootCauseQuery(task),
      upload,
      selectedFileName || undefined,
    );
  };

  if (started || items.length > 0) return <div className="flex min-h-0 flex-1 flex-col">
    <div className="border-b border-steel-200/70 bg-rose-50/50 px-4 py-2.5 sm:px-6">
      <div className="mx-auto flex max-w-3xl items-center gap-2 text-xs text-steel-600">
        <BatteryWarning className="h-4 w-4 text-rose-700" />
        <span className="font-medium text-steel-800">{CELL_CAPACITY_ROOT_CAUSE_AGENT.name}</span>
        <span className="text-steel-300">·</span><span>结构化任务已提交，可继续追问或补充要求</span>
      </div>
    </div>
    <ChatView showEmptyState={false} />
    <ChatInput streaming={streaming} onSubmit={(text, file) => void sendQuery(text, file)} onStop={stop} />
  </div>;

  return <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
    <div className="mx-auto w-full max-w-4xl pb-8">
      <div className="mb-5 rounded-2xl border border-rose-200/80 bg-gradient-to-br from-rose-50 to-white p-5">
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-rose-100 text-rose-700"><BatteryWarning className="h-5 w-5" /></span>
          <div><h2 className="text-base font-semibold text-steel-900">配置容量偏低根因分析任务</h2><p className="mt-1 text-xs leading-5 text-steel-500">以分容容量为目标，通过树模型、特征重要性与 TreeSHAP 定位关键工艺参数。</p></div>
        </div>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormSection number="1" title="选择分析数据" description="选择同时包含分容容量与候选工艺参数的 CSV 文件。">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <select value={selectedFileName} onChange={(event) => { setSelectedFileName(event.target.value); if (event.target.value) setUpload(null); }} disabled={datasetsLoading} className={fieldClass}>
              <option value="">{datasetsLoading ? '正在加载我的数据…' : '从我的数据中选择'}</option>
              {datasets.filter((dataset) => dataset.extension === 'csv').map((dataset) => <option key={dataset.file_name} value={dataset.file_name}>{dataset.name}</option>)}
            </select>
            <label className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border border-steel-200 bg-white px-4 text-xs font-medium text-steel-700 hover:border-rose-400 hover:bg-rose-50"><FileUp className="h-4 w-4" />上传新数据<input type="file" accept=".csv" onChange={handleUpload} className="hidden" /></label>
          </div>
          {(upload || selectedDataset) && <div className="mt-3 flex items-center gap-2 rounded-lg bg-steel-50 px-3 py-2 text-xs text-steel-600"><Database className="h-3.5 w-3.5 text-rose-700" /><span className="font-medium">{upload?.name ?? selectedDataset?.name}</span></div>}
          {datasetError && <p className="mt-2 text-xs text-rose-600">{datasetError}</p>}
        </FormSection>

        <FormSection number="2" title="设置分析范围" description="预测目标固定为分容容量；选择参与根因建模的候选参数范围。">
          <div className="rounded-xl bg-steel-50 px-3 py-2.5 text-xs text-steel-700"><span className="text-steel-500">分析目标：</span><span className="font-medium">分容容量</span></div>
          <div className="mt-4 flex flex-wrap gap-2">{FEATURE_SCOPES.map((scope) => <button key={scope} type="button" onClick={() => toggleScope(scope)} className={cn('rounded-full border px-3 py-1.5 text-xs transition-colors', task.featureScopes.includes(scope) ? 'border-rose-400 bg-rose-50 font-medium text-rose-800' : 'border-steel-200 bg-white text-steel-600 hover:border-rose-300')}>{scope}</button>)}</div>
        </FormSection>

        <FormSection number="3" title="设置模型参数" description="默认按数据原始顺序进行 7:1:2 切分，适合具有时间顺序的生产数据。">
          <div className="grid gap-3 sm:grid-cols-4">
            <Field label="切分方式"><select value={task.splitStrategy} onChange={(event) => setTask({ ...task, splitStrategy: event.target.value as CellCapacityRootCauseTask['splitStrategy'] })} className={fieldClass}><option value="chronological">按原始顺序</option><option value="random">随机切分</option></select></Field>
            <NumberField label="训练集比例" value={task.trainRatio} min={0.05} max={0.9} step={0.05} onChange={(value) => setTask({ ...task, trainRatio: value })} />
            <NumberField label="验证集比例" value={task.validationRatio} min={0.05} max={0.9} step={0.05} onChange={(value) => setTask({ ...task, validationRatio: value })} />
            <NumberField label="测试集比例" value={task.testRatio} min={0.05} max={0.9} step={0.05} onChange={(value) => setTask({ ...task, testRatio: value })} />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <NumberField label="最大迭代次数" value={task.iterations} min={10} max={5000} onChange={(value) => setTask({ ...task, iterations: value })} />
            <NumberField label="学习率" value={task.learningRate} min={0.001} max={1} step={0.001} onChange={(value) => setTask({ ...task, learningRate: value })} />
            <NumberField label="树深度" value={task.depth} min={2} max={16} onChange={(value) => setTask({ ...task, depth: value })} />
          </div>
        </FormSection>

        <FormSection number="4" title="补充要求（可选）" description="可补充分容工步、设备编号、批次范围或需要重点验证的参数。"><textarea value={task.additionalRequirements} onChange={(event) => setTask({ ...task, additionalRequirements: event.target.value })} rows={3} maxLength={500} className="w-full resize-y rounded-xl border border-steel-200 bg-white px-3 py-2.5 text-xs leading-5 text-steel-700 outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100" /></FormSection>
        <div className="flex items-center justify-between gap-4 pt-1"><p className="text-xs text-rose-600">{formError}</p><Button type="submit" disabled={streaming} className="min-w-32">{streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}开始分析</Button></div>
      </form>
    </div>
  </div>;
}

function FormSection({ number, title, description, children }: { number: string; title: string; description: string; children: ReactNode }) {
  return <section className="rounded-2xl border border-steel-200/80 bg-white p-5 shadow-sm"><div className="mb-4 flex items-start gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-rose-100 text-[11px] font-bold text-rose-700">{number}</span><div><h3 className="text-sm font-semibold text-steel-800">{title}</h3><p className="mt-0.5 text-[11px] text-steel-500">{description}</p></div></div>{children}</section>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-steel-600">{label}</span>{children}</label>;
}

function NumberField({ label, value, min, max, step = 1, onChange }: { label: string; value: number; min: number; max: number; step?: number; onChange: (value: number) => void }) {
  return <Field label={label}><input type="number" value={value} min={min} max={max} step={step} onChange={(event) => onChange(Number(event.target.value))} className={fieldClass} /></Field>;
}
