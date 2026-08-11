/**
 * Type definitions for the Industrial Time Series Agent frontend.
 *
 * These mirror the FastAPI/LangGraph backend in `agent_app/`:
 *   - `models/schemas.py` for SessionState / Message / TechPath / ColumnMapping / TaskSpec
 *   - `api.py` SSE event stream shape (`token` / `update` / `interrupt` / `completed`)
 *   - The three interrupt kinds: choose_tech_path | upload_csv | clarification
 */

/* ------------------------------------------------------------------ *
 * Conversational primitives
 * ------------------------------------------------------------------ */

export type Role = 'user' | 'assistant' | 'system';

export interface Message {
  role: Role;
  content: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

/* ------------------------------------------------------------------ *
 * Session
 * ------------------------------------------------------------------ */

export type TaskStage =
  | 'Router'
  | 'CHAT'
  | 'Parse'
  | 'PROFILING'
  | 'Proposal'
  | 'CLARIFICATION'
  | 'EXECUTION';

export type IntentType = 'chat' | 'industrial';

export type TaskType = 'prediction' | 'anomaly_detection' | 'analysis' | 'monitoring';

export interface SessionInfo {
  session_id: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  current_task?: TaskType | string | null;
  current_stage: TaskStage | string;
  has_csv_profile: boolean;
  has_confirmed_spec: boolean;
  dialogue_turns: number;
  clarification_pending: boolean;
  analysis_artifacts_count: number;
}

/* ------------------------------------------------------------------ *
 * Conversation history (sidebar "历史对话" list + message replay).
 * Backed by GET /api/sessions, GET /api/sessions/{id}/messages and
 * DELETE /api/sessions/{id}. The lightweight summary is what the
 * sidebar lists; the full transcript is fetched on demand when the
 * user reopens a thread.
 * ------------------------------------------------------------------ */

/** One row in the user's session index. */
export interface SessionSummary {
  session_id: string;
  user_id: string;
  /** Short title derived from the first user message. */
  title: string;
  /** ISO timestamp (UTC) of first creation. */
  created_at: string;
  /** ISO timestamp (UTC) of last activity. */
  updated_at: string;
  /** Count of messages currently stored in ``dialogue_history``. */
  message_count: number;
}

export interface SessionsResponse {
  sessions: SessionSummary[];
  total: number;
  user_id?: string;
}

/** A single stored dialogue turn, returned by /api/sessions/{id}/messages. */
export interface StoredMessage {
  role: 'user' | 'assistant' | 'system' | string;
  content: string;
}

/**
 * Latest visual artifacts persisted in the session checkpoint. Each
 * field is `null` when that kind of artifact wasn't produced during the
 * session. NOTE: only the most recent chart of each type is returned —
 * earlier rounds are overwritten in state. A full chronological event
 * log would require a schema change.
 */
export interface SessionArtifacts {
  csv_preview?: CSVPreview | null;
  anomaly_chart?: AnomalyChart | null;
  analysis_chart?: AnalysisChart | null;
  prediction_chart?: PredictionChart | null;
}

/**
 * One entry in the chronological ``event_log`` persisted in state.
 * Replay order matches what the user saw during live chat — user msg,
 * assistant text segment, csv_preview card, more assistant text, chart
 * card, etc. — instead of the lossy "all messages then all artifacts"
 * fallback used for older sessions.
 *
 * - ``kind === 'message'``: ``role`` + ``content`` are set, ``data`` is null.
 * - ``kind === 'csv_preview' | 'anomaly_chart' | 'analysis_chart' | 'prediction_chart'``:
 *   ``data`` is set (matches the corresponding stream-event payload),
 *   ``role`` / ``content`` are null.
 */
export interface SessionEvent {
  kind:
    | 'message'
    | 'csv_preview'
    | 'anomaly_chart'
    | 'analysis_chart'
    | 'prediction_chart'
    | string;
  role?: 'user' | 'assistant' | 'system' | string;
  content?: string;
  data?: unknown;
  ts?: string;
}

export interface SessionMessagesResponse {
  session_id: string;
  messages: StoredMessage[];
  /** Visual artifacts persisted alongside the transcript. May be `{}`. */
  artifacts?: SessionArtifacts | null;
  /** Chronological event log — preferred source for UI replay. */
  events?: SessionEvent[];
  total: number;
}

/* ------------------------------------------------------------------ *
 * Proposal / Technical paths (choose_tech_path interrupt)
 * ------------------------------------------------------------------ */

export interface TechPathStep {
  step_title: string;
  content: string;
}

export interface TechPath {
  path_id: string;
  title: string;
  short_summary: string;
  model_type?: string | null;
  target_objects?: string[];
  steps?: TechPathStep[];
  expected_effect?: string | null;
  [k: string]: unknown;
}

/* ------------------------------------------------------------------ *
 * Clarification (column mapping)
 * ------------------------------------------------------------------ */

export type MappingStatus = 'mapped' | 'unmapped' | 'uncertain';

export interface ColumnMapping {
  semantic_name: string;
  csv_column?: string | null;
  status: MappingStatus;
}

/* ------------------------------------------------------------------ *
 * NDJSON stream events emitted by `POST /api/query`.
 * The backend writes one JSON object per line with
 * `media_type="application/x-ndjson"`.
 * ------------------------------------------------------------------ */

export interface TokenEvent {
  type: 'token';
  content: string;
}

export interface UpdateEvent {
  type: 'update';
  data: Record<string, unknown>;
}

export interface CompletedEvent {
  type: 'completed';
  data: Record<string, unknown>;
}

export interface ErrorEvent {
  type: 'error';
  error: string;
}

/* ------------------------------------------------------------------ *
 * CSV preview chart (emitted by the profiling node)
 * ------------------------------------------------------------------ */

export type CSVColumnKind =
  | 'numeric'
  | 'categorical'
  | 'temporal'
  | 'text'
  | 'boolean'
  | 'unknown';

export interface CSVPreviewColumn {
  name: string;
  kind: CSVColumnKind;
  chartable: boolean;
}

export interface CSVPreview {
  file_name: string;
  total_rows: number;
  preview_rows: number;
  columns: CSVPreviewColumn[];
  /** x-axis index: 0..preview_rows-1 */
  index: number[];
  /** Only chartable columns appear here; values are float | null (gaps). */
  series: Record<string, (number | null)[]>;
  error?: string;
}

export interface CsvPreviewEvent {
  type: 'csv_preview';
  data: CSVPreview;
}

/* ------------------------------------------------------------------ *
 * Anomaly-detection chart (emitted by the execute_task node when an
 * anomaly-detection tool ran and produced score/threshold/labels).
 * Mirrors the Python side in
 * `agent_app/agents/anomaly_detection_agent.py:_build_chart_from_tool_result`.
 * ------------------------------------------------------------------ */

export interface AnomalyInterval {
  start_index: number;
  end_index: number;
  length: number;
  time_start?: string | number | null;
  time_end?: string | number | null;
}

export interface AnomalyTopRow {
  row_index?: number | null;
  score?: number | null;
  is_anomaly?: boolean | null;
  time?: string | number | null;
  values?: Record<string, number | string | null>;
}

export type AnomalyChart = AnomalyScoresChart | AnomalyEvaluationChart;

export interface AnomalyScoresChart {
  chart_type: 'anomaly_scores';
  tool_name: string;
  detector_name: string;
  title: string;
  summary?: string | null;
  n_samples: number;
  n_anomalies: number;
  /** x-axis label (sample index by default, time column name when present). */
  x_label: string;
  /** Per-sample time labels; null means use integer index. */
  x_values: (string | number)[] | null;
  /** Sampled anomaly scores. May be downsampled for very long series. */
  scores: number[];
  /** Decision threshold → horizontal reference line. */
  threshold: number | null;
  /** Indices into `scores` flagged as anomalies (red dots). */
  anomaly_indices: number[];
  /** Contiguous anomaly intervals (time-series mode only); null otherwise. */
  anomaly_intervals: AnomalyInterval[] | null;
  /** Top-N highest-scoring rows for the side table. */
  top_anomalies: AnomalyTopRow[];
  feature_columns: string[];
  downsampled?: boolean;
  original_n_samples?: number;
}

export interface AnomalyEvaluationMetrics {
  roc_auc: number | null;
  average_precision: number | null;
  precision_at_n: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
}

export interface AnomalyEvaluationChart {
  chart_type: 'anomaly_evaluation';
  tool_name: 'evaluate_detection';
  detector_name: string;
  title: string;
  summary?: string | null;
  n_samples: number;
  n_anomalies: number;
  n_features: number;
  threshold: number | null;
  label_column: string | null;
  supports_out_of_sample: boolean | null;
  metrics: AnomalyEvaluationMetrics;
  confusion_matrix: { tp: number; fp: number; fn: number; tn: number } | null;
  scores_summary: {
    min: number | null;
    max: number | null;
    mean: number | null;
    std: number | null;
  };
  notes: string[];
}

export interface AnomalyChartEvent {
  type: 'anomaly_chart';
  data: AnomalyChart;
}

/* ------------------------------------------------------------------ *
 * Analysis charts (emitted by execute_task when an analysis sub-agent
 * ran a Tier-1 visualisable tool). Six chart types in Tier 1; the
 * registry in ChatView dispatches on ``chart_type``.
 * ------------------------------------------------------------------ */

export type AnalysisChartType =
  | 'correlation_heatmap'
  | 'histogram'
  | 'decomposition'
  | 'control_chart'
  | 'changepoint'
  | 'acf';

/** Union of all Tier-1 analysis-chart payloads. Discriminated by
 *  ``chart_type`` so the React component registry can pick the right
 *  card. Each variant only carries the fields its own chart needs. */
export type AnalysisChart =
  | CorrelationHeatmapChart
  | HistogramChart
  | DecompositionChart
  | ControlChart
  | ChangePointChart
  | AcfChart;

export interface CorrelationHeatmapChart {
  chart_type: 'correlation_heatmap';
  tool_name: string;
  title: string;
  summary?: string | null;
  columns: string[];
  rows: { column: string; values: (number | null)[] }[];
  method: string;
  n_columns: number;
  top_pairs: { a: string; b: string; r: number | null }[];
  n_high_multicollinearity: number;
}

export interface HistogramBin {
  index: number;
  range: [number | null, number | null];
  center: number | null;
  count: number;
  density: number | null;
}

export interface HistogramChart {
  chart_type: 'histogram';
  tool_name: string;
  summary?: string | null;
  active_column: string;
  columns: Record<string, HistogramColumn>;
}

export interface HistogramColumn {
  title: string;
  bins: HistogramBin[];
  bin_count: number;
  bin_strategy: string;
  cumulative: (number | null)[];
  concentration_ratio_top1: number | null;
  n_valid: number;
}

export interface DecompositionChart {
  chart_type: 'decomposition';
  tool_name: string;
  summary?: string | null;
  active_column: string;
  columns: Record<string, DecompositionColumn>;
}

export interface DecompositionColumn {
  title: string;
  observed: (number | null)[];
  trend: (number | null)[];
  seasonal: (number | null)[];
  residual: (number | null)[];
  n_points: number;
  downsampled: boolean;
  original_n: number;
  period: number | null;
  method: string;
  model: string;
  strength_trend: number | null;
  strength_seasonal: number | null;
}

export interface ControlChart {
  chart_type: 'control_chart';
  tool_name: string;
  summary?: string | null;
  active_column: string;
  columns: Record<string, ControlChartColumn>;
}

export interface ControlChartColumn {
  title: string;
  values: (number | null)[];
  violation_indices: number[];
  n_points: number;
  downsampled: boolean;
  original_n: number;
  center_line: number | null;
  ucl: number | null;
  lcl: number | null;
  sigma: number | null;
  sigma_width: number | null;
  agg: string;
  rule_violation_counts: Record<string, number>;
  n_total_violations: number;
}

export interface ChangePointChart {
  chart_type: 'changepoint';
  tool_name: string;
  summary?: string | null;
  active_column: string;
  columns: Record<string, ChangePointColumn>;
}

export interface ChangePointColumn {
  title: string;
  segments: {
    start: number;
    end: number;
    length: number;
    mean: number | null;
    std: number | null;
  }[];
  step_points: { x: number; y: number | null; kind: 'start' | 'end' }[];
  change_points: {
    index: number;
    delta_mean: number | null;
    left_mean: number | null;
    right_mean: number | null;
    p_value: number | null;
    confidence?: string | null;
  }[];
  n_valid: number;
  n_change_points: number;
}

export interface AcfChart {
  chart_type: 'acf';
  tool_name: string;
  summary?: string | null;
  active_column: string;
  columns: Record<string, AcfColumn>;
}

export interface AcfColumn {
  title: string;
  acf: (number | null)[];
  pacf: (number | null)[];
  confidence_band: number | null;
  ci_level: number | null;
  max_lag: number;
  significant_acf_lags: number[];
  significant_pacf_lags: number[];
  lag_1_autocorr: number | null;
  n_valid: number;
}

export interface AnalysisChartEvent {
  type: 'analysis_chart';
  data: AnalysisChart;
}

/* ------------------------------------------------------------------ *
 * Forecast chart (emitted by execute_task when the prediction sub-agent
 * ran forecast_time_series or forecast_multi_models). A single chart
 * type with ``is_multi_model`` discriminating whether the secondary
 * model-chip row should appear.
 * ------------------------------------------------------------------ */

/** Quantile forecast output for one (column, model) cell. ``point_forecast``
 *  always equals ``quantiles.p50``. */
export interface ForecastModelSeries {
  point_forecast: number[];
  quantiles: {
    p10: number[];
    p20: number[];
    p30: number[];
    p40: number[];
    p50: number[];
    p60: number[];
    p70: number[];
    p80: number[];
    p90: number[];
  };
}

export interface ForecastColumnData {
  /** Downsampled history (length ≤ 400). */
  history: number[];
  /** Original history length before downsampling. */
  n_history_full: number;
  history_downsampled: boolean;
  horizon: number;
  models: Record<string, ForecastModelSeries>;
}

export interface ForecastChart {
  chart_type: 'forecast';
  tool_name: string;
  title: string;
  summary?: string | null;
  model_names: string[];
  is_multi_model: boolean;
  prediction_length: number;
  per_column: Record<string, ForecastColumnData>;
  all_columns: string[];
}

/* ------------------------------------------------------------------ *
 * Backtest chart (emitted by execute_task when the prediction sub-agent
 * ran backtest_forecast or compare_forecast_models_backtest). Shares
 * the ``prediction_chart`` SSE channel with ForecastChart; the two
 * payloads are discriminated by ``chart_type``. ``is_multi_model``
 * further discriminates single-model (quantile band + actual overlay)
 * from multi-model (N dashed point-forecast lines + actual overlay).
 * ------------------------------------------------------------------ */

/** Per-(column, model) cell for the backtest chart. Single-model mode
 *  carries the full 9-quantile band; multi-model mode only carries
 *  ``point_forecast`` (the compare tool does not retain quantiles). */
export interface BacktestModelSeries {
  point_forecast: number[];
  quantiles?: {
    p10: number[];
    p20: number[];
    p30: number[];
    p40: number[];
    p50: number[];
    p60: number[];
    p70: number[];
    p80: number[];
    p90: number[];
  };
  metrics?: Partial<Record<'mae' | 'rmse' | 'mape' | 'smape' | 'mase' | 'n', number | null>>;
}

export interface BacktestRankRow {
  model: string;
  /** Metric the ranking was sorted by (smaller is better). */
  rank_metric?: string | null;
  n_columns_ok?: number | null;
  mae?: number | null;
  rmse?: number | null;
  mape?: number | null;
  smape?: number | null;
  mase?: number | null;
}

export interface BacktestColumnData {
  /** Downsampled train tail (length ≤ 400). */
  history: number[];
  /** Original train length before downsampling. */
  n_history_full: number;
  history_downsampled: boolean;
  /** Length of the holdout window (= number of forecast points). */
  horizon: number;
  /** Holdout ground-truth values, length === horizon. */
  actual: number[];
  models: Record<string, BacktestModelSeries>;
  /** Best-scoring model on this column (multi-model only). */
  best_model?: string | null;
  /** Value of the best_model on the rank_by metric (or mae). */
  best_metric_value?: number | null;
}

export interface BacktestChart {
  chart_type: 'backtest';
  tool_name: string;
  title: string;
  summary?: string | null;
  model_names: string[];
  is_multi_model: boolean;
  test_steps: number;
  /** Multi-model only; which metric the ranking was sorted by. */
  rank_by?: string | null;
  per_column: Record<string, BacktestColumnData>;
  all_columns: string[];
  /** Multi-model only; per-model aggregate metrics, best-first. */
  ranking?: BacktestRankRow[];
}

/** Any chart payload carried by the ``prediction_chart`` SSE channel.
 *  Dispatched on ``chart_type`` in ChatView.tsx. */
export type PredictionChart = ForecastChart | BacktestChart;

export interface ForecastChartEvent {
  type: 'prediction_chart';
  data: PredictionChart;
}

export interface InterruptBase<TKind extends string, TData> {
  type: 'interrupt';
  data: { type: TKind } & TData;
}

export interface ChooseTechPathInterruptData {
  message: string;
  paths: TechPath[];
}

export interface UploadCsvInterruptData {
  message: string;
  hint?: string;
  /** True 时在 CSV 上传卡片内额外渲染「复用已训练模型」选择器。
   *  后端仅在异常检测任务下置 true；其它任务保持 undefined 以维持
   *  向后兼容（旧会话回放不会携带此字段）。 */
  allow_model?: boolean;
  /** 当前任务类型字符串（如 'anomaly_detection'），用于 UI 提示。
   *  缺省时不影响行为，仅作为辅助信息。 */
  current_task_type?: string;
}

export interface ClarificationInterruptData {
  message?: string;
  hint?: string;
  feature_columns?: ColumnMapping[];
  target_columns?: ColumnMapping[];
  candidate_columns?: string[];
}

export type InterruptEvent =
  | InterruptBase<'choose_tech_path', ChooseTechPathInterruptData>
  | InterruptBase<'upload_csv', UploadCsvInterruptData>
  | InterruptBase<'clarification', ClarificationInterruptData>;

export type StreamEvent =
  | TokenEvent
  | UpdateEvent
  | CompletedEvent
  | ErrorEvent
  | CsvPreviewEvent
  | AnomalyChartEvent
  | AnalysisChartEvent
  | ForecastChartEvent
  | InterruptEvent;

/* Discriminated helper for the interrupt payload we pass around the UI */
export type InterruptPayload = InterruptEvent['data'];

export function isInterrupt(ev: StreamEvent): ev is InterruptEvent {
  return ev.type === 'interrupt';
}

/* ------------------------------------------------------------------ *
 * Resume values (sent back to `POST /api/query` as `resume_value`)
 * ------------------------------------------------------------------ */

export interface ChoosePathResume {
  path_id: string;
}

export interface UploadCsvResume {
  file_path?: string;
  /** 用户在 ModelPicker 中选择了某个已训练模型时填写以下字段。
   *  全部缺省 = 不复用模型（由 LLM 自由决策训练或加载）。
   *  后端会把它们打包成 ModelRef 写入 SessionState.selected_model_ref，
   *  并透传给 anomaly_agent 的 context 供 resolve_model_path 跨域定位。 */
  save_name?: string;
  model_thread_id?: string | null;
  model_source_file?: string | null;
  detector_name?: string | null;
}

export interface ClarificationResume {
  target_columns?: ColumnMapping[];
  feature_columns?: ColumnMapping[];
}

export type ResumeValue = ChoosePathResume | UploadCsvResume | ClarificationResume;

/* ------------------------------------------------------------------ *
 * Misc API envelopes
 * ------------------------------------------------------------------ */

export interface StandardResponse<T = unknown> {
  success: boolean;
  message?: string | null;
  error?: string | null;
  timestamp?: number;
  data?: T;
}

/* ------------------------------------------------------------------ *
 * Auth — mirrors the backend `AuthResponse` / `AuthRequest` pydantic
 * models in agent_app/api.py. ``user_id`` is the stable identity the
 * client persists (utils/user.ts) and sends back as ``X-User-Id``.
 * ------------------------------------------------------------------ */

export interface AuthRequest {
  username: string;
  password: string;
}

export interface AuthResponse {
  success: boolean;
  user_id?: string | null;
  username?: string | null;
  error?: string | null;
}

/* ------------------------------------------------------------------ *
 * Asset listings (uploaded files + trained models). Backed by the
 * GET /api/datasets and GET /api/models endpoints.
 * ------------------------------------------------------------------ */

export interface DatasetEntry {
  /** Original filename (without the session-id prefix). */
  name: string;
  /** On-disk filename including the session-id prefix. */
  file_name: string;
  /** Lowercase extension without the dot: ``csv`` | ``xlsx`` | ``parquet``. */
  extension: string;
  size_bytes: number;
  /** ISO timestamp (UTC) of the last modification. */
  modified_at: string;
  /** Session id parsed from the on-disk prefix, when present. */
  session_id?: string | null;
}

export interface DatasetsResponse {
  datasets: DatasetEntry[];
  total: number;
  root?: string;
}

export interface ModelEntry {
  /** Persisted model family. Older anomaly-model records omit this field. */
  category?: 'anomaly_detection' | 'time_series_prediction' | string | null;
  task_type?: 'anomaly_detection' | 'prediction' | string | null;
  model_type?: string | null;
  save_name: string;
  file_name: string;
  detector_name?: string | null;
  model_class?: string | null;
  contamination?: number | null;
  n_samples?: number | null;
  n_features?: number | null;
  feature_columns?: string[];
  source?: string | null;
  n_anomalies?: number | null;
  threshold?: number | null;
  transductive?: boolean | null;
  trained_at?: string | null;
  saved_at?: string | null;
  pyod_version?: string | null;
  sklearn_version?: string | null;
  size_bytes: number;
  /** Thread id parsed from the artifacts subpath. */
  thread_id?: string | null;
  /** Stem of the source dataset file (without ``_anomaly_detection`` suffix). */
  source_file?: string | null;
  /** True for joblib files lacking the versioned envelope. */
  legacy?: boolean;
}

export interface ModelsResponse {
  models: ModelEntry[];
  total: number;
  root?: string;
  failed?: { file_name: string; error: string }[];
}
