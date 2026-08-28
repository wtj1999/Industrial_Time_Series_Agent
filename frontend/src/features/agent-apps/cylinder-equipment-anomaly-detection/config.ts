import {
  CONTAMINATION_OPTIONS,
  DETECTION_MODELS,
  type DetectionModel,
} from '@/features/agent-apps/coating-areal-density-anomaly-detection/config';

export const CYLINDER_EQUIPMENT_ANOMALY_AGENT = {
  id: 'cylinder-equipment-anomaly-detection',
  name: '锂电气缸设备异常检测智能体',
  domain: '设备域',
  description: '监测气缸压力、位移、速度和运行节拍等关键特征，定位异常时段与潜在故障。',
  supportedExtensions: ['csv'],
} as const;

export const CYLINDER_ANOMALY_TARGETS = [
  '气缸压力',
  '活塞位移',
  '活塞速度',
  '缸体温度',
  '振动幅值',
  '单次动作周期',
  '耗气量',
  '泄漏率',
] as const;

export { CONTAMINATION_OPTIONS, DETECTION_MODELS };
export type { DetectionModel };

export const DEFAULT_CYLINDER_ANOMALY_REQUIREMENTS =
  '输出异常时间点、连续异常区间、异常分数、判定阈值、Top异常样本、主要异常特征、异常方向、可能故障模式、设备影响和建议排查项；优先生成异常分数时序图，并区分瞬时异常与持续异常。';

export interface CylinderAnomalyTask {
  anomalyTargets: string[];
  model: DetectionModel;
  contamination: number;
  windowSize: number;
  returnTopN: number;
  randomState: number;
  additionalRequirements: string;
}

export function resolvedCylinderDetectionModel(
  task: Pick<CylinderAnomalyTask, 'anomalyTargets' | 'model'>,
): string {
  if (task.model !== '自动推荐') return task.model;
  return task.anomalyTargets.length === 1 ? 'SpectralResidual' : 'TimeSeriesOD + ECOD';
}

export function usesCylinderDetectionWindow(
  task: Pick<CylinderAnomalyTask, 'anomalyTargets' | 'model'>,
): boolean {
  return resolvedCylinderDetectionModel(task) !== 'SpectralResidual';
}

export function buildCylinderAnomalyQuery(task: CylinderAnomalyTask): string {
  const targets = task.anomalyTargets.join('、');
  const resolvedModel = resolvedCylinderDetectionModel(task);
  const model = task.model === '自动推荐'
    ? `自动推荐（${resolvedModel}）`
    : task.model;
  const parameters = [
    '按时序模式检测',
    `预期异常比例=${(task.contamination * 100).toFixed(1)}%`,
    ...(usesCylinderDetectionWindow(task) ? [`检测窗口=${task.windowSize} 个采样点`] : []),
    `返回异常数量=${task.returnTopN}`,
    `随机种子=${task.randomState}`,
  ];
  const extra = task.additionalRequirements.trim() || DEFAULT_CYLINDER_ANOMALY_REQUIREMENTS;

  return [
    '请执行锂电气缸设备时序异常检测任务。',
    `异常检测目标：${targets}。`,
    '检测重点：识别目标特征的瞬时突变、持续偏移、局部形态异常及多特征协同异常。',
    `异常检测模型：${model}。`,
    `检测参数：${parameters.join('；')}。`,
    `补充要求：${extra}`,
  ].join('\n');
}
