import { apiBaseUrl } from '../config';
import type { AnalyzeResponse, GenerateResponse, HistoryItem, Language, TaskType } from './types';

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new ApiError('Network request failed', 0, 'NETWORK_ERROR');
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = payload.error ?? {};
    throw new ApiError(error.message ?? 'The request failed', response.status, error.code ?? 'REQUEST_FAILED');
  }
  return payload as T;
}

export const api = {
  generate(prompt: string, language: Language, taskType: TaskType): Promise<GenerateResponse> {
    return request('/generate', { method: 'POST', body: JSON.stringify({ prompt, language, task_type: taskType }) });
  },
  analyze(code: string, language: Language, taskType: TaskType): Promise<AnalyzeResponse> {
    return request('/analyze', { method: 'POST', body: JSON.stringify({ code, language, task_type: taskType }) });
  },
  history(): Promise<HistoryItem[]> {
    return request('/history');
  },
  health(): Promise<{ status: string }> {
    return request('/health');
  },
};
