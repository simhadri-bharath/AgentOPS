import { api } from './client'

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
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString()
  return api.get(`/api/v1/evaluations${query ? `?${query}` : ''}`)
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

export function startEvaluation(body) {
  return api.post('/api/v1/evaluations/run', {
    agent_id: body.agent_id,
    dataset_id: body.dataset_id,
    framework: body.framework || 'vertex_ai',
    metrics: body.metrics,
  })
}

export function retryEvaluation(evaluationId) {
  return api.post(`/api/v1/evaluations/${evaluationId}/retry`)
}
