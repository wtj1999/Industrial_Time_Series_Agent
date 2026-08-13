/**
 * Thin client around the Industrial Time Series Agent REST API.
 *
 * Backend (agent_app/api.py) exposes:
 *   POST  /api/query                 - NDJSON-over-POST stream (main entry)
 *   GET   /api/session/{id}          - session info (Header/Sidebar badges)
 *   DELETE /api/session/{id}/reset   - reset current task
 *   GET   /health                    - health probe
 *
 * The stream is newline-delimited JSON (NDJSON): one JSON object per line.
 */

import type {
  AnomalyChart,
  AnalysisChart,
  AuthResponse,
  CSVPreview,
  DatasetsResponse,
  ModelsResponse,
  PredictionChart,
  ResumeValue,
  SessionInfo,
  SessionMessagesResponse,
  SessionsResponse,
  StandardResponse,
  StreamEvent,
} from '@/types';
import { getUserId } from '@/utils/user';

const envBase = import.meta.env.VITE_API_BASE_URL;
/** Empty base => use the Vite dev proxy (relative URLs). */
export const API_BASE = (envBase ?? '').replace(/\/$/, '');

function url(path: string): string {
  return `${API_BASE}${path}`;
}

/**
 * Headers every API call must carry so the backend can namespace
 * uploads + trained-model artifacts by user. Centralised here so the
 * identity flows through automatically without each call site needing
 * to remember to add it.
 */
function authHeaders(extra?: HeadersInit): HeadersInit {
  return { 'X-User-Id': getUserId(), ...(extra ?? {}) };
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) return null as unknown as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    // The FastAPI exception handler returns a non-JSON body for some errors.
    throw new Error(text.slice(0, 300));
  }
}

/**
 * The FastAPI exception handlers in agent_app/api.py return plain dicts
 * `{success, error, status_code}` which FastAPI serializes as HTTP 200.
 * So we must also inspect the body for `success: false`, not just `res.ok`.
 */
function raiseIfFailed(
  res: Response,
  body: { success?: boolean; error?: string | null } | null,
  fallback: string,
): void {
  if (!res.ok) {
    throw new Error(body?.error ?? `${fallback} (${res.status})`);
  }
  if (body && body.success === false) {
    throw new Error(body.error ?? fallback);
  }
}

async function getJson<T>(
  path: string,
  init: RequestInit,
  fallback: string,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url(path), {
      ...init,
      headers: authHeaders(init.headers),
    });
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') throw err;
    throw new Error('网络错误，请确认后端服务已启动');
  }
  const body = await parseJson<T & { success?: boolean; error?: string | null }>(res).catch(
    () => null,
  );
  if (body === null) {
    throw new Error(!res.ok ? `${fallback} (${res.status})` : '响应解析失败');
  }
  raiseIfFailed(res, body, fallback);
  return body as T;
}

/* ------------------------------------------------------------------ *
 * Plain REST endpoints
 * ------------------------------------------------------------------ */

export async function getSessionInfo(sessionId: string): Promise<SessionInfo> {
  return getJson<SessionInfo>(
    `/api/session/${encodeURIComponent(sessionId)}`,
    { method: 'GET' },
    '获取会话信息失败',
  );
}

export async function resetSessionTask(sessionId: string): Promise<StandardResponse> {
  return getJson<StandardResponse>(
    `/api/session/${encodeURIComponent(sessionId)}/reset`,
    { method: 'DELETE' },
    '重置任务失败',
  );
}

/* ------------------------------------------------------------------ *
 * Conversation history endpoints — sidebar "历史对话" list + replay.
 * ------------------------------------------------------------------ */

/** List every conversation thread owned by the current user. */
export async function listSessions(): Promise<SessionsResponse> {
  return getJson<SessionsResponse>(
    '/api/sessions',
    { method: 'GET' },
    '获取历史对话失败',
  );
}

/** Fetch the stored dialogue transcript for a single thread. */
export async function getSessionMessages(
  sessionId: string,
): Promise<SessionMessagesResponse> {
  return getJson<SessionMessagesResponse>(
    `/api/sessions/${encodeURIComponent(sessionId)}/messages`,
    { method: 'GET' },
    '获取对话内容失败',
  );
}

/** Delete a conversation thread (index row + checkpoint state). */
export async function deleteSession(sessionId: string): Promise<StandardResponse> {
  return getJson<StandardResponse>(
    `/api/sessions/${encodeURIComponent(sessionId)}`,
    { method: 'DELETE' },
    '删除对话失败',
  );
}

