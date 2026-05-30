import { api } from './client'

export function fetchTraces(params = {}) {
  const qs = new URLSearchParams()
  if (params.hours != null) qs.set('hours', String(params.hours))
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.agent) qs.set('agent', params.agent)
  const query = qs.toString()
  return api.get(`/api/v1/traces${query ? `?${query}` : ''}`)
}

export function fetchTraceDetail(traceId) {
  return api.get(`/api/v1/traces/${traceId}`)
}
