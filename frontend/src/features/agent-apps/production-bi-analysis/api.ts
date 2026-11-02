import { API_BASE } from '@/services/api';
import { getAuthHeaders, handleUnauthorized } from '@/utils/user';
import type { BiOptionsPage, BiQueryPayload, BiResponse } from './types';

export async function queryProductionBi(
  payload: BiQueryPayload,
  signal?: AbortSignal,
  endpoint = '/api/bi/query',
): Promise<BiResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      signal,
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    throw new Error('网络错误，请确认生产 BI 服务已启动');
  }

  handleUnauthorized(response);
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

export async function queryNgOptions(
  payload: { thread_id: string; confirmation_id: string; field: string; search: string; offset: number },
  signal: AbortSignal,
): Promise<BiOptionsPage> {
  const response = await fetch(`${API_BASE}/api/bi/ng/options`, {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(payload),
  });
  handleUnauthorized(response);
  const body = await response.json().catch(() => null);
  if (!response.ok || !body) throw new Error(body?.detail ?? '无法加载筛选选项，请重试');
  return body as BiOptionsPage;
}