/** List every uploaded data file (CSV / XLSX / Parquet). */
export async function listDatasets(): Promise<DatasetsResponse> {
  return getJson<DatasetsResponse>(
    '/api/datasets',
    { method: 'GET' },
    '获取数据列表失败',
  );
}

/** List every persisted anomaly-detection model across all sessions. */
export async function listModels(): Promise<ModelsResponse> {
  return getJson<ModelsResponse>(
    '/api/models',
    { method: 'GET' },
    '获取模型列表失败',
  );
}

/* ------------------------------------------------------------------ *
 * Auth endpoints — login / register / validate-session.
 *
 * All three return the same ``AuthResponse`` envelope. On success the
 * caller (AuthContext) persists ``{user_id, username}`` via
 * ``utils/user.ts``; the ``X-User-Id`` header then flows automatically
 * through :func:`authHeaders` on every subsequent request.
 *
 * ``getMe`` is called on mount to validate a stored session — it sends
 * the current ``X-User-Id`` and the backend looks it up; a
 * ``success:false`` response means the stored id is stale and the user
 * is bounced back to the login page.
 * ------------------------------------------------------------------ */

export async function login(username: string, password: string): Promise<AuthResponse> {
  return postJson<AuthResponse>(
    '/api/auth/login',
    { username, password },
    '登录失败',
  );
}

export async function register(username: string, password: string): Promise<AuthResponse> {
  return postJson<AuthResponse>(
    '/api/auth/register',
    { username, password },
    '注册失败',
  );
}

export async function getMe(): Promise<AuthResponse> {
  return getJson<AuthResponse>(
    '/api/auth/me',
    { method: 'GET' },
    '验证失败',
  );
}

/** POST JSON helper — mirrors :func:`getJson` but defaults the method
 *  to POST and stringifies the body. Auth endpoints are the only JSON
 *  bodies in the app; the rest are multipart or GET. */
async function postJson<T>(
  path: string,
  body: unknown,
  fallback: string,
): Promise<T> {
  return getJson<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
  }, fallback);
}

/* ------------------------------------------------------------------ *
 * Streaming query endpoint (NDJSON over POST)
 * ------------------------------------------------------------------ */

export interface QueryParams {
  sessionId: string;
  query?: string;
  file?: File | null;
  /**
   * On-disk filename within uploads/<user_id>/ to re-use instead of
   * uploading a fresh file. Mutually exclusive with ``file`` — when
   * both are supplied the backend prefers ``file``.
   */
  existingFileName?: string;
  resumeValue?: ResumeValue | null;
  signal?: AbortSignal;
}

export interface QueryCallbacks {
  onToken?: (text: string) => void;
  onUpdate?: (data: Record<string, unknown>) => void;
  onAnomalyTrainingProgress?: (progress: import('@/types').AnomalyTrainingProgress) => void;
  onInterrupt?: (data: StreamEvent) => void;
  onCompleted?: (data: Record<string, unknown>) => void;
  /** Fired the moment the profiling node finishes building the CSV preview. */
  onCsvPreview?: (preview: CSVPreview) => void;
  /** Fired when anomaly-detection finishes and a chart payload is available. */
  onAnomalyChart?: (chart: AnomalyChart) => void;
  /** Fired when an analysis sub-agent finishes and a chart payload is available. */
  onAnalysisChart?: (chart: AnalysisChart) => void;
  /** Fired when a prediction sub-agent finishes and a forecast/backtest chart payload is available. */
  onPredictionChart?: (chart: PredictionChart) => void;
  onError?: (err: Error) => void;
}

/**
 * POST /api/query as multipart/form-data and stream NDJSON events.
 *
 * The backend (agent_app/api.py) writes one JSON object per `\n`-delimited
 * line with `media_type="application/x-ndjson"`. The endpoint is POST +
 * multipart, so we drive a `ReadableStream` reader manually.
 */
