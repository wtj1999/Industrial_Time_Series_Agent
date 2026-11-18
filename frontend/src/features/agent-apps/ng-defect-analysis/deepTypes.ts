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
  ng_name: string;
  period: { start_date: string; end_date: string };
  counts: { NG: number; OK: number; excluded: number };
  target: { id: string; name: string; process_name: string; date_filter_field?: string; sort_time_field?: string; groups: Record<'NG' | 'OK', BoxStats> };
  boxes: DeepFeatureResult[];
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
  stage: 'preparing' | 'target' | 'trace' | 'features' | 'statistics' | 'completed' | 'failed' | 'cancelled';
  message: string;
  sequence: number;
  elapsed_seconds: number;
  rows?: number;
  total?: number;
}
