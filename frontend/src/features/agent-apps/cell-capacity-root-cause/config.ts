export const CELL_CAPACITY_ROOT_CAUSE_AGENT = {
  id: 'cell-capacity-root-cause',
  name: '锂电分容容量偏低根因分析智能体',
  domain: '设备域',
  description: '基于分容容量与全流程工艺参数，定位容量偏低的关键影响因素并提供验证建议。',
  supportedExtensions: ['csv'],
} as const;

export const FEATURE_SCOPES = [
  '分容关键工步参数',
  '化成关键工步参数',
  '注液工艺参数',
  '高温浸润工艺参数',
  '全部可用工艺参数',
] as const;

export const DEFAULT_ROOT_CAUSE_REQUIREMENTS =
  '输出容量偏低的关键影响参数排序、TreeSHAP贡献方向、模型评估指标、重点排查对象和可执行的工艺验证建议。';

export interface CellCapacityRootCauseTask {
  featureScopes: string[];
  trainRatio: number;
  validationRatio: number;
  testRatio: number;
  splitStrategy: 'chronological' | 'random';
  iterations: number;
  learningRate: number;
  depth: number;
  additionalRequirements: string;
}

export function buildCellCapacityRootCauseQuery(task: CellCapacityRootCauseTask): string {
  const scopes = task.featureScopes.join('、');
  const extra = task.additionalRequirements.trim() || DEFAULT_ROOT_CAUSE_REQUIREMENTS;
  return [
    '请执行锂电分容容量偏低根因分析任务。',
    '分析目标：分容容量。将分容容量列设置为 target_columns。',
    `候选特征范围：${scopes}；将匹配的数据列设置为 feature_columns，排除时间列、ID列、分容容量本身及明显泄漏字段。`,
    '分析方法：调用 analyze_root_causes_catboost，分别训练目标列模型，输出模型评估、特征重要性和 TreeSHAP。',
    `数据切分：方式=${task.splitStrategy}；训练集=${task.trainRatio}；验证集=${task.validationRatio}；测试集=${task.testRatio}。`,
    `模型参数：iterations=${task.iterations}；learning_rate=${task.learningRate}；depth=${task.depth}。`,
    `补充要求：${extra}。`,
  ].join('\n');
}
