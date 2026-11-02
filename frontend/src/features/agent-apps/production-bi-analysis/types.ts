export type BiScalar = string | number | boolean | null;

export interface BiConfirmField {
  cls: string;
  cls_name: string;
  values: string[];
  selected_values?: string[];
  has_more?: boolean;
  next_offset?: number;
}

export interface BiOptionsPage {
  values: string[];
  has_more: boolean;
  next_offset: number;
}

export type BiOptionsLoader = (field: string, search: string, offset: number, signal: AbortSignal) => Promise<BiOptionsPage>;

export interface BiGroupDimension {
  field: string;
  label: string;
}

export interface NgChartRow {
  ng_type: string;
  ng_name: string;
  ng_process_name?: string | null;
  ng_count: number;
  dimensions?: Record<string, string | null>;
}

export type NgAnalysis = {
  status: 'success';
  summary: string;
  findings: Array<{ title: string; detail: string }>;
  recommendations: Array<{ priority: '高' | '中' | '低'; action: string; verification: string }>;
  limitations: string[];
} | {
  status: 'empty' | 'unavailable';
  message: string;
};

export interface BiConfirmPayload {
  type?: string;
  message?: string;
  selected_table?: string;
  rewritten_query?: string;
  need_confirm?: BiConfirmField[];
  filter_conditions?: BiConfirmField[];
  thread_id?: string;
  confirmation_id?: string;
  locked_conditions?: string[];
  group_by?: BiGroupDimension[];
  filter_matches?: Array<{
    field: string;
    field_name: string;
    input_value: string;
    status: 'matched' | 'ambiguous' | 'unmatched';
    values: string[];
    message: string;
  }>;
}

export interface BiNeedConfirmResponse {
  status: 'need_confirm';
  type?: 'field_confirm' | string;
  thread_id: string;
  confirm: BiConfirmPayload;
}

export interface BiSuccessResponse {
  status: 'success';
  type?: 'success' | string;
  thread_id: string;
  rewritten_query?: string;
  table?: string;
  recall_tables?: string[];
  sql?: string;
  sql_explanation?: string;
  row_count?: number;
  analysis?: NgAnalysis;
  data?: Array<Record<string, BiScalar>>;
  chart?: {
    type: 'ng_bar';
    rows: NgChartRow[];
    group_by?: BiGroupDimension[];
    period: { start_date: string; end_date: string };
    total_ng_count: number;
  };
}

export type BiResponse = BiNeedConfirmResponse | BiSuccessResponse | {
  status: string;
  type?: string;
  thread_id: string;
  [key: string]: unknown;
};

export interface BiQueryPayload {
  query: string;
  thread_id: string;
  resume?: Record<string, string[]>;
  confirmation_id?: string;
}

