import { SAMPLE_WINDOWS } from '../signalSamples';
export interface ArchiveRecord {
  id: string;
  title: string;
  en: string;
  department: string;
  category: string;
  date: string;
  lead: string;
  clearance: string;
  abstract: string;
  findings: string[];
  source: string;
}

export const archiveColumns = ['温度', '电流', '振动', '压力', '转速'];
export const records: ArchiveRecord[] = archiveColumns.flatMap((category, lane) => SAMPLE_WINDOWS.map((sample, row) => ({
  id: `TS-${lane + 1}-${row + 1}`, title: sample.name, en: `${sample.time} — ${sample.end}`,
  department: '伺服电机 · 演示数据', category, date: sample.time, lead: '工业时序智能体',
  clearance: '示例', abstract: sample.note, findings: [], source: '模拟采样'
})));
export const categories = ["全部信号", ...archiveColumns];


export function columnFiles(lane: number) {
  return records
    .map((record, index) => ({ record, index }))
    .filter(({ record }) => record.category === archiveColumns[lane])
    .map(({ index }) => index);
}
export function fileLocation(index: number) {
  const lane = archiveColumns.indexOf(records[index].category);
  const row = 12 + columnFiles(lane).indexOf(index);
  return { lane, row, slot: lane * 32 + row };
}
export function fileAtSlot(slot: number) {
  const files = columnFiles(Math.floor(slot / 32));
  return files[Math.max(0, Math.min(files.length - 1, (slot % 32) - 12))];
}
