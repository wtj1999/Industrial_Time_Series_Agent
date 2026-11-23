import type { DeepFeatureResult, PortraitRow, TargetPortrait } from './deepTypes';

export type TargetDimension = keyof TargetPortrait['dimensions'];
export interface TargetGroupColumn {
  key: string;
  label: string;
  members: Array<{ row: PortraitRow; index: number; shift: string | null }>;
}

// Keep a device's shifts together, including unknown shifts and identical device names on different lines.
export function targetGroupColumns(rows: PortraitRow[], dimension: TargetDimension, devices: PortraitRow[] = []): TargetGroupColumn[] {
  if (dimension !== 'device_shift') return rows.map((row, index) => ({
    key: JSON.stringify(row.key), label: row.label,
    members: [{ row, index, shift: dimension === 'shift' ? row.key[0] ?? row.label : null }],
  }));
  const deviceLabels = new Map(devices.map(row => [JSON.stringify(row.key), row.label]));
  const multipleLines = new Set(rows.map(row => JSON.stringify(row.key.slice(0, -2)))).size > 1;
  const columns = new Map<string, TargetGroupColumn>();
  rows.forEach((row, index) => {
    const identity = row.key.slice(0, -1), key = JSON.stringify(identity);
    if (!columns.has(key)) columns.set(key, { key,
      label: deviceLabels.get(key) ?? (multipleLines ? identity.join(' · ') : identity.at(-1)) ?? '未知设备', members: [] });
    columns.get(key)!.members.push({ row, index, shift: row.key.at(-1) ?? '未知班次' });
  });
  return [...columns.values()];
}

export function targetIntervalBubble(row: PortraitRow): NonNullable<DeepFeatureResult['bubble']> {
  // Every valid target product has exactly one value. Preserve the recorded bin counts and edges.
  const bins = (row.histogram ?? []).map((bin, index) => {
    const count = bin.NG + bin.OK;
    return { ...bin, index, product_count: count, ng_rate: count ? bin.NG / count : null,
      source_record_count: count, upstream_code_count: 0, association_count: count };
  });
  return { strategy: 'equal_width', max_bins: bins.length, denominator: 'valid_target_products_within_interval',
    size_metric: 'product_count', range_min: bins[0]?.lower ?? null, range_max: bins.at(-1)?.upper ?? null,
    covered_products: bins.reduce((total, bin) => total + bin.product_count, 0), bins };
}
