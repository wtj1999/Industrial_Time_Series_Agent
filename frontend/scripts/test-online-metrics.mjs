import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/components/datasets/onlineMetrics.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } });
const { createMetricsQueue, formatMetricPercent, formatMetricFreshness, formatMetricTime } = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputText).toString('base64')}`);

const now = Date.parse('2026-10-22T12:00:00+08:00');
const metrics = { sample_rows: 100, checked_at: '2026-10-22T12:00:00+08:00', freshness_seconds: 900 };
assert.equal(formatMetricPercent(98.555), '98.56%');
assert.equal(formatMetricPercent(0), '0%');
assert.equal(formatMetricPercent(null), '—');
assert.equal(formatMetricFreshness(metrics, now), '15分钟前');
assert.equal(formatMetricFreshness(metrics, now + 3600_000), '1小时前');
assert.equal(formatMetricFreshness({ ...metrics, sample_rows: 0 }, now), '暂无数据');
assert.equal(formatMetricFreshness({ ...metrics, freshness_seconds: null }, now), '无有效时间');
assert.equal(formatMetricFreshness({ ...metrics, freshness_seconds: -3600 }, now), '时间超前');
assert.equal(formatMetricFreshness({ ...metrics, freshness_seconds: 0 }, now), '刚更新');
assert.equal(formatMetricFreshness({ ...metrics, freshness_seconds: 86400 * 3 }, now), '3天前');
assert.match(formatMetricTime('2026-10-22T04:00:00Z'), /12:00:00/);
assert.equal(formatMetricTime('invalid'), '无有效入库时间');

const enqueue = createMetricsQueue(2);
const controllers = Array.from({ length: 5 }, () => new AbortController());
const releases = [];
const started = [];
let active = 0;
let maxActive = 0;
const jobs = controllers.map((controller, index) => enqueue(() => {
  started.push(index);
  active += 1;
  maxActive = Math.max(maxActive, active);
  return new Promise((resolve) => releases.push(() => { active -= 1; resolve(index); }));
}, controller.signal).catch((error) => error.name));
await new Promise(setImmediate);
assert.deepEqual(started, [0, 1]);
controllers[2].abort();
releases.shift()();
await new Promise(setImmediate);
assert.deepEqual(started, [0, 1, 3]);
releases.shift()();
await new Promise(setImmediate);
assert.deepEqual(started, [0, 1, 3, 4]);
while (releases.length) releases.shift()();
assert.deepEqual(await Promise.all(jobs), [0, 1, 'AbortError', 3, 4]);
assert.equal(maxActive, 2);

const failureQueue = createMetricsQueue(1);
const controller = new AbortController();
const failed = failureQueue(() => Promise.reject(new Error('offline')), controller.signal).catch((error) => error.message);
const next = failureQueue(() => Promise.resolve('recovered'), controller.signal);
assert.deepEqual(await Promise.all([failed, next]), ['offline', 'recovered']);
console.log('Online metric checks passed: percentages, timezones, empty/future times, aging, bounded concurrency, cancellation and failure recovery.');
