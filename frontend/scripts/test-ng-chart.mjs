import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

// chartData has no runtime dependencies. Exercise the exact shipped TypeScript
// transform without adding a browser/test-framework dependency to the application.
const source = await readFile(new URL('../src/features/agent-apps/ng-defect-analysis/chartData.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } });
const { buildNgChartData } = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputText).toString('base64')}`);
const row = (ng_type, ng_name, ng_count, dimensions = {}) => ({ ng_type, ng_name, ng_count, dimensions });
const sum = (points, key) => points.reduce((total, point) => total + Number(point[key] ?? 0), 0);

const original = buildNgChartData([row('A', '外观', 2), row('B', '尺寸', 7)], []);
assert.deepEqual(original.points.map((point) => point.label), ['尺寸', '外观']);
assert.equal(sum(original.points, 'total'), 9);

const device = [{ field: 'device_name', label: '设备' }];
const grouped = buildNgChartData([
  row('A', '电压超上限', 2, { device_name: '设备1' }),
  row('B', '电压超上限', 3, { device_name: '设备1' }),
  row('A', '电压超上限', 7, { device_name: '设备2' }),
  row('C', '外观', 1, { device_name: '设备2' }),
], device);
assert.equal(grouped.points.length, 3);
assert.equal(sum(grouped.points, 'total'), 13);
assert.equal(grouped.total, 13);
assert.equal(grouped.combinations.length, 2);
assert.deepEqual(grouped.points.map((point) => [point.ng_type, point.total]), [['A', 9], ['B', 3], ['C', 1]]);
assert.equal(grouped.points.filter((point) => point.label === '电压超上限').length, 2);
const device1 = grouped.combinations.find((combination) => combination.dimensions.device_name === '设备1');
const device2 = grouped.combinations.find((combination) => combination.dimensions.device_name === '设备2');
assert.deepEqual(device1.points.map((point) => [point.ng_type, point.total]), [['B', 3], ['A', 2]]);
assert.deepEqual(device2.points.map((point) => [point.ng_type, point.total]), [['A', 7], ['C', 1]]);
assert.equal(grouped.combinations.reduce((total, combination) => total + combination.total, 0), grouped.total);
for (const combination of grouped.combinations) {
  assert.equal(sum(combination.points, 'total'), combination.total);
}

const dates = buildNgChartData([
  row('A', '外观', 100, { shift_date: '2026-10-10' }),
  row('A', '外观', 1, { shift_date: '2026-10-09' }),
], [{ field: 'shift_date', label: '日期' }]);
assert.deepEqual(dates.combinations.map((combination) => combination.label), ['2026-10-09', '2026-10-10']);
assert.equal(dates.points.length, 1);
assert.equal(dates.points[0].total, 101);

const nullAndEmpty = buildNgChartData([
  row('A', '外观', 1, { device_name: null }), row('A', '外观', 2, { device_name: '' }),
], device);
assert.equal(nullAndEmpty.combinations.length, 2);
assert.equal(new Set(nullAndEmpty.combinations.map((combination) => combination.key)).size, 2);

const combined = buildNgChartData([
  row('A', '外观', 2, { device_name: 'a|b', technics_process_name: 'c' }),
  row('A', '外观', 3, { device_name: 'a', technics_process_name: 'b|c' }),
], [...device, { field: 'technics_process_name', label: '工序' }]);
assert.equal(combined.combinations.length, 2);
assert.equal(sum(combined.points, 'total'), 5);
assert.equal(buildNgChartData([], device).points.length, 0);
assert.equal(buildNgChartData([], device).combinations.length, 0);
const manyTypes = buildNgChartData(Array.from({ length: 25 }, (_, index) => row(`NG${index}`, `不良${index}`, index + 1, { device_name: '设备1' })), device);
assert.equal(manyTypes.combinations[0].points.length, 25);
assert.equal(manyTypes.combinations[0].total, 325);
const manyCombinations = buildNgChartData(Array.from({ length: 96 }, (_, index) => row('A', '外观', 1, { device_name: `设备${index}` })), device);
assert.equal(manyCombinations.combinations.length, 96);
assert.equal(manyCombinations.points[0].total, 96);
console.log('NG chart checks passed: per-combination NG distributions, all-combination totals, duplicate names, date ordering, nulls, all NG types, all combinations, empty results.');
