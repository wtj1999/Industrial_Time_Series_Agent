import { useEffect, useRef, useState } from 'react';
import * as api from '@/services/api';
import { getAuthHeaders, handleUnauthorized } from '@/utils/user';
import type { DatasetEntry, OnlineSource } from '@/types';
import './AgentDataSelector.css';

export function AgentDataSelector({ value, uploadedFile, csvOnly = false, fieldClassName, onChange }: {
  value: string; uploadedFile: File | null; csvOnly?: boolean; fieldClassName: string;
  onChange: (dataset: DatasetEntry | null, file?: File) => void;
}) {
  const [kind, setKind] = useState('offline');
  const [group, setGroup] = useState('private');
  const [sources, setSources] = useState<OnlineSource[]>([]);
  const [options, setOptions] = useState<DatasetEntry[]>([]);
  const [selected, setSelected] = useState('');
  const [loading, setLoading] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);
  const request = useRef<AbortController | null>(null);
  const preparedFile = useRef<File | null>(null);
  const callback = useRef(onChange);
  callback.current = onChange;

  function reset() {
    request.current?.abort(); request.current = null;
    setSelected(''); setError(''); setPreparing(false); preparedFile.current = null;
    callback.current(null);
  }
  useEffect(() => {
    let alive = true;
    setLoading(true); setError(''); setOptions([]);
    const load = async () => {
      if (kind === 'online') {
        const result = await api.listOnlineSources();
        if (!alive) return;
        setSources(result.sources);
        if (!group) return;
        const tables = await api.listOnlineTables(group);
        if (alive) setOptions(tables.tables.map(table => ({ name: table.name, file_name: table.table_name, extension: 'csv', size_bytes: 0, modified_at: '' })));
      } else {
        const result = await (group === 'public' ? api.listPublicDatasets() : api.listDatasets());
        if (alive) setOptions(result.datasets.filter(item => !csvOnly || item.extension.toLowerCase() === 'csv'));
      }
    };
    void load().catch(err => { if (alive) setError(err instanceof Error ? err.message : '读取数据列表失败'); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; request.current?.abort(); };
  }, [kind, group, csvOnly, version]);
  useEffect(() => {
    // A newly uploaded file takes precedence over any pending selection.
    if (uploadedFile && uploadedFile !== preparedFile.current) {
      request.current?.abort(); setSelected(''); setPreparing(false); setError('');
    } else if (!value && !uploadedFile && !request.current) setSelected('');
  }, [value, uploadedFile]);
  useEffect(() => () => request.current?.abort(), []);

  async function choose(name: string) {
    reset(); setSelected(name);
    const dataset = options.find(item => item.file_name === name);
    if (!dataset) return;
    if (kind === 'offline' && group === 'private') { callback.current(dataset); return; }
    const controller = new AbortController(); request.current = controller;
    setPreparing(true);
    try {
      const response = await fetch(`${api.API_BASE}/api/data-selection`, {
        method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(kind === 'online' ? { kind: 'online', source_id: group, table_name: name } : { kind: 'public', file_name: name }),
      });
      handleUnauthorized(response);
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(typeof body?.detail === 'string' ? body.detail : '数据读取失败，请重试');
      }
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      if (blob.size > 100 * 1024 * 1024) throw new Error('数据大小不能超过 100MB');
      const file = new File([blob], kind === 'online' ? `${dataset.name.replace(/[\\/]/g, '_')}.csv` : dataset.file_name, { type: blob.type });
      preparedFile.current = file;
      callback.current(dataset, file);
    } catch (err) {
      if (!controller.signal.aborted) { setError(err instanceof Error ? err.message : '数据读取失败'); setSelected(''); }
    } finally {
      if (request.current === controller) { request.current = null; setPreparing(false); }
    }
  }

  return <div className="agent-data-selector" aria-label="任务数据选择">
    <div className="agent-data-selector-fields">
      <label><span>数据源类型</span><select aria-label="数据源类型" className={fieldClassName} value={kind} onChange={e => { reset(); setKind(e.target.value); setGroup(e.target.value === 'online' ? '' : 'private'); }}><option value="offline">离线数据源</option><option value="online">在线数据源</option></select></label>
      <label><span>{kind === 'online' ? '基地' : '数据分类'}</span><select aria-label="基地或数据分类" className={fieldClassName} value={group} onChange={e => { reset(); setGroup(e.target.value); }}>
        {kind === 'online' ? <><option value="">请选择基地</option>{sources.map(source => <option key={source.id} value={source.id}>{source.name}</option>)}</> : <><option value="private">私有数据</option><option value="public">公共数据</option></>}
      </select></label>
      <label><span>{kind === 'online' ? '数据表' : '数据文件'}</span><select aria-label="具体表或文件" className={fieldClassName} value={selected} disabled={loading || kind === 'online' && !group} onChange={e => void choose(e.target.value)}>
        <option value="">{loading ? '正在加载…' : preparing ? '正在读取数据…' : kind === 'online' && !group ? '请先选择基地' : options.length ? '请选择数据' : '暂无可用数据'}</option>
        {options.map(item => <option key={item.file_name} value={item.file_name}>{item.name}</option>)}
      </select></label>
    </div>
    {kind === 'online' && <p>默认读取按入库时间最近的 5,000 条记录（不足则全部读取），按时间升序用于分析。</p>}
    {preparing && <p role="status">正在读取任务数据，请稍候…</p>}
    {error && <p role="alert">{error} <button type="button" onClick={() => { const name = selected; reset(); if (name) void choose(name); else setVersion(v => v + 1); }}>重试</button></p>}
  </div>;
}
