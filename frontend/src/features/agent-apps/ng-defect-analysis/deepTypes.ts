export interface DeepField {
  id: string;
  name: string;
  process_code: string;
  process_name: string;
  process_order: number;
  reason: string;
  recommended: boolean;
}

export interface DeepPlan {
  status: 'need_field_confirm';
  thread_id: string;
  plan_id: string;
  ng_name: string;
  period: { start_date: string; end_date: string };
  filters: Record<string, string[]>;
  row_dimensions: Record<string, string | null>;
  target_id: string;
  feature_ids: string[];
  targets: DeepField[];
  features: DeepField[];
  message: string;
}

export interface BoxStats {
  count: number;
  missing_count: number;
  matched_products?: number;
  direct_products?: number;
  input_code_products?: number;
  ambiguous_products?: number;
  ads_products?: number;
  parameter_record_count?: number;
  parameter_record_median?: number | null;
  target_products?: number;
  valid_products?: number;
  missing_products?: number;
  complete_products?: number;
  partial_products?: number;
  trace_missing_products?: number;
  multi_code_products?: number;
  expected_samples?: number;
  min: number | null;
  q1: number | null;
  median: number | null;
  q3: number | null;
  max: number | null;
  mean: number | null;
  whisker_low: number | null;
  whisker_high: number | null;
  outlier_count: number;
  outliers: number[];
}

export interface IntervalBubble {
  index: number;
  lower: number;
  upper: number;
  upper_inclusive: boolean;
  NG: number;
  OK: number;
  product_count: number;
  ng_rate: number | null;
  source_record_count: number;
  upstream_code_count: number;
  association_count: number;
}

export interface DeepFeatureResult {
  field_id: string;
  name: string;
  process_name: string;
  process_code?: string;
  sample_unit?: string;
  analysis_type?: 'shared_material' | 'individual';
  groups: Record<'NG' | 'OK', BoxStats>;
  bubble?: {
    strategy: 'equal_width';
    max_bins: number;
    denominator: string;
    size_metric: string;
    range_min: number | null;
    range_max: number | null;
    covered_products: number;
    bins: IntervalBubble[];
  };
}

export interface DeepResult {
  status: 'success';
  thread_id: string;
  plan_id: string;
  analysis_id?: string;
  factory_id?: string;
  ng_name: string;
  period: { start_date: string; end_date: string };
  counts: { NG: number; OK: number; excluded: number };
  target: { id: string; name: string; process_name: string; date_filter_field?: string; sort_time_field?: string; groups: Record<'NG' | 'OK', BoxStats> };
  boxes: DeepFeatureResult[];
  target_profile?: TargetPortrait;
  root_cause?: RootCauseResult;
  measurement_quality?: MeasurementQualitySummary;
  timing: {
    total_seconds: number;
    target_query: { seconds: number; rows: number; source_rows?: number; duplicate_rows: number; invalid_product_rows: number; date_filter_field?: string; sort_time_field?: string };
    feature_wall_seconds: number;
    feature_queries: Array<{ table: string; process_code: string; seconds: number; rows: number; product_batch_size: number }>;
    workers: number;
    trace_wall_seconds?: number;
    trace_queries?: Array<{ route: string; table: string; seconds: number; rows: number; lookup_count: number }>;
  };
  rules: string[];
  warnings: string[];
}

export interface DeepProgress {
  stage: 'preparing' | 'target' | 'cleaning' | 'profiling' | 'trace' | 'features' | 'statistics' | 'screening' | 'modeling' | 'validation' | 'report' | 'completed' | 'failed' | 'cancelled';
  message: string;
  sequence: number;
  elapsed_seconds: number;
  rows?: number;
  total?: number;
}

