/**
 * Global session state for the chat workspace.
 *
 * Responsibilities
 *  - Track the active session id and metadata
 *  - Hold the conversation as a list of items (user / assistant / interrupt / status)
 *  - Drive the NDJSON stream via services/api.streamQuery
 *  - Expose actions: sendQuery, resumeQuery, resetTask, newSession, stop
 *  - Expose the *current interrupt* so the UI can render breakpoint panels
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import * as api from '@/services/api';
import {
  genId,
  genSessionId,
  isAbortError,
  shortId,
  stageLabel,
  taskLabel,
} from '@/utils/format';
import type {
  AnomalyChart,
  AnomalyTrainingProgress,
  PredictionFinetuningProgress,
  AnalysisChart,
  CompletedEvent,
  CSVPreview,
  InterruptEvent,
  InterruptPayload,
  Message,
  PredictionChart,
  ResumeValue,
  SessionInfo,
  SessionSummary,
  StreamEvent,
} from '@/types';

/** A single chat-bubble slot in the transcript. */
export type ConversationItem =
  | { kind: 'message'; id: string; message: Message }
  | { kind: 'interrupt'; id: string; interrupt: InterruptPayload; status: 'pending' | 'submitted' }
  | { kind: 'csv_preview'; id: string; preview: CSVPreview }
  | { kind: 'anomaly_chart'; id: string; chart: AnomalyChart }
  | {
      kind: 'anomaly_training_progress';
      id: string;
      progress: AnomalyTrainingProgress;
      history: AnomalyTrainingProgress[];
    }
  | {
      kind: 'prediction_finetuning_progress';
      id: string;
      progress: PredictionFinetuningProgress;
      history: PredictionFinetuningProgress[];
    }
  | { kind: 'analysis_chart'; id: string; chart: AnalysisChart }
  | { kind: 'prediction_chart'; id: string; chart: PredictionChart }
  | { kind: 'status'; id: string; text: string; tone: 'info' | 'error' | 'success' };

interface PendingAssistant {
  /** id of the in-flight assistant bubble we are streaming tokens into. */
  id: string;
  /** Accumulated token buffer. */
  buffer: string;
}

interface SessionState {
  sessionId: string;
  items: ConversationItem[];
  streaming: boolean;
  interrupt: InterruptPayload | null;
  sessionInfo: SessionInfo | null;
  error: string | null;
}

