// Shared constants for EasyForm extension

export const CONFIG = {
  backendUrl: 'https://easyform-ai.com',
  mode: 'automatic' // 'automatic' or 'manual'
};

// Storage keys - per-tab for request IDs
export const STORAGE_KEYS = {
  getRequestId: (tabId) => `request_${tabId}`,
  getStartTime: (tabId) => `startTime_${tabId}`,
  ANALYSIS_STATE: 'analysisState',
  ANALYSIS_RESULT: 'analysisResult',
  ANALYSIS_ERROR: 'analysisError'
};

// Analysis states
export const ANALYSIS_STATES = {
  IDLE: 'idle',
  RUNNING: 'running',
  SUCCESS: 'success',
  ERROR: 'error'
};

// Polling configuration
export const POLL_INTERVAL_MS = 1000; // Poll every 1 second
export const POLL_TIMEOUT_MS = 1200000; // 20 minutes timeout
