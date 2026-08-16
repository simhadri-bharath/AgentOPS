/**
 * Severity bands for red-team scores, in one place.
 *
 * 11/31/56/81 were hardcoded across six spots in two pages, free to drift from
 * the backend's 0.35/0.45/0.65/0.85. These defaults mirror the backend, and
 * `loadScoringConfig()` replaces them with what the backend actually scores
 * with, so the colours can never disagree with the verdict.
 */
import { api } from '../api/client'

// 0..100, mirroring backend SCORING.thresholds.
export const SEVERITY_BANDS = {
  critical: 85,
  high: 65,
  medium: 45,
  low: 35,
}

export const SEVERITY_COLORS = {
  critical: '#dc2626',
  high: '#ef4444',
  medium: '#f59e0b',
  low: '#3b82f6',
  minimal: '#10b981',
}

export const SEVERITY_VARIANTS = {
  critical: 'red',
  high: 'red',
  medium: 'amber',
  low: 'blue',
  minimal: 'green',
}

/** Band name for a 0..100 score. */
export function severityForScore(score) {
  const value = Number(score) || 0
  if (value >= SEVERITY_BANDS.critical) return 'critical'
  if (value >= SEVERITY_BANDS.high) return 'high'
  if (value >= SEVERITY_BANDS.medium) return 'medium'
  if (value >= SEVERITY_BANDS.low) return 'low'
  return 'minimal'
}

export function severityColor(score) {
  return SEVERITY_COLORS[severityForScore(score)]
}

export function severityVariantForScore(score) {
  return SEVERITY_VARIANTS[severityForScore(score)]
}

export function severityLabel(score) {
  const band = severityForScore(score)
  return band.charAt(0).toUpperCase() + band.slice(1)
}

/** Adopt the backend's thresholds so the UI cannot disagree with the verdict. */
export async function loadScoringConfig() {
  try {
    const cfg = await api.get('/api/v1/redteam/meta/scoring')
    const bands = cfg?.severity_bands_0_100
    if (bands) Object.assign(SEVERITY_BANDS, bands)
    return cfg
  } catch {
    // Defaults already mirror the backend; a failed fetch is not worth
    // blocking the page over.
    return null
  }
}
