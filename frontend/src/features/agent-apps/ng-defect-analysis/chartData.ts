import type { BiGroupDimension, NgChartRow } from '../production-bi-analysis/types';

export interface NgPlotPoint {
  key: string;
  ng_type: string;
  label: string;
  total: number;
}

export interface NgChartCombination {
  key: string;
  label: string;
  fullLabel: string;
  total: number;
  dimensions: Record<string, string | null>;
  points: NgPlotPoint[];
}

function addCount(counts: Map<string, NgPlotPoint>, row: NgChartRow) {
  counts.set(row.ng_type, {
    key: JSON.stringify([row.ng_type]), ng_type: row.ng_type, label: row.ng_name,
    total: (counts.get(row.ng_type)?.total ?? 0) + row.ng_count,
  });
}

function sortedPoints(counts: Map<string, NgPlotPoint>): NgPlotPoint[] {
  return Array.from(counts.values()).sort((a, b) => b.total - a.total || a.label.localeCompare(b.label) || a.ng_type.localeCompare(b.ng_type));
}

function displayValue(value: string | null): string {
  return value === null ? '未填写' : value === '' ? '空值' : value;
}

export function buildNgChartData(rows: NgChartRow[], dimensions: BiGroupDimension[]): {
  points: NgPlotPoint[];
  combinations: NgChartCombination[];
  total: number;
} {
  const allCounts = new Map<string, NgPlotPoint>();
  const groups = new Map<string, { combination: NgChartCombination; counts: Map<string, NgPlotPoint> }>();
  let total = 0;
  for (const row of rows) {
    addCount(allCounts, row);
    total += row.ng_count;
    if (dimensions.length === 0) continue;

    const values = dimensions.map((dimension) => row.dimensions?.[dimension.field] ?? null);
    const key = JSON.stringify(values);
    let group = groups.get(key);
    if (!group) {
      group = {
        combination: {
          key, label: values.map(displayValue).join(' · '),
          fullLabel: dimensions.map((dimension, index) => `${dimension.label}：${displayValue(values[index])}`).join(' / '),
          total: 0, dimensions: Object.fromEntries(dimensions.map((dimension, index) => [dimension.field, values[index]])),
          points: [],
        },
        counts: new Map(),
      };
      groups.set(key, group);
    }
    group.combination.total += row.ng_count;
    addCount(group.counts, row);
  }

  const combinations = Array.from(groups.values()).map(({ combination, counts }) => ({ ...combination, points: sortedPoints(counts) }));
  combinations.sort((a, b) => {
    if (dimensions.some((dimension) => dimension.field === 'shift_date')) {
      const dateOrder = (a.dimensions.shift_date ?? '').localeCompare(b.dimensions.shift_date ?? '');
      if (dateOrder) return dateOrder;
    }
    return b.total - a.total || a.label.localeCompare(b.label);
  });
  return { points: sortedPoints(allCounts), combinations, total };
}
