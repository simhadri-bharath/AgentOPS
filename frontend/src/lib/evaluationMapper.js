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

const SCORE_META_KEYS = new Set(['invocation_error', 'actual_output_nonempty'])
const HIDDEN_EXPLANATION_METRICS = new Set(['hallucination'])

/** Split evaluation_results.scores JSON into displayable metrics and explanations. */
export function partitionSampleScores(scores = {}) {
  const metrics = []
  const explanations = {}
  for (const [key, value] of Object.entries(scores || {})) {
    if (key.endsWith('_explanation')) {
      const metricKey = key.replace(/_explanation$/, '')
      if (!HIDDEN_EXPLANATION_METRICS.has(metricKey)) {
        explanations[metricKey] = value
      }
      continue
    }
    if (SCORE_META_KEYS.has(key)) continue
    metrics.push({ key, value })
  }
  metrics.sort((a, b) => a.key.localeCompare(b.key))
  return {
    metrics,
    explanations,
    invocationError: scores.invocation_error,
    outputNonempty: scores.actual_output_nonempty,
  }
}

/** Human-readable value for a single metric entry in scores JSON. */
export function formatMetricScore(key, value) {
  if (value == null) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (key === 'response_length' && typeof value === 'number') {
    return `${value} chars`
  }
  if (key === 'latency_ms' && typeof value === 'number') {
    return formatLatencyMs(value)
  }
  if (typeof value === 'number') {
    if (value === 0 || value === 1) {
      return value === 1 ? 'Pass (1.0)' : 'Fail (0.0)'
    }
    if (value >= 0 && value <= 1) {
      return `${(value * 100).toFixed(1)}%`
    }
    return String(value)
  }
  return String(value)
}

/** 0–1 score for metric progress bars; null if not applicable. */
export function metricScoreRatio(key, value) {
  if (value == null || typeof value !== 'number') return null
  if (key === 'response_length' || key === 'latency_ms') return null
  if (value >= 0 && value <= 1) return value
  return null
}