interface SessionContextValue extends SessionState {
  /** Conversation history for the sidebar list. */
  sessions: SessionSummary[];
  /** True while the history list is loading (initial fetch). */
  sessionsLoading: boolean;
  /** Initialize a brand-new (client-generated) session id. */
  initNewSession: (id?: string) => void;
  /** Switch to a past session: clear current items, load transcript. */
  loadSession: (sessionId: string) => Promise<void>;
  /** Send a fresh user query. */
  sendQuery: (query: string, file?: File | null) => Promise<void>;
  /** Resume the current interrupt with a user-provided payload. */
  resumeQuery: (
    resumeValue: ResumeValue,
    file?: File | null,
    existingFileName?: string,
  ) => Promise<void>;
  /** Reset the current task server-side. */
  resetTask: () => Promise<void>;
  /** Delete a past conversation thread (sidebar action). */
  removeSession: (sessionId: string) => Promise<void>;
  /** Refresh the conversation history list. */
  refreshSessions: () => Promise<void>;
  /** Abort the current stream (if any). */
  stop: () => void;
  /** Clear the current interrupt once consumed. */
  dismissInterrupt: () => void;
  /** Refresh session metadata. */
  refreshSessionInfo: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string>(() => genSessionId());
  const [items, setItems] = useState<ConversationItem[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [interrupt, setInterrupt] = useState<InterruptPayload | null>(null);
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const pendingRef = useRef<PendingAssistant | null>(null);

  const pushItem = useCallback((item: ConversationItem) => {
    setItems((prev) => [...prev, item]);
  }, []);

  const pushStatus = useCallback(
    (text: string, tone: 'info' | 'error' | 'success') => {
      pushItem({ kind: 'status', id: genId(), text, tone });
    },
    [pushItem],
  );

  const refreshSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const res = await api.listSessions();
      setSessions(res.sessions ?? []);
    } catch {
      // Silently ignore — the sidebar simply stays empty / stale. The
      // listing endpoint is best-effort; main chat flow doesn't depend
      // on it.
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  // Load the history list once on mount so the user sees their past
  // threads as soon as they land in the workspace.
  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const initNewSession = useCallback(
    (id?: string) => {
      abortRef.current?.abort();
      pendingRef.current = null;
      setSessionId(id ?? genSessionId());
      setItems([]);
      setInterrupt(null);
      setError(null);
      setSessionInfo(null);
      setStreaming(false);
    },
    [],
  );

  const loadSession = useCallback(
    async (targetSessionId: string) => {
      if (!targetSessionId) return;
      // Abort any in-flight stream before switching — otherwise tokens
      // from the old session could leak into the new transcript.
      abortRef.current?.abort();
      pendingRef.current = null;
      setStreaming(false);
      setError(null);
      setInterrupt(null);
      setItems([]);
      setSessionId(targetSessionId);

      // Replay the stored conversation. We prefer the chronological
      // ``events`` log when present (preserves original card positions —
      // csv_preview appears between the LLM's pre-profile narration and
      // its post-profile analysis, exactly as it did during live chat).
      // For older sessions that pre-date event_log we fall back to
      // ``messages`` + append artifacts at the end.
      //
      // Interrupt cards (tech_path picker / clarification / csv upload)
      // are NEVER replayed — they were one-shot prompts, either
      // already answered or regenerated when the user continues.
      try {
        const res = await api.getSessionMessages(targetSessionId);
        const nextItems: ConversationItem[] = [];

        const normaliseRole = (r?: string): Message['role'] =>
          r === 'user' || r === 'system' ? r : 'assistant';

        if (res.events && res.events.length > 0) {
          // Chronological replay — positions match live chat.
          for (const e of res.events) {
            switch (e.kind) {
              case 'message':
                nextItems.push({
                  kind: 'message',
                  id: genId(),
                  message: {
                    role: normaliseRole(e.role),
                    content: e.content ?? '',
                    timestamp: e.ts ?? '',
                  },
                });
                break;
              case 'csv_preview':
                if (e.data) {
                  nextItems.push({
                    kind: 'csv_preview',
                    id: genId(),
                    preview: e.data as CSVPreview,
                  });
                }
                break;
              case 'anomaly_chart':
                if (e.data) {
                  nextItems.push({
                    kind: 'anomaly_chart',
                    id: genId(),
                    chart: e.data as AnomalyChart,
                  });
                }
                break;
              case 'analysis_chart':
                if (e.data) {
                  nextItems.push({
                    kind: 'analysis_chart',
                    id: genId(),
                    chart: e.data as AnalysisChart,
                  });
                }
                break;
              case 'prediction_chart':
                if (e.data) {
                  nextItems.push({
                    kind: 'prediction_chart',
                    id: genId(),
                    chart: e.data as PredictionChart,
                  });
                }
                break;
              default:
                // Unknown event kinds are ignored — adding a new kind
                // on the backend doesn't break older frontends.
                break;
            }
          }
        } else {
          // Fallback: messages + artifacts-at-end (pre-event_log sessions).
          for (const m of res.messages ?? []) {
            nextItems.push({
              kind: 'message',
              id: genId(),
              message: {
                role: normaliseRole(m.role),
                content: m.content ?? '',
                timestamp: '',
              },
            });
          }
          const artifacts = res.artifacts ?? {};
          if (artifacts.csv_preview) {
            nextItems.push({
              kind: 'csv_preview',
              id: genId(),
              preview: artifacts.csv_preview,
            });
          }
          if (artifacts.anomaly_chart) {
            nextItems.push({
              kind: 'anomaly_chart',
              id: genId(),
              chart: artifacts.anomaly_chart,
            });
          }
          if (artifacts.analysis_chart) {
            nextItems.push({
              kind: 'analysis_chart',
              id: genId(),
              chart: artifacts.analysis_chart,
            });
          }
          if (artifacts.prediction_chart) {
            nextItems.push({
              kind: 'prediction_chart',
              id: genId(),
              chart: artifacts.prediction_chart,
            });
          }
        }

        setItems(nextItems);
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载历史对话失败');
      }

      // Best-effort: refresh sessionInfo for the newly loaded thread so
      // the sidebar "当前会话" card reflects the correct stage/task.
      api
        .getSessionInfo(targetSessionId)
        .then(setSessionInfo)
        .catch(() => {
          /* ignore — thread may not have a checkpoint yet */
        });
    },
    [],
  );

  const removeSession = useCallback(
    async (targetSessionId: string) => {
      try {
        await api.deleteSession(targetSessionId);
        setSessions((prev) => prev.filter((s) => s.session_id !== targetSessionId));
        // If the user deleted the currently-open thread, reset to a
        // fresh blank session so they don't keep typing into a tombstone.
        if (targetSessionId === sessionId) {
          initNewSession();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '删除对话失败');
      }
    },
    [initNewSession, sessionId],
  );

  const handleEvent = useCallback(
    (ev: StreamEvent, assistantId: string) => {
      switch (ev.type) {
        case 'token': {
          // Capture the next buffer in a LOCAL variable before scheduling
          // the setItems callback. React queues state updates and runs the
          // callback asynchronously — between queueing and execution,
          // `pendingRef.current` may be reset to null by a racing
          // `completed` / `interrupt` / `stop()` event, and reading
          // `pendingRef.current.buffer` inside the callback would then
          // throw "Cannot read properties of null (reading 'buffer')".
          // Closing over `nextBuffer` sidesteps the race entirely.
          const nextBuffer = (pendingRef.current?.buffer ?? '') + ev.content;
          pendingRef.current = { id: assistantId, buffer: nextBuffer };
          setItems((prev) =>
            prev.map((it) =>
              it.kind === 'message' && it.id === assistantId
                ? {
                    ...it,
                    message: { ...it.message, content: nextBuffer },
                  }
                : it,
            ),
          );
          break;
        }
        case 'update': {
          // Optional: surface intermediate state changes as ephemeral status lines.
          const data = ev.data ?? {};
          const stage = typeof data.current_stage === 'string' ? data.current_stage : undefined;
          if (stage) {
            pushStatus(`阶段更新：${stageLabel(stage)}`, 'info');
          }
          break;
        }
        case 'anomaly_training_progress': {
          const progress = ev.data;
          setItems((prev) => {
            const index = prev.findIndex(
              (item) => item.kind === 'anomaly_training_progress' &&
                item.progress.operation_id === progress.operation_id,
            );
            if (index < 0) {
              return [...prev, {
                kind: 'anomaly_training_progress' as const,
                id: `training-${progress.operation_id}`,
                progress,
                history: [progress],
              }];
            }
            const next = [...prev];
            const current = next[index];
            if (current.kind === 'anomaly_training_progress') {
              next[index] = {
                ...current,
                progress,
                history: [...current.history, progress],
              };
            }
            return next;
          });
          break;
        }
        case 'prediction_finetuning_progress': {
          const progress = ev.data;
          setItems((prev) => {
            const index = prev.findIndex(
              (item) => item.kind === 'prediction_finetuning_progress' &&
                item.progress.operation_id === progress.operation_id,
            );
            if (index < 0) {
              return [...prev, {
                kind: 'prediction_finetuning_progress' as const,
                id: `finetuning-${progress.operation_id}`,
                progress,
                history: [progress],
              }];
            }
            const next = [...prev];
            const current = next[index];
            if (current.kind === 'prediction_finetuning_progress') {
              next[index] = { ...current, progress, history: [...current.history, progress] };
            }
            return next;
          });
          break;
        }
        case 'interrupt': {
          const payload = ev.data;
          pendingRef.current = null;
          setInterrupt(payload);
          pushItem({
            kind: 'interrupt',
            id: genId(),
            interrupt: payload,
            status: 'pending',
          });
          break;
        }
        case 'csv_preview': {
          // Emitted by the profiling node the moment it finishes
          // building the preview payload. We push it as a dedicated
          // assistant-side chat item so the chart shows up inline in
          // the transcript — appearing as part of the assistant's
          // reply rather than in a side panel.
          pushItem({
            kind: 'csv_preview',
            id: genId(),
            preview: ev.data,
          });
          break;
        }
        case 'anomaly_chart': {
          // Emitted by the execute_task node when anomaly detection
          // produced a chartable result. Same inline-as-a-reply
          // treatment as csv_preview.
          pushItem({
            kind: 'anomaly_chart',
            id: genId(),
            chart: ev.data,
          });
          break;
        }
        case 'analysis_chart': {
          // Emitted when an analysis sub-agent ran a Tier-1 visualisable
          // tool (correlation / histogram / decomposition / control /
          // changepoint / acf). ChatView dispatches on chart_type via
          // a registry to pick the right card component.
          pushItem({
            kind: 'analysis_chart',
            id: genId(),
            chart: ev.data,
          });
          break;
        }
        case 'prediction_chart': {
          // Emitted when the prediction sub-agent ran a forecast or
          // backtest tool. ``ev.data.chart_type`` discriminates:
          //   - 'forecast'  -> forecast_time_series / forecast_multi_models
          //   - 'backtest'  -> backtest_forecast / compare_forecast_models_backtest
          // ChatView.tsx dispatches on chart_type to pick the right card.
          pushItem({
            kind: 'prediction_chart',
            id: genId(),
            chart: ev.data,
          });
          break;
        }
        case 'completed': {
          // finalize
          pendingRef.current = null;
          break;
        }
        case 'error': {
          // Stream errors are normally handled by api.streamQuery's
          // onError callback. Keep this branch for exhaustive typing and
          // for callers that dispatch a StreamEvent directly.
          pendingRef.current = null;
          break;
        }
        default: {
          const _exhaustive: never = ev;
          void _exhaustive;
        }
      }
    },
    [pushItem, pushStatus],
  );

  const runStream = useCallback(
    async (params: api.QueryParams) => {
      const assistantId = genId();
      // Placeholder assistant bubble for streamed tokens
      pushItem({
        kind: 'message',
        id: assistantId,
        message: {
          role: 'assistant',
          content: '',
          timestamp: new Date().toISOString(),
        },
      });
      pendingRef.current = { id: assistantId, buffer: '' };

      const controller = new AbortController();
      abortRef.current = controller;
      params.signal = controller.signal;
      setStreaming(true);
      setError(null);

      let completedData: CompletedEvent['data'] | null = null;

      await api.streamQuery(params, {
        onToken: (t) => handleEvent({ type: 'token', content: t }, assistantId),
        onUpdate: (d) => handleEvent({ type: 'update', data: d }, assistantId),
        onAnomalyTrainingProgress: (p) => handleEvent(
          { type: 'anomaly_training_progress', data: p }, assistantId,
        ),
        onPredictionFinetuningProgress: (p) => handleEvent(
          { type: 'prediction_finetuning_progress', data: p }, assistantId,
        ),
        onInterrupt: (ev) => handleEvent(ev as InterruptEvent, assistantId),
        onCsvPreview: (p) => handleEvent({ type: 'csv_preview', data: p }, assistantId),
        onAnomalyChart: (c) => handleEvent({ type: 'anomaly_chart', data: c }, assistantId),
        onAnalysisChart: (c) => handleEvent({ type: 'analysis_chart', data: c }, assistantId),
        onPredictionChart: (c) => handleEvent({ type: 'prediction_chart', data: c }, assistantId),
        onCompleted: (d) => {
          completedData = d;
          handleEvent({ type: 'completed', data: d }, assistantId);
        },
        onError: (err) => {
          if (isAbortError(err)) return;
          setError(err.message);
          pushStatus(`错误：${err.message}`, 'error');
        },
      });

      setStreaming(false);
      abortRef.current = null;

      // Aborted streams (user switched / created a session mid-flight)
      // must not trigger the post-stream refresh — this stream's session
      // is no longer the active one.
      if (controller.signal.aborted) return;

      // After completion, attempt to refresh session metadata. Pass the
      // session id this stream actually ran on — the `sessionId` state
      // captured by this memoized closure can be stale (see refresh()).
      void refresh(completedData, params.sessionId);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [handleEvent, pushItem],
  );

  // Kept outside useCallback deps to avoid re-binding runStream each render.
  // ``sid`` MUST be the session id the stream actually ran on — the
  // ``sessionId`` state captured by this memoized closure can be stale
  // (e.g. the id generated at mount, before the user created a new
  // session), which used to cause spurious 404s on /api/session/{id}.
  async function refresh(
    completedData?: CompletedEvent['data'] | null,
    sid: string = sessionId,
  ) {
    // The streaming `completed` event carries the raw LangGraph state dict,
    // whose field names differ from the SessionInfo shape (e.g. `task_type`
    // vs `current_task`, `csv_profile` object vs `has_csv_profile` bool).
    // Map them here so the UI updates immediately, then refresh from the
    // server for the canonical view.
    if (completedData && typeof completedData === 'object') {
      const raw = completedData as Record<string, unknown>;
      if (raw.session_id || raw.current_stage) {
        const dialogueTurns = Array.isArray(raw.dialogue_history)
          ? raw.dialogue_history.length
          : (raw.dialogue_turns as number | undefined);
        setSessionInfo((prev) => ({
          session_id: (raw.session_id as string) ?? prev?.session_id ?? sid,
          created_at: (raw.created_at as string) ?? prev?.created_at ?? '',
          updated_at: (raw.updated_at as string) ?? new Date().toISOString(),
          is_active: (raw.is_active as boolean) ?? prev?.is_active ?? true,
          current_task:
            (raw.current_task as SessionInfo['current_task']) ??
            (raw.task_type as SessionInfo['current_task']) ??
            prev?.current_task ??
            null,
          current_stage:
            (raw.current_stage as string) ?? prev?.current_stage ?? '',
          has_csv_profile:
            raw.csv_profile != null || (raw.has_csv_profile as boolean) || prev?.has_csv_profile || false,
          has_confirmed_spec:
            raw.confirmed_spec != null ||
            (raw.has_confirmed_spec as boolean) ||
            prev?.has_confirmed_spec ||
            false,
          dialogue_turns: dialogueTurns ?? prev?.dialogue_turns ?? 0,
          clarification_pending:
            (raw.clarification_pending as boolean) ?? prev?.clarification_pending ?? false,
          analysis_artifacts_count:
            (raw.analysis_artifacts_count as number | undefined) ??
            (raw.execution_results != null ? 1 : prev?.analysis_artifacts_count ?? 0),
        }));
      }
    }
    // Best-effort server refresh — overwrites the locally-derived snapshot
    // with the canonical SessionInfo from /api/session/{id}.
    api
      .getSessionInfo(sid)
      .then(setSessionInfo)
      .catch(() => {
        /* Ignore background refresh errors - the session may not exist server-side
           until the first successful query. */
      });
    // Also refresh the conversation history list so a brand-new thread
    // appears in the sidebar as soon as its first turn completes, and
    // existing threads move to the top on resume.
    void refreshSessions();
  }

  const sendQuery = useCallback(
    async (query: string, file: File | null = null) => {
      if (!query.trim() && !file) return;
      pushItem({
        kind: 'message',
        id: genId(),
        message: { role: 'user', content: query || `📎 ${file?.name ?? ''}`.trim(), timestamp: new Date().toISOString() },
      });
      setInterrupt(null);
      await runStream({ sessionId, query, file });
    },
    [pushItem, runStream, sessionId],
  );

  const resumeQuery = useCallback(
    async (
      resumeValue: ResumeValue,
      file: File | null = null,
      existingFileName?: string,
    ) => {
      // Mark the current interrupt item as submitted
      setItems((prev) =>
        prev.map((it) => (it.kind === 'interrupt' && it.status === 'pending'
          ? { ...it, status: 'submitted' }
          : it)),
      );
      setInterrupt(null);
      await runStream({ sessionId, resumeValue, file, existingFileName });
    },
    [runStream, sessionId],
  );

  const resetTask = useCallback(async () => {
    try {
      await api.resetSessionTask(sessionId);
      setInterrupt(null);
      pushStatus('已重置当前任务', 'success');
      await api.getSessionInfo(sessionId).then(setSessionInfo).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : '重置失败');
      pushStatus('重置失败', 'error');
    }
  }, [sessionId, pushStatus]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
    pendingRef.current = null;
  }, []);

