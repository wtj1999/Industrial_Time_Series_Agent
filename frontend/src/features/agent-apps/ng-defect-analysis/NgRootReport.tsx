import { useMemo } from 'react';
import { NgReportFlow, type ReportFlowStage } from './NgReportFlow';
import { fmt } from './NgDeepCharts';
import { buildPrioritizedReport, REPORT_RULES } from './rootReportData';
import type { RootCauseResult, RootFactor, TargetPortrait } from './deepTypes';

const percent = (value: number) => `${(value * 100).toFixed(2)}%`;
const levelName = { device: '设备', shift: '班次', upstream: '上游因素' };

function factorAdvice(factor: RootFactor) {
  const advice = [`先核对${factor.process_name} / ${factor.name}的测量与记录，固定目标设备、班次、工单及物料批次做对照复验。`];
  if (factor.adjustment?.adjusted_risk_difference != null && factor.adjustment.adjusted_risk_difference !== 0) {
    const adjustment = factor.adjustment;
    advice.push(`以 ${fmt(adjustment.threshold)} 为探索分界，重点复核参数${adjustment.adjusted_risk_difference! > 0 ? '较高' : '较低'}一侧的NG表现；该分界不作为工艺上下限。`);
  } else if (factor.worst_interval) {
    advice.push(`优先复核 [${fmt(factor.worst_interval.lower)}, ${fmt(factor.worst_interval.upper)}] 区间，并选相邻区间在相同生产条件下对照。`);
  }
  advice.push('在批准的工艺范围内一次只调整一个因素，记录调整前后NG/总数，并在独立批次复验。');
  return advice;
}

