export type BiScalar = string | number | boolean | null;

export interface BiConfirmField {
  cls: string;
  cls_name: string;
  values: string[];
}

export interface BiConfirmPayload {
  type?: string;
  message?: string;
  selected_table?: string;
  rewritten_query?: string;
  need_confirm?: BiConfirmField[];
  filter_conditions?: BiConfirmField[];
  thread_id?: string;
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
  data?: Array<Record<string, BiScalar>>;
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
}

