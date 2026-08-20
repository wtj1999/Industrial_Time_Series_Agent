import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react';
import { Activity, Database, FileUp, Loader2, Play } from 'lucide-react';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatView } from '@/components/chat/ChatView';
import { Button } from '@/components/ui/Button';
import { useSession } from '@/context/SessionContext';
import * as api from '@/services/api';
import type { DatasetEntry } from '@/types';
import { cn } from '@/utils/cn';
import {
  ANALYSIS_MODES,
  COATING_AREAL_DENSITY_AGENT,
  COATING_SCOPES,
  DEFAULT_COATING_REQUIREMENTS,
  buildCoatingAnalysisQuery,
  type CoatingAnalysisMode,
  type CoatingAnalysisTask,
} from './config';

const MAX_FILE_MB = 100;
const fieldClass = 'h-10 w-full rounded-xl border border-steel-200 bg-white px-3 text-xs text-steel-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100';

export function CoatingArealDensityAnalysisApp() {
  const { items, streaming, sendQuery, sendAgentTask, stop } = useSession();
  const [datasets, setDatasets] = useState<DatasetEntry[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [datasetError, setDatasetError] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState('');
  const [upload, setUpload] = useState<File | null>(null);
  const [started, setStarted] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [task, setTask] = useState<CoatingAnalysisTask>({
    analysisMode: '稳定性评估',
    coatingScopes: ['A面分区', 'A+B双面分区'],
    window: 30,
    subgroupSize: 1,
    lsl: null,
    target: null,
    usl: null,
    additionalRequirements: DEFAULT_COATING_REQUIREMENTS,
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
    if (!COATING_AREAL_DENSITY_AGENT.supportedExtensions.includes(
      extension as (typeof COATING_AREAL_DENSITY_AGENT.supportedExtensions)[number],
    )) {
      setFormError('涂布面密度分析当前仅支持 CSV 文件');
      return;
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      setFormError(`文件大小不能超过 ${MAX_FILE_MB}MB`);
      return;
    }
    setUpload(file);
    setSelectedFileName('');
  };

  const toggleScope = (scope: string) => {
    setTask((current) => ({
      ...current,
      coatingScopes: current.coatingScopes.includes(scope)
        ? current.coatingScopes.filter((item) => item !== scope)
        : [...current.coatingScopes, scope],
    }));
  };

  const parseOptionalNumber = (value: string): number | null => value === '' ? null : Number(value);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!upload && !selectedFileName) {
      setFormError('请从“我的数据”选择文件，或上传一个新文件');
      return;
    }
    if (!Number.isInteger(task.window) || task.window < 2 || task.window > 5000) {
      setFormError('滚动窗口必须是 2 到 5000 之间的整数');
      return;
    }
    if (!Number.isInteger(task.subgroupSize) || task.subgroupSize < 1 || task.subgroupSize > 1000) {
      setFormError('控制图子组大小必须是 1 到 1000 之间的整数');
      return;
    }
    if (task.analysisMode === '过程能力' && task.lsl === null && task.usl === null) {
      setFormError('过程能力分析必须填写规格下限或规格上限');
      return;
    }
    if (task.lsl !== null && task.usl !== null && task.lsl >= task.usl) {
      setFormError('规格下限必须小于规格上限');
      return;
    }
    setFormError(null);
    setStarted(true);
    void sendAgentTask(
      COATING_AREAL_DENSITY_AGENT.id,
      {
        analysis_mode: task.analysisMode,
        coating_scopes: task.coatingScopes,
        window: task.window,
        subgroup_size: task.subgroupSize,
        lsl: task.lsl,
        target: task.target,
        usl: task.usl,
        additional_requirements: task.additionalRequirements,
      },
      buildCoatingAnalysisQuery(task),
      upload,
      selectedFileName || undefined,
    );
  };

  if (started || items.length > 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="border-b border-steel-200/70 bg-cyan-50/50 px-4 py-2.5 sm:px-6">
          <div className="mx-auto flex max-w-3xl items-center gap-2 text-xs text-steel-600">
            <Activity className="h-4 w-4 text-cyan-700" />
            <span className="font-medium text-steel-800">{COATING_AREAL_DENSITY_AGENT.name}</span>
            <span className="text-steel-300">·</span><span>结构化任务已提交，可继续追问或补充要求</span>
          </div>
        </div>
        <ChatView showEmptyState={false} />
        <ChatInput streaming={streaming} onSubmit={(text, file) => void sendQuery(text, file)} onStop={stop} />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
      <div className="mx-auto w-full max-w-4xl pb-8">
        <div className="mb-5 rounded-2xl border border-cyan-200/80 bg-gradient-to-br from-cyan-50 to-white p-5">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-cyan-100 text-cyan-700"><Activity className="h-5 w-5" /></span>
            <div><h2 className="text-base font-semibold text-steel-900">配置面密度分析任务</h2><p className="mt-1 text-xs leading-5 text-steel-500">面向涂布横向分区时序数据，选择一个主分析目标；综合诊断最多执行三个互补分析。</p></div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <FormSection number="1" title="选择分析数据" description="选择包含时间列及涂布面密度分区数据的文件。">
            <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
              <select value={selectedFileName} onChange={(event) => { setSelectedFileName(event.target.value); if (event.target.value) setUpload(null); }} disabled={datasetsLoading} className={fieldClass}>
                <option value="">{datasetsLoading ? '正在加载我的数据…' : '从我的数据中选择'}</option>
                {datasets.filter((dataset) => dataset.extension === 'csv').map((dataset) => <option key={dataset.file_name} value={dataset.file_name}>{dataset.name}</option>)}
              </select>
              <label className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border border-steel-200 bg-white px-4 text-xs font-medium text-steel-700 transition-colors hover:border-cyan-400 hover:bg-cyan-50"><FileUp className="h-4 w-4" />上传新数据<input type="file" accept=".csv" onChange={handleUpload} className="hidden" /></label>
            </div>
            {(upload || selectedDataset) && <div className="mt-3 flex items-center gap-2 rounded-lg bg-steel-50 px-3 py-2 text-xs text-steel-600"><Database className="h-3.5 w-3.5 text-cyan-700" /><span className="font-medium">{upload?.name ?? selectedDataset?.name}</span></div>}
            {datasetError && <p className="mt-2 text-xs text-rose-600">{datasetError}</p>}
          </FormSection>

          <FormSection number="2" title="设置主分析目标" description="默认只执行最直接的一个分析工具，避免重复计算。">
            <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-steel-600">分析类型</span><select value={task.analysisMode} onChange={(event) => setTask({ ...task, analysisMode: event.target.value as CoatingAnalysisMode })} className={fieldClass}>{ANALYSIS_MODES.map((mode) => <option key={mode}>{mode}</option>)}</select></label>
            <div className="mt-4"><p className="mb-2 text-[11px] font-medium text-steel-600">面密度范围</p><div className="flex flex-wrap gap-2">{COATING_SCOPES.map((scope) => <button key={scope} type="button" onClick={() => toggleScope(scope)} className={cn('rounded-full border px-3 py-1.5 text-xs transition-colors', task.coatingScopes.includes(scope) ? 'border-cyan-400 bg-cyan-50 font-medium text-cyan-800' : 'border-steel-200 bg-white text-steel-600 hover:border-cyan-300')}>{scope}</button>)}</div></div>
          </FormSection>

          <FormSection number="3" title="设置分析参数" description="窗口按采样点计数；规格参数主要用于过程能力分析。">
            <div className="grid gap-3 sm:grid-cols-2"><Field label="滚动窗口（采样点）"><input type="number" min={2} max={5000} value={task.window} onChange={(event) => setTask({ ...task, window: Number(event.target.value) })} className={fieldClass} /></Field><Field label="控制图子组大小"><input type="number" min={1} max={1000} value={task.subgroupSize} onChange={(event) => setTask({ ...task, subgroupSize: Number(event.target.value) })} className={fieldClass} /></Field></div>
            <div className="mt-3 grid gap-3 sm:grid-cols-3"><Field label="规格下限 LSL"><input type="number" step="any" value={task.lsl ?? ''} onChange={(event) => setTask({ ...task, lsl: parseOptionalNumber(event.target.value) })} placeholder="可选" className={fieldClass} /></Field><Field label="目标值"><input type="number" step="any" value={task.target ?? ''} onChange={(event) => setTask({ ...task, target: parseOptionalNumber(event.target.value) })} placeholder="可选" className={fieldClass} /></Field><Field label="规格上限 USL"><input type="number" step="any" value={task.usl ?? ''} onChange={(event) => setTask({ ...task, usl: parseOptionalNumber(event.target.value) })} placeholder="可选" className={fieldClass} /></Field></div>
          </FormSection>

          <FormSection number="4" title="补充要求（可选）" description="可指定关注分区、时段、设备事件或结果口径。"><textarea value={task.additionalRequirements} onChange={(event) => setTask({ ...task, additionalRequirements: event.target.value })} rows={3} maxLength={500} className="w-full resize-y rounded-xl border border-steel-200 bg-white px-3 py-2.5 text-xs leading-5 text-steel-700 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100" /></FormSection>

          <div className="flex items-center justify-between gap-4 pt-1"><p className="text-xs text-rose-600">{formError}</p><Button type="submit" disabled={streaming} className="min-w-32">{streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}开始分析</Button></div>
        </form>
      </div>
    </div>
  );
}

function FormSection({ number, title, description, children }: { number: string; title: string; description: string; children: React.ReactNode }) {
  return <section className="rounded-2xl border border-steel-200/80 bg-white p-5 shadow-sm"><div className="mb-4 flex items-start gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan-100 text-[11px] font-bold text-cyan-700">{number}</span><div><h3 className="text-sm font-semibold text-steel-800">{title}</h3><p className="mt-0.5 text-[11px] text-steel-500">{description}</p></div></div>{children}</section>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-steel-600">{label}</span>{children}</label>;
}
