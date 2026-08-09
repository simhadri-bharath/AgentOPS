import { api } from './client'

export function fetchDeployments({ refresh = false, inspectSessions = true } = {}) {
  const qs = new URLSearchParams()
  if (refresh) qs.set('refresh', 'true')
  if (!inspectSessions) qs.set('inspect_sessions', 'false')
  const query = qs.toString()
  return api.get(`/api/v1/deployments${query ? `?${query}` : ''}`)
}

export function fetchDeployment(engineId, region) {
  const qs = region ? `?region=${encodeURIComponent(region)}` : ''
  return api.get(`/api/v1/deployments/${engineId}${qs}`)
}

export function onboardDeployment(body) {
  return api.post('/api/v1/deployments/onboard', body)
}

export function offboardAgent(agentId) {
  return api.delete(`/api/v1/deployments/onboard/${agentId}`)
}

export function patchAgent(agentId, body) {
  return api.patch(`/api/v1/agents/${agentId}`, body)
}

export function testInvokeAgent(agentId, prompt) {
  return api.post(`/api/v1/agents/${agentId}/test-invoke`, { prompt })
}

export const AGENT_TYPES = [
  { value: 'rag', label: 'RAG', hint: 'Retrieves documents, answers from them' },
  { value: 'tool_calling', label: 'Tool calling', hint: 'Selects and invokes tools' },
  { value: 'conversational', label: 'Conversational', hint: 'Multi-turn dialogue' },
  { value: 'task', label: 'Task', hint: 'Single well-defined job' },
  { value: 'multi_agent', label: 'Multi-agent', hint: 'Sub-agents hand off to each other' },
  { value: 'unknown', label: 'Unknown', hint: 'Not classified yet' },
]

export const CAPABILITIES = [
  'retrieval',
  'tool_use',
  'reasoning',
  'code_execution',
  'external_api',
  'memory',
  'multi_agent',
]

export const ENVIRONMENTS = [
  { value: 'development', label: 'Development' },
  { value: 'staging', label: 'Staging' },
  { value: 'production', label: 'Production' },
]
