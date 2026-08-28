import {
  CONTAMINATION_OPTIONS,
  DETECTION_MODELS,
  type DetectionModel,
} from '@/features/agent-apps/coating-areal-density-anomaly-detection/config';

export const WELDING_EQUIPMENT_ANOMALY_AGENT = {
  id: 'welding-equipment-anomaly-detection',
  name: '锂电焊接设备异常检测智能体',
  domain: '设备域',
  description: '监测焊接功率、速度、焦点和熔池温度等关键特征，定位设备异常与潜在焊接缺陷。',
  supportedExtensions: ['csv'],
} as const;

export const WELDING_ANOMALY_TARGETS = [
  '激光功率',
  '焊接电流',
  '焊接电压',
  '焊接速度',
  '焦点偏移',
  '保护气体流量',
  '熔池温度',
  '振动幅值',
] as const;

export { CONTAMINATION_OPTIONS, DETECTION_MODELS };
export type { DetectionModel };

export const DEFAULT_WELDING_REQUIREMENTS =
  '输出异常时间点、连续异常区间、异常分数、判定阈值、Top异常样本、主要异常特征、异常方向、可能焊接缺陷、设备影响和建议排查项；优先生成异常分数时序图，并区分瞬时异常与持续异常。';

export interface WeldingAnomalyTask {
  anomalyTargets: string[];
  model: DetectionModel;
  contamination: number;
  windowSize: number;
  returnTopN: number;
  randomState: number;
  additionalRequirements: string;
}

export function resolvedWeldingModel(task: Pick<WeldingAnomalyTask, 'anomalyTargets' | 'model'>): string {
  if (task.model !== '自动推荐') return task.model;
  return task.anomalyTargets.length === 1 ? 'SpectralResidual' : 'TimeSeriesOD + ECOD';
}

export function usesWeldingWindow(task: Pick<WeldingAnomalyTask, 'anomalyTargets' | 'model'>): boolean {
  return resolvedWeldingModel(task) !== 'SpectralResidual';
}

export function buildWeldingAnomalyQuery(task: WeldingAnomalyTask): string {
  const resolvedModel = resolvedWeldingModel(task);
  const model = task.model === '自动推荐' ? `自动推荐（${resolvedModel}）` : task.model;
  const parameters = [
    '按时序模式检测',
    `预期异常比例=${(task.contamination * 100).toFixed(1)}%`,
    ...(usesWeldingWindow(task) ? [`检测窗口=${task.windowSize} 个采样点`] : []),
    `返回异常数量=${task.returnTopN}`,
    `随机种子=${task.randomState}`,
  ];
  const extra = task.additionalRequirements.trim() || DEFAULT_WELDING_REQUIREMENTS;
  return [
    '请执行锂电焊接设备时序异常检测任务。',
    `异常检测目标：${task.anomalyTargets.join('、')}。`,
    '检测重点：识别焊接过程参数的瞬时突变、持续漂移、周期形态异常及多特征协同异常。',
    `异常检测模型：${model}。`,
    `检测参数：${parameters.join('；')}。`,
    `补充要求：${extra}`,
  ].join('\n');
}
