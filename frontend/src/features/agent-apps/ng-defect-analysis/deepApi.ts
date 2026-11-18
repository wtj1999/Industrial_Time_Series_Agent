import { API_BASE } from '@/services/api';
import { getAuthHeaders, handleUnauthorized } from '@/utils/user';
import type { DeepPlan, DeepProgress, DeepResult } from './deepTypes';
import { readDeepStream } from './deepStream';

async function post<T>(action: string, payload: unknown, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}/api/bi/ng/deep/${action}`, {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(payload),
  });
  handleUnauthorized(response);
  const body = await response.json().catch(() => null);
  if (!response.ok || !body) throw new Error(body?.detail ?? `深度分析失败 (${response.status})`);
  return body as T;
}

export const recommendNgFields = (payload: { factory_id?: string; thread_id: string; source_id: string; row_index: number }, signal: AbortSignal) => post<DeepPlan>('recommend', payload, signal);
export async function analyzeNgFields(payload: { factory_id?: string; thread_id: string; plan_id: string; target_id: string; feature_ids: string[] }, signal: AbortSignal, onProgress?: (progress: DeepProgress) => void): Promise<DeepResult> {
  const response = await fetch(`${API_BASE}/api/bi/ng/deep/analyze/stream`, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json', ...getAuthHeaders() }, body: JSON.stringify(payload),
  });
  handleUnauthorized(response);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? body?.error ?? `深度分析失败 (${response.status})`);
  }
  if (!response.headers.get('content-type')?.includes('application/x-ndjson')) throw new Error('后端未返回取数进度流，请确认后端已更新');
  return readDeepStream(response, signal, onProgress);
}
