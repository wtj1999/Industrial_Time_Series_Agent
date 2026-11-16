import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/components/announcements/feed.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } });
const module = { exports: {} };
new Function('exports', 'module', compiled.outputText)(module.exports, module);
const { parseAnnouncements, announcementDate, recentAnnouncements } = module.exports;
const path = new URL('../public/announcements.json', import.meta.url);
const raw = JSON.parse(await readFile(path, 'utf8'));
parseAnnouncements(raw);
console.log(`PASS: announcement feed format (${raw.items.length} entries).`);

// Check scheduling, draft visibility, ordering and unsafe/invalid content boundaries.
const entry = { id: 'test', title: '测试公告', publishedAt: '2026-01-01T00:00:00+08:00', category: 'agent', summary: '概述', details: ['更新内容'], target: '/agents' };
const feed = items => ({ schemaVersion: 1, items });
const now = Date.parse('2026-11-13T12:00:00+08:00');
assert.equal(parseAnnouncements(feed([{ ...entry, published: false }]), now).length, 0);
assert.equal(parseAnnouncements(feed([{ ...entry, publishedAt: '2099-01-01T00:00:00+08:00' }]), now).length, 0);
assert.deepEqual(parseAnnouncements(feed([entry, { ...entry, id: 'new', publishedAt: '2026-11-13T00:00:00+08:00' }]), now).map(item => item.id), ['new', 'test']);
for (const change of [{ category: '__proto__' }, { publishedAt: '2026-11-13' }, { details: 'not-array' }, { target: 'javascript:alert(1)' }, { id: 'bad id' }, { published: 'false' }]) assert.throws(() => parseAnnouncements(feed([{ ...entry, ...change }]), now));
assert.throws(() => parseAnnouncements(feed([entry, entry]), now));
assert.throws(() => parseAnnouncements({ schemaVersion: 2, items: [] }, now));
assert.deepEqual(parseAnnouncements(feed([])), []);
assert.equal(announcementDate('2026-11-12T16:00:00Z'), '2026/11/13');
console.log('PASS: drafts, scheduled dates, ordering, unique IDs, allowed links, malformed fields and Beijing dates.');
const recent = recentAnnouncements([
  { ...entry, id: 'boundary', publishedAt: '2026-11-07T00:00:00+08:00' },
  { ...entry, id: 'old', publishedAt: '2026-11-06T23:59:59+08:00' },
  { ...entry, id: 'today', publishedAt: '2026-11-13T11:59:59+08:00' },
  { ...entry, id: 'future', publishedAt: '2026-11-13T12:00:01+08:00' },
], now);
assert.deepEqual(recent.map(item => item.id), ['boundary', 'today']);
assert.equal(recentAnnouncements([{ ...entry, publishedAt: '2026-11-07T00:00:00+08:00' }], Date.parse('2026-11-14T00:00:00+08:00')).length, 0);
console.log('PASS: seven-day Beijing calendar window, exact boundary, future exclusion and midnight expiration.');
