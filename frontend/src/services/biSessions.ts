import { API_BASE } from './api';
import { getAuthHeaders, handleUnauthorized } from '@/utils/user';
import type { SessionSummary } from '@/types';

export const BI_HISTORY_EVENT = 'bi-history-changed';
export interface BiSessionSummary extends SessionSummary {
  source: 'bi'; thread_id: string; app_id: string; app_name: string;
  factory_id?: string | null; factory_name?: string | null; tenant_id?: string | null;
}
export interface BiConversation extends BiSessionSummary {
  version: number; turns: Array<{ id: string; kind: string; [key: string]: unknown }>;
}
export interface BiHistoryEvent { sessionId?: string; threadId?: string }

export function notifyBiHistory(response?: Response, threadId?: string) {
  if (typeof window === 'undefined') return;
  const sessionId = response?.headers.get('X-BI-Session-ID') || undefined;
  if (sessionId || threadId) window.dispatchEvent(new CustomEvent<BiHistoryEvent>(BI_HISTORY_EVENT, { detail: { sessionId, threadId } }));
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}/api/bi/sessions${path}`, { ...options, headers: getAuthHeaders() });
  handleUnauthorized(response);
  const body = await response.json().catch(() => null);
  if (!response.ok || !body) throw new Error(typeof body?.detail === 'string' ? body.detail : '读取BI历史对话失败');
  return body;
}
export const listBiSessions = () => request<{ sessions: BiSessionSummary[] }> ('');
export const deleteBiSession = (id: string) => request<{success: boolean}>(`/${encodeURIComponent(id)}`, { method: 'DELETE' });
export async function readBiSession(id: string, signal?: AbortSignal) {
  const body = await request<BiConversation>(`/${encodeURIComponent(id)}`, { signal });
  if (body.version !== 1 || !Array.isArray(body.turns) || body.turns.some(turn => !turn || typeof turn.id !== 'string' || typeof turn.kind !== 'string'))
    throw new Error('BI历史对话格式不正确');
  return body;
}
export function biConversationUrl(appId: string, sessionId?: string, factoryId?: string | null, tenantId?: string | null) {
  const query = new URLSearchParams();
  if (factoryId) query.set('factory', factoryId);
  if (tenantId) query.set('tenant', tenantId);
  return `/agents/bi/${encodeURIComponent(appId)}${sessionId ? `/${encodeURIComponent(sessionId)}` : ''}${query.size ? `?${query}` : ''}`;
}
