export const COATING_AREAL_DENSITY_AGENT = {
  id: 'coating-areal-density-analysis',
  name: '锂电涂布面密度分析智能体',
  domain: '设备域',
  description: '分析涂布面密度的稳定性、控制状态、过程能力、漂移、变点与分区关联。',
  supportedExtensions: ['csv'],
} as const;

export const ANALYSIS_MODES = [
  '稳定性评估',
  'SPC控制图',
  '过程能力',
  '趋势漂移',
  '均值变点',
  '波动变点',
  '异常点分析',
  '分区关联分析',
  '综合诊断',
] as const;

export type CoatingAnalysisMode = (typeof ANALYSIS_MODES)[number];

export const COATING_SCOPES = ['A面分区', 'A+B双面分区', '全部面密度分区'];

export const DEFAULT_COATING_REQUIREMENTS =
  '输出核心结论、关键指标、异常或失稳位置、可能原因、业务影响和可执行建议。';

export interface CoatingAnalysisTask {
  analysisMode: CoatingAnalysisMode;
  coatingScopes: string[];
  window: number;
  subgroupSize: number;
  lsl: number | null;
  target: number | null;
  usl: number | null;
  additionalRequirements: string;
}

function formatNumber(value: number | null): string {
  return value === null ? '未设置' : String(value);
}

export function buildCoatingAnalysisQuery(task: CoatingAnalysisTask): string {
  const intent: Record<CoatingAnalysisMode, string> = {
    稳定性评估: '评估面密度的过程稳定性、变异系数、滚动均值漂移和滚动波动。',
    SPC控制图: '使用 SPC 控制图识别超控制限点及 Western Electric 规则违例。',
    过程能力: '依据规格限分析 Cp/Cpk、Pp/Ppk 和潜在缺陷风险。',
    趋势漂移: '分析面密度随时间的上升、下降或持续漂移趋势。',
    均值变点: '检测面密度均值发生显著改变的时间位置和前后差异。',
    波动变点: '检测面密度波动幅度突变和工况失稳的时间位置。',
    异常点分析: '识别面密度中的单变量异常点、异常程度和集中区段。',
    分区关联分析: '分析各横向分区面密度之间的相关关系和不同步分区。',
    综合诊断: '进行综合诊断；最多选择三个互补分析，覆盖基线、稳定性及最高价值的异常证据。',
  };
  const scopes = task.coatingScopes.length > 0
    ? task.coatingScopes.join('、')
    : '全部面密度分区';
  const extra = task.additionalRequirements.trim() || DEFAULT_COATING_REQUIREMENTS;
  const lines = [
    '请执行锂电涂布面密度时序分析任务。',
    `主分析目标：${task.analysisMode}；${intent[task.analysisMode]}`,
    `分析范围：${scopes}。`,
    `滚动窗口：${task.window} 个采样点；控制图子组大小：${task.subgroupSize}。`,
  ];
  if (task.analysisMode === '过程能力' || [task.lsl, task.target, task.usl].some((value) => value !== null)) {
    lines.push(`规格参数：LSL=${formatNumber(task.lsl)}；目标值=${formatNumber(task.target)}；USL=${formatNumber(task.usl)}。`);
  }
  lines.push(`补充要求：${extra}。`);
  return lines.join('\n');
}
