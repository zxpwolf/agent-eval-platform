// Typed API client for the Agent Observability Backend

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ──────────────────────────────────────────────
// Response types (matching backend Pydantic models)
// ──────────────────────────────────────────────

export interface SpanEvent {
  timestamp: number
  name: string
  attributes: Record<string, unknown>
}

export interface Span {
  span_id: string
  trace_id: string
  name: string
  span_type: string
  start_time: number
  end_time: number | null
  parent_span_id: string | null
  status: string
  attributes: Record<string, unknown>
  events: SpanEvent[]
  model: string | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  cost: number | null
  input_data: unknown
  output_data: unknown
}

export interface Trace {
  trace_id: string
  name: string
  start_time: number
  end_time: number | null
  user_id: string | null
  session_id: string | null
  metadata: Record<string, unknown>
  spans: Span[]
}

export interface TraceListItem {
  trace_id: string
  name: string
  start_time: number
  end_time: number | null
  user_id: string | null
  session_id: string | null
  span_count: number
  total_tokens: number
  total_cost: number
  duration_ms: number
}

export interface TraceListResponse {
  traces: TraceListItem[]
  total: number
}

export interface ModelStats {
  model: string
  call_count: number
  tokens: number
}

export interface StatsResponse {
  trace_count: number
  span_count: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  total_cost: number
  models: ModelStats[]
}

export interface ReplayStatus {
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'stopped'
  progress: number
  current_index: number
  total_calls: number
  replayed_calls_count: number
  error: string | null
}

export interface ReplaySessionInfo {
  session_id: string
  trace_id: string
  status: string
}

export interface ReplayLogInfo {
  log_id: string
  trace_id: string
  created_at: number
  calls_count: number
}

// ──────────────────────────────────────────────
// API error type
// ──────────────────────────────────────────────

export interface ApiError {
  error: string
  detail?: string
}

// ──────────────────────────────────────────────
// Internal fetch wrapper
// ──────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || body.error || detail
    } catch {
      // ignore
    }
    throw new Error(`API ${res.status}: ${detail}`)
  }
  return res.json()
}

// ──────────────────────────────────────────────
// Traces API
// ──────────────────────────────────────────────

export async function listTraces(
  limit: number = 50,
  offset: number = 0,
  filters?: { user_id?: string; session_id?: string; model?: string }
): Promise<TraceListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (filters?.user_id) params.set('user_id', filters.user_id)
  if (filters?.session_id) params.set('session_id', filters.session_id)
  if (filters?.model) params.set('model', filters.model)
  return apiFetch<TraceListResponse>(`/api/traces/?${params.toString()}`)
}

export async function getTrace(traceId: string): Promise<Trace> {
  return apiFetch<Trace>(`/api/traces/${traceId}`)
}

export async function createTrace(trace: Trace): Promise<Trace> {
  return apiFetch<Trace>('/api/traces/', {
    method: 'POST',
    body: JSON.stringify(trace),
  })
}

