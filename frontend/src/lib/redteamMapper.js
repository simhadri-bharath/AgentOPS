export function shortId(id) {
  if (!id) return '—'
  const s = String(id)
  return s.length > 8 ? `${s.slice(0, 8)}…` : s
}

export function classificationVariant(c) {
  if (c === 'PASS') return 'green'
  if (c === 'FAIL') return 'red'
  return 'amber'
}

export function severityVariant(s) {
  const v = (s || '').toLowerCase()
  if (v === 'critical') return 'red'
  if (v === 'high') return 'amber'
  if (v === 'low') return 'gray'
  if (v === 'unknown') return 'gray'
  return 'blue'
}

export function runStatusVariant(status) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'running') return 'blue'
  return 'gray'
}

export function categoryLabel(id) {
  const map = {
    prompt_injection: 'Prompt injection',
    jailbreak: 'Jailbreak',
    pii_extraction: 'PII extraction',
    boundary: 'Boundary',
  }
  return map[id] || id
}

export function traceUrl(traceId) {
  if (!traceId) return null
  return `/traces?trace=${encodeURIComponent(traceId)}`
}
