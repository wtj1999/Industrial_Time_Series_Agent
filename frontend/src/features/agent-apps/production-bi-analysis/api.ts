import { API_BASE } from '@/services/api';
import { getUserId } from '@/utils/user';
import type { BiQueryPayload, BiResponse } from './types';

export async function queryProductionBi(
  payload: BiQueryPayload,
  signal?: AbortSignal,
): Promise<BiResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/bi/query`, {
      method: 'POST',
      signal,
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': getUserId(),
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    throw new Error('网络错误，请确认生产 BI 服务已启动');
  }

  const body = await response.json().catch(() => null) as
    | (BiResponse & { detail?: string; error?: string })
    | null;
  if (!response.ok || !body) {
    throw new Error(body?.detail ?? body?.error ?? `生产 BI 查询失败 (${response.status})`);
  }
  if (typeof body.status !== 'string' || typeof body.thread_id !== 'string') {
    throw new Error('生产 BI 服务返回的数据格式不正确');
  }
  return body;
}

