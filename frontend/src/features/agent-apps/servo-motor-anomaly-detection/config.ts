import {
  CONTAMINATION_OPTIONS,
  DETECTION_MODELS,
  type DetectionModel,
} from '@/features/agent-apps/coating-areal-density-anomaly-detection/config';

export const SERVO_MOTOR_ANOMALY_AGENT = {
  id: 'servo-motor-anomaly-detection',
  name: '锂电伺服电机异常检测智能体',
  domain: '设备域',
  description: '监测伺服电机电流、扭矩、转速和位置误差等关键特征，定位运行异常与潜在故障。',
  supportedExtensions: ['csv'],
} as const;

export const SERVO_MOTOR_ANOMALY_TARGETS = [
  '电机转速',
  '输出扭矩',
  '驱动电流',
  '母线电压',
  '电机温度',
  '振动幅值',
  '位置跟随误差',
  '编码器位置',
] as const;

export { CONTAMINATION_OPTIONS, DETECTION_MODELS };
export type { DetectionModel };

export const DEFAULT_SERVO_MOTOR_REQUIREMENTS =
  '输出异常时间点、连续异常区间、异常分数、判定阈值、Top异常样本、主要异常特征、异常方向、可能故障模式、设备影响和建议排查项；优先生成异常分数时序图，并区分瞬时异常与持续异常。';

export interface ServoMotorAnomalyTask {
  anomalyTargets: string[];
  model: DetectionModel;
  contamination: number;
  windowSize: number;
  returnTopN: number;
  randomState: number;
  additionalRequirements: string;
}

export function resolvedServoMotorModel(task: Pick<ServoMotorAnomalyTask, 'anomalyTargets' | 'model'>): string {
  if (task.model !== '自动推荐') return task.model;
  return task.anomalyTargets.length === 1 ? 'SpectralResidual' : 'TimeSeriesOD + ECOD';
}

export function usesServoMotorWindow(task: Pick<ServoMotorAnomalyTask, 'anomalyTargets' | 'model'>): boolean {
  return resolvedServoMotorModel(task) !== 'SpectralResidual';
}

export function buildServoMotorAnomalyQuery(task: ServoMotorAnomalyTask): string {
  const resolvedModel = resolvedServoMotorModel(task);
  const model = task.model === '自动推荐' ? `自动推荐（${resolvedModel}）` : task.model;
  const parameters = [
    '按时序模式检测',
    `预期异常比例=${(task.contamination * 100).toFixed(1)}%`,
    ...(usesServoMotorWindow(task) ? [`检测窗口=${task.windowSize} 个采样点`] : []),
    `返回异常数量=${task.returnTopN}`,
    `随机种子=${task.randomState}`,
  ];
  const extra = task.additionalRequirements.trim() || DEFAULT_SERVO_MOTOR_REQUIREMENTS;
  return [
    '请执行锂电伺服电机时序异常检测任务。',
    `异常检测目标：${task.anomalyTargets.join('、')}。`,
    '检测重点：识别目标特征的瞬时突变、持续偏移、周期形态异常及多特征协同异常。',
    `异常检测模型：${model}。`,
    `检测参数：${parameters.join('；')}。`,
    `补充要求：${extra}`,
  ].join('\n');
}
