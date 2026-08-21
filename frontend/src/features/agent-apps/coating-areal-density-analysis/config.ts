export const COATING_AREAL_DENSITY_AGENT = {
  id: 'coating-areal-density-analysis',
  name: '锂电涂布面密度分析智能体',
  domain: '设备域',
  description: '分析涂布面密度的稳定性、控制状态、过程能力、漂移、变点与分区关联。',
  supportedExtensions: ['csv'],
} as const;

export const ANALYSIS_MODES = [
  'SPC控制状态分析',
  '均值变点定位',
  '分区相关性分析',
  '面密度分布分析',
  '自相关与周期结构分析',
  '趋势与周期分解',
  '过程稳定性评估',
  '过程能力分析',
  '长期趋势与持续漂移',
  '波动突变分析',
  '综合质量诊断',
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
  sigmaWidth: number;
  maxChangePoints: number;
  minSegmentLength: number;
  correlationMethod: 'pearson' | 'spearman' | 'kendall';
  minAbsCorrelation: number;
  histogramBins: number;
  binStrategy: 'equal_width' | 'quantile';
  maxLag: number;
  ciLevel: number;
  periodSteps: number | null;
  decompositionModel: 'additive' | 'multiplicative';
  decompositionMethod: 'stl' | 'classical';
  driftThreshold: number;
  trendMethod: '稳健线性趋势' | 'CUSUM持续漂移';
  cusumThreshold: number;
  cusumDrift: number;
  varianceRatioThreshold: number;
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
    SPC控制状态分析: '使用 analyze_control_chart 识别控制限及 Western Electric 规则违例，并生成控制图。',
    均值变点定位: '使用 detect_mean_change_points 定位均值显著改变的位置，并生成分段均值图。',
    分区相关性分析: '使用 analyze_correlation_matrix 分析横向分区的相关关系，并生成相关性热力图。',
    面密度分布分析: '使用 analyze_histogram 分析集中区间、偏态、双峰或截断，并生成直方图。',
    自相关与周期结构分析: '使用 analyze_autocorrelation 分析滞后依赖和周期结构，并生成 ACF/PACF 图。',
    趋势与周期分解: '使用 decompose_time_series 按指定周期拆分趋势、周期和残差，并生成分解图。',
    过程稳定性评估: '使用 analyze_stability 评估变异系数、滚动均值漂移和滚动波动。',
    过程能力分析: '使用 analyze_process_capability 计算 Cp/Cpk、Pp/Ppk 和潜在缺陷风险。',
    长期趋势与持续漂移: '分析长期升降趋势或微小持续偏移，优先选择线性趋势或 CUSUM 中最匹配的一个。',
    波动突变分析: '使用 detect_variance_change 定位波动幅度突变和工况失稳位置。',
    综合质量诊断: '最多选择三个互补分析，覆盖基线、稳定性和最高价值的异常证据，并优先保留可视化结果。',
  };
  const scopes = task.coatingScopes.length > 0
    ? task.coatingScopes.join('、')
    : '全部面密度分区';
  const extra = task.additionalRequirements.trim() || DEFAULT_COATING_REQUIREMENTS;
  const lines = [
    '请执行锂电涂布面密度时序分析任务。',
    `主分析目标：${task.analysisMode}；${intent[task.analysisMode]}`,
    `分析范围：${scopes}。`,
  ];
  if (task.analysisMode === 'SPC控制状态分析') {
    lines.push(`分析参数：控制限宽度=${task.sigmaWidth}σ；控制图子组大小=${task.subgroupSize}；应用标准 Western Electric 规则。`);
  } else if (task.analysisMode === '均值变点定位') {
    lines.push(`分析参数：最大变点数=${task.maxChangePoints}；最小分段长度=${task.minSegmentLength} 个采样点。`);
  } else if (task.analysisMode === '分区相关性分析') {
    lines.push(`分析参数：相关方法=${task.correlationMethod}；最小绝对相关系数=${task.minAbsCorrelation}。`);
  } else if (task.analysisMode === '面密度分布分析') {
    lines.push(`分析参数：分箱数量=${task.histogramBins}；分箱策略=${task.binStrategy}。`);
  } else if (task.analysisMode === '自相关与周期结构分析') {
    lines.push(`分析参数：最大滞后阶数=${task.maxLag}；置信水平=${task.ciLevel}。`);
  } else if (task.analysisMode === '趋势与周期分解') {
    lines.push(`分析参数：周期采样点数=${task.periodSteps}；分解模型=${task.decompositionModel}；分解方法=${task.decompositionMethod}；稳健分解=true。`);
  } else if (task.analysisMode === '过程稳定性评估') {
    lines.push(`分析参数：滚动窗口=${task.window} 个采样点；漂移阈值=${task.driftThreshold}。`);
  } else if (task.analysisMode === '过程能力分析') {
    lines.push(`规格参数：LSL=${formatNumber(task.lsl)}；目标值=${formatNumber(task.target)}；USL=${formatNumber(task.usl)}。`);
  } else if (task.analysisMode === '长期趋势与持续漂移') {
    lines.push(task.trendMethod === 'CUSUM持续漂移'
      ? `分析参数：趋势方法=CUSUM持续漂移；触发阈值=${task.cusumThreshold}；容忍漂移=${task.cusumDrift}；最小分段长度=${task.minSegmentLength}。`
      : '分析参数：趋势方法=稳健线性趋势；robust=true。');
  } else if (task.analysisMode === '波动突变分析') {
    lines.push(`分析参数：滚动窗口=${task.window} 个采样点；最大变点数=${task.maxChangePoints}；波动比阈值=${task.varianceRatioThreshold}。`);
  } else {
    lines.push(`分析参数：综合诊断参考窗口=${task.window} 个采样点。`);
  }
  lines.push(`补充要求：${extra}。`);
  return lines.join('\n');
}