  const dismissInterrupt = useCallback(() => setInterrupt(null), []);

  const refreshSessionInfo = useCallback(async () => {
    try {
      const info = await api.getSessionInfo(sessionId);
      setSessionInfo(info);
    } catch {
      /* ignore */
    }
  }, [sessionId]);

  const value = useMemo<SessionContextValue>(
    () => ({
      sessionId,
      items,
      streaming,
      interrupt,
      sessionInfo,
      error,
      sessions,
      sessionsLoading,
      initNewSession,
      loadSession,
      sendQuery,
      resumeQuery,
      resetTask,
      removeSession,
      refreshSessions,
      stop,
      dismissInterrupt,
      refreshSessionInfo,
    }),
    [
      sessionId,
      items,
      streaming,
      interrupt,
      sessionInfo,
      error,
      sessions,
      sessionsLoading,
      initNewSession,
      loadSession,
      sendQuery,
      resumeQuery,
      resetTask,
      removeSession,
      refreshSessions,
      stop,
      dismissInterrupt,
      refreshSessionInfo,
    ],
  );

  // Surface short session id for debugging in devtools via a getter on window? No, keep clean.

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within <SessionProvider>');
  return ctx;
}

/** Helper exposed for components that only need the short id. */
export function useShortSessionId(): string {
  const { sessionId } = useSession();
  return shortId(sessionId);
}

export { taskLabel, stageLabel };
