import { FORECAST_MODELS, type ForecastModel } from '@/features/agent-apps/battery-installation-forecast/config';
import type { ProductionForecastGranularity } from '@/features/agent-apps/cell-production-forecast/config';

export const FACTORY_ENERGY_FORECAST_AGENT = {
  id: 'factory-energy-forecast',
  name: '锂电工厂能耗预测智能体',
  domain: '生产域',
  description: '结合各工段、公共设备和生产负荷数据，预测工厂未来能耗及单位产量能耗变化。',
  supportedExtensions: ['csv', 'xlsx', 'parquet'],
} as const;

export { FORECAST_MODELS };
export type { ForecastModel, ProductionForecastGranularity };

export const ENERGY_SEGMENTS = [
  '一工段',
  '二工段',
  '三工段',
  'pack',
  '公共设备',
  '总计(千度)',
];

export const ENERGY_EXTERNAL_VARIABLES = [
  '电芯产量',
  'PACK产量',
  '开工时长',
  '设备负载率',
  '环境温度',
  '峰谷电价',
];

export const DEFAULT_ENERGY_REQUIREMENTS =
  '输出点预测、置信区间、能耗趋势解读、环比变化、单位产量能耗以及主要能耗风险提示。';

export interface FactoryEnergyForecastTask {
  model: ForecastModel;
  granularity: ProductionForecastGranularity;
  horizon: number;
  energySegments: string[];
  externalVariables: string[];
  additionalRequirements: string;
}

export function buildFactoryEnergyForecastQuery(task: FactoryEnergyForecastTask): string {
  const periodUnit = { 日度: '天', 周度: '周', 月度: '月' }[task.granularity];
  const segments = task.energySegments.length > 0 ? task.energySegments.join('、') : '总计(千度)';
  const externalVariables = task.externalVariables.length > 0
    ? task.externalVariables.join('、')
    : '不指定，由系统根据数据字段自动判断';
  const additionalRequirements = task.additionalRequirements.trim() || DEFAULT_ENERGY_REQUIREMENTS;

  return [
    '请执行锂电工厂能耗时间序列预测任务。',
    `预测目标：锂电工厂能耗；指定预测模型：${task.model}；时间粒度：${task.granularity}。`,
    `预测未来 ${task.horizon} 个${periodUnit}。`,
    `分析维度：${segments}。`,
    `可参考的外生变量：${externalVariables}。`,
    `补充要求：${additionalRequirements}。`,
  ].join('\n');
}
