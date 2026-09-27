declare global {
  interface Window {
    WORKBENCH_CONFIG?: { apiBaseUrl?: string };
  }
}

export const apiBaseUrl = window.WORKBENCH_CONFIG?.apiBaseUrl ?? '/api/v1';
