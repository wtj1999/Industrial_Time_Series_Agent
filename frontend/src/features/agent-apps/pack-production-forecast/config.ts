import { FORECAST_MODELS, type ForecastModel } from '@/features/agent-apps/battery-installation-forecast/config';
import type { ProductionForecastGranularity } from '@/features/agent-apps/cell-production-forecast/config';

export const PACK_PRODUCTION_FORECAST_AGENT = {
  id: 'pack-production-forecast',
  name: '锂电PACK产量预测智能体',
  domain: '生产域',
  description: '结合电芯齐套、PACK产线运行与质量数据，预测未来PACK产量及产能缺口。',
  supportedExtensions: ['csv', 'xlsx', 'parquet'],
} as const;

export { FORECAST_MODELS };
export type { ForecastModel, ProductionForecastGranularity };

export const PACK_SEGMENTS = [
  '乘用车PACK',
  '商用车PACK',
  '储能PACK',
  '换电PACK',
  '特种车辆PACK',
];

export const PACK_EXTERNAL_VARIABLES = [
  '计划排产量',
  '电芯齐套量',
  'PACK产线OEE',
  '一次合格率',
  'BMS与结构件到货量',
];

export const DEFAULT_PACK_REQUIREMENTS =
  '输出点预测、置信区间、PACK产量趋势解读、环比变化、产能缺口及主要生产风险提示。';

export interface PackProductionForecastTask {
  model: ForecastModel;
  granularity: ProductionForecastGranularity;
  horizon: number;
  packSegments: string[];
  externalVariables: string[];
  additionalRequirements: string;
}

export function buildPackProductionForecastQuery(task: PackProductionForecastTask): string {
  const periodUnit = { 日度: '天', 周度: '周', 月度: '月' }[task.granularity];
  const segments = task.packSegments.length > 0 ? task.packSegments.join('、') : '全部PACK产品';
  const externalVariables = task.externalVariables.length > 0
    ? task.externalVariables.join('、')
    : '不指定，由系统根据数据字段自动判断';
  const additionalRequirements = task.additionalRequirements.trim() || DEFAULT_PACK_REQUIREMENTS;

  return [
    '请执行锂电PACK产量时间序列预测任务。',
    `预测目标：锂电PACK产量；指定预测模型：${task.model}；时间粒度：${task.granularity}。`,
    `预测未来 ${task.horizon} 个${periodUnit}。`,
    `分析维度：${segments}。`,
    `可参考的外生变量：${externalVariables}。`,
    `补充要求：${additionalRequirements}。`,
  ].join('\n');
}
