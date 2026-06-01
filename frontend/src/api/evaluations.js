import { api } from './client'

/** Legacy metric list for backward-compatible direct-run flow. */
export const SUPPORTED_METRICS = [
  { id: 'exact_match', label: 'Exact match', defaultOn: true },
  { id: 'contains_expected', label: 'Contains expected', defaultOn: true },
  { id: 'response_nonempty', label: 'Response non-empty', defaultOn: true },
  { id: 'response_length', label: 'Response length', defaultOn: true },
  { id: 'latency_ms', label: 'Latency (ms)', defaultOn: true },
]

export function fetchEvaluations(params = {}) {
  const qs = new URLSearchParams()
  if (params.agent_id) qs.set('agent_id', params.agent_id)
  if (params.status) qs.set('status', params.status)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString()
  return api.get(`/api/v1/evaluations${query ? `?${query}` : ''}`)
}

export function fetchJobs(params = {}) {
  const qs = new URLSearchParams()
  if (params.status) qs.set('status', params.status)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString()
  return api.get(`/api/v1/evaluations/jobs${query ? `?${query}` : ''}`)
}

export function fetchEvaluation(evaluationId) {
  return api.get(`/api/v1/evaluations/${evaluationId}`)
}

export function fetchEvaluationResults(evaluationId, params = {}) {
  const qs = new URLSearchParams()
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString()
  return api.get(
    `/api/v1/evaluations/${evaluationId}/results${query ? `?${query}` : ''}`
  )
}

export function createEvaluationJob(body) {
  return api.post('/api/v1/evaluations/jobs', {
    agent_id: body.agent_id,
    dataset_id: body.dataset_id,
    framework: body.framework || 'vertex',
    metrics: body.metrics,
    name: body.name,
  })
}

export function updateEvaluationJob(evaluationId, body) {
  return api.patch(`/api/v1/evaluations/${evaluationId}`, {
    agent_id: body.agent_id,
    dataset_id: body.dataset_id,
    framework: body.framework || 'vertex',
    metrics: body.metrics || [],
  })
}

export function runEvaluationJob(evaluationId) {
  return api.post(`/api/v1/evaluations/${evaluationId}/run`)
}

export function startEvaluation(body) {
  return api.post('/api/v1/evaluations/run', {
    agent_id: body.agent_id,
    dataset_id: body.dataset_id,
    framework: body.framework || 'vertex',
    metrics: body.metrics,
    name: body.name,
  })
}

export function retryEvaluation(evaluationId) {
  return api.post(`/api/v1/evaluations/${evaluationId}/retry`)
}
