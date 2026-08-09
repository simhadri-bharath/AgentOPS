import React, { useEffect, useMemo, useState } from 'react'
import { Code2, Route, Sparkles, ShieldCheck, Activity, Loader2, Sprout } from 'lucide-react'

import MetricSection from './MetricSection'
import MetricRow from './MetricRow'
import SummaryPanel from './SummaryPanel'
import InfoBanner from './InfoBanner'
import Badge from '../Badge'
import Btn from '../Btn'
import { fetchMetricCatalogue, fetchRecommendedMetrics } from '../../api/evaluations'

const CATEGORY_META = {
  quality: { label: 'Response quality', icon: Sparkles, description: 'Is the answer any good?' },
  rag: { label: 'Retrieval & grounding', icon: Sprout, description: 'Is the answer supported by what was retrieved?' },
  trajectory: { label: 'Tool use & trajectory', icon: Route, description: 'Did the agent take the right path?' },
  trace_health: { label: 'Trace health', icon: Activity, description: 'Deterministic checks. No judge, no reference, no cost.' },
  safety: { label: 'Safety', icon: ShieldCheck, description: 'Toxicity and bias.' },
  deterministic: { label: 'Deterministic', icon: Code2, description: 'Exact string comparisons. Cheap and reproducible.' },
}

const CATEGORY_ORDER = ['quality', 'rag', 'trajectory', 'safety', 'trace_health', 'deterministic']

const COST_VARIANT = { free: 'green', low: 'blue', medium: 'amber', high: 'red' }

export default function MetricsStep({
  metricsOn,
  onToggleMetric,
  onApplyRecommended,
  selectedAgent,
  selectedDataset,
  selectedFramework,
}) {
  const [catalogue, setCatalogue] = useState([])
  const [recommended, setRecommended] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchMetricCatalogue()
        if (!cancelled) setCatalogue(data.items || [])
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!selectedAgent?.id) return
    let cancelled = false
    fetchRecommendedMetrics(selectedAgent.id)
      .then((data) => {
        if (cancelled) return
        setRecommended(data)
        // Pre-select the pack that suits this agent. Overridable, not a gate.
        onApplyRecommended?.(data.metrics || [])
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
    // onApplyRecommended is stable in the parent; agent id drives this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgent?.id])

  const grouped = useMemo(() => {
    const byCategory = {}
    for (const metric of catalogue) {
      ;(byCategory[metric.category] ||= []).push(metric)
    }
    return CATEGORY_ORDER.filter((c) => byCategory[c]).map((c) => ({
      id: c,
      ...CATEGORY_META[c],
      metrics: byCategory[c],
    }))
  }, [catalogue])

  const selected = Object.entries(metricsOn)
    .filter(([, on]) => on)
    .map(([id]) => id)

  const recommendedSet = new Set(recommended?.metrics || [])
  const referenceBased = new Set(recommended?.reference_based || [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-500 gap-2">
        <Loader2 size={18} className="animate-spin" />
        Loading metric catalogue…
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start animate-in fade-in duration-300">
      <div className="lg:col-span-2 flex flex-col gap-4">
        {error && (
          <div className="px-3 py-2 rounded-lg text-[13px] bg-red-50 text-red-800 border border-red-200">
            {error}
          </div>
        )}

        {recommended && (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50/60 px-3.5 py-3">
            <div className="flex items-center justify-between gap-3 mb-1">
              <span className="text-[13px] font-semibold text-indigo-900">
                Recommended for {recommended.agent_type}
                {recommended.capabilities.length > 0
                  ? ` · ${recommended.capabilities.join(', ')}`
                  : ''}
              </span>
              <Btn onClick={() => onApplyRecommended?.(recommended.metrics)}>Apply pack</Btn>
            </div>
            <div className="text-[12px] text-indigo-800">{recommended.rationale}</div>
            {recommended.note && (
              <div className="text-[11px] text-indigo-700 mt-1">{recommended.note}</div>
            )}
          </div>
        )}

        {grouped.map((cat) => {
          const activeCount = cat.metrics.filter((m) => !!metricsOn[m.name]).length
          return (
            <MetricSection
              key={cat.id}
              title={cat.label}
              icon={cat.icon}
              description={cat.description}
              activeCountText={`${activeCount} active`}
            >
              {cat.id === 'trace_health' && (
                <InfoBanner
                  message="These run on every sample with no judge call and no reference data."
                  type="info"
                />
              )}
              <div className="grid grid-cols-1 md:grid-cols-2">
                {cat.metrics.map((m, idx) => (
                  <div
                    key={m.name}
                    className={`border-b border-gray-100 md:border-b ${
                      idx % 2 === 0 ? 'md:border-r md:border-gray-100' : ''
                    }`}
                  >
                    <MetricRow
                      label={
                        <span className="flex items-center gap-1.5">
                          {m.label}
                          {recommendedSet.has(m.name) && <Badge variant="purple">recommended</Badge>}
                          {m.requires_reference && <Badge variant="amber">needs reference</Badge>}
                          {m.supports_span && <Badge variant="blue">per sub-agent</Badge>}
                          <Badge variant={COST_VARIANT[m.cost] || 'gray'}>{m.cost}</Badge>
                        </span>
                      }
                      description={
                        m.requires_reference && referenceBased.has(m.name)
                          ? `${m.description} Requires: ${m.requires.join(', ')}.`
                          : m.description
                      }
                      checked={!!metricsOn[m.name]}
                      onChange={(on) => onToggleMetric(m.name, on)}
                    />
                  </div>
                ))}
              </div>
            </MetricSection>
          )
        })}
      </div>

      <div className="lg:sticky lg:top-4">
        <SummaryPanel
          agent={selectedAgent}
          dataset={selectedDataset}
          framework={selectedFramework}
          selectedMetrics={selected}
        />
      </div>
    </div>
  )
}
