import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react';
import { Database, FileUp, Flame, Loader2, Play } from 'lucide-react';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatView } from '@/components/chat/ChatView';
import { Button } from '@/components/ui/Button';
import { useSession } from '@/context/SessionContext';
import * as api from '@/services/api';
import type { DatasetEntry } from '@/types';
import { cn } from '@/utils/cn';
import {
  CONTAMINATION_OPTIONS,
  DEFAULT_WELDING_REQUIREMENTS,
  DETECTION_MODELS,
  WELDING_ANOMALY_TARGETS,
  WELDING_EQUIPMENT_ANOMALY_AGENT,
  buildWeldingAnomalyQuery,
  type DetectionModel,
  type WeldingAnomalyTask,
  usesWeldingWindow,
} from './config';

const MAX_FILE_MB = 100;
const fieldClass = 'h-10 w-full rounded-xl border border-steel-200 bg-white px-3 text-xs text-steel-700 outline-none focus:border-orange-400 focus:ring-2 focus:ring-orange-100';

export function WeldingEquipmentAnomalyDetectionApp() {
  const { items, streaming, sendQuery, sendAgentTask, stop } = useSession();
  const [datasets, setDatasets] = useState<DatasetEntry[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [datasetError, setDatasetError] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState('');
  const [upload, setUpload] = useState<File | null>(null);
  const [started, setStarted] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [task, setTask] = useState<WeldingAnomalyTask>({
    anomalyTargets: ['激光功率'],
    model: '自动推荐',
    contamination: 0.01,
    windowSize: 30,
    returnTopN: 20,
    randomState: 42,
    additionalRequirements: DEFAULT_WELDING_REQUIREMENTS,
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

  const toggleTarget = (target: string) => {
    setTask((current) => ({
      ...current,
      anomalyTargets: current.anomalyTargets.includes(target)
        ? current.anomalyTargets.filter((item) => item !== target)
        : [...current.anomalyTargets, target],
    }));
  };

  const handleUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    event.target.value = '';
    setFormError(null);
    if (!file) return;
    if (file.name.split('.').pop()?.toLowerCase() !== 'csv') {
      setFormError('焊接设备异常检测当前仅支持 CSV 文件');
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
    if (task.anomalyTargets.length === 0) {
      setFormError('请至少选择一个异常检测目标');
      return;
    }
    if (usesWeldingWindow(task) && (!Number.isInteger(task.windowSize) || task.windowSize < 2 || task.windowSize > 5000)) {
      setFormError('检测窗口必须是 2 到 5000 之间的整数');
      return;
    }
    if (!Number.isInteger(task.returnTopN) || task.returnTopN < 1 || task.returnTopN > 100) {
      setFormError('返回异常数量必须是 1 到 100 之间的整数');
      return;
    }
    if (!Number.isInteger(task.randomState)) {
      setFormError('随机种子必须是整数');
      return;
    }
    setFormError(null);
    setStarted(true);
    void sendAgentTask(
      WELDING_EQUIPMENT_ANOMALY_AGENT.id,
      {
        anomaly_targets: task.anomalyTargets,
        model: task.model,
        contamination: task.contamination,
        window_size: task.windowSize,
        return_top_n: task.returnTopN,
        random_state: task.randomState,
        additional_requirements: task.additionalRequirements,
      },
      buildWeldingAnomalyQuery(task),
      upload,
      selectedFileName || undefined,
    );
  };

  if (started || items.length > 0) {
    return <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-steel-200/70 bg-orange-50/50 px-4 py-2.5 sm:px-6"><div className="mx-auto flex max-w-3xl items-center gap-2 text-xs text-steel-600"><Flame className="h-4 w-4 text-orange-700" /><span className="font-medium text-steel-800">{WELDING_EQUIPMENT_ANOMALY_AGENT.name}</span><span className="text-steel-300">·</span><span>结构化任务已提交，可继续追问或补充要求</span></div></div>
      <ChatView showEmptyState={false} />
      <ChatInput streaming={streaming} onSubmit={(text, file) => void sendQuery(text, file)} onStop={stop} />
    </div>;
  }

  return <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6"><div className="mx-auto w-full max-w-4xl pb-8">
    <div className="mb-5 rounded-2xl border border-orange-200/80 bg-gradient-to-br from-orange-50 to-white p-5"><div className="flex items-start gap-3"><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-orange-100 text-orange-700"><Flame className="h-5 w-5" /></span><div><h2 className="text-base font-semibold text-steel-900">配置焊接设备异常检测任务</h2><p className="mt-1 text-xs leading-5 text-steel-500">联合监测能量、运动、光路和熔池状态，识别参数漂移与潜在焊接缺陷。</p></div></div></div>
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormSection number="1" title="选择检测数据" description="选择包含时间列及焊接设备关键过程特征的 CSV 文件。">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]"><select value={selectedFileName} onChange={(event) => { setSelectedFileName(event.target.value); if (event.target.value) setUpload(null); }} disabled={datasetsLoading} className={fieldClass}><option value="">{datasetsLoading ? '正在加载我的数据…' : '从我的数据中选择'}</option>{datasets.filter((dataset) => dataset.extension === 'csv').map((dataset) => <option key={dataset.file_name} value={dataset.file_name}>{dataset.name}</option>)}</select><label className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border border-steel-200 bg-white px-4 text-xs font-medium text-steel-700 transition-colors hover:border-orange-400 hover:bg-orange-50"><FileUp className="h-4 w-4" />上传新数据<input type="file" accept=".csv" onChange={handleUpload} className="hidden" /></label></div>
        {(upload || selectedDataset) && <div className="mt-3 flex items-center gap-2 rounded-lg bg-steel-50 px-3 py-2 text-xs text-steel-600"><Database className="h-3.5 w-3.5 text-orange-700" /><span className="font-medium">{upload?.name ?? selectedDataset?.name}</span></div>}
        {datasetError && <p className="mt-2 text-xs text-rose-600">{datasetError}</p>}
      </FormSection>

      <FormSection number="2" title="选择异常检测目标" description="框选数据中需要重点监测的焊接设备关键特征，可同时选择多个目标。">
        <div className="flex flex-wrap gap-2">{WELDING_ANOMALY_TARGETS.map((target) => <button key={target} type="button" onClick={() => toggleTarget(target)} className={cn('rounded-xl border px-3 py-2 text-xs transition-all', task.anomalyTargets.includes(target) ? 'border-orange-400 bg-orange-50 font-medium text-orange-800 shadow-sm' : 'border-steel-200 bg-white text-steel-600 hover:border-orange-300 hover:bg-orange-50/40')}>{target}</button>)}</div>
        <p className="mt-3 text-[11px] leading-5 text-steel-500">已选择 {task.anomalyTargets.length} 项；系统将检测单特征异常以及所选特征之间的协同异常。</p>
      </FormSection>

      <FormSection number="3" title="设置检测模型与参数" description="单目标自动推荐突变检测模型，多目标自动推荐多变量异常检测模型。">
        <div className={cn('grid gap-3', usesWeldingWindow(task) ? 'sm:grid-cols-4' : 'sm:grid-cols-3')}>
          <Field label="异常检测模型"><select value={task.model} onChange={(event) => setTask({ ...task, model: event.target.value as DetectionModel })} className={fieldClass}>{DETECTION_MODELS.map((item) => <option key={item}>{item}</option>)}</select></Field>
          <Field label="预期异常比例"><select value={task.contamination} onChange={(event) => setTask({ ...task, contamination: Number(event.target.value) })} className={fieldClass}>{CONTAMINATION_OPTIONS.map((value) => <option key={value} value={value}>{value * 100}%</option>)}</select></Field>
          {usesWeldingWindow(task) && <Field label="检测窗口（采样点）"><input type="number" min={2} max={5000} value={task.windowSize} onChange={(event) => setTask({ ...task, windowSize: Number(event.target.value) })} className={fieldClass} /></Field>}
          <Field label="返回异常数量"><input type="number" min={1} max={100} value={task.returnTopN} onChange={(event) => setTask({ ...task, returnTopN: Number(event.target.value) })} className={fieldClass} /></Field>
        </div>
        <details className="mt-3 rounded-xl bg-steel-50 px-3 py-2"><summary className="cursor-pointer text-[11px] font-medium text-steel-600">高级设置</summary><div className="mt-3 max-w-xs"><Field label="随机种子"><input type="number" value={task.randomState} onChange={(event) => setTask({ ...task, randomState: Number(event.target.value) })} className={fieldClass} /></Field></div></details>
      </FormSection>

      <FormSection number="4" title="补充要求（可选）" description="可指定关注时段、焊接工位、产品型号、缺陷类型或异常解释口径。"><textarea value={task.additionalRequirements} onChange={(event) => setTask({ ...task, additionalRequirements: event.target.value })} rows={4} maxLength={500} className="w-full resize-y rounded-xl border border-steel-200 bg-white px-3 py-2.5 text-xs leading-5 text-steel-700 outline-none focus:border-orange-400 focus:ring-2 focus:ring-orange-100" /></FormSection>
      <div className="flex items-center justify-between gap-4 pt-1"><p className="text-xs text-rose-600">{formError}</p><Button type="submit" disabled={streaming} className="min-w-32">{streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}开始检测</Button></div>
    </form>
  </div></div>;
}

function FormSection({ number, title, description, children }: { number: string; title: string; description: string; children: ReactNode }) {
  return <section className="rounded-2xl border border-steel-200/80 bg-white p-5 shadow-sm"><div className="mb-4 flex items-start gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-orange-100 text-[11px] font-bold text-orange-700">{number}</span><div><h3 className="text-sm font-semibold text-steel-800">{title}</h3><p className="mt-0.5 text-[11px] text-steel-500">{description}</p></div></div>{children}</section>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-steel-600">{label}</span>{children}</label>;
}
