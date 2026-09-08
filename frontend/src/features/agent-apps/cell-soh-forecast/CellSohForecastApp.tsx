import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react';
import { BatteryMedium, Database, FileUp, Loader2, Play } from 'lucide-react';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatView } from '@/components/chat/ChatView';
import { Button } from '@/components/ui/Button';
import { useSession } from '@/context/SessionContext';
import * as api from '@/services/api';
import type { DatasetEntry } from '@/types';
import { cn } from '@/utils/cn';
import {
  CAPACITY_BASELINES,
  CELL_SOH_FORECAST_AGENT,
  DEFAULT_CELL_SOH_REQUIREMENTS,
  FORECAST_MODELS,
  SOH_THRESHOLDS,
  buildCellSohForecastQuery,
  type CapacityBaseline,
  type CapacityUnit,
  type CellSohForecastTask,
  type ForecastModel,
} from './config';

const MAX_FILE_MB = 100;
const fieldClassName = 'h-10 w-full rounded-xl border border-steel-200 bg-white px-3 text-xs text-steel-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100';

export function CellSohForecastApp() {
  const { items, streaming, sendQuery, sendAgentTask, stop } = useSession();
  const [datasets, setDatasets] = useState<DatasetEntry[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [datasetError, setDatasetError] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState('');
  const [upload, setUpload] = useState<File | null>(null);
  const [started, setStarted] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [task, setTask] = useState<CellSohForecastTask>({
    model: 'sundial',
    sohThreshold: 80,
    capacityBaseline: '自动识别',
    nominalCapacity: null,
    capacityUnit: 'Ah',
    additionalRequirements: DEFAULT_CELL_SOH_REQUIREMENTS,
  });

  useEffect(() => {
    let alive = true;
    api.listDatasets()
      .then((response) => { if (alive) setDatasets(response.datasets ?? []); })
      .catch((error: unknown) => {
        if (alive) setDatasetError(error instanceof Error ? error.message : '获取数据列表失败');
      })
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
    setFormError(null);
    if (!file) return;
    const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (!CELL_SOH_FORECAST_AGENT.supportedExtensions.includes(
      extension as (typeof CELL_SOH_FORECAST_AGENT.supportedExtensions)[number],
    )) {
      setFormError('仅支持 CSV、XLSX 和 Parquet 文件');
      return;
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      setFormError(`文件大小不能超过 ${MAX_FILE_MB}MB`);
      return;
    }
    setUpload(file);
    setSelectedFileName('');
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!upload && !selectedFileName) {
      setFormError('请从“我的数据”选择文件，或上传一个新文件');
      return;
    }
    if (task.capacityBaseline === '额定容量'
      && (task.nominalCapacity == null || !Number.isFinite(task.nominalCapacity) || task.nominalCapacity <= 0)) {
      setFormError('请输入大于 0 的额定容量');
      return;
    }
    setFormError(null);
    setStarted(true);
    void sendAgentTask(
      CELL_SOH_FORECAST_AGENT.id,
      {
        model: task.model,
        soh_threshold: task.sohThreshold,
        capacity_baseline: task.capacityBaseline,
        nominal_capacity: task.capacityBaseline === '额定容量' ? task.nominalCapacity : null,
        capacity_unit: task.capacityUnit,
        additional_requirements: task.additionalRequirements,
      },
      buildCellSohForecastQuery(task),
      upload,
      selectedFileName || undefined,
    );
  };

  if (started || items.length > 0) {
    return <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-steel-200/70 bg-teal-50/50 px-4 py-2.5 sm:px-6"><div className="mx-auto flex max-w-3xl items-center gap-2 text-xs text-steel-600"><BatteryMedium className="h-4 w-4 text-teal-700" /><span className="font-medium text-steel-800">{CELL_SOH_FORECAST_AGENT.name}</span><span className="text-steel-300">·</span><span>结构化任务已提交，可继续追问或补充要求</span></div></div>
      <ChatView showEmptyState={false} />
      <ChatInput streaming={streaming} onSubmit={(text, file) => void sendQuery(text, file)} onStop={stop} />
    </div>;
  }

  return <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6"><div className="mx-auto w-full max-w-4xl pb-8">
    <div className="mb-5 rounded-2xl border border-teal-200/80 bg-gradient-to-br from-teal-50 to-white p-5"><div className="flex items-start gap-3"><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-teal-100 text-teal-700"><BatteryMedium className="h-5 w-5" /></span><div><h2 className="text-base font-semibold text-steel-900">配置电芯SOH预测任务</h2><p className="mt-1 text-xs leading-5 text-steel-500">上传容量衰减序列并选择目标SOH，系统将自行推断需要预测的循环步数。</p></div></div></div>
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormSection number="1" title="选择容量衰减数据" description="选择包含循环圈数和容量或SOH序列的数据文件。">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]"><select value={selectedFileName} onChange={(event) => { setSelectedFileName(event.target.value); if (event.target.value) setUpload(null); }} disabled={datasetsLoading} className={fieldClassName}><option value="">{datasetsLoading ? '正在加载我的数据…' : '从我的数据中选择'}</option>{datasets.map((dataset) => <option key={dataset.file_name} value={dataset.file_name}>{dataset.name}</option>)}</select><label className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border border-steel-200 bg-white px-4 text-xs font-medium text-steel-700 transition-colors hover:border-teal-400 hover:bg-teal-50"><FileUp className="h-4 w-4" />上传新数据<input type="file" accept=".csv,.xlsx,.parquet" onChange={handleUpload} className="hidden" /></label></div>
        {(upload || selectedDataset) && <div className="mt-3 flex items-center gap-2 rounded-lg bg-steel-50 px-3 py-2 text-xs text-steel-600"><Database className="h-3.5 w-3.5 text-teal-700" /><span className="font-medium">{upload?.name ?? selectedDataset?.name}</span></div>}
        {datasetError && <p className="mt-2 text-xs text-rose-600">{datasetError}</p>}
      </FormSection>

      <FormSection number="2" title="设置预测方式" description="无需设置时间粒度和预测周期，系统会根据衰减趋势推断输出步长。">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="预测模型"><select value={task.model} onChange={(event) => setTask({ ...task, model: event.target.value as ForecastModel })} className={fieldClassName}>{FORECAST_MODELS.map((model) => <option key={model}>{model}</option>)}</select></Field>
          <Field label="SOH计算基准"><select value={task.capacityBaseline} onChange={(event) => setTask({ ...task, capacityBaseline: event.target.value as CapacityBaseline })} className={fieldClassName}>{CAPACITY_BASELINES.map((baseline) => <option key={baseline}>{baseline}</option>)}</select></Field>
        </div>
        {task.capacityBaseline === '额定容量' && <div className="mt-3 grid gap-3 sm:max-w-md sm:grid-cols-[1fr_110px]">
          <Field label="额定容量"><input type="number" min="0" step="any" value={task.nominalCapacity ?? ''} onChange={(event) => setTask({ ...task, nominalCapacity: event.target.value === '' ? null : Number(event.target.value) })} placeholder="例如 3.2" className={fieldClassName} /></Field>
          <Field label="容量单位"><select value={task.capacityUnit} onChange={(event) => setTask({ ...task, capacityUnit: event.target.value as CapacityUnit })} className={fieldClassName}><option>Ah</option><option>mAh</option></select></Field>
        </div>}
      </FormSection>

      <FormSection number="3" title="选择目标SOH" description="单选一个目标阈值，系统将预测首次达到该SOH所需的循环圈数。">
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">{SOH_THRESHOLDS.map((threshold) => <button key={threshold} type="button" aria-pressed={task.sohThreshold === threshold} onClick={() => setTask({ ...task, sohThreshold: threshold })} className={cn('relative rounded-xl border px-2 py-3 text-center transition-all', task.sohThreshold === threshold ? 'border-teal-400 bg-teal-50 text-teal-800 shadow-sm' : 'border-steel-200 bg-white text-steel-500 hover:border-teal-300')}><span className="text-base font-semibold tabular-nums">{threshold}%</span><span className="mt-0.5 block text-[9px]">目标阈值</span></button>)}</div>
        <p className="mt-3 text-[11px] leading-5 text-steel-500">默认使用全部有效历史序列，并根据所选阈值自动估算预测步长。</p>
      </FormSection>

      <FormSection number="4" title="补充要求（可选）" description="可指定电芯批次、测试工况、容量口径或结果输出重点。"><textarea value={task.additionalRequirements} onChange={(event) => setTask({ ...task, additionalRequirements: event.target.value })} rows={4} maxLength={500} className="w-full resize-y rounded-xl border border-steel-200 bg-white px-3 py-2.5 text-xs leading-5 text-steel-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100" /></FormSection>
      <div className="flex items-center justify-between gap-4 pt-1"><p className="text-xs text-rose-600">{formError}</p><Button type="submit" disabled={streaming} className="min-w-32">{streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}开始预测</Button></div>
    </form>
  </div></div>;
}

function FormSection({ number, title, description, children }: { number: string; title: string; description: string; children: ReactNode }) {
  return <section className="rounded-2xl border border-steel-200/80 bg-white p-5 shadow-sm"><div className="mb-4 flex items-start gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-teal-100 text-[11px] font-bold text-teal-700">{number}</span><div><h3 className="text-sm font-semibold text-steel-800">{title}</h3><p className="mt-0.5 text-[11px] text-steel-500">{description}</p></div></div>{children}</section>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-steel-600">{label}</span>{children}</label>;
}
