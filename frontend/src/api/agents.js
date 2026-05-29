import { api } from './client'

export function fetchAgents(params = {}) {
  const qs = new URLSearchParams()
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  if (params.deployment_type) qs.set('deployment_type', params.deployment_type)
  const query = qs.toString()
  return api.get(`/api/v1/agents${query ? `?${query}` : ''}`)
}

export function fetchAgent(agentId) {
  return api.get(`/api/v1/agents/${agentId}`)
}

export function fetchAgentEvaluations(agentId, params = {}) {
  const qs = new URLSearchParams()
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString()
  return api.get(`/api/v1/agents/${agentId}/evaluations${query ? `?${query}` : ''}`)
}
