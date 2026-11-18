import { useEffect, useRef, useState } from 'react';
import { DatabaseZap, Sparkles } from 'lucide-react';
import { ChatInput } from '@/components/chat/ChatInput';
import { MessageBubble } from '@/components/chat/MessageBubble';
import type { Message } from '@/types';
import { recommendNgFields, analyzeNgFields } from '../ng-defect-analysis/deepApi';
import type { DeepPlan, DeepProgress, DeepResult } from '../ng-defect-analysis/deepTypes';
import { NgDeepFieldCard } from '../ng-defect-analysis/NgDeepFieldCard';
import { NgDeepResultCard } from '../ng-defect-analysis/NgDeepResultCard';
import { NgDeepProgressCard } from '../ng-defect-analysis/NgDeepProgressCard';
import { queryNgOptions, queryProductionBi } from './api';
import type { ProductionBiAgent } from './config';
import { BiResultCard } from './BiResultCard';
import { FieldConfirmationCard } from './FieldConfirmationCard';
import type {
  BiConfirmPayload,
  BiNeedConfirmResponse,
  BiResponse,
  BiSuccessResponse,
  BiQueryPayload,
} from './types';

type BiTurn =
  | { id: string; kind: 'message'; message: Message }
  | { id: string; kind: 'confirm'; confirm: BiConfirmPayload; threadId: string; submitted: boolean; expired?: boolean; analysisQuery: string }
  | { id: string; kind: 'result'; result: BiSuccessResponse }
  | { id: string; kind: 'deep_confirm'; plan: DeepPlan; submitted: boolean }
  | { id: string; kind: 'deep_progress'; progress: DeepProgress; history: DeepProgress[] }
  | { id: string; kind: 'deep_result'; result: DeepResult };