export function NgRootReport({ root, portrait, processName = '目标工序', targetName = '目标字段', onValidate }: {
  root: RootCauseResult; portrait?: TargetPortrait; processName?: string; targetName?: string; onValidate: (id: string) => void;
}) {
  const report = useMemo(() => buildPrioritizedReport(root, portrait), [root, portrait]);
  const primary = report.alerts[0];
  const conclusion = primary ? `首要定位：${levelName[report.level]}维度 · ${primary.row.label}`
    : report.ranking === 'model' ? '设备与班次层未定位到明确异常，进入上游因素预测贡献 Top 3。'
      : report.ranking === 'distribution' ? '设备与班次层未定位到明确异常，先列出上游分布差异候选。'
        : '当前未定位到有足够证据支撑的优先因素。';
  const activeStage = { device: 0, shift: 1, upstream: 2 }[report.level];
  const stages: ReportFlowStage[] = [...report.stages.map(stage => ({ key: stage.level, name: levelName[stage.level], reason: stage.reason, insufficient: stage.status === 'insufficient',
    summary: stage.status === 'detected' ? `偏高${stage.alerts.length}组` : stage.status === 'not_detected' ? '未见偏高' : '证据不足' })),
    { key: 'upstream', name: '上游因素', insufficient: report.ranking === 'none',
      summary: report.ranking === 'model' ? `贡献${report.factors.length}项` : report.ranking === 'distribution' ? `候选${report.factors.length}项` : '证据不足',
      reason: report.ranking === 'model' ? `已按模型预测贡献筛选出 ${report.factors.length} 个上游因素。`
        : report.ranking === 'distribution' ? `暂缺可用模型贡献，按分布差异列出 ${report.factors.length} 个候选。` : '暂无满足证据条件的上游因素。' }];
  return <div className="min-w-0 space-y-4 text-xs leading-6" aria-label="根因证据报告" data-report-level={report.level}>
    <p className="break-words rounded-lg bg-emerald-50 p-3 font-medium text-emerald-800">{conclusion}</p>
    <NgReportFlow stages={stages} activeStage={activeStage} />
    {report.alerts.map(item => {
      const device = report.level === 'device';
      const reference = device ? '同租户、产线的其他已知设备' : '其他已知班次';
      const shifts = device ? portrait?.dimensions.device_shift.filter(row => JSON.stringify(row.key.slice(0, -1)) === JSON.stringify(item.row.key)) ?? [] : [];
      return <article key={JSON.stringify(item.row.key)} className="min-w-0 space-y-3 rounded-xl border border-steel-200 p-3" aria-label={`${item.row.label}排查建议`}>
        <h4 className="break-words font-semibold text-steel-800">{processName} / {item.row.label}</h4>
        <div className="grid gap-2 sm:grid-cols-3">
          <p className="rounded-lg bg-rose-50 p-2 text-rose-700">当前分组 NG占比 {percent(item.rate)}<span className="block">NG {item.row.NG} / 总数 {item.row.NG + item.row.OK}</span></p>
          <p className="rounded-lg bg-steel-50 p-2 text-steel-600">{reference} {percent(item.referenceRate)}<span className="block">NG {item.referenceNG} / 总数 {item.referenceNG + item.referenceOK}</span></p>
          <p className="rounded-lg bg-amber-50 p-2 text-amber-700">高出 {(item.difference * 100).toFixed(2)} 个百分点<span className="block">{item.referenceRate ? `约为对照的 ${(item.rate / item.referenceRate).toFixed(2)} 倍` : '对照中未观察到当前缺陷NG'}</span></p>
        </div>
        {shifts.length ? <div className="space-y-1 text-steel-600"><p className="font-medium">该设备各班次表现</p>{shifts.map(row => <p key={JSON.stringify(row.key)}>{row.key.at(-1)}：NG {row.NG} / 总数 {row.NG + row.OK} · NG占比 {row.NG + row.OK ? percent(row.NG / (row.NG + row.OK)) : '—'}</p>)}</div> : null}
        <div className="space-y-1 text-steel-700"><p className="font-medium">排查与验证建议</p><ol className="list-decimal space-y-1 pl-5">
          {device ? <>
            <li>优先核查该设备的{targetName}测量系统、工艺设定、报警与点检/维护记录，与低NG设备核对同工单、同批次条件。</li>
            <li>用同一工单、相同物料和相同班次，在该设备与对照设备抽取连续产品复测，区分设备差异与来料、工单分配差异。</li>
            <li>依据核查结果安排校准、维护或工艺设定复核，保持其他条件一致，比较处理前后NG占比并在独立批次复验。</li>
          </> : <>
            <li>重点复核{item.row.label}的交接班、启停机、点检、工艺调整与生产环境记录，围绕{targetName}核对异常时间。</li>
            <li>在相同设备、工单和物料批次内比较不同班次，排查设备利用和工单分配造成的占比差异。</li>
            <li>对核查发现的具体差异安排标准化交接或点检改进，记录前后NG/总数并跨日期复验。</li>
          </>}
        </ol></div>
        <p className="text-[11px] text-steel-400">单侧Fisher检验，分组多重比较BH校正 q={fmt(item.qValue)}。</p>
      </article>;
    })}
    {report.level === 'upstream' ? <>
      {report.ranking === 'model' ? <p className="text-steel-500">按{root.model.evaluation_set === 'validation' ? '验证集' : root.model.evaluation_set === 'test' ? '历史测试集' : '历史验证集'}上游字段平均绝对SHAP贡献排序，每个字段合并中位数与极差的贡献。贡献占比表示模型对该字段的依赖程度。</p>
        : <p className="text-steel-500">本轮没有可用的上游模型贡献排名；下列仅按分布差异排序，不表示异常贡献大小。</p>}
      {report.stages.some(stage => stage.status === 'insufficient') ? <p className="rounded-lg bg-amber-50 p-3 text-amber-800">设备或班次层证据不足，尚未排除这些维度的影响；上游结果作为并行排查候选。</p> : null}
      {report.ranking === 'model' && root.model.average_precision_gain != null && root.model.average_precision_gain <= 0 ? <p className="text-amber-700">加入上游因素尚未改善测试/验证集AP，当前贡献排序仍需进一步核实。</p> : null}
      {report.factors.map(({ factor: f, contribution, share }, index) => <article key={f.field_id} className="min-w-0 space-y-2 rounded-xl border border-steel-200 p-3" data-report-factor={f.field_id}>
        <h4 className="break-words font-semibold text-steel-800">{index + 1}. {f.process_name} / {f.name}</h4>
        <p className="text-emerald-700">{contribution !== null ? <>模型贡献 {fmt(contribution)} · 贡献占比 {percent(share!)}</> : <>分布/极差效应 {fmt(f.distribution_effect)} / {fmt(f.spread_effect)}</>}</p>
        <p className="text-steel-600">有效覆盖 NG {f.coverage.NG.valid}/{f.coverage.NG.total}，OK {f.coverage.OK.valid}/{f.coverage.OK.total}；中位数 NG {fmt(f.median_NG)}，OK {fmt(f.median_OK)}。</p>
        {f.status === 'low_coverage' ? <p className="text-amber-700">至少一组的字段覆盖不足50%，模型贡献仅反映可用产品，不能代表全部产品。</p> : null}
        {f.status === 'limited_sources' ? <p className="text-amber-700">共享物料仅有 {f.source_codes} 个独立编码；模型按目标产品构建，需补充独立物料批次复验。</p> : null}
        {f.status === 'confounded' ? <p className="text-amber-700">在可比生产条件内，单因素关联明显减弱或反向，需优先排除共同变化因素。</p> : null}
        {f.adjustment?.adjusted_risk_difference != null ? <p className="text-steel-600">可比条件内，{f.name}高于 {fmt(f.adjustment.threshold)} 一侧的NG占比，比不高于该值的一侧{f.adjustment.adjusted_risk_difference > 0 ? '高' : f.adjustment.adjusted_risk_difference < 0 ? '低' : '相差'} {Math.abs(f.adjustment.adjusted_risk_difference * 100).toFixed(2)} 个百分点。</p> : null}
        {root.report.factors.find(entry => entry.field_id === f.field_id)?.hypothesis ? <p className="text-steel-600">{root.report.factors.find(entry => entry.field_id === f.field_id)!.hypothesis}</p> : null}
        <div><p className="font-medium text-steel-700">排查与验证建议</p><ol className="list-decimal space-y-1 pl-5 text-steel-600">{factorAdvice(f).map(advice => <li key={advice}>{advice}</li>)}</ol></div>
        <button type="button" className="rounded-md border border-emerald-200 px-3 py-1 text-emerald-700 hover:bg-emerald-50" onClick={() => onValidate(f.field_id)}>记录验证计划</button>
      </article>)}
      {report.factors.length < 3 ? <p className="text-steel-500">当前仅有 {report.factors.length} 个满足证据条件的上游因素，不补足无依据的候选。</p> : null}
    </> : null}
    <p className="text-[11px] text-steel-500">以上为优先排查方向，现场验证完成前不确认根因。</p>
    <details className="text-[11px] text-steel-500"><summary className="cursor-pointer">明显偏高的判定</summary><p>当前组与对照组各至少{REPORT_RULES.minProducts}个产品，当前组至少{REPORT_RULES.minNG}个NG；NG占比至少高{(REPORT_RULES.minDifference * 100).toFixed(2)}个百分点且至少为对照的{REPORT_RULES.minRatio}倍，单侧Fisher检验经BH校正q≤{REPORT_RULES.maxQ}。设备只与同租户、产线的其他已知设备比较；未知分组不作为正常对照。</p></details>
  </div>;
}
