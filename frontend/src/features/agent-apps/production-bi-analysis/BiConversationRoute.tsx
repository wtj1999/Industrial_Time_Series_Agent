import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, MessageSquarePlus, RefreshCw } from 'lucide-react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { BI_HISTORY_EVENT, biConversationUrl, readBiSession, type BiConversation, type BiHistoryEvent } from '@/services/biSessions';
import { ProductionBiAnalysisApp, type BiTurn } from './ProductionBiAnalysisApp';
import { PRODUCTION_BI_AGENTS, type ProductionBiAgent } from './config';
import { NG_DEFECT_AGENT } from '../ng-defect-analysis/config';
import { CONTROL_PLAN_AGENT } from '../control-plan-analysis/config';
import { ControlPlanAnalysisApp, type ControlPlanTurn } from '../control-plan-analysis/ControlPlanAnalysisApp';
import { genSessionId } from '@/utils/format';

const agents: readonly ProductionBiAgent[] = [...PRODUCTION_BI_AGENTS, NG_DEFECT_AGENT, CONTROL_PLAN_AGENT];
const uuid = genSessionId;
const factories: Record<string, string> = { 'jinzhai-phase-2': '金寨二期', 'jinzhai-phase-3': '金寨三期', 'wuhu-phase-1': '芜湖一期' };

export function BiConversationRoute() {
  const { agentId = '', biSessionId } = useParams();
  const location = useLocation(), navigate = useNavigate();
  const [record, setRecord] = useState<BiConversation>();
  const [seed, setSeed] = useState<string>(uuid);
  const [loading, setLoading] = useState(!!biSessionId);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const ownedHistory = useRef<string>();
  const lastNewLocation = useRef<string>();
  const agent = agents.find(item => item.id === agentId);
  const query = new URLSearchParams(location.search);
  const factory = record?.factory_id ?? query.get('factory') ?? undefined;
  const tenant = record?.tenant_id ?? query.get('tenant') ?? undefined;
  const invalid = !agent ? '该BI智能体不存在' : factory && !factories[factory] ? '不支持的基地' : tenant && !/^\d{1,64}$/.test(tenant) ? '无效的租户' : '';

  useEffect(() => {
    if (!biSessionId) {
      if (lastNewLocation.current !== location.key) {
        lastNewLocation.current = location.key; ownedHistory.current = undefined;
        setSeed(uuid()); setRecord(undefined); setError(''); setLoading(false);
      }
      return;
    }
    if (ownedHistory.current === biSessionId && !reload) return;
    const controller = new AbortController();
    setLoading(true); setError(''); setRecord(undefined);
    readBiSession(biSessionId, controller.signal).then(snapshot => {
      if (controller.signal.aborted) return;
      if (snapshot.app_id !== agentId) throw new Error('这条历史对话不属于当前智能体');
      setRecord(snapshot); setSeed(snapshot.session_id); ownedHistory.current = snapshot.session_id;
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '读取历史对话失败'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [agentId, biSessionId, location.key, reload]);

  useEffect(() => {
    const remember = (event: Event) => {
      const { sessionId, threadId } = (event as CustomEvent<BiHistoryEvent>).detail ?? {};
      if (!sessionId || threadId !== (record?.thread_id ?? seed) || sessionId === ownedHistory.current) return;
      ownedHistory.current = sessionId;
      navigate(biConversationUrl(agentId, sessionId, factory, tenant), { replace: true });
    };
    window.addEventListener(BI_HISTORY_EVENT, remember);
    return () => window.removeEventListener(BI_HISTORY_EVENT, remember);
  }, [agentId, record?.thread_id, seed, factory, tenant, navigate]);

  const productionTurns = (record?.turns ?? []).filter(turn => ['message','confirm','result','deep_confirm','deep_progress','deep_result'].includes(turn.kind)) as BiTurn[];
  const controlTurns = (record?.turns ?? []).filter(turn => ['message','confirm','result'].includes(turn.kind)) as ControlPlanTurn[];
  return <div className="flex min-h-0 flex-1 flex-col">
    <div className="flex flex-wrap items-center gap-2 border-b border-steel-200 bg-white px-4 py-3 sm:px-6">
      <button type="button" aria-label="返回智能体列表" title="返回智能体列表" className="rounded-lg p-2 text-steel-600 hover:bg-steel-50" onClick={() => navigate('/agents')}><ArrowLeft size={16}/></button>
      <div className="min-w-0 flex-1"><h1 className="text-sm font-semibold text-steel-800">{agent?.name ?? 'BI历史对话'}</h1>{factory && factories[factory] ? <p className="text-xs text-steel-500">{factories[factory]}</p> : null}</div>
      {biSessionId ? <button type="button" aria-label="刷新当前BI对话" title="刷新当前BI对话" className="rounded-lg p-2 text-steel-500 hover:bg-steel-50" disabled={loading} onClick={() => { ownedHistory.current = undefined; setReload(value => value + 1); }}><RefreshCw size={15}/></button> : null}
      <button type="button" aria-label="新建BI对话" title="新建BI对话" className="rounded-lg p-2 text-emerald-700 hover:bg-emerald-50" onClick={() => { setReload(0); navigate(biConversationUrl(agentId, undefined, factory, tenant), { state: { newBiConversation: true } }); }}><MessageSquarePlus size={17}/></button>
    </div>
    {loading || !error && (biSessionId ? ownedHistory.current !== biSessionId : lastNewLocation.current !== location.key) ? <p className="p-8 text-center text-sm text-steel-500">正在恢复历史对话…</p> : error || invalid ? <div role="alert" className="p-6 text-sm text-rose-700">{error || invalid}</div> : agent?.id === CONTROL_PLAN_AGENT.id
      ? <ControlPlanAnalysisApp key={seed} initialConversation={{ thread_id: record?.thread_id ?? seed, turns: controlTurns }} />
      : agent ? <ProductionBiAnalysisApp key={seed} agent={{ ...agent, ...(agent.id === NG_DEFECT_AGENT.id ? { ngFactoryId: factory ?? 'jinzhai-phase-3' } : tenant ? { tenantId: tenant } : {}) }}
          initialConversation={{ thread_id: record?.thread_id ?? seed, turns: productionTurns }} /> : null}
  </div>;
}
