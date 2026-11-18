import type { DeepProgress, DeepResult } from './deepTypes';

export async function readDeepStream(response: Response, signal: AbortSignal, onProgress?: (progress: DeepProgress) => void): Promise<DeepResult> {
  if (!response.body) throw new Error('深度分析没有返回数据流');
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let last: DeepProgress | undefined;
  let result: DeepResult | undefined;
  const aborted = () => { if (signal.aborted) throw new DOMException('分析已停止', 'AbortError'); };
  const dispatch = (line: string) => {
    if (!line.trim()) return;
    aborted();
    let event;
    try { event = JSON.parse(line); } catch { throw new Error('深度分析进度数据格式异常，请重试'); }
    if (event.type === 'error') throw new Error(event.message || '深度分析未完成');
    if (event.type === 'progress') {
      if (typeof event.data?.message !== 'string' || typeof event.data?.stage !== 'string'
        || !Number.isInteger(event.data?.sequence) || !Number.isFinite(event.data?.elapsed_seconds)) throw new Error('深度分析进度数据不完整');
      last = event.data as DeepProgress;
      onProgress?.(last);
    } else if (event.type === 'heartbeat' && last && Number.isFinite(event.elapsed_seconds)) {
      last = { ...last, elapsed_seconds: event.elapsed_seconds };
      onProgress?.(last);
    } else if (event.type === 'result') {
      if (event.data?.status !== 'success') throw new Error('深度分析结果不完整');
      result = event.data as DeepResult;
    }
  };
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener('abort', cancel, { once: true });
  try {
    aborted();
    while (!result) {
      const chunk = await reader.read();
      aborted();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      let index = buffer.indexOf('\n');
      while (index >= 0 && !result) {
        const line = buffer.slice(0, index); buffer = buffer.slice(index + 1);
        dispatch(line); index = buffer.indexOf('\n');
      }
      if (chunk.done) { if (!result && buffer.trim()) dispatch(buffer); break; }
    }
    if (!result) throw new Error('深度分析数据流在完成前中断，请重新提交分析');
    return result;
  } finally {
    signal.removeEventListener('abort', cancel);
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
