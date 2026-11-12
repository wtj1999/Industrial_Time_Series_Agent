import { useEffect, useRef, useState } from 'react';
import { ClipboardList, Filter, Check, ChevronLeft, ChevronRight } from 'lucide-react';
import { ChatInput } from '@/components/chat/ChatInput';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { Button } from '@/components/ui/Button';
import { BiResultCard } from '../production-bi-analysis/BiResultCard';
import { API_BASE } from '@/services/api';
import { genId } from '@/utils/format';
import { getAuthHeaders, handleUnauthorized } from '@/utils/user';
import type { Message } from '@/types';
import type { BiSuccessResponse } from '../production-bi-analysis/types';
import { CONTROL_PLAN_AGENT } from './config';

type Selection = { option_ids: string[] };
interface Confirmation {
  selection_mode: 'multiple';
  options: Array<{ id: string; label: string; detail?: string; selected?: boolean }>;
  preselect?: string[];
  shown_count?: number;
  page_size?: number;
  total_count?: number;
}
interface Response {
  status: 'need_confirm' | 'success'; session_id: string; thread_id: string;
  content_type: 'options' | 'table'; empty?: boolean;
  message?: string; confirm?: Confirmation; columns?: Record<string, string>; page_size?: number;
  data?: BiSuccessResponse['data']; row_count?: number; analysis?: BiSuccessResponse['analysis'];
}
type Turn = { id: string; kind: 'message'; message: Message }
  | { id: string; kind: 'confirm'; response: Response; submitted: boolean; expired: boolean }
  | { id: string; kind: 'result'; response: Response };

