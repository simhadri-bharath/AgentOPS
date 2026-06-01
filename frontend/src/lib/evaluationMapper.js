/** Helpers for evaluation API data in the UI. */

export function formatEvalDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function shortId(uuid) {
  if (!uuid) return '—'
  const s = String(uuid)
  return s.length > 8 ? s.slice(0, 8) : s
}

export function runStatusLabel(status) {
  const s = (status || '').toLowerCase()
  if (s === 'draft') return 'Draft'
  if (s === 'completed') return 'Completed'
  if (s === 'running') return 'Running'
  if (s === 'queued') return 'Queued'
  if (s === 'failed') return 'Failed'
  return status || 'Unknown'
}

export function runStatusVariant(status, aggregates = {}) {
  const s = (status || '').toLowerCase()
  if (s === 'draft') return 'gray'
  if (s === 'failed') return 'red'
  if (s === 'running' || s === 'queued') return 'amber'
  const total = aggregates.total_samples || 0
  const passed = aggregates.total_passed || 0
  if (total > 0 && passed === total) return 'green'
  if (total > 0 && passed > 0) return 'amber'
  if (total > 0) return 'red'
  return 'blue'
}

export function passRateFromAggregates(aggregates = {}) {
  const total = aggregates.total_samples || 0
  const passed = aggregates.total_passed || 0
  if (!total) return null
  return Math.round((passed / total) * 100)
}

/** Mirrors backend compute_aggregates per-sample pass logic. */
export function samplePassed(scores = {}) {
  if (scores.invocation_error) return false
  const em = scores.exact_match
  const ce = scores.contains_expected
  const rn = scores.response_nonempty
  if (em === 1 || em === 1.0) return true
  if (ce === 1 || ce === 1.0) return true
  if (rn === 1 || rn === 1.0) return true
  if (em == null && ce == null && scores.actual_output_nonempty) return true
  return false
}

export function formatLatencyMs(ms) {
  if (ms == null || Number.isNaN(ms)) return '—'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}
