import { useEffect, useRef, useState } from 'react';
import { BarChart3, DatabaseZap, Sparkles } from 'lucide-react';
import { ChatInput } from '@/components/chat/ChatInput';
import { MessageBubble } from '@/components/chat/MessageBubble';
import type { Message } from '@/types';
import { queryProductionBi } from './api';
import { BiResultCard } from './BiResultCard';
import { FieldConfirmationCard } from './FieldConfirmationCard';
import type {
  BiConfirmPayload,
  BiNeedConfirmResponse,
  BiResponse,
  BiSuccessResponse,
} from './types';

type BiTurn =
  | { id: string; kind: 'message'; message: Message }
  | { id: string; kind: 'confirm'; confirm: BiConfirmPayload; threadId: string; submitted: boolean }
  | { id: string; kind: 'result'; result: BiSuccessResponse };

const SUGGESTIONS = [
  '查询本月PACK入库工序的产出计划完成率',
  '分析最近30天电芯计划产出与实际产出的差异',
  '统计本周各生产工序的完成率并按完成率排序',
];

function newId(): string {
  return globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function ProductionBiAnalysisApp() {
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

  const appendResponse = (response: BiResponse) => {
    setThreadId(response.thread_id);
    if (response.status === 'need_confirm' && 'confirm' in response) {
      const confirmation = response as BiNeedConfirmResponse;
      setTurns((current) => [...current, {
        id: newId(),
        kind: 'confirm',
        confirm: confirmation.confirm,
        threadId: confirmation.thread_id,
        submitted: false,
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

  const runRequest = async (payload: {
    query: string;
    thread_id: string;
    resume?: Record<string, string[]>;
  }) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      appendResponse(await queryProductionBi(payload, controller.signal));
      return true;
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') return false;
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
      if (abortRef.current === controller) abortRef.current = null;
      setLoading(false);
    }
  };

  const submitQuery = (query: string) => {
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    setTurns((current) => [...current, {
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
  ) => {
    if (loading) return;
    const succeeded = await runRequest({ query: '', thread_id: confirmationThreadId, resume });
    if (succeeded) {
      setTurns((current) => current.map((turn) => (
        turn.id === turnId && turn.kind === 'confirm' ? { ...turn, submitted: true } : turn
      )));
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setLoading(false);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-gradient-to-b from-steel-50/50 to-white">
      <div ref={scrollerRef} className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-10">
        <div className="mx-auto w-full max-w-3xl">
          {turns.length === 0 && <EmptyBiState onPick={submitQuery} />}
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
                    onSubmit={(resume) => void submitConfirmation(turn.id, turn.threadId, resume)}
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
        placeholder="输入生产经营问题，回车发送，Shift+Enter 换行"
        footerText="连接生产 BI 服务 · 如筛选条件不明确，将由你确认后继续查询"
        busyText="生产 BI 查询中"
        onSubmit={(text) => submitQuery(text)}
        onStop={stop}
      />
    </div>
  );
}

function EmptyBiState({ onPick }: { onPick: (query: string) => void }) {
  return (
    <div className="mb-8 mt-8 flex flex-col items-center text-center animate-fade-in">
      <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-700 text-white shadow-soft">
        <BarChart3 className="h-8 w-8" />
        <span className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-lg border-2 border-white bg-brand-600">
          <DatabaseZap className="h-3 w-3" />
        </span>
      </div>
      <h2 className="mt-5 text-xl font-semibold text-steel-900">生产数据，直接用业务语言查询</h2>
      <p className="mt-2 max-w-lg text-sm leading-6 text-steel-500">
        无需配置任务或上传文件。描述时间范围、工序和关注指标，智能体会检索生产数据并在必要时请你确认筛选条件。
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((suggestion) => (
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
