import {
  DEFAULT_ADDITIONAL_REQUIREMENTS,
  FORECAST_MODELS,
  type ForecastGranularity,
  type ForecastModel,
} from '@/features/agent-apps/battery-installation-forecast/config';

export const NEW_ENERGY_VEHICLE_SALES_AGENT = {
  id: 'new-energy-vehicle-sales',
  name: '新能源汽车销量预测智能体',
  domain: '市场域',
  description: '基于历史销量与市场影响因素，预测新能源汽车未来销量及细分市场趋势。',
  supportedExtensions: ['csv', 'xlsx', 'parquet'],
} as const;

export { DEFAULT_ADDITIONAL_REQUIREMENTS, FORECAST_MODELS };
export type { ForecastGranularity, ForecastModel };

export const VEHICLE_SEGMENTS = ['BEV', 'PHEV', 'EREV', '乘用车', '商用车'];

export const VEHICLE_EXTERNAL_VARIABLES = [
  '新能源汽车产量',
  '动力电池装车量',
  '充电基础设施数量',
  '汽车出口量',
  '购置补贴与政策指标',
];

export interface VehicleSalesForecastTask {
  model: ForecastModel;
  granularity: ForecastGranularity;
  horizon: number;
  vehicleSegments: string[];
  externalVariables: string[];
  additionalRequirements: string;
}

export function buildVehicleSalesForecastQuery(task: VehicleSalesForecastTask): string {
  const periodUnit = task.granularity === '月度' ? '月' : '季度';
  const segments = task.vehicleSegments.length > 0
    ? task.vehicleSegments.join('、')
    : '全部车型';
  const externalVariables = task.externalVariables.length > 0
    ? task.externalVariables.join('、')
    : '不指定，由系统根据数据字段自动判断';
  const additionalRequirements = task.additionalRequirements.trim()
    || DEFAULT_ADDITIONAL_REQUIREMENTS;

  return [
    '请执行新能源汽车销量时间序列预测任务。',
    `预测目标：新能源汽车销量；指定预测模型：${task.model}；时间粒度：${task.granularity}。`,
    `预测未来 ${task.horizon} 个${periodUnit}。`,
    `分析维度：${segments}。`,
    `可参考的外生变量：${externalVariables}。`,
    `补充要求：${additionalRequirements}。`,
  ].join('\n');
}
