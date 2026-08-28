import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react';
import { Coins, Database, FileUp, Loader2, Play } from 'lucide-react';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatView } from '@/components/chat/ChatView';
import { Button } from '@/components/ui/Button';
import { useSession } from '@/context/SessionContext';
import * as api from '@/services/api';
import type { DatasetEntry } from '@/types';
import { cn } from '@/utils/cn';
import {
  DEFAULT_RAW_MATERIAL_REQUIREMENTS,
  FORECAST_MODELS,
  RAW_MATERIAL_CATEGORIES,
  RAW_MATERIAL_EXTERNAL_VARIABLES,
  RAW_MATERIAL_PRICE_FORECAST_AGENT,
  buildRawMaterialPriceForecastQuery,
  type ForecastModel,
  type RawMaterialForecastGranularity,
  type RawMaterialPriceForecastTask,
} from './config';

const MAX_FILE_MB = 100;

export function RawMaterialPriceForecastApp() {
  const { items, streaming, sendQuery, sendAgentTask, stop } = useSession();
  const [datasets, setDatasets] = useState<DatasetEntry[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [datasetError, setDatasetError] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState('');
  const [upload, setUpload] = useState<File | null>(null);
  const [started, setStarted] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [task, setTask] = useState<RawMaterialPriceForecastTask>({
    model: 'sundial',
    granularity: '月度',
    horizon: 6,
    materialCategories: [],
    externalVariables: [],
    additionalRequirements: DEFAULT_RAW_MATERIAL_REQUIREMENTS,
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

  const toggleValue = (field: 'materialCategories' | 'externalVariables', value: string) => {
    setTask((current) => ({
      ...current,
      [field]: current[field].includes(value)
        ? current[field].filter((item) => item !== value)
        : [...current[field], value],
    }));
  };

  const handleUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    event.target.value = '';
    setFormError(null);
    if (!file) return;
    const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (!RAW_MATERIAL_PRICE_FORECAST_AGENT.supportedExtensions.includes(
      extension as (typeof RAW_MATERIAL_PRICE_FORECAST_AGENT.supportedExtensions)[number],
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
    if (!Number.isInteger(task.horizon) || task.horizon < 1 || task.horizon > 90) {
      setFormError('预测周期必须是 1 到 90 之间的整数');
      return;
    }
    setFormError(null);
    setStarted(true);
    void sendAgentTask(
      RAW_MATERIAL_PRICE_FORECAST_AGENT.id,
      {
        model: task.model,
        granularity: task.granularity,
        horizon: task.horizon,
        material_categories: task.materialCategories,
        external_variables: task.externalVariables,
        additional_requirements: task.additionalRequirements,
      },
      buildRawMaterialPriceForecastQuery(task),
      upload,
      selectedFileName || undefined,
    );
  };

  if (started || items.length > 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="border-b border-steel-200/70 bg-orange-50/50 px-4 py-2.5 sm:px-6">
          <div className="mx-auto flex max-w-3xl items-center gap-2 text-xs text-steel-600">
            <Coins className="h-4 w-4 text-orange-700" />
            <span className="font-medium text-steel-800">{RAW_MATERIAL_PRICE_FORECAST_AGENT.name}</span>
            <span className="text-steel-300">·</span>
            <span>结构化任务已提交，可继续追问或补充要求</span>
          </div>
        </div>
        <ChatView showEmptyState={false} />
        <ChatInput streaming={streaming} onSubmit={(text, file) => void sendQuery(text, file)} onStop={stop} />
      </div>
    );
  }

  const horizonUnit = { 日度: '天', 周度: '周', 月度: '个月' }[task.granularity];

  return (
    <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
      <div className="mx-auto w-full max-w-4xl pb-8">
        <div className="mb-5 rounded-2xl border border-orange-200/80 bg-gradient-to-br from-orange-50 to-white p-5">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-orange-100 text-orange-700"><Coins className="h-5 w-5" /></span>
            <div><h2 className="text-base font-semibold text-steel-900">配置原材料价格预测任务</h2><p className="mt-1 text-xs leading-5 text-steel-500">选择历史价格数据、原材料品类和供需影响因素，预测未来价格走势。</p></div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <FormSection number="1" title="选择预测数据" description="选择包含日期、原材料品类和历史价格的数据文件。">
            <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
              <select value={selectedFileName} onChange={(event) => { setSelectedFileName(event.target.value); if (event.target.value) setUpload(null); }} disabled={datasetsLoading} className={fieldClassName}>
                <option value="">{datasetsLoading ? '正在加载我的数据…' : '从我的数据中选择'}</option>
                {datasets.map((dataset) => <option key={dataset.file_name} value={dataset.file_name}>{dataset.name}</option>)}
              </select>
              <label className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border border-steel-200 bg-white px-4 text-xs font-medium text-steel-700 transition-colors hover:border-orange-400 hover:bg-orange-50"><FileUp className="h-4 w-4" />上传新数据<input type="file" accept=".csv,.xlsx,.parquet" onChange={handleUpload} className="hidden" /></label>
            </div>
            {(upload || selectedDataset) && <div className="mt-3 flex items-center gap-2 rounded-lg bg-steel-50 px-3 py-2 text-xs text-steel-600"><Database className="h-3.5 w-3.5 text-orange-700" /><span className="font-medium">{upload?.name ?? selectedDataset?.name}</span></div>}
            {datasetError && <p className="mt-2 text-xs text-rose-600">{datasetError}</p>}
          </FormSection>

          <FormSection number="2" title="设置预测参数" description="预测目标固定为锂电原材料价格。">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="预测模型"><select value={task.model} onChange={(event) => setTask({ ...task, model: event.target.value as ForecastModel })} className={fieldClassName}>{FORECAST_MODELS.map((model) => <option key={model}>{model}</option>)}</select></Field>
              <Field label="时间粒度"><select value={task.granularity} onChange={(event) => setTask({ ...task, granularity: event.target.value as RawMaterialForecastGranularity })} className={fieldClassName}><option>日度</option><option>周度</option><option>月度</option></select></Field>
              <Field label={`预测周期（${horizonUnit}）`}><input type="number" min={1} max={90} step={1} value={task.horizon} onChange={(event) => setTask({ ...task, horizon: Number(event.target.value) })} className={fieldClassName} /></Field>
            </div>
          </FormSection>

          <FormSection number="3" title="选择分析维度" description="可多选；不选择原材料品类时默认分析数据中的全部原材料。">
            <ChoiceGroup label="原材料品类" values={RAW_MATERIAL_CATEGORIES} selected={task.materialCategories} onToggle={(value) => toggleValue('materialCategories', value)} />
            <ChoiceGroup label="供需与市场影响因素" values={RAW_MATERIAL_EXTERNAL_VARIABLES} selected={task.externalVariables} onToggle={(value) => toggleValue('externalVariables', value)} />
          </FormSection>

          <FormSection number="4" title="补充要求（可选）" description="可调整输出内容、价格口径或重点关注的风险因素。">
            <textarea value={task.additionalRequirements} onChange={(event) => setTask({ ...task, additionalRequirements: event.target.value })} rows={3} maxLength={500} className="w-full resize-y rounded-xl border border-steel-200 bg-white px-3 py-2.5 text-xs leading-5 text-steel-700 outline-none focus:border-orange-400 focus:ring-2 focus:ring-orange-100" />
          </FormSection>

          <div className="flex items-center justify-between gap-4 pt-1"><p className="text-xs text-rose-600">{formError}</p><Button type="submit" disabled={streaming} className="min-w-32">{streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}开始预测</Button></div>
        </form>
      </div>
    </div>
  );
}

const fieldClassName = 'h-10 w-full rounded-xl border border-steel-200 bg-white px-3 text-xs text-steel-700 outline-none focus:border-orange-400 focus:ring-2 focus:ring-orange-100';

function FormSection({ number, title, description, children }: { number: string; title: string; description: string; children: ReactNode }) {
  return <section className="rounded-2xl border border-steel-200/80 bg-white p-5 shadow-sm"><div className="mb-4 flex items-start gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-orange-100 text-[11px] font-bold text-orange-700">{number}</span><div><h3 className="text-sm font-semibold text-steel-800">{title}</h3><p className="mt-0.5 text-[11px] text-steel-500">{description}</p></div></div>{children}</section>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-steel-600">{label}</span>{children}</label>;
}

function ChoiceGroup({ label, values, selected, onToggle }: { label: string; values: string[]; selected: string[]; onToggle: (value: string) => void }) {
  return <div className="mb-4 last:mb-0"><p className="mb-2 text-[11px] font-medium text-steel-600">{label}</p><div className="flex flex-wrap gap-2">{values.map((value) => <button key={value} type="button" onClick={() => onToggle(value)} className={cn('rounded-full border px-3 py-1.5 text-xs transition-colors', selected.includes(value) ? 'border-orange-400 bg-orange-50 font-medium text-orange-800' : 'border-steel-200 bg-white text-steel-600 hover:border-orange-300')}>{value}</button>)}</div></div>;
}