export function ControlPlanAnalysisApp() {
  const [sessionId] = useState(() => genId());
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);
  const analysisQuery = useRef('');
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight }); }, [turns, loading]);
  async function run(payload: { query: string } | { confirm: Selection }) {
    if (request.current) return false;
    const controller = new AbortController(); request.current = controller; setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/bi/control-plan/query`, {
        method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ session_id: sessionId, analysis_query: analysisQuery.current, ...payload }),
      });
      handleUnauthorized(response);
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : body?.error ?? 'Control Plan 查询失败');
      if (body?.status === 'error' && body.content_type === 'text') throw new Error(body.message || 'Control Plan 查询失败');
      if (!body || !['need_confirm', 'success'].includes(body.status) || body.content_type !== (body.status === 'need_confirm' ? 'options' : 'table') || (body.status === 'need_confirm' && !Array.isArray(body.confirm?.options))) throw new Error('Control Plan 服务响应格式不正确');
      if (controller.signal.aborted) return false;
      setTurns(current => [...current, body.status === 'need_confirm'
        ? { id: genId(), kind: 'confirm', response: body, submitted: false, expired: false }
        : { id: genId(), kind: 'result', response: body }]);
      return true;
    } catch (error) {
      if (!controller.signal.aborted) setTurns(current => [...current, { id: genId(), kind: 'message', message: { role: 'assistant', content: `查询未完成：${error instanceof Error ? error.message : '请稍后重试'}`, timestamp: new Date().toISOString() } }]);
      return false;
    } finally {
      if (request.current === controller) { request.current = null; setLoading(false); }
    }
  }
  function ask(query: string) {
    if (!query.trim() || request.current) return;
    analysisQuery.current = query.trim();
    setTurns(current => [...current.map(turn => turn.kind === 'confirm' && !turn.submitted ? { ...turn, expired: true } : turn), { id: genId(), kind: 'message', message: { role: 'user', content: query.trim(), timestamp: new Date().toISOString() } }]);
    void run({ query: query.trim() });
  }
  return <div className="flex min-h-0 flex-1 flex-col bg-gradient-to-b from-steel-50/50 to-white">
    <div ref={scroller} className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-10"><div className="mx-auto w-full max-w-3xl">
      {!turns.length && <div className="mb-8 mt-8 flex flex-col items-center text-center">
        <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-700 text-white shadow-soft"><ClipboardList size={32}/></span>
        <h2 className="mt-5 text-xl font-semibold text-steel-900">Control Plan 工艺参数查询</h2><p className="mt-2 max-w-lg text-sm leading-6 text-steel-500">{CONTROL_PLAN_AGENT.description}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">{CONTROL_PLAN_AGENT.suggestions.map(query => <button type="button" key={query} onClick={() => ask(query)} className="rounded-full border border-steel-200 bg-white px-3.5 py-1.5 text-xs text-steel-700 hover:border-emerald-300 hover:bg-emerald-50">{query}</button>)}</div>
      </div>}
      <div className="space-y-5">{turns.map(turn => turn.kind === 'message' ? <MessageBubble key={turn.id} message={turn.message}/>
        : turn.kind === 'result' ? <BiResultCard key={turn.id} result={{ ...turn.response, status: 'success', data: turn.response.empty ? [] : turn.response.data }} columnLabels={turn.response.columns} pageSize={turn.response.page_size ?? 10} message={turn.response.message} nullDisplay=""/>
        : <ConfirmationCard key={turn.id} response={turn.response} disabled={loading || turn.submitted || turn.expired} submitted={turn.submitted} expired={turn.expired} onSubmit={async confirm => {
          if (await run({ confirm })) setTurns(current => current.map(item => item.id === turn.id && item.kind === 'confirm' ? { ...item, submitted: true } : item));
        }}/>)}</div>
      {loading && <MessageBubble streaming message={{ role: 'assistant', content: '', timestamp: new Date().toISOString() }}/>}
    </div></div>
    <ChatInput streaming={loading} allowFileUpload={false} placeholder="输入基地、工序或工艺参数问题" footerText="Control Plan 工艺查询与分析 · 按提示确认路线和参数" busyText="Control Plan 查询与分析中" onSubmit={ask} onStop={() => { request.current?.abort(); request.current = null; setLoading(false); }}/>
  </div>;
}

function ConfirmationCard({ response, disabled, submitted, expired, onSubmit }: { response: Response; disabled: boolean; submitted: boolean; expired: boolean; onSubmit: (selection: Selection) => void }) {
  const confirm = response.confirm!;
  const [inputName] = useState(() => genId());
  const [initialSelected] = useState<string[]>(() => {
    const initial = confirm.preselect?.length ? confirm.preselect : confirm.options.filter(option => option.selected).map(option => option.id);
    const valid = new Set(confirm.options.map(option => option.id));
    return [...new Set(initial.filter(id => valid.has(id)))];
  });
  const [selected, setSelected] = useState<string[]>(initialSelected);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = Math.max(1, Math.min(100, confirm.page_size ?? 10));
  const defaults = new Set(initialSelected);
  const options = [
    ...confirm.options.filter(option => defaults.has(option.id)),
    ...confirm.options.filter(option => !defaults.has(option.id)),
  ].filter(option => `${option.label} ${option.detail ?? ''}`.toLowerCase().includes(search.toLowerCase()));
  const pageCount = Math.max(1, Math.ceil(options.length / pageSize));
  const visible = options.slice(page * pageSize, (page + 1) * pageSize);
  return <section className="overflow-hidden rounded-2xl border border-brand-200 bg-white shadow-soft">
    <div className="flex items-center gap-3 border-b border-steel-200 bg-gradient-to-r from-brand-50/70 to-transparent px-4 py-3"><span className="rounded-lg bg-brand-600 p-2 text-white"><Filter size={16}/></span><h3 className="text-sm font-semibold text-steel-900">选择查询范围</h3><span className="ml-auto text-[10px] text-steel-500">{expired ? '已失效' : submitted ? '已提交' : '等待你的输入'}</span></div>
    <div className="space-y-4 p-4 sm:p-5"><p className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2.5 text-xs leading-5 text-steel-700">{response.message || '可选择多项，不勾选时查询当前层全部候选。'}</p>
      <p className="text-[11px] leading-5 text-steel-500">展示 {confirm.options.length} / {confirm.total_count ?? confirm.options.length} 个候选 · 请确认勾选范围，可自行调整{(confirm.total_count ?? 0) > confirm.options.length ? '；未勾选时包含尚未展示的候选' : ''}</p>
      <div className="flex items-center gap-3"><input aria-label="搜索路线或参数" value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} disabled={disabled} placeholder="搜索名称、基地、路线或工序" className="h-9 min-w-0 flex-1 rounded-lg border border-steel-200 px-3 text-xs"/><button type="button" disabled={disabled} className="shrink-0 text-xs text-brand-700 disabled:opacity-50" onClick={() => setSelected(selected.length === confirm.options.length ? [] : confirm.options.map(option => option.id))}>{selected.length && selected.length === confirm.options.length ? '取消全选' : '全选展示项'}</button></div>
      <div className="grid gap-2 sm:grid-cols-2">{visible.map(option => <label key={option.id} className={`flex min-w-0 items-start gap-2 rounded-xl border px-3 py-3 text-xs ${selected.includes(option.id) ? 'border-brand-300 bg-brand-50' : 'border-steel-200 bg-white'} ${disabled ? 'opacity-60' : 'cursor-pointer'}`}>
        <input type="checkbox" name={`selection-${inputName}`} checked={selected.includes(option.id)} disabled={disabled} onChange={() => setSelected(current => current.includes(option.id) ? current.filter(id => id !== option.id) : [...current, option.id])}/>
        <span className="min-w-0 break-words"><span className="block font-medium text-steel-800">{option.label}</span>{option.detail && <span className="mt-1 block text-[11px] text-steel-500">{option.detail}</span>}</span>
      </label>)}</div>
      {!visible.length && <p className="text-xs text-steel-500">暂无匹配选项</p>}
      {pageCount > 1 && <div className="flex items-center justify-end gap-2 text-xs text-steel-500"><button type="button" aria-label="上一页选项" disabled={page === 0} onClick={() => setPage(p => p - 1)}><ChevronLeft size={16}/></button>{page + 1} / {pageCount}<button type="button" aria-label="下一页选项" disabled={page + 1 === pageCount} onClick={() => setPage(p => p + 1)}><ChevronRight size={16}/></button></div>}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-steel-100 pt-3"><p className="text-[11px] text-steel-500">{selected.length ? `已选择 ${selected.length} 项` : '未勾选，默认查询当前层全部候选'}</p><Button disabled={disabled} onClick={() => onSubmit({ option_ids: selected })}><Check size={15}/>{selected.length ? '确认所选项' : '查询当前层全部'}</Button></div>
    </div>
  </section>;
}
