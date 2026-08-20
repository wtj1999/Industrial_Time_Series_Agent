export const BATTERY_INSTALLATION_AGENT = {
  id: 'battery-installation-forecast',
  name: '动力电池装车量预测智能体',
  domain: '市场域',
  description: '基于历史装车量与市场数据，分析变化趋势并预测未来动力电池装车量。',
  supportedExtensions: ['csv', 'xlsx', 'parquet'],
} as const;

export type ForecastGranularity = '月度' | '季度';
export type ForecastModel =
  | 'sundial'
  | 'toto-2'
  | 'timer-s1'
  | 'chronos-2'
  | 'timesfm-2.5'
  | 'moirai-2.0'
  | 'tirex-1.1';

export const FORECAST_MODELS: ForecastModel[] = [
  'sundial',
  'toto-2',
  'timer-s1',
  'chronos-2',
  'timesfm-2.5',
  'moirai-2.0',
  'tirex-1.1',
];

export const DEFAULT_ADDITIONAL_REQUIREMENTS =
  '输出点预测、置信区间、趋势解读、同比或环比变化以及主要风险提示。';

export interface BatteryForecastTask {
  model: ForecastModel;
  granularity: ForecastGranularity;
  horizon: number;
  batteryTypes: string[];
  externalVariables: string[];
  additionalRequirements: string;
}

export function buildBatteryForecastQuery(task: BatteryForecastTask): string {
  const periodUnit = task.granularity === '月度' ? '月' : '季度';
  const batteryTypes = task.batteryTypes.length > 0
    ? task.batteryTypes.join('、')
    : '全部电池类型';
  const externalVariables = task.externalVariables.length > 0
    ? task.externalVariables.join('、')
    : '不指定，由系统根据数据字段自动判断';
  const additionalRequirements = task.additionalRequirements.trim() || DEFAULT_ADDITIONAL_REQUIREMENTS;

  return [
    '请执行动力电池装车量时间序列预测任务。',
    `预测目标：动力电池装车量；指定预测模型：${task.model}；时间粒度：${task.granularity}。`,
    `预测未来 ${task.horizon} 个${periodUnit}。`,
    `电池类型：${batteryTypes}。`,
    `可参考的外生变量：${externalVariables}。`,
    `补充要求：${additionalRequirements}。`,
  ].join('\n');
}