function newId(): string {
  return globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function ProductionBiAnalysisApp({ agent }: { agent: ProductionBiAgent }) {
  const [threadId, setThreadId] = useState(() => newId());
  const [turns, setTurns] = useState<BiTurn[]>([]);
  const [loading, setLoading] = useState(false);
  const [deepProgressId, setDeepProgressId] = useState<string | null>(null);
  const [injectedText, setInjectedText] = useState<string>();
  const [pendingDeep, setPendingDeep] = useState<{ sourceId: string; rowIndex: number; threadId: string; ngName: string }>();
  const abortRef = useRef<AbortController | null>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const scroller = scrollerRef.current;
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  }, [turns, loading]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const appendResponse = (response: BiResponse, analysisQuery: string) => {
    setThreadId(response.thread_id);
    if (response.status === 'need_confirm' && 'confirm' in response) {
      const confirmation = response as BiNeedConfirmResponse;
      setTurns((current) => [...current, {
        id: newId(),
        kind: 'confirm',
        confirm: confirmation.confirm,
        threadId: confirmation.thread_id,
        submitted: false,
        analysisQuery,
      }]);
      return;
    }
    if (response.status === 'success') {
      setTurns((current) => [...current, {
        id: newId(),
        kind: 'result',
        result: response as BiSuccessResponse,
      }]);
      return;
    }
    throw new Error(`生产 BI 服务返回了暂不支持的状态：${response.status}`);
  };

  const runRequest = async (payload: BiQueryPayload) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const response = await queryProductionBi({ ...payload, ...(agent.tenantId ? { tenant_id: agent.tenantId } : {}), ...(agent.analysisDomain ? { domain: agent.analysisDomain } : {}), ...(agent.ngFactoryId ? { factory_id: agent.ngFactoryId } : {}) }, controller.signal, agent.endpoint);
      if (controller.signal.aborted) return false;
      appendResponse(response, payload.analysis_query || payload.query);
      return true;
    } catch (error) {
      if (controller.signal.aborted || (error instanceof Error && error.name === 'AbortError')) return false;
      const message = error instanceof Error ? error.message : '生产 BI 查询失败';
      setTurns((current) => [...current, {
        id: newId(),
        kind: 'message',
        message: {
          role: 'assistant',
          content: `查询未完成：${message}`,
          timestamp: new Date().toISOString(),
        },
      }]);
      return false;
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setLoading(false);
      }
    }
  };

  const submitQuery = (query: string) => {
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    if (pendingDeep) {
      const context = pendingDeep;
      setPendingDeep(undefined);
      setTurns((current) => [...current, { id: newId(), kind: 'message', message: { role: 'user', content: trimmed, timestamp: new Date().toISOString() } }]);
      void runDeep(async (signal) => {
        const plan = await recommendNgFields({ source_id: context.sourceId, row_index: context.rowIndex, thread_id: context.threadId, ...(agent.ngFactoryId ? { factory_id: agent.ngFactoryId } : {}) }, signal);
        if (!signal.aborted) setTurns((current) => [...current, { id: newId(), kind: 'deep_confirm', plan, submitted: false }]);
      });
      return;
    }
    setTurns((current) => [...current.map((turn) => (
      turn.kind === 'confirm' && !turn.submitted ? { ...turn, expired: true } : turn
    )), {
      id: newId(),
      kind: 'message',
      message: { role: 'user', content: trimmed, timestamp: new Date().toISOString() },
    }]);
    void runRequest({ query: trimmed, thread_id: threadId });
  };

  const runDeep = async (action: (signal: AbortSignal) => Promise<void>) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      await action(controller.signal);
    } catch (error) {
      if (!controller.signal.aborted) setTurns((current) => [...current, { id: newId(), kind: 'message', message: { role: 'assistant', content: `深度分析未完成：${error instanceof Error ? error.message : '请重试'}`, timestamp: new Date().toISOString() } }]);
    } finally {
      if (abortRef.current === controller) { abortRef.current = null; setLoading(false); setDeepProgressId(null); }
    }
  };

  const submitDeepFields = (turnId: string, plan: DeepPlan, targetId: string, featureIds: string[]) => {
    if (loading) return;
    const progressId = newId();
    const initial: DeepProgress = { stage: 'preparing', message: '正在提交已确认字段，准备读取数据', sequence: 0, elapsed_seconds: 0 };
    setDeepProgressId(progressId);
    setTurns(current => [...current, { id: progressId, kind: 'deep_progress', progress: initial, history: [initial] }]);
    const update = (progress: DeepProgress) => setTurns(current => current.map(turn => turn.id === progressId && turn.kind === 'deep_progress'
      ? { ...turn, progress, history: turn.progress.sequence === progress.sequence ? turn.history : [...turn.history, progress].slice(-160) } : turn));
    const finish = (stage: 'completed' | 'failed', message: string) => setTurns(current => current.map(turn => {
      if (turn.id !== progressId || turn.kind !== 'deep_progress' || turn.progress.stage === stage) return turn;
      const progress: DeepProgress = { ...turn.progress, stage, message, sequence: turn.progress.sequence + 1 };
      return { ...turn, progress, history: [...turn.history, progress].slice(-160) };
    }));
    void runDeep(async (signal) => {
      try {
        const result = await analyzeNgFields({ thread_id: plan.thread_id, plan_id: plan.plan_id, target_id: targetId, feature_ids: featureIds, ...(agent.ngFactoryId ? { factory_id: agent.ngFactoryId } : {}) }, signal,
          progress => { if (!signal.aborted) update(progress); });
        if (signal.aborted) return;
        finish('completed', `取数与分析完成 · ${result.timing.total_seconds.toFixed(2)}秒`);
        setTurns((current) => [...current.map((turn) => turn.id === turnId && turn.kind === 'deep_confirm' ? { ...turn, submitted: true } : turn), { id: newId(), kind: 'deep_result', result }]);
      } catch (error) {
        if (!signal.aborted) finish('failed', error instanceof Error ? error.message : '取数与分析失败');
        throw error;
      }
    });
  };

  const submitConfirmation = async (
    turnId: string,
    confirmationThreadId: string,
    resume: Record<string, string[]>,
    confirmationId?: string,
    analysisQuery?: string,
  ) => {
    if (loading) return;
    const succeeded = await runRequest({ query: '', thread_id: confirmationThreadId, resume, confirmation_id: confirmationId, ...(agent.analysisDomain ? { analysis_query: analysisQuery } : {}) });
    if (succeeded) {
      setTurns((current) => current.map((turn) => (
        turn.id === turnId && turn.kind === 'confirm' ? { ...turn, submitted: true } : turn
      )));
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setTurns(current => current.map(turn => {
      if (turn.id !== deepProgressId || turn.kind !== 'deep_progress') return turn;
      const progress: DeepProgress = { ...turn.progress, stage: 'cancelled', message: '已停止接收取数进度', sequence: turn.progress.sequence + 1 };
      return { ...turn, progress, history: [...turn.history, progress].slice(-160) };
    }));
    setDeepProgressId(null);
    setLoading(false);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-gradient-to-b from-steel-50/50 to-white">
      <div ref={scrollerRef} className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-10">
        <div className="mx-auto w-full max-w-3xl">
          {turns.length === 0 && <EmptyBiState agent={agent} onPick={submitQuery} />}
          <div className="space-y-5">
            {turns.map((turn) => {
              if (turn.kind === 'message') {
                return <MessageBubble key={turn.id} message={turn.message} />;
              }
              if (turn.kind === 'confirm') {
                return (
                  <FieldConfirmationCard
                    key={turn.id}
                    confirm={turn.confirm}
                    disabled={loading}
                    submitted={turn.submitted}
                    expired={turn.expired}
                    loadOptions={turn.confirm.confirmation_id ? (field, search, offset, signal) => queryNgOptions({
                      thread_id: turn.threadId, confirmation_id: turn.confirm.confirmation_id!, field, search, offset,
                      ...(agent.ngFactoryId ? { factory_id: agent.ngFactoryId } : {}),
                    }, signal) : undefined}
                    onSubmit={(resume) => void submitConfirmation(turn.id, turn.threadId, resume, turn.confirm.confirmation_id, turn.analysisQuery)}
                  />
                );
              }
              if (turn.kind === 'deep_confirm') return <NgDeepFieldCard key={turn.id} plan={turn.plan} submitted={turn.submitted} disabled={loading} onSubmit={(targetId, featureIds) => submitDeepFields(turn.id, turn.plan, targetId, featureIds)} />;
              if (turn.kind === 'deep_result') return <NgDeepResultCard key={turn.id} result={turn.result} />;
              if (turn.kind === 'deep_progress') return <NgDeepProgressCard key={turn.id} progress={turn.progress} history={turn.history} />;
              return <BiResultCard key={turn.id} result={turn.result} deepDisabled={loading} onDeepAnalyze={turn.result.chart?.type === 'ng_bar' && turn.result.source_id ? (rowIndex) => {
                const row = turn.result.chart!.rows[rowIndex];
                if (!row) return;
                setPendingDeep({ sourceId: turn.result.source_id!, rowIndex, threadId: turn.result.thread_id, ngName: row.ng_name });
                setInjectedText(`针对当前${row.ng_name}进行深度分析`);
              } : undefined} />;
            })}
            {loading && !deepProgressId && (
              <MessageBubble
                streaming
                message={{ role: 'assistant', content: '', timestamp: new Date().toISOString() }}
              />
            )}
          </div>
        </div>
      </div>
      {pendingDeep && <div className="px-4 pb-2 sm:px-6 lg:px-10">
        <div aria-label="已选深度分析类型" className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          <span className="min-w-0">已选 {pendingDeep.ngName}，提交后解析目标和上游数值特征。</span>
          <button type="button" onClick={() => setPendingDeep(undefined)} className="shrink-0 underline">取消深度分析</button>
        </div>
      </div>}
      <ChatInput
        injectedText={injectedText}
        onConsumeInjected={() => setInjectedText(undefined)}
        streaming={loading}
        allowFileUpload={false}
        placeholder={`输入${agent.category}分析问题，回车发送，Shift+Enter 换行`}
        footerText={agent.footerText ?? '连接生产 BI 服务 · 如筛选条件不明确，将由你确认后继续查询'}
        busyText={`${agent.category} BI 查询中`}
        onSubmit={(text) => submitQuery(text)}
        onStop={stop}
      />
    </div>
  );
}

function EmptyBiState({ agent, onPick }: { agent: ProductionBiAgent; onPick: (query: string) => void }) {
  const Icon = agent.icon;
  return (
    <div className="mb-8 mt-8 flex flex-col items-center text-center animate-fade-in">
      <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-700 text-white shadow-soft">
        <Icon className="h-8 w-8" />
        <span className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-lg border-2 border-white bg-brand-600">
          <DatabaseZap className="h-3 w-3" />
        </span>
      </div>
      <h2 className="mt-5 text-xl font-semibold text-steel-900">{agent.category}数据，直接用业务语言查询</h2>
      <p className="mt-2 max-w-lg text-sm leading-6 text-steel-500">
        {agent.description}描述时间范围和关注指标，即可查询；筛选条件不明确时会请你确认。
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {agent.suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onPick(suggestion)}
            className="inline-flex items-center gap-1.5 rounded-full border border-steel-200 bg-white px-3.5 py-1.5 text-xs text-steel-700 transition-colors hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-800"
          >
            <Sparkles className="h-3 w-3" />{suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
