import { api } from './client'

export const REDTEAM_CATEGORIES = [
  { id: 'prompt_injection', label: 'Prompt injection', desc: 'Override system instructions' },
  { id: 'jailbreak', label: 'Jailbreak', desc: 'Persona and policy bypasses' },
  { id: 'pii_extraction', label: 'PII extraction', desc: 'Sensitive data exfiltration' },
  { id: 'boundary', label: 'Boundary testing', desc: 'Off-topic adversarial inputs' },
]

export function fetchRedTeamDashboard() {
  return api.get('/api/v1/redteam/dashboard')
}

export function fetchRedTeamRuns(params = {}) {
  const qs = new URLSearchParams()
  if (params.agent_id) qs.set('agent_id', params.agent_id)
  if (params.status) qs.set('status', params.status)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString()
  return api.get(`/api/v1/redteam/runs${query ? `?${query}` : ''}`)
}

export function fetchRedTeamRun(runId) {
  return api.get(`/api/v1/redteam/runs/${runId}`)
}

export function fetchRedTeamResults(runId, params = {}) {
  const qs = new URLSearchParams()
  if (params.classification) qs.set('classification', params.classification)
  if (params.category) qs.set('category', params.category)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString()
  return api.get(`/api/v1/redteam/runs/${runId}/results${query ? `?${query}` : ''}`)
}

export function fetchRedTeamResult(runId, resultId) {
  return api.get(`/api/v1/redteam/runs/${runId}/results/${resultId}`)
}

export function fetchTestCases(params = {}) {
  const qs = new URLSearchParams()
  if (params.category) qs.set('category', params.category)
  if (params.source) qs.set('source', params.source)
  if (params.limit != null) qs.set('limit', String(params.limit))
  const query = qs.toString()
  return api.get(`/api/v1/redteam/test-cases${query ? `?${query}` : ''}`)
}

export function createTestCase(body) {
  return api.post('/api/v1/redteam/test-cases', body)
}

export function startRedTeamRun(body) {
  const payload = {
    agent_id: body.agent_id,
    scan_mode: body.scan_mode || 'custom',
    judge_model: body.judge_model || 'gemini-2.5-flash',
  }

  if (body.scan_mode === 'dynamic') {
    // Dynamic mode (DeepTeam) fields
    payload.target_purpose = body.target_purpose
    payload.target_system_prompt = body.target_system_prompt
    payload.vulnerabilities = body.vulnerabilities
    payload.attacks = body.attacks
    payload.categories = (body.vulnerabilities || []).map((v) => v.name || v.id)
  } else {
    // Custom mode fields
    payload.categories = body.categories
    payload.use_llm_judge = body.use_llm_judge !== false
    payload.include_custom_cases = body.include_custom_cases !== false
    if (body.selected_case_ids != null) {
      payload.selected_case_ids = body.selected_case_ids
    }
  }
  return api.post('/api/v1/redteam/runs', payload)
}

export function fetchJudgeModels() {
  return api.get('/api/v1/redteam/meta/judge-models')
}

// DeepTeam catalog APIs
export function fetchDeepTeamVulnerabilities() {
  return api.get('/api/v1/redteam/deepteam/vulnerabilities')
}

export function fetchDeepTeamFrameworks() {
  return api.get('/api/v1/redteam/deepteam/frameworks')
}

export function fetchDeepTeamAttacks() {
  return api.get('/api/v1/redteam/deepteam/attacks')
}

// Agent metadata (for metadata preview step)
export function fetchAgentMetadata(agentId) {
  return api.get(`/api/v1/agents/${agentId}/metadata`)
}
