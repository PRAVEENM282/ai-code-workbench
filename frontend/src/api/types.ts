// Language names are open-ended for provider requests; Monaco and analyzers may support a subset.
export type Language = string;
export type TaskType = 'boilerplate' | 'unit_test' | 'review' | 'security' | 'refactor' | 'translation' | 'documentation';

export interface Finding {
  line_number: number;
  column?: number;
  severity?: 'error' | 'warning' | 'info' | 'convention';
  issue_type?: string;
  description?: string;
  rule?: string;
  message?: string;
  suggested_fix?: string;
  tool?: string;
}

export interface GenerateResponse {
  code: string;
  explanation?: string | null;
  routed_model: string;
  request_id?: string;
}

export interface AnalyzeResponse {
  static_analysis: Finding[];
  llm_feedback: Finding[];
  routed_model: string;
  request_id?: string;
  analysis_errors?: string[];
}

export interface HistoryItem {
  id: string;
  endpoint_used: string;
  task_type: string;
  language: string;
  user_input: string;
  model_routed_to: string | null;
  created_at: string;
  response_payload: GenerateResponse | AnalyzeResponse | null;
}