export async function deleteTrace(traceId: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/api/traces/${traceId}`, { method: 'DELETE' })
}

export async function getStats(): Promise<StatsResponse> {
  return apiFetch<StatsResponse>('/api/traces/stats/summary')
}

// ──────────────────────────────────────────────
// Replay API
// ──────────────────────────────────────────────

export async function exportReplayLog(
  traceId: string
): Promise<{ log_id: string; message: string }> {
  return apiFetch(`/api/replay/export/${traceId}`, { method: 'POST' })
}

export async function startReplay(
  traceId: string,
  options?: { mock_llm?: boolean; mock_tools?: boolean; speed_multiplier?: number }
): Promise<{ session_id: string; trace_id: string; status: string }> {
  const params = new URLSearchParams({ trace_id: traceId })
  if (options?.mock_llm !== undefined) params.set('mock_llm', String(options.mock_llm))
  if (options?.mock_tools !== undefined) params.set('mock_tools', String(options.mock_tools))
  if (options?.speed_multiplier !== undefined) params.set('speed_multiplier', String(options.speed_multiplier))
  return apiFetch(`/api/replay/start?${params.toString()}`, { method: 'POST' })
}

export async function getReplayStatus(sessionId: string): Promise<ReplayStatus> {
  return apiFetch<ReplayStatus>(`/api/replay/${sessionId}/status`)
}

export async function pauseReplay(sessionId: string): Promise<{ session_id: string; status: string }> {
  return apiFetch(`/api/replay/${sessionId}/pause`, { method: 'POST' })
}

export async function resumeReplay(sessionId: string): Promise<{ session_id: string; status: string }> {
  return apiFetch(`/api/replay/${sessionId}/resume`, { method: 'POST' })
}

export async function stopReplay(sessionId: string): Promise<{ session_id: string; status: string }> {
  return apiFetch(`/api/replay/${sessionId}/stop`, { method: 'POST' })
}

export async function stepReplay(sessionId: string): Promise<{ session_id: string; step_result: unknown }> {
  return apiFetch(`/api/replay/${sessionId}/step`, { method: 'POST' })
}

export async function listReplaySessions(): Promise<{ sessions: ReplaySessionInfo[] }> {
  return apiFetch('/api/replay/sessions')
}

export async function compareReplays(
  sessionId1: string,
  sessionId2: string
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams({ session_id_1: sessionId1, session_id_2: sessionId2 })
  return apiFetch(`/api/replay/compare?${params.toString()}`, { method: 'POST' })
}

export async function listReplayLogs(): Promise<{ logs: ReplayLogInfo[] }> {
  return apiFetch('/api/replay/logs')
}

export async function deleteReplayLog(logId: string): Promise<{ message: string }> {
  return apiFetch(`/api/replay/logs/${logId}`, { method: 'DELETE' })
}

// ──────────────────────────────────────────────
// Session API
// ──────────────────────────────────────────────

export interface SessionInfo {
  session_id: string
  trace_count: number
  first_trace_time: number
  last_trace_time: number
  user_id: string | null
}

export async function listSessions(limit: number = 50): Promise<{ sessions: SessionInfo[] }> {
  return apiFetch(`/api/traces/sessions?limit=${limit}`)
}

export async function getSessionTraces(
  sessionId: string
): Promise<{ session_id: string; traces: Trace[] }> {
  return apiFetch(`/api/traces/sessions/${sessionId}`)
}

// ──────────────────────────────────────────────
// Evaluation API types
// ──────────────────────────────────────────────

export interface Dataset {
  dataset_id: string
  name: string
  description: string
  metadata: Record<string, unknown>
  items?: DatasetItem[]
  item_count?: number
  created_at: number
}

export interface DatasetItem {
  item_id: string
  dataset_id: string
  input_data: unknown
  expected_output: unknown
  metadata: Record<string, unknown>
  created_at: number
}

export interface Evaluator {
  evaluator_id: string
  name: string
  evaluator_type: 'heuristic' | 'llm_judge' | 'custom'
  config: Record<string, unknown>
  description: string
  created_at: number
}

export interface EvalRun {
  run_id: string
  dataset_id: string
  evaluator_ids: string[]
  trace_id: string | null
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  config: Record<string, unknown>
  started_at: number
  completed_at: number | null
  results_summary: Record<string, unknown> | null
  results?: EvalResult[]
  live_status?: { progress: number; completed: number; total: number }
}

export interface EvalResult {
  result_id: string
  run_id: string
  item_id: string
  evaluator_id: string
  score: number
  passed: boolean
  reasoning: string
  metadata: Record<string, unknown>
  created_at: number
}

export interface EvalRunComparison {
  run_id_1: string
  run_id_2: string
  summary_1: Record<string, unknown>
  summary_2: Record<string, unknown>
  comparison: Array<{
    item_id: string
    run_1: { score: number | null; passed: boolean | null; reasoning: string }
    run_2: { score: number | null; passed: boolean | null; reasoning: string }
    delta: number
  }>
}

// ──────────────────────────────────────────────
// Evaluation API - Datasets
// ──────────────────────────────────────────────

export async function listDatasets(
  limit: number = 50,
  offset: number = 0
): Promise<{ datasets: Dataset[]; total: number }> {
  return apiFetch(`/api/evaluations/datasets?limit=${limit}&offset=${offset}`)
}

export async function getDataset(datasetId: string): Promise<Dataset> {
  return apiFetch(`/api/evaluations/datasets/${datasetId}`)
}

export async function createDataset(
  name: string,
  description: string = ''
): Promise<Dataset> {
  return apiFetch('/api/evaluations/datasets', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  })
}

export async function deleteDataset(datasetId: string): Promise<{ message: string }> {
  return apiFetch(`/api/evaluations/datasets/${datasetId}`, { method: 'DELETE' })
}

export async function addDatasetItems(
  datasetId: string,
  items: Array<{ input_data: unknown; expected_output: unknown; metadata?: Record<string, unknown> }>
): Promise<{ added: number; items: DatasetItem[] }> {
  return apiFetch(`/api/evaluations/datasets/${datasetId}/items`, {
    method: 'POST',
    body: JSON.stringify({ items }),
  })
}

export async function deleteDatasetItem(
  datasetId: string,
  itemId: string
): Promise<{ message: string }> {
  return apiFetch(`/api/evaluations/datasets/${datasetId}/items/${itemId}`, { method: 'DELETE' })
}

// ──────────────────────────────────────────────
// Evaluation API - Evaluators
// ──────────────────────────────────────────────

export async function listEvaluators(
  limit: number = 50,
  offset: number = 0
): Promise<{ evaluators: Evaluator[]; total: number }> {
  return apiFetch(`/api/evaluations/evaluators?limit=${limit}&offset=${offset}`)
}

export async function createEvaluator(
  name: string,
  evaluatorType: string,
  config: Record<string, unknown>,
  description: string = ''
): Promise<Evaluator> {
  return apiFetch('/api/evaluations/evaluators', {
    method: 'POST',
    body: JSON.stringify({ name, evaluator_type: evaluatorType, config, description }),
  })
}

export async function deleteEvaluator(evaluatorId: string): Promise<{ message: string }> {
  return apiFetch(`/api/evaluations/evaluators/${evaluatorId}`, { method: 'DELETE' })
}

// ──────────────────────────────────────────────
// Evaluation API - Runs
// ──────────────────────────────────────────────

export async function startEvalRun(
  datasetId: string,
  evaluatorIds: string[],
  traceId?: string
): Promise<{ run_id: string; status: string }> {
  return apiFetch('/api/evaluations/runs', {
    method: 'POST',
    body: JSON.stringify({
      dataset_id: datasetId,
      evaluator_ids: evaluatorIds,
      ...(traceId ? { trace_id: traceId } : {}),
    }),
  })
}

export async function listEvalRuns(
  datasetId?: string,
  status?: string,
  limit: number = 50
): Promise<{ runs: EvalRun[]; total: number }> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (datasetId) params.set('dataset_id', datasetId)
  if (status) params.set('status', status)
  return apiFetch(`/api/evaluations/runs?${params.toString()}`)
}

export async function getEvalRun(runId: string): Promise<EvalRun> {
  return apiFetch(`/api/evaluations/runs/${runId}`)
}

export async function getEvalRunResults(
  runId: string
): Promise<{ run_id: string; results: EvalResult[] }> {
  return apiFetch(`/api/evaluations/runs/${runId}/results`)
}

export async function cancelEvalRun(
  runId: string
): Promise<{ run_id: string; status: string }> {
  return apiFetch(`/api/evaluations/runs/${runId}/cancel`, { method: 'POST' })
}

export async function compareEvalRuns(
  runId1: string,
  runId2: string
): Promise<EvalRunComparison> {
  return apiFetch('/api/evaluations/compare', {
    method: 'POST',
    body: JSON.stringify({ run_id_1: runId1, run_id_2: runId2 }),
  })
}
