// Synthetic UI fixture; these figures are not manufacturing observations.
export function reportScenario(result, level) {
  const data = structuredClone(result), template = result.target_profile.dimensions.device[0];
  const row = (label,key,NG,OK) => ({...structuredClone(template),label,key,NG,OK,ng_share:NG/(NG+OK),
    groups:{NG:{...template.groups.NG,count:NG},OK:{...template.groups.OK,count:OK}},
    histogram:template.histogram.map((bin,i)=>({...bin,NG:i?NG-Math.floor(NG/2):Math.floor(NG/2),OK:i?OK-Math.floor(OK/2):Math.floor(OK/2)}))});
  const highDevice = level==='device', highShift = level!=='upstream';
  data.counts = {NG:100,OK:1900,excluded:0};
  data.target_profile.dimensions = {overall:[row('总体',[],100,1900)],
    device:[row('#4切卷一体机',['A','L','#4'],highDevice?90:50,highDevice?910:950),row('#2切卷一体机',['A','L','#2'],highDevice?10:50,highDevice?990:950)],
    shift:[row('白班',['白班'],highShift?90:50,highShift?910:950),row('夜班',['夜班'],highShift?10:50,highShift?990:950)],
    device_shift:[row('#4 · 白班',['A','L','#4','白班'],highDevice?80:highShift?45:25,highDevice?420:highShift?455:475),
      row('#4 · 夜班',['A','L','#4','夜班'],highDevice?10:highShift?5:25,highDevice?490:highShift?495:475),
      row('#2 · 白班',['A','L','#2','白班'],highDevice?10:highShift?45:25,highDevice?490:highShift?455:475),
      row('#2 · 夜班',['A','L','#2','夜班'],highDevice?0:highShift?5:25,highDevice?500:highShift?495:475)]};
  const weights=[.05,.4,.1,.25,.15,.05];
  data.root_cause.factors=data.root_cause.factors.map((f,i)=>({...f,status:'candidate',score:.2+i*.1,model_contribution:weights[i],
    coverage:{NG:{valid:100,total:100},OK:{valid:1900,total:1900}}}));
  data.root_cause.model.contributions=data.root_cause.factors.map((f,i)=>({field_id:f.field_id,name:f.name,mean_abs_shap:weights[i]}));
  data.root_cause.model.selected_fields=data.root_cause.factors.map(f=>f.field_id);
  return data;
}

