import {
  DEFAULT_ADDITIONAL_REQUIREMENTS,
  FORECAST_MODELS,
  type ForecastGranularity,
  type ForecastModel,
} from '@/features/agent-apps/battery-installation-forecast/config';

export interface VehicleSalesAgent {
  id: string;
  name: string;
  domain: '市场域';
  description: string;
  target: string;
  brand?: string;
  vehicleModels?: readonly string[];
  supportedExtensions: readonly string[];
}

export const NEW_ENERGY_VEHICLE_SALES_AGENT = {
  id: 'new-energy-vehicle-sales',
  name: '新能源汽车销量预测智能体',
  domain: '市场域',
  description: '基于历史销量与市场影响因素，预测新能源汽车未来销量及细分市场趋势。',
  target: '新能源汽车销量',
  supportedExtensions: ['csv', 'xlsx', 'parquet'],
} as const satisfies VehicleSalesAgent;

export const BRAND_VEHICLE_SALES_AGENTS = [
  {
    id: 'leapmotor-sales-forecast', name: '零跑汽车销量预测智能体', brand: '零跑汽车',
    target: '零跑汽车销量', domain: '市场域',
    vehicleModels: ['C01', 'C10', 'C11', 'C16', 'B01', 'B10', 'T03'],
    description: '基于零跑汽车历史销量与市场影响因素，预测未来销量及车型变化趋势。',
    supportedExtensions: ['csv', 'xlsx', 'parquet'],
  },
  {
    id: 'geely-sales-forecast', name: '吉利汽车销量预测智能体', brand: '吉利汽车',
    target: '吉利汽车销量', domain: '市场域',
    vehicleModels: ['星瑞', '星越L', '帝豪', '博越L', '缤越', '豪越L', '吉利星愿'],
    description: '基于吉利汽车历史销量与市场影响因素，预测未来销量及车型变化趋势。',
    supportedExtensions: ['csv', 'xlsx', 'parquet'],
  },
  {
    id: 'great-wall-sales-forecast', name: '长城汽车销量预测智能体', brand: '长城汽车',
    target: '长城汽车销量', domain: '市场域',
    vehicleModels: ['哈弗H6', '哈弗大狗', '坦克300', '坦克500', '魏牌蓝山', '魏牌高山', '欧拉好猫', '长城炮'],
    description: '基于长城汽车历史销量与市场影响因素，预测未来销量及车型变化趋势。',
    supportedExtensions: ['csv', 'xlsx', 'parquet'],
  },
] as const satisfies readonly VehicleSalesAgent[];

export const VEHICLE_SALES_AGENTS: readonly VehicleSalesAgent[] = [
  NEW_ENERGY_VEHICLE_SALES_AGENT, ...BRAND_VEHICLE_SALES_AGENTS,
];

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

export function buildVehicleSalesForecastQuery(task: VehicleSalesForecastTask, agent: VehicleSalesAgent = NEW_ENERGY_VEHICLE_SALES_AGENT): string {
  const periodUnit = task.granularity === '月度' ? '月' : '季度';
  const segments = task.vehicleSegments.length > 0
    ? task.vehicleSegments.join('、')
    : '全部车型';
  const externalVariables = task.externalVariables.length > 0
    ? task.externalVariables.join('、')
    : '不指定，由系统根据数据字段自动判断';
  const additionalRequirements = task.additionalRequirements.trim()
    || DEFAULT_ADDITIONAL_REQUIREMENTS;

  const brandScope = agent.brand ? [
    `品牌范围：仅分析${agent.brand}销量；若数据包含多个品牌，须确认并筛选对应品牌，不能以全行业销量或其他品牌销量代替。`
      + '无法确认品牌范围或缺少对应数据时，请用户提供该品牌的历史销量数据，不编造数据。',
  ] : [];
  return [
    `请执行${agent.target}时间序列预测任务。`,
    `预测目标：${agent.target}；指定预测模型：${task.model}；时间粒度：${task.granularity}。`,
    ...brandScope,
    `预测未来 ${task.horizon} 个${periodUnit}。`,
    `${agent.brand ? '车型型号' : '分析维度'}：${segments}。`,
    `可参考的外生变量：${externalVariables}。`,
    `补充要求：${additionalRequirements}。`,
  ].join('\n');
}
