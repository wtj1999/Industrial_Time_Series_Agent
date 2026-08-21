export const COATING_AREAL_DENSITY_ANOMALY_AGENT = {
  id: 'coating-areal-density-anomaly-detection',
  name: '锂电涂布面密度异常检测智能体',
  domain: '设备域',
  description: '检测涂布面密度的异常时间点、连续异常区间及主要异常分区。',
  supportedExtensions: ['csv'],
} as const;

export const DETECTION_TASKS = [
  '瞬时突变检测',
  '局部形态异常检测',
  '多分区协同异常检测',
  '连续异常区间检测',
  '分区异常贡献分析',
  '综合异常诊断',
] as const;

export type DetectionTask = (typeof DETECTION_TASKS)[number];

export const DETECTION_MODELS = [
  '自动推荐',
  'SpectralResidual',
  'MatrixProfile',
  'SAND',
  'TimeSeriesOD + ECOD',
  'TimeSeriesOD + IForest',
  'LSTMAD',
  'AnomalyTransformer',
] as const;

export type DetectionModel = (typeof DETECTION_MODELS)[number];

export const COATING_SCOPES = ['A面分区', 'A+B双面分区', '全部面密度分区'];

export const CONTAMINATION_OPTIONS = [0.005, 0.01, 0.02, 0.05, 0.1] as const;

export const DEFAULT_ANOMALY_REQUIREMENTS =
  '输出异常时间点、连续异常区间、异常分数、判定阈值、Top异常样本、主要异常分区、异常方向、可能原因、生产影响和建议排查项；优先生成异常分数时序图，并区分瞬时异常与持续异常。';

export interface CoatingAnomalyTask {
  detectionTask: DetectionTask;
  coatingScopes: string[];
  model: DetectionModel;
  contamination: number;
  windowSize: number;
  returnTopN: number;
  randomState: number;
  additionalRequirements: string;
}

const TASK_INTENTS: Record<DetectionTask, string> = {
  瞬时突变检测: '重点识别突然升高、突然降低、尖峰和跌落。',
  局部形态异常检测: '重点识别一段时间内偏离正常生产模式的局部波形。',
  多分区协同异常检测: '联合多个横向分区识别同步异常、局部失衡和组合模式异常。',
  连续异常区间检测: '聚合连续异常点，定位异常开始、结束和持续时间。',
  分区异常贡献分析: '在检测异常样本后，分析主要驱动分区及其偏高或偏低方向。',
  综合异常诊断: '最多选择三个互补步骤，完成时序检测、异常区间定位和分区贡献诊断。',
};

const AUTO_MODELS: Record<DetectionTask, string> = {
  瞬时突变检测: 'SpectralResidual',
  局部形态异常检测: 'MatrixProfile',
  多分区协同异常检测: 'TimeSeriesOD + ECOD',
  连续异常区间检测: 'SAND',
  分区异常贡献分析: 'TimeSeriesOD + ECOD',
  综合异常诊断: 'SAND',
};

export function resolvedDetectionModel(task: Pick<CoatingAnomalyTask, 'detectionTask' | 'model'>): string {
  return task.model === '自动推荐' ? AUTO_MODELS[task.detectionTask] : task.model;
}

export function usesDetectionWindow(task: Pick<CoatingAnomalyTask, 'detectionTask' | 'model'>): boolean {
  return resolvedDetectionModel(task) !== 'SpectralResidual';
}

export function buildCoatingAnomalyQuery(task: CoatingAnomalyTask): string {
  const scopes = task.coatingScopes.length > 0
    ? task.coatingScopes.join('、')
    : '全部面密度分区';
  const extra = task.additionalRequirements.trim() || DEFAULT_ANOMALY_REQUIREMENTS;
  const resolvedModel = resolvedDetectionModel(task);
  const model = task.model === '自动推荐'
    ? `自动推荐（${resolvedModel}）`
    : task.model;
  const parameters = [
    '按时序模式检测',
    `预期异常比例=${(task.contamination * 100).toFixed(1)}%`,
    ...(usesDetectionWindow(task) ? [`检测窗口=${task.windowSize} 个采样点`] : []),
    `返回异常数量=${task.returnTopN}`,
    `随机种子=${task.randomState}`,
  ];
  return [
    '请执行锂电涂布面密度时序异常检测任务。',
    `主检测任务：${task.detectionTask}；${TASK_INTENTS[task.detectionTask]}`,
    `检测范围：${scopes}。`,
    `异常检测模型：${model}。`,
    `检测参数：${parameters.join('；')}。`,
    `补充要求：${extra}`,
  ].join('\n');
}
