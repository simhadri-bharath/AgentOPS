import { api } from './client'

// Metric names come from GET /api/v1/evaluations/meta/metrics. A hardcoded
// list here named response_length and latency_ms, which the registry rejects.

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

export function fetchEvaluationResult(evaluationId, resultId) {
  return api.get(`/api/v1/evaluations/${evaluationId}/results/${resultId}`)
}

export function createEvaluationJob(body) {
  return api.post('/api/v1/evaluations/jobs', {
    agent_id: body.agent_id,
    dataset_id: body.dataset_id,
    framework: body.framework || 'deepeval',
    metrics: body.metrics,
    name: body.name,
  })
}

export function updateEvaluationJob(evaluationId, body) {
  return api.patch(`/api/v1/evaluations/${evaluationId}`, {
    agent_id: body.agent_id,
    dataset_id: body.dataset_id,
    framework: body.framework || 'deepeval',
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
    framework: body.framework || 'deepeval',
    metrics: body.metrics,
    name: body.name,
  })
}

export function retryEvaluation(evaluationId) {
  return api.post(`/api/v1/evaluations/${evaluationId}/retry`)
}

export function fetchMetricCatalogue() {
  return api.get('/api/v1/evaluations/meta/metrics')
}

export function fetchRecommendedMetrics(agentId) {
  return api.get(`/api/v1/agents/${agentId}/recommended-metrics`)
}

export function cancelEvaluation(evaluationId) {
  return api.post(`/api/v1/evaluations/${evaluationId}/cancel`)
}

export function deleteEvaluation(evaluationId) {
  return api.delete(`/api/v1/evaluations/${evaluationId}`)
}

export function compareEvaluations(evaluationId, baselineId) {
  return api.get(`/api/v1/evaluations/${evaluationId}/compare?baseline=${baselineId}`)
}
