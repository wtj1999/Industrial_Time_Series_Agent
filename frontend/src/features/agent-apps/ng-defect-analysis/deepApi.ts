import { API_BASE } from '@/services/api';
import { getAuthHeaders, handleUnauthorized } from '@/utils/user';
import type { DeepPlan, DeepProgress, DeepResult, ValidationDraft, ValidationRecord, MeasurementAuditPage } from './deepTypes';
import { readDeepStream } from './deepStream';
import { notifyBiHistory } from '@/services/biSessions';

async function post<T>(action: string, payload: unknown, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}/api/bi/ng/deep/${action}`, {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(payload),
  });
  if (action === 'recommend') notifyBiHistory(response, (payload as {thread_id:string}).thread_id);
  handleUnauthorized(response);
  const body = await response.json().catch(() => null);
  if (!response.ok || !body) throw new Error(typeof body?.detail === 'string' ? body.detail : Array.isArray(body?.detail) ? body.detail.map((d: { msg?: string }) => d.msg).join('；') : `深度分析失败 (${response.status})`);
  return body as T;
}

type ValidationContext = { factory_id?: string; thread_id: string; analysis_id: string };
export async function listNgValidations(context: ValidationContext): Promise<ValidationRecord[]> {
  const result = await post<{ records: ValidationRecord[] }>('validation/list', context, new AbortController().signal);
  return result.records;
}
export function recordNgValidation(context: ValidationContext, draft: ValidationDraft) {
  return post<ValidationRecord>('validation/record', { ...context, ...draft }, new AbortController().signal);
}
export function loadNgQualityAudit(context: ValidationContext, fieldId: string, offset = 0) {
  return post<MeasurementAuditPage>('quality/audit', { ...context, field_id: fieldId, offset, limit:50 }, new AbortController().signal);
}

export const recommendNgFields = (payload: { factory_id?: string; thread_id: string; source_id: string; row_index: number; display_message?: string }, signal: AbortSignal) => post<DeepPlan>('recommend', payload, signal);
export async function analyzeNgFields(payload: { factory_id?: string; thread_id: string; plan_id: string; target_id: string; feature_ids: string[] }, signal: AbortSignal, onProgress?: (progress: DeepProgress) => void): Promise<DeepResult> {
  const response = await fetch(`${API_BASE}/api/bi/ng/deep/analyze/stream`, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json', ...getAuthHeaders() }, body: JSON.stringify(payload),
  });
  notifyBiHistory(response, payload.thread_id);
  handleUnauthorized(response);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? body?.error ?? `深度分析失败 (${response.status})`);
  }
  if (!response.headers.get('content-type')?.includes('application/x-ndjson')) throw new Error('后端未返回取数进度流，请确认后端已更新');
  try { return await readDeepStream(response, signal, onProgress); }
  finally { notifyBiHistory(response, payload.thread_id); }
}
