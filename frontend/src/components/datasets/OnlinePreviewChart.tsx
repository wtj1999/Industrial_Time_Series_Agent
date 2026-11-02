import { useMemo, useState } from 'react';
import type { CSVPreview, DatasetTablePreview } from '@/types';
import { CsvPreviewBody } from '@/components/csv_preview/CsvPreviewCard';
import { ColumnChips } from '@/components/analysis_chart/shared';
import { cn } from '@/utils/cn';

const MAX_GROUPS = 6;

export function OnlinePreviewChart({ preview }: { preview: DatasetTablePreview }) {
  const metadata = preview.column_metadata ?? [];
  const numeric = metadata.filter((column) => column.chartable).map((column) => column.name);
  const dimensions = metadata.filter((column) => column.filterable && new Set(preview.rows.map((row) => row[preview.columns.indexOf(column.name)])).size > 1).map((column) => column.name);
  // Start with every varying string dimension: never silently join different categories.
  // Users can exclude identifiers or descriptive text that do not identify a series.
  const [groupFields, setGroupFields] = useState<string[]>(dimensions);
  const [metric, setMetric] = useState(numeric[0] ?? '');
  const temporal = metadata.filter((column) => column.temporal).map((column) => column.name);
  const [timeColumn, setTimeColumn] = useState('insert_time');
  const activeMetric = numeric.includes(metric) ? metric : numeric[0] ?? '';
  const fields = groupFields.filter((field) => dimensions.includes(field));
  const fieldKey = JSON.stringify(fields);
  const timeIndex = preview.columns.indexOf(timeColumn);
  const groups = useMemo(() => {
    const chosenFields: string[] = JSON.parse(fieldKey);
    const indices = chosenFields.map((field) => preview.columns.indexOf(field));
    const grouped = new Map<string, { label: string; rows: DatasetTablePreview['rows'] }>();
    // Backend returns newest first; reverse for chronological insertion order.
    for (const row of [...preview.rows].reverse()) {
      const values = indices.map((index) => row[index]);
      const key = JSON.stringify(values);
      if (!grouped.has(key)) grouped.set(key, { label: chosenFields.map((field, index) => `${field}：${values[index] === null ? 'NULL' : values[index] === '' ? '空字符串' : values[index]}`).join(' · '), rows: [] });
      grouped.get(key)!.rows.push(row);
    }
    // Sorting remains within each group, never across category boundaries.
    if (timeColumn !== 'insert_time') for (const group of grouped.values()) {
      group.rows.sort((a, b) => String(a[timeIndex] ?? '').localeCompare(String(b[timeIndex] ?? '')));
    }
    return [...grouped.entries()];
  }, [preview, fieldKey, timeColumn, timeIndex]);

  return <section aria-label="在线数据曲线" className="rounded-2xl border border-steel-200/80 bg-white px-4 py-3 shadow-sm">
    <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-[11px] font-semibold uppercase tracking-wider text-steel-500">数据预览</p><h3 className="mt-0.5 text-[13px] font-medium text-steel-800">筛选结果曲线</h3></div><span className="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] text-brand-700">最近 {preview.preview_rows} 条匹配记录</span></div>
    <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-steel-500"><span>横轴时间</span><select aria-label="曲线时间字段" value={timeColumn} onChange={(event) => setTimeColumn(event.target.value)} className="rounded-md border border-steel-200 bg-white px-2 py-1 text-steel-700">{[...new Set(['insert_time', ...temporal])].map((column) => <option key={column}>{column}</option>)}</select></div>
    {dimensions.length > 0 && <div className="mt-3"><p className="mb-1.5 text-[11px] text-steel-500">按字符列分组 · 每个组合单独绘制，可取消无需区分的列（如唯一编号）</p><div className="flex flex-wrap gap-1.5">{dimensions.map((field) => <button key={field} type="button" aria-pressed={fields.includes(field)} onClick={() => setGroupFields((current) => fields.includes(field) ? current.filter((name) => name !== field) : [...current, field])} className={cn('rounded-md border px-2 py-0.5 text-[11px] font-medium transition-all', fields.includes(field) ? 'border-brand-500 bg-brand-500 text-white shadow-soft' : 'border-steel-200 text-steel-600 hover:border-brand-300')}>{field}</button>)}</div></div>}
    {numeric.length > 0 ? <><div className="mt-3 text-[11px] text-steel-500">选择指标</div><ColumnChips columns={numeric} activeColumn={activeMetric} onChange={setMetric} />
      {groups.length > MAX_GROUPS ? <div role="status" className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-700">当前有 {groups.length} 个类别组合。最多同时绘制 {MAX_GROUPS} 组，请在表头缩小筛选范围，或取消无需分组的列。</div>
        : groups.map(([key, group]) => {
          const metricIndex = preview.columns.indexOf(activeMetric);
          const chart: CSVPreview = {
            file_name: preview.file_name, total_rows: group.rows.length, preview_rows: group.rows.length,
            columns: [{ name: activeMetric, kind: 'numeric', chartable: true }],
            index: group.rows.map((_, index) => index),
            series: { [activeMetric]: group.rows.map((row) => {
              const value = row[metricIndex];
              if (value === null || value === undefined || value === '') return null;
              const numericValue = Number(value);
              return Number.isFinite(numericValue) ? numericValue : null;
            }) },
          };
          return <div key={key} className="mt-3 border-t border-steel-100 pt-3"><p className="break-all text-[11px] font-medium text-steel-700">{group.label || '当前筛选结果'}<span className="ml-2 font-normal text-steel-400">{group.rows.length} 条</span></p><CsvPreviewBody preview={chart} showColumnChips={false} indexLabels={group.rows.map((row) => String(row[timeIndex] ?? '时间缺失'))} /></div>;
        })}</> : <p className="py-10 text-center text-xs text-steel-500">当前表没有可绘图的数值列。</p>}
    {dimensions.length > 0 && fields.length === 0 && <p className="mt-2 text-[11px] text-amber-700">当前未分组，记录中仍有不同字符值。请确认它们属于同一条序列，或选择必要的分组列。</p>}
    <p className="mt-2 border-t border-steel-100 pt-2 text-[10px] text-steel-400">曲线按组内时间升序排列 · 横轴为记录时间标签，点间距按记录顺序均匀排列 · null 值形成空隙 · 统计仅基于当前预览记录{preview.has_more ? '，不代表全部匹配数据' : ''}</p>
  </section>;
}
