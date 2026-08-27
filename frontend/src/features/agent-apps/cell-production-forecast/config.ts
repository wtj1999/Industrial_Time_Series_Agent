import { FORECAST_MODELS, type ForecastModel } from '@/features/agent-apps/battery-installation-forecast/config';

export const CELL_PRODUCTION_FORECAST_AGENT = {
  id: 'cell-production-forecast',
  name: '锂电电芯产量预测智能体',
  domain: '生产域',
  description: '结合历史产量、产线运行与质量数据，预测未来电芯产量及潜在产能缺口。',
  supportedExtensions: ['csv', 'xlsx', 'parquet'],
} as const;

export { FORECAST_MODELS };
export type { ForecastModel };

export type ProductionForecastGranularity = '日度' | '周度' | '月度';

export const CELL_SEGMENTS = [
  '方形电芯',
  '圆柱电芯',
  '软包电芯',
  '动力电芯',
  '储能电芯',
];

export const PRODUCTION_EXTERNAL_VARIABLES = [
  '计划排产量',
  '设备综合效率（OEE）',
  '开工率',
  '良品率',
  '原材料到货量',
];

export const DEFAULT_PRODUCTION_REQUIREMENTS =
  '输出点预测、置信区间、产量趋势解读、环比变化、产能缺口及主要生产风险提示。';

export interface CellProductionForecastTask {
  model: ForecastModel;
  granularity: ProductionForecastGranularity;
  horizon: number;
  cellSegments: string[];
  externalVariables: string[];
  additionalRequirements: string;
}

export function buildCellProductionForecastQuery(task: CellProductionForecastTask): string {
  const periodUnit = { 日度: '天', 周度: '周', 月度: '月' }[task.granularity];
  const segments = task.cellSegments.length > 0 ? task.cellSegments.join('、') : '全部电芯';
  const externalVariables = task.externalVariables.length > 0
    ? task.externalVariables.join('、')
    : '不指定，由系统根据数据字段自动判断';
  const additionalRequirements = task.additionalRequirements.trim()
    || DEFAULT_PRODUCTION_REQUIREMENTS;

  return [
    '请执行锂电电芯产量时间序列预测任务。',
    `预测目标：锂电电芯产量；指定预测模型：${task.model}；时间粒度：${task.granularity}。`,
    `预测未来 ${task.horizon} 个${periodUnit}。`,
    `分析维度：${segments}。`,
    `可参考的外生变量：${externalVariables}。`,
    `补充要求：${additionalRequirements}。`,
  ].join('\n');
}
