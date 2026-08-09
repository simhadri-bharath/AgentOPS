import React, { useMemo, useState } from 'react'
import { AlertTriangle, GitCompare, Loader2 } from 'lucide-react'
import { Card, CardHeader } from './Card'
import Badge from './Badge'
import Btn from './Btn'
import { compareEvaluations } from '../api/evaluations'
import { metricLabel } from '../lib/evaluationConstants'

const DIRECTION = {
  improved: { variant: 'green', arrow: '▲' },
  regressed: { variant: 'red', arrow: '▼' },
  unchanged: { variant: 'gray', arrow: '–' },
  new: { variant: 'blue', arrow: '+' },
  dropped: { variant: 'amber', arrow: '×' },
}

/**
 * Compare two runs.
 *
 * The deltas are the easy part. The warnings are the point: a score that moved
 * because the judge model changed is not evidence about the agent, and this
 * says so rather than letting the number speak for itself.
 */
export default function RunComparison({ runs }) {
  const comparable = useMemo(
    () => runs.filter((r) => r.status === 'completed'),
    [runs],
  )
  const [current, setCurrent] = useState('')
  const [baseline, setBaseline] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const run = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await compareEvaluations(current, baseline))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (comparable.length < 2) return null

  const label = (r) => `${r.name} · ${new Date(r.created_at).toLocaleDateString()}`

  return (
    <Card className="mb-5">
      <CardHeader title="Compare runs" />
      <div className="px-3 pb-3">
        <div className="flex flex-wrap items-end gap-2 mb-3">
          <div>
            <label className="block text-[11px] text-gray-500 mb-1">This run</label>
            <select value={current} onChange={(e) => setCurrent(e.target.value)} style={{ width: 220 }}>
              <option value="">Select…</option>
              {comparable.map((r) => (
                <option key={r.id} value={r.id}>{label(r)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[11px] text-gray-500 mb-1">Baseline</label>
            <select value={baseline} onChange={(e) => setBaseline(e.target.value)} style={{ width: 220 }}>
              <option value="">Select…</option>
              {comparable.filter((r) => r.id !== current).map((r) => (
                <option key={r.id} value={r.id}>{label(r)}</option>
              ))}
            </select>
          </div>
          <Btn primary onClick={run} disabled={!current || !baseline || loading}>
            {loading ? <Loader2 size={13} className="animate-spin" /> : <GitCompare size={13} />}
            Compare
          </Btn>
        </div>

        {error && (
          <div className="mb-3 px-3 py-2 rounded-lg text-[12px] bg-red-50 text-red-800 border border-red-200">
            {error}
          </div>
        )}

        {result && (
          <>
            <div className="text-[13px] font-medium text-gray-900 mb-2">{result.summary}</div>

            {!result.comparable && (
              <div className="mb-3 px-3 py-2 rounded-lg text-[12px] bg-amber-50 text-amber-900 border border-amber-200">
                <div className="flex items-center gap-1.5 font-medium mb-1">
                  <AlertTriangle size={13} />
                  These runs are not directly comparable
                </div>
                <ul className="list-disc pl-4 space-y-0.5">
                  {result.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
              {result.metric_deltas.map((m) => {
                const d = DIRECTION[m.direction] || DIRECTION.unchanged
                return (
                  <div
                    key={m.metric}
                    className="flex items-center justify-between border-b border-gray-100 py-1.5"
                  >
                    <span className="text-[12px] text-gray-800">{metricLabel(m.metric)}</span>
                    <span className="flex items-center gap-2 text-[12px]">
                      <span className="text-gray-400">
                        {m.baseline ?? '—'} → {m.current ?? '—'}
                      </span>
                      <Badge variant={d.variant}>
                        {d.arrow} {m.delta == null ? m.direction : m.delta.toFixed(4)}
                      </Badge>
                    </span>
                  </div>
                )
              })}
            </div>

            {result.span_deltas.length > 0 && (
              <div className="mt-4">
                <div className="text-[12px] font-medium text-gray-900 mb-1">
                  By sub-agent
                </div>
                {/* This is what turns "faithfulness fell" into a place to look. */}
                {result.span_deltas.map((s) => (
                  <div
                    key={`${s.author}-${s.metric}`}
                    className="flex items-center justify-between border-b border-gray-100 py-1.5 text-[12px]"
                  >
                    <span className="text-gray-800">
                      {s.author} · {metricLabel(s.metric)}
                    </span>
                    <Badge variant={s.delta < 0 ? 'red' : 'green'}>
                      {s.baseline} → {s.current} ({s.delta > 0 ? '+' : ''}
                      {s.delta})
                    </Badge>
                  </div>
                ))}
              </div>
            )}

            {result.regressed_samples.length > 0 && (
              <div className="mt-4">
                <div className="text-[12px] font-medium text-gray-900 mb-1">
                  Regressed samples ({result.regressed_samples.length})
                </div>
                {result.regressed_samples.slice(0, 10).map((s, i) => (
                  <div key={i} className="border-b border-gray-100 py-1.5">
                    <div className="text-[12px] text-gray-800">
                      #{s.sample_index} · {metricLabel(s.metric)}{' '}
                      <span className="text-red-700">
                        {s.baseline} → {s.current} ({s.delta})
                      </span>
                    </div>
                    <div className="text-[11px] text-gray-500">{s.input}</div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </Card>
  )
}