export async function streamQuery(params: QueryParams, cb: QueryCallbacks): Promise<void> {
  const { sessionId, query, file, resumeValue, signal, existingFileName } = params;

  const form = new FormData();
  form.append('session_id', sessionId);
  if (query) form.append('query', query);
  if (file) form.append('file', file);
  // ``file`` takes precedence — only send existing_file_name when no new
  // upload is attached. The backend enforces the same precedence, but we
  // avoid sending contradictory data in the first place.
  if (!file && existingFileName) {
    form.append('existing_file_name', existingFileName);
  }
  if (resumeValue) form.append('resume_value', JSON.stringify(resumeValue));

  let res: Response;
  try {
    res = await fetch(url('/api/query'), {
      method: 'POST',
      body: form,
      signal,
      headers: authHeaders(),
      // Do not set Content-Type - the browser sets it with the multipart boundary.
    });
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') return;
    cb.onError?.(err instanceof Error ? err : new Error('Network error'));
    return;
  }

  // The FastAPI exception handler returns HTTP 200 with a JSON body
  // `{success:false, error, status_code}` for errors. Detect that case by
  // inspecting Content-Type — a real stream is `text/event-stream`.
  const ct = res.headers.get('content-type') ?? '';
  const isStream = ct.includes('text/event-stream') || ct.includes('application/x-ndjson');

  if (!res.ok || !res.body || !isStream) {
    const errBody = await parseJson<StandardResponse>(res).catch(() => null);
    cb.onError?.(new Error(errBody?.error ?? `请求失败 (${res.status})`));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let dispatchedAny = false;
  let receivedTerminal = false;
  let receivedBytes = 0;

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      receivedBytes += value?.byteLength ?? 0;
      buffer += decoder.decode(value, { stream: true });

      // Process complete lines
      let nlIdx = buffer.indexOf('\n');
      while (nlIdx >= 0) {
        const line = buffer.slice(0, nlIdx).trim();
        buffer = buffer.slice(nlIdx + 1);
        nlIdx = buffer.indexOf('\n');
        if (!line) continue;
        try {
          const evt = JSON.parse(line) as StreamEvent | StandardResponse;
          // Backend may still emit an inline `{success:false,...}` envelope
          // in the middle of an otherwise-OK stream.
          if (
            evt && typeof evt === 'object' &&
            (evt as StandardResponse).success === false &&
            (evt as StreamEvent).type === undefined
          ) {
            cb.onError?.(new Error((evt as StandardResponse).error ?? '执行失败'));
            return;
          }
          if ((evt as StreamEvent).type === 'error') {
            cb.onError?.(new Error((evt as Extract<StreamEvent, { type: 'error' }>).error));
            return;
          }
          dispatchEvent(evt as StreamEvent, cb);
          dispatchedAny = true;
          if ((evt as StreamEvent).type === 'completed' || (evt as StreamEvent).type === 'interrupt') {
            receivedTerminal = true;
          }
        } catch (e) {
          // Ignore malformed partial lines, they will be retried on next chunk
          console.warn('Failed to parse stream line', e, line);
        }
      }
    }
    // Flush trailing buffer
    const tail = buffer.trim();
    if (tail) {
      try {
        const evt = JSON.parse(tail) as StreamEvent;
        if (evt.type === 'error') {
          cb.onError?.(new Error(evt.error));
          return;
        }
        dispatchEvent(evt, cb);
        dispatchedAny = true;
        if (evt.type === 'completed' || evt.type === 'interrupt') receivedTerminal = true;
      } catch {
        /* ignore */
      }
    }
    if (!dispatchedAny) {
      cb.onError?.(new Error(
        receivedBytes === 0
          ? `后端事件流响应体为空（Content-Type: ${ct || '未知'}）`
          : `后端返回了 ${receivedBytes} 字节，但没有可解析的事件`,
      ));
    } else if (!receivedTerminal) {
      cb.onError?.(new Error('后端事件流在任务完成前中断'));
    }
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') return;
    cb.onError?.(err instanceof Error ? err : new Error('Stream read error'));
  }
}

function dispatchEvent(evt: StreamEvent, cb: QueryCallbacks): void {
  switch (evt.type) {
    case 'token':
      cb.onToken?.(evt.content);
      break;
    case 'update':
      cb.onUpdate?.(evt.data);
      break;
    case 'anomaly_training_progress':
      cb.onAnomalyTrainingProgress?.(evt.data);
      break;
    case 'interrupt':
      cb.onInterrupt?.(evt);
      break;
    case 'completed':
      cb.onCompleted?.(evt.data);
      break;
    case 'csv_preview':
      cb.onCsvPreview?.(evt.data);
      break;
    case 'anomaly_chart':
      cb.onAnomalyChart?.(evt.data);
      break;
    case 'analysis_chart':
      cb.onAnalysisChart?.(evt.data);
      break;
    case 'prediction_chart':
      cb.onPredictionChart?.(evt.data);
      break;
    case 'error':
      cb.onError?.(new Error(evt.error));
      break;
    default:
      // Unknown event types are tolerated — forward as update so the UI can
      // decide whether to render them.
      cb.onUpdate?.({ ...(evt as Record<string, unknown>) });
  }
}
