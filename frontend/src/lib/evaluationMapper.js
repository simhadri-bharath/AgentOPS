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
/**
 * Whether a sample passed. Mirrors the backend rule in runner.aggregate():
 * the mean of the sample's scores must clear the threshold.
 *
 * The previous version returned true for any non-empty response, which is the
 * rule the backend no longer uses -- so the table would show a green tick on
 * samples the run counted as failures.
 */
export const PASS_THRESHOLD = 0.7

export function samplePassed(scores = {}, state = 'SUCCESS') {
  // An invocation that never succeeded is not a quality failure, and is not
  // scored at all.
  if (state && state !== 'SUCCESS') return false
  const values = Object.values(scores).filter((v) => typeof v === 'number')
  if (!values.length) return false
  return values.reduce((a, b) => a + b, 0) / values.length >= PASS_THRESHOLD
}

export function formatLatencyMs(ms) {
  if (ms == null || Number.isNaN(ms)) return '—'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

const SCORE_META_KEYS = new Set(['invocation_error', 'actual_output_nonempty'])

/** Split evaluation_results.scores JSON into displayable metrics and explanations. */
export function partitionSampleScores(scores = {}) {
  const metrics = []
  const explanations = {}
  for (const [key, value] of Object.entries(scores || {})) {
    if (key.endsWith('_explanation')) {
      explanations[key.replace(/_explanation$/, '')] = value
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
  if (typeof value === 'number') {
    // Every registry metric is 0..1 and higher-is-better, so a percentage is
    // always the right rendering. Binary values are shown as percentages too
    // rather than "Pass/Fail", which would imply a threshold that is not
    // per-metric.
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
  if (value >= 0 && value <= 1) return value
  return null
}
