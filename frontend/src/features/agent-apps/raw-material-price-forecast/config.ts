import {
  FORECAST_MODELS,
  type ForecastModel,
} from '@/features/agent-apps/battery-installation-forecast/config';

export const RAW_MATERIAL_PRICE_FORECAST_AGENT = {
  id: 'raw-material-price-forecast',
  name: '锂电原材料价格预测智能体',
  domain: '市场域',
  description: '结合历史价格与供需、库存和下游需求数据，预测锂电原材料价格走势。',
  supportedExtensions: ['csv', 'xlsx', 'parquet'],
} as const;

export { FORECAST_MODELS };
export type { ForecastModel };

export type RawMaterialForecastGranularity = '日度' | '周度' | '月度';

export const RAW_MATERIAL_CATEGORIES = [
  '电池级碳酸锂',
  '电池级氢氧化锂',
  '磷酸铁锂',
  '六氟磷酸锂',
  '硫酸镍',
  '硫酸钴',
  '硫酸锰',
];

export const RAW_MATERIAL_EXTERNAL_VARIABLES = [
  '国内产量',
  '港口与社会库存',
  '进口量',
  '动力电池装车量',
  '新能源汽车销量',
  '美元兑人民币汇率',
];

export const DEFAULT_RAW_MATERIAL_REQUIREMENTS =
  '输出点预测、置信区间、价格趋势解读、周期涨跌幅、供需驱动因素以及主要价格风险提示。';

export interface RawMaterialPriceForecastTask {
  model: ForecastModel;
  granularity: RawMaterialForecastGranularity;
  horizon: number;
  materialCategories: string[];
  externalVariables: string[];
  additionalRequirements: string;
}

export function buildRawMaterialPriceForecastQuery(task: RawMaterialPriceForecastTask): string {
  const periodUnit = { 日度: '天', 周度: '周', 月度: '个月' }[task.granularity];
  const categories = task.materialCategories.length > 0
    ? task.materialCategories.join('、')
    : '全部原材料';
  const externalVariables = task.externalVariables.length > 0
    ? task.externalVariables.join('、')
    : '不指定，由系统根据数据字段自动判断';
  const additionalRequirements = task.additionalRequirements.trim()
    || DEFAULT_RAW_MATERIAL_REQUIREMENTS;

  return [
    '请执行锂电原材料价格时间序列预测任务。',
    `预测目标：锂电原材料价格；指定预测模型：${task.model}；时间粒度：${task.granularity}。`,
    `预测未来 ${task.horizon} ${periodUnit}。`,
    `原材料品类：${categories}。`,
    `可参考的外生变量：${externalVariables}。`,
    `补充要求：${additionalRequirements}。`,
  ].join('\n');
}
