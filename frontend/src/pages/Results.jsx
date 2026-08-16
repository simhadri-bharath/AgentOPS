import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { History, Loader2, RotateCcw } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import Btn from '../components/Btn'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import { useAgents } from '../context/AgentsContext'
import * as evaluationsApi from '../api/evaluations'
import {
  formatEvalDate,
  formatLatencyMs,
  passRateFromAggregates,
  runStatusLabel,
  runStatusVariant,
  samplePassed,
  shortId,
} from '../lib/evaluationMapper'

function ScoreCard({ value, label, barWidth, barColor }) {
  return (
    <div
      className="bg-white border border-gray-200 rounded-lg p-3 text-center"
      style={{ borderWidth: '0.5px' }}
    >
      <div className="text-[26px] font-medium" style={{ color: barColor }}>
        {value}
      </div>
      <div
        className="w-[60px] h-1.5 rounded-full overflow-hidden mx-auto mt-1"
        style={{ background: '#F3F4F6' }}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${Math.min(barWidth, 100)}%`, background: barColor }}
        />
      </div>
      <div className="text-[11px] text-gray-500 text-center mt-1.5">{label}</div>
    </div>
  )
}

const resultBadge = (passed) =>
  passed ? <Badge variant="green">Pass</Badge> : <Badge variant="red">Fail</Badge>

const POLL_MS = 3000
const TERMINAL = new Set(['completed', 'failed'])

export default function Results() {
  const { evaluationId } = useParams()
  const nav = useNavigate()
  const { agents } = useAgents()

  const [run, setRun] = useState(null)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')
  const [retrying, setRetrying] = useState(false)

  const load = useCallback(async () => {
    if (!evaluationId) return null
    const [runData, resultsData] = await Promise.all([
      evaluationsApi.fetchEvaluation(evaluationId),
      evaluationsApi.fetchEvaluationResults(evaluationId),
    ])
    setRun(runData)
    setResults(resultsData)
    setError(null)
    return runData
  }, [evaluationId])

  useEffect(() => {
    let cancelled = false
    let timer = null

    async function poll() {
      try {
        const runData = await load()
        if (cancelled) return
        if (runData && !TERMINAL.has(runData.status)) {
          timer = setTimeout(poll, POLL_MS)
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load evaluation')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    setLoading(true)
    poll()

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [evaluationId, load])

  const agentName = useMemo(() => {
    if (!run) return '—'
    const a = agents.find((x) => x.id === String(run.agent_id))
    return a?.name || shortId(run.agent_id)
  }, [run, agents])

  const aggregates = results?.aggregate_scores || run?.aggregate_scores || {}
  const items = results?.items || []
  const status = run?.status || results?.status || 'unknown'
  const passRate = passRateFromAggregates(aggregates)

  const filteredItems = useMemo(() => {
    return items.filter((row) => {
      const passed = samplePassed(row.scores, row.state)
      if (filter === 'passed') return passed
      if (filter === 'failed') return !passed
      return true
    })
  }, [items, filter])

  const handleRetry = async () => {
    setRetrying(true)
    setError(null)
    try {
      await evaluationsApi.retryEvaluation(evaluationId)
      await load()
    } catch (err) {
      setError(err.message || 'Retry failed')
    } finally {
      setRetrying(false)
    }
  }

  if (!evaluationId) {
    return <EmptyState message="No evaluation id in URL." />
  }

  const inProgress = status === 'queued' || status === 'running'

  return (
    <div>
      <PageHeader
        title={`Eval results · ${shortId(evaluationId)}`}
        subtitle={`${agentName} · ${run?.framework || 'vertex_ai'} · ${aggregates.total_samples ?? items.length} samples · ${formatEvalDate(run?.completed_at || run?.created_at)}`}
      >
        <Badge variant={runStatusVariant(status)}>{runStatusLabel(status)}</Badge>
        {(status === 'failed' || status === 'queued') && (
          <Btn disabled={retrying} onClick={handleRetry}>
            {retrying ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
            Retry
          </Btn>
        )}
        <Btn onClick={() => nav('/history')}>
          <History size={13} />
          History
        </Btn>
      </PageHeader>

      {error && (
        <div
          className="mb-4 px-3 py-2 rounded-md text-[12px]"
          style={{ background: '#FEF2F2', color: '#991B1B' }}
        >
          {error}
        </div>
      )}

      {run?.error_message && (
        <div
          className="mb-4 px-3 py-2 rounded-md text-[12px]"
          style={{ background: '#FFFBEB', color: '#92400E', border: '0.5px solid #FDE68A' }}
        >
          {run.error_message}
        </div>
      )}

      {inProgress && (
        <div className="flex items-center gap-2 mb-4 text-[12px] text-gray-600">
          <Loader2 size={16} className="animate-spin text-indigo-600" />
          Evaluation {runStatusLabel(status).toLowerCase()}… refreshing every few seconds.
        </div>
      )}

      <div className="grid grid-cols-5 gap-3 mb-4">
        <ScoreCard
          value={passRate != null ? `${passRate}%` : '—'}
          label="Pass rate"
          barWidth={passRate ?? 0}
          barColor="#22C55E"
        />
        <ScoreCard
          value={aggregates.total_passed ?? '—'}
          label="Passed"
          barWidth={
            aggregates.total_samples
              ? ((aggregates.total_passed || 0) / aggregates.total_samples) * 100
              : 0
          }
          barColor="#4F46E5"
        />
        <ScoreCard
          value={aggregates.total_failed ?? '—'}
          label="Failed"
          barWidth={
            aggregates.total_samples
              ? ((aggregates.total_failed || 0) / aggregates.total_samples) * 100
              : 0
          }
          barColor="#EF4444"
        />
        <ScoreCard
          value={formatLatencyMs(aggregates.avg_latency_ms)}
          label="Avg latency"
          barWidth={50}
          barColor="#F59E0B"
        />
        <ScoreCard
          value={aggregates.empty_responses ?? 0}
          label="Empty responses"
          barWidth={aggregates.empty_responses ? 100 : 0}
          barColor="#EF4444"
        />
      </div>

      <Card>
        <CardHeader title="Per-sample breakdown">
          <select style={{ width: 130 }} value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All cases</option>
            <option value="failed">Failed only</option>
            <option value="passed">Passed only</option>
          </select>
        </CardHeader>
        {loading && items.length === 0 ? (
          <div className="flex items-center gap-2 text-[12px] text-gray-500 p-4">
            <Loader2 size={14} className="animate-spin" />
            Loading results…
          </div>
        ) : filteredItems.length === 0 ? (
          <EmptyState
            message={
              inProgress
                ? 'Waiting for sample results…'
                : 'No samples match this filter.'
            }
          />
        ) : (
          <Table>
            <THead>
              <Th>#</Th>
              <Th>Input</Th>
              <Th>Output</Th>
              <Th>Latency</Th>
              <Th>Result</Th>
            </THead>
            <tbody>
              {filteredItems.map((row) => {
                const passed = samplePassed(row.scores, row.state)
                return (
                  <TRow
                    key={row.id}
                    highlight={!passed}
                    onClick={() => nav(`/results/${evaluationId}/samples/${row.id}`)}
                  >
                    <Td style={{ color: '#9CA3AF' }}>{row.sample_index + 1}</Td>
                    <Td
                      style={{
                        maxWidth: 180,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={row.input}
                    >
                      {row.input}
                    </Td>
                    <Td
                      style={{
                        maxWidth: 200,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={row.actual_output || row.scores?.invocation_error || ''}
                    >
                      {row.actual_output ||
                        (row.scores?.invocation_error ? (
                          <span style={{ color: '#991B1B' }}>{row.scores.invocation_error}</span>
                        ) : (
                          '—'
                        ))}
                    </Td>
                    <Td>{formatLatencyMs(row.latency_ms)}</Td>
                    <Td>{resultBadge(passed)}</Td>
                  </TRow>
                )
              })}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  )
}
