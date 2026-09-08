import {
  FORECAST_MODELS,
  type ForecastModel,
} from '@/features/agent-apps/battery-installation-forecast/config';

export const CELL_SOH_FORECAST_AGENT = {
  id: 'cell-soh-forecast',
  name: '锂电电芯SOH预测智能体',
  domain: '市场域',
  description: '根据历史容量衰减序列，预测电芯达到目标SOH所需的循环圈数。',
  supportedExtensions: ['csv', 'xlsx', 'parquet'],
} as const;

export { FORECAST_MODELS };
export type { ForecastModel };

export const SOH_THRESHOLDS = [95, 90, 85, 80, 75, 70] as const;
export const CAPACITY_BASELINES = ['自动识别', '额定容量', '初始稳定容量'] as const;
export type CapacityBaseline = (typeof CAPACITY_BASELINES)[number];
export type CapacityUnit = 'Ah' | 'mAh';

export const DEFAULT_CELL_SOH_REQUIREMENTS =
  '输出容量衰减预测曲线、目标SOH的预计首次到达圈数、剩余可用圈数、置信区间、衰减趋势解读和主要不确定性；未可靠覆盖的阈值不要强行外推。';

export interface CellSohForecastTask {
  model: ForecastModel;
  sohThreshold: number;
  capacityBaseline: CapacityBaseline;
  nominalCapacity: number | null;
  capacityUnit: CapacityUnit;
  additionalRequirements: string;
}

export function buildCellSohForecastQuery(task: CellSohForecastTask): string {
  const extra = task.additionalRequirements.trim() || DEFAULT_CELL_SOH_REQUIREMENTS;
  const baseline = task.capacityBaseline === '额定容量'
    ? `额定容量（${task.nominalCapacity} ${task.capacityUnit}）`
    : task.capacityBaseline;

  return [
    '请执行锂电电芯SOH时间序列预测任务。',
    '预测目标：基于历史容量衰减序列，预测电芯达到设定SOH阈值所需的循环圈数。',
    `指定预测模型：${task.model}；SOH计算基准：${baseline}。`,
    `目标SOH阈值：${task.sohThreshold}%。`,
    '历史数据范围：默认使用上传文件中的全部有效历史容量衰减序列，不主动截取最近窗口。',
    '以循环序号或圈数作为时间轴，根据所选基准计算SOH；数据中已有SOH列时优先复用并校验其口径。',
    '请根据历史容量衰减速度、近期趋势和已完成循环数，自行估算覆盖目标SOH所需的预测输出步长，并留出合理裕量；不要要求用户预先提供时间粒度或预测周期。若单次预测无法覆盖目标阈值，请分段续推，直到达到阈值或确认无法可靠外推。',
    `补充要求：${extra}`,
  ].join('\n');
}