export interface PortraitRow {
  key: string[]; label: string; NG: number; OK: number; excluded: number; ng_share: number | null;
  groups: Record<'NG' | 'OK', BoxStats>;
  histogram: Array<{ lower: number; upper: number; upper_inclusive: boolean; NG: number; OK: number }>;
}
export interface TargetPortrait {
  dimensions: Record<'overall' | 'device' | 'shift' | 'device_shift', PortraitRow[]>;
  unit: string; rate_denominator: string; rate_note: string; shift_note: string;
  findings: string[];
}
export interface RootFactor {
  field_id: string; name: string; process_name: string; status: string; reason: string; score: number;
  coverage: Record<'NG' | 'OK', { valid: number; total: number }>;
  source_codes: number; shared_sources: boolean; distinct_values: number;
  median_NG: number | null; median_OK: number | null; distribution_effect: number | null;
  spread_effect: number | null;
  target_relation: { products: number; spearman: number | null };
  rank_effect: number | null; p_value: number | null; q_value: number | null; model_contribution: number | null;
  adjustment: { threshold: number; raw_risk_difference: number | null; adjusted_risk_difference: number | null;
    matched_products: number; comparable_strata: number; controls: string[]; method: string } | null;
  stability: { status: string; periods: Array<{ date: string; risk_difference: number; products: number }>; consistent_fraction: number | null };
  worst_interval: { lower: number; upper: number; ng_share: number; baseline_share: number; products: number; lift: number } | null;
}
export interface ModelMetrics { roc_auc: number; average_precision: number; NG_share: number }
export interface RootCauseResult {
  version: number; label: string; factors: RootFactor[]; methods: string[];
  model: { status: string; reason: string; note: string; train_products: number; test_products: number; purged_products: number;
    validation_products?: number;
    train_counts?: Partial<Record<'NG' | 'OK', number>>; validation_counts?: Partial<Record<'NG' | 'OK', number>>; test_counts?: Partial<Record<'NG' | 'OK', number>>;
    validation: string; cross_date: boolean; baseline: ModelMetrics | null; augmented: ModelMetrics | null;
    evaluation_set?: 'test' | 'validation'; sample_unit?: string; shared_material_policy?: string;
    initial_split_products?: { train: number; validation: number; test?: number };
    missing_products?: { train: number; validation: number; test?: number };
    training?: { iterations: number; early_stopping: boolean;
      baseline?: { tree_count: number; trained_iterations: number }; augmented?: { tree_count: number; trained_iterations: number } };
    early_stopping?: { metric: string; rounds: number; max_iterations: number;
      baseline?: { best_iteration: number; tree_count: number; trained_iterations: number };
      augmented?: { best_iteration: number; tree_count: number; trained_iterations: number } };
    average_precision_gain?: number; assessment?: string;
    selected_fields?: string[]; selection_method?: string;
    statistical_cleaning?: { method: string; fit_products: number; flagged_records: number };
    contributions: Array<{ field_id: string; name: string; mean_abs_shap: number }>;
    interactions: Array<{ field_ids: string[]; strength: number; status: string }>;
  };
  report: { conclusion: string; factors: Array<{ field_id: string; name: string; process_name: string; status: string;
    evidence: string[]; hypothesis: string; alternatives: string; action: string; causal_status: string }> };
}
export interface ValidationDraft {
  field_id: string; hypothesis: string; action: string; controls: string;
  decision: 'planned' | 'supported' | 'refuted' | 'inconclusive'; replicated: boolean; notes: string;
  before_total: number | null; before_ng: number | null; after_total: number | null; after_ng: number | null;
  quality_view?: 'automatic_cleaned' | 'include_suspects' | 'exclude_suspects';
}

export interface MeasurementQualitySummary {
  policy?: string;
  version: string; revision: string; exclude_statistical: boolean; min_records: number; modified_z_limit: number; note: string;
  fields: Array<{ field_id: string; name: string; process_name: string; standard_unit: string | null; configured: boolean;
    records: number; original_valid: number; converted: number; missing: number; removed: number; flagged: number;
    statistically_excluded: number; algorithm_removed?: number; limits?: MeasurementQualitySummary['baselines']; remaining: number; reasons: Record<string, number>; affected_products: Record<'NG' | 'OK', number> }>;
  baselines: Array<{ field_id: string; group: string[]; records: number; median: number | null; mad: number | null; lower: number | null; upper: number | null; status: string }>;
}
export interface MeasurementAuditPage {
  total: number; offset: number;
  records: Array<{ record_ref: string; field_id: string; identity: Record<string, string | number | null>;
    original_value: string | number | null; value: number | null; converted: boolean; status: string; reason: string;
    statistical_suspect: boolean; statistical_reason: string | null; cohort?: string; unit: string | null; rule_version: string; rule_revision: string }>;
}
export interface ValidationRecord extends ValidationDraft {
  id: string; recorded_at: string; source: string; causal_status: string;
  before_rate?: number; after_rate?: number; change_percentage_points?: number;
}
