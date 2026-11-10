import { useEffect, useRef, useState } from 'react';
import { DatabaseZap, Sparkles } from 'lucide-react';
import { ChatInput } from '@/components/chat/ChatInput';
import { MessageBubble } from '@/components/chat/MessageBubble';
import type { Message } from '@/types';
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
  | { id: string; kind: 'result'; result: BiSuccessResponse };

function newId(): string {
  return globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function ProductionBiAnalysisApp({ agent }: { agent: ProductionBiAgent }) {
  const [threadId, setThreadId] = useState(() => newId());
  const [turns, setTurns] = useState<BiTurn[]>([]);
  const [loading, setLoading] = useState(false);
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
      const response = await queryProductionBi({ ...payload, ...(agent.tenantId ? { tenant_id: agent.tenantId } : {}), ...(agent.analysisDomain ? { domain: agent.analysisDomain } : {}) }, controller.signal, agent.endpoint);
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
    setTurns((current) => [...current.map((turn) => (
      turn.kind === 'confirm' && !turn.submitted ? { ...turn, expired: true } : turn
    )), {
      id: newId(),
      kind: 'message',
      message: { role: 'user', content: trimmed, timestamp: new Date().toISOString() },
    }]);
    void runRequest({ query: trimmed, thread_id: threadId });
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
                    }, signal) : undefined}
                    onSubmit={(resume) => void submitConfirmation(turn.id, turn.threadId, resume, turn.confirm.confirmation_id, turn.analysisQuery)}
                  />
                );
              }
              return <BiResultCard key={turn.id} result={turn.result} />;
            })}
            {loading && (
              <MessageBubble
                streaming
                message={{ role: 'assistant', content: '', timestamp: new Date().toISOString() }}
              />
            )}
          </div>
        </div>
      </div>
      <ChatInput
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
