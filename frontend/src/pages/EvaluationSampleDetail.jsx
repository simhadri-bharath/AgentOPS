import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import PageHeader from '../components/PageHeader'
import * as evaluationsApi from '../api/evaluations'
import { METRIC_SUMMARY_LABELS } from '../lib/evaluationConstants'
import {
  formatLatencyMs,
  formatMetricScore,
  metricScoreRatio,
  partitionSampleScores,
  samplePassed,
  shortId,
} from '../lib/evaluationMapper'

function metricLabel(key) {
  return METRIC_SUMMARY_LABELS[key] || key.replace(/_/g, ' ')
}

function MetricScoreRow({ metricKey, value, explanation }) {
  const ratio = metricScoreRatio(metricKey, value)
  const display = formatMetricScore(metricKey, value)

  return (
    <div className="py-2.5 border-b border-gray-100 last:border-b-0">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[12px] font-medium text-gray-800">{metricLabel(metricKey)}</span>
        <span className="text-[12px] font-mono text-gray-700">{display}</span>
      </div>
      {ratio != null && (
        <div className="flex items-center gap-2 mt-1.5">
          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.round(ratio * 100)}%`,
                backgroundColor:
                  ratio >= 0.7 ? '#22c55e' : ratio >= 0.4 ? '#f59e0b' : '#ef4444',
              }}
            />
          </div>
          <span className="text-[10px] text-gray-400 min-w-[32px] text-right">
            {(ratio * 100).toFixed(0)}%
          </span>
        </div>
      )}
      {explanation && (
        <p className="text-[11px] text-gray-600 mt-1.5 whitespace-pre-wrap">{explanation}</p>
      )}
    </div>
  )
}

export default function EvaluationSampleDetail() {
  const { evaluationId, resultId } = useParams()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await evaluationsApi.fetchEvaluationResult(evaluationId, resultId)
        if (!cancelled) setResult(data)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load sample')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    if (evaluationId && resultId) load()
    return () => {
      cancelled = true
    }
  }, [evaluationId, resultId])

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-gray-500 text-[12px]">
        <Loader2 className="animate-spin" size={16} />
        Loading sample…
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="p-8 text-red-700 text-[12px]">
        {error || 'Sample not found'}
        <Link to={`/results/${evaluationId}`} className="block mt-2 text-indigo-600">
          Back to evaluation results
        </Link>
      </div>
    )
  }

  const passed = samplePassed(result.scores)
  const { metrics, explanations, invocationError, outputNonempty } = partitionSampleScores(
    result.scores
  )

  return (
    <div>
      <PageHeader
        title={`Sample ${result.sample_index + 1}`}
        subtitle={`Eval ${shortId(evaluationId)} · Result ${shortId(resultId)}`}
      >
        <Link to={`/results/${evaluationId}`} className="text-[12px] text-indigo-600">
          ← Back to results
        </Link>
      </PageHeader>

      <div className="flex flex-wrap gap-2 mb-4">
        {passed ? <Badge variant="green">Pass</Badge> : <Badge variant="red">Fail</Badge>}
        <Badge variant="gray">Latency {formatLatencyMs(result.latency_ms)}</Badge>
        {outputNonempty != null && (
          <Badge variant={outputNonempty ? 'green' : 'red'}>
            Output {outputNonempty ? 'non-empty' : 'empty'}
          </Badge>
        )}
      </div>

      {invocationError && (
        <div
          className="mb-4 px-3 py-2 rounded-md text-[12px]"
          style={{ background: '#FEF2F2', color: '#991B1B' }}
        >
          Invocation error: {invocationError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        <Card>
          <CardHeader title="Input prompt" />
          <pre className="p-3 text-[12px] whitespace-pre-wrap text-gray-800">{result.input}</pre>
        </Card>

        {result.expected_output && (
          <Card>
            <CardHeader title="Expected output" />
            <pre className="p-3 text-[12px] whitespace-pre-wrap text-gray-800">
              {result.expected_output}
            </pre>
          </Card>
        )}

        <Card>
          <CardHeader title="Agent output" />
          <pre className="p-3 text-[12px] whitespace-pre-wrap text-gray-800">
            {result.actual_output || '(empty)'}
          </pre>
        </Card>

        <Card>
          <CardHeader title="Evaluation metrics" />
          {metrics.length === 0 ? (
            <p className="p-3 text-[12px] text-gray-500 italic">No metrics recorded for this sample.</p>
          ) : (
            <div className="px-3 pb-2">
              {metrics.map(({ key, value }) => (
                <MetricScoreRow
                  key={key}
                  metricKey={key}
                  value={value}
                  explanation={explanations[key]}
                />
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