export function withRca(result) {
  const groups = result.boxes[0].groups;
  const portraitRow = (label, key, NG, OK) => ({ label, key, NG, OK, excluded: 0, ng_share: NG / (NG + OK),
    groups: { NG: { ...groups.NG, count: NG }, OK: { ...groups.OK, count: OK } },
    histogram: [{ lower: 0, upper: 2, upper_inclusive: false, NG: Math.floor(NG/2), OK: Math.floor(OK/2) }, { lower: 2, upper: 4, upper_inclusive: true, NG: NG-Math.floor(NG/2), OK: OK-Math.floor(OK/2) }] });
  const factors = result.boxes.map((f, i) => ({ field_id: f.field_id, name: f.name, process_name: f.process_name,
    status: i ? 'constant' : 'candidate', reason: i ? '当前字段无有效变化' : '观察到待验证的分布差异', score: .4,
    coverage: { NG: { valid: 2, total: 2 }, OK: { valid: 4, total: 4 } }, source_codes: 10, shared_sources: false,
    distinct_values: 4, median_NG: 0, median_OK: 2, distribution_effect: .4, spread_effect: .2, rank_effect: -.3, p_value: .01, q_value: .02,
    target_relation: { products: 6, spearman: .3 }, model_contribution: .2,
    adjustment: { threshold: 2, raw_risk_difference: .2, adjusted_risk_difference: .1, matched_products: 6, comparable_strata: 1, controls: ['device_name', 'shift'], method: 'stratified' },
    stability: { status: 'insufficient', periods: [], consistent_fraction: null },
    worst_interval: i ? null : { lower: 0, upper: 2, ng_share: .5, products: 2, baseline_share: 1/3, lift: 1.5 } }));
  const enriched = { ...result, analysis_id: 'fixture-analysis', target_profile: {
    unit: 'distinct_target_product', rate_denominator: 'current_NG_plus_confirmed_OK', rate_note: 'NG占比以当前NG与OK为分母。', shift_note: '读取shift，不按end_time推断。', findings: ['目标数值分布存在待验证差异。'],
    dimensions: { overall: [portraitRow('总体', [], 2, 4)], device: [portraitRow('#10切卷一体机', ['A', 'L', '#10'], 1, 3), portraitRow('#11切卷一体机', ['A', 'L', '#11'], 1, 1)],
      shift: [portraitRow('白班', ['白班'], 1, 2), portraitRow('夜班', ['夜班'], 1, 2)], device_shift: [
        portraitRow('#10 · 白班', ['A', 'L', '#10', '白班'], 1, 1), portraitRow('#10 · 夜班', ['A', 'L', '#10', '夜班'], 0, 2),
        portraitRow('#11 · 白班', ['A', 'L', '#11', '白班'], 0, 1), portraitRow('#11 · 夜班', ['A', 'L', '#11', '夜班'], 1, 0)] },
  }, root_cause: { version: 1, label: 'current_defect_NG_vs_confirmed_OK', factors,
    model: { status: 'completed', reason: '已完成7:3划分与固定1000轮训练，因果仍待现场验证。', note: 'SHAP解释验证集预测依据，不能解释为因果贡献。', train_products: 70, validation_products: 30, test_products: 0, purged_products: 0,
      evaluation_set: 'validation', initial_split_products: {train:70,validation:30}, missing_products: {train:0,validation:0},
      train_counts:{NG:14,OK:56}, validation_counts:{NG:6,OK:24},
      training:{iterations:1000,early_stopping:false,baseline:{tree_count:1000,trained_iterations:1000},augmented:{tree_count:1000,trained_iterations:1000}},
      validation: 'chronological_70_30', cross_date: true, baseline: { roc_auc: .6, average_precision: .2, NG_share: .1 }, augmented: { roc_auc: .8, average_precision: .5, NG_share: .1 },
      average_precision_gain: .3, assessment: '上游因素提供额外预测信息', contributions: [{ field_id: factors[0].field_id, name: factors[0].name, mean_abs_shap: .2 }], interactions: [] },
    methods: ['按目标产品按时间7:3划分，共享上游码保留，固定训练1000轮，验证集评估。'], report: { conclusion: '当前输出为根因候选，现场验证完成前不确认根因。', factors: factors.map(f => ({ field_id: f.field_id, name: f.name, process_name: f.process_name,
      status: '待验证候选', evidence: ['存在观察性差异，需独立验证。'], hypothesis: '该因素变化可能与当前NG有关。', alternatives: '核对设备与班次。', action: '设计对照并在独立批次复验。', causal_status: 'unconfirmed' })) } } };
  const limits = [
    {field_id:result.boxes[0].field_id,group:['A','L','NG'],records:50,median:3,mad:1,lower:-4.4136,upper:10.4136,status:'applied'},
    {field_id:result.boxes[0].field_id,group:['A','L','OK'],records:50,median:4,mad:1,lower:-3.4136,upper:11.4136,status:'applied'}
  ];
  const quality = { version:'fixture-3',revision:'fixture',policy:'automatic_by_tenant_line_label',exclude_statistical:true,min_records:50,modified_z_limit:5,note:'合成UI样本，无实际产线数据。',baselines:limits,
    fields:[{field_id:result.boxes[0].field_id,name:result.boxes[0].name,process_name:result.boxes[0].process_name,standard_unit:null,configured:false,
      records:100,original_valid:100,converted:0,missing:0,removed:1,flagged:1,statistically_excluded:1,algorithm_removed:2,limits,remaining:98,reasons:{},affected_products:{NG:1,OK:0}}]};
  return {...enriched,measurement_quality:quality};
}
