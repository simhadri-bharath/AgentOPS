import React, { useMemo, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Loader2 } from 'lucide-react'
import StatCard from '../components/StatCard'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import AgentIcon from '../components/AgentIcon'
import Btn from '../components/Btn'
import EmptyState from '../components/EmptyState'
import FirstRunGuide from '../components/FirstRunGuide'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import { useAgents } from '../context/AgentsContext'
import { formatRelativeTime } from '../lib/agentMapper'
import { fetchEvaluations } from '../api/evaluations'
import { fetchDatasets } from '../api/datasets'
import { shortId } from '../lib/evaluationMapper'

const statusBadge = (s) => {
  if (s === 'Healthy' || s === 'Pass' || s === 'Passed') return <Badge variant="green">{s}</Badge>
  if (s === 'Degraded' || s === 'Warn' || s === 'Partial') return <Badge variant="amber">{s}</Badge>
  if (s === 'Inactive') return <Badge variant="gray">{s}</Badge>
  if (s === 'Fail' || s === 'Failed') return <Badge variant="red">{s}</Badge>
  return <Badge>{s}</Badge>
}

const platformBadge = (p) => {
  if (p === 'Vertex AI') return <Badge variant="purple">{p}</Badge>
  if (p === 'GKE') return <Badge variant="amber">{p}</Badge>
  return <Badge variant="blue">{p}</Badge>
}

export default function Dashboard() {
  const nav = useNavigate()
  const { agents, loading, lastSyncedAt, health } = useAgents()

  const [runs, setRuns] = useState([])
  const [datasetCount, setDatasetCount] = useState(0)
  const [runsLoading, setRunsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetchEvaluations({ limit: 100 })
      .then((data) => {
        if (!cancelled) {
          setRuns(data.items || [])
        }
      })
      .catch((err) => {
        console.error('Failed to load dashboard evaluations:', err)
      })
      .finally(() => {
        if (!cancelled) setRunsLoading(false)
      })
    // Only the count matters here, for the first-run guide's second step.
    fetchDatasets({ limit: 1 })
      .then((data) => {
        if (!cancelled) setDatasetCount(data.total ?? (data.items || []).length)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const healthyCount = agents.filter((a) => a.status === 'Healthy').length
  const degradedCount = agents.length - healthyCount

  const syncLabel = useMemo(() => {
    if (lastSyncedAt) return `Last synced ${formatRelativeTime(lastSyncedAt.toISOString())}`
    return health?.status === 'healthy' ? 'Connected to backend' : 'Connect backend & run discovery'
  }, [lastSyncedAt, health])

  const agentNameById = useMemo(() => {
    const map = {}
    for (const a of agents) map[a.id] = a.name
    return map
  }, [agents])

  // 1. Eval runs (7d)
  const runs7d = useMemo(() => {
    const sevenDaysAgo = new Date()
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
    return runs.filter((r) => new Date(r.created_at) >= sevenDaysAgo)
  }, [runs])

  const runs7dMeta = useMemo(() => {
    if (runsLoading) return 'Loading…'
    const completed = runs7d.filter((r) => r.status === 'completed').length
    const failed = runs7d.filter((r) => r.status === 'failed').length
    return `${completed} completed · ${failed} failed`
  }, [runs7d, runsLoading])

  const completedRuns = useMemo(() => runs.filter((r) => r.status === 'completed'), [runs])

  // 2. Pass rate — samples that met their threshold. This is a pass rate, not a
  // metric score, and is labelled as one: calling it "faithfulness" invented a
  // number nothing measured.
  const passRate = useMemo(() => {
    const totalPassed = completedRuns.reduce((acc, r) => acc + (r.aggregate_scores?.total_passed || 0), 0)
    const totalSamples = completedRuns.reduce((acc, r) => acc + (r.aggregate_scores?.total_samples || 0), 0)
    return totalSamples > 0 ? totalPassed / totalSamples : null
  }, [completedRuns])

  const passRateMeta = useMemo(() => {
    if (runsLoading) return 'Loading…'
    if (passRate == null) return 'No completed runs yet'
    return `Across ${completedRuns.length} completed run${completedRuns.length !== 1 ? 's' : ''}`
  }, [completedRuns, passRate, runsLoading])

  // Mean of the metric scores actually recorded.
  //
  // aggregate_scores mixes 0-1 metric averages with diagnostics under the same
  // `avg_` prefix, and runs predating the metric registry declare metrics that
  // no longer exist -- `response_length` (a character count) and `latency_ms`
  // averaged in as "scores" of 7845 and 93448. Every registry metric is 0-1, so
  // anything outside that range is not a score.
  const avgQuality = useMemo(() => {
    const scores = completedRuns.flatMap((r) =>
      (r.metrics || [])
        .map((m) => r.aggregate_scores?.[`avg_${m}`])
        .filter((v) => typeof v === 'number' && v >= 0 && v <= 1),
    )
    if (scores.length === 0) return null
    return { value: scores.reduce((a, b) => a + b, 0) / scores.length, count: scores.length }
  }, [completedRuns])

  const avgLatency = useMemo(() => {
    const withLatency = completedRuns.filter((r) => r.aggregate_scores?.avg_latency_ms != null)
    if (withLatency.length === 0) return null
    const sum = withLatency.reduce((acc, r) => acc + r.aggregate_scores.avg_latency_ms, 0)
    return sum / withLatency.length / 1000
  }, [completedRuns])

  // 3. Status label mapper for runs
  const getRunStatusLabel = (run) => {
    if (run.status === 'failed') return 'Fail'
    if (run.status === 'queued') return 'Queued'
    if (run.status === 'running') return 'Running'
    const total = run.aggregate_scores?.total_samples || 0
    const passed = run.aggregate_scores?.total_passed || 0
    if (total > 0 && passed === total) return 'Pass'
    if (total > 0 && passed > 0) return 'Warn'
    if (total > 0) return 'Fail'
    return '—'
  }

  // 4. Metric trends (7d)
  const metricTrendsData = useMemo(() => {
    const result = []
    const now = new Date()
    for (let i = 6; i >= 0; i--) {
      const d = new Date()
      d.setDate(now.getDate() - i)
      const dayLabel = i === 0 ? 'Today' : d.toLocaleDateString([], { weekday: 'short' })

      const dayRuns = runs.filter((r) => {
        if (r.status !== 'completed' || !r.completed_at) return false
        const compDate = new Date(r.completed_at)
        return compDate.toDateString() === d.toDateString()
      })

      let avgPassRate = null
      let avgLatencySec = null
      if (dayRuns.length > 0) {
        const totalPassed = dayRuns.reduce((acc, r) => acc + (r.aggregate_scores?.total_passed || 0), 0)
        const totalSamples = dayRuns.reduce((acc, r) => acc + (r.aggregate_scores?.total_samples || 0), 0)
        avgPassRate = totalSamples > 0 ? totalPassed / totalSamples : 0

        const runsWithLatency = dayRuns.filter((r) => r.aggregate_scores?.avg_latency_ms != null)
        if (runsWithLatency.length > 0) {
          const sum = runsWithLatency.reduce((acc, r) => acc + r.aggregate_scores.avg_latency_ms, 0)
          avgLatencySec = (sum / runsWithLatency.length) / 1000
        }
      }

      // null, not 0: a day with no runs is a gap in the line, not a zero score.
      result.push({
        day: dayLabel,
        passRate: avgPassRate != null ? Number(avgPassRate.toFixed(2)) : null,
        latency: avgLatencySec != null ? Number(avgLatencySec.toFixed(2)) : null,
        runs: dayRuns.length,
      })
    }
    return result
  }, [runs])

  // A chart with no runs behind it used to render eight hardcoded points that a
  // user could not tell from their own results.
  const trendsHaveData = useMemo(
    () => metricTrendsData.some((d) => d.passRate != null || d.latency != null),
    [metricTrendsData],
  )

  return (
    <div>
      <div className="mb-5">
        <div className="text-[20px] font-medium text-gray-900 mb-1">Platform Overview</div>
        <div className="text-[13px] text-gray-500">
          All agents across your GCP environment — {syncLabel}
        </div>
      </div>

      {/* Empty charts tell a new user nothing about where to start. */}
      <FirstRunGuide agents={agents} datasets={datasetCount} runs={runs.length} />

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-5">
        <StatCard
          label="Total agents"
          value={loading ? '…' : String(agents.length)}
          meta={
            loading ? null : (
              <>
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 mr-1" />
                {healthyCount} reachable · {degradedCount} unreachable
              </>
            )
          }
        />
        <StatCard
          label="Eval runs (7d)"
          value={runsLoading ? '…' : String(runs7d.length)}
          meta={runs7dMeta}
        />
        <StatCard
          label="Pass rate"
          value={runsLoading ? '…' : passRate == null ? '—' : passRate.toFixed(2)}
          meta={passRateMeta}
        />
        <StatCard
          label="Avg metric score"
          value={runsLoading ? '…' : avgQuality == null ? '—' : avgQuality.value.toFixed(2)}
          meta={
            runsLoading
              ? 'Loading…'
              : avgQuality == null
                ? 'No scored metrics yet'
                : `Mean of ${avgQuality.count} recorded metric score${avgQuality.count !== 1 ? 's' : ''}`
          }
        />
        <StatCard
          label="Avg latency"
          value={runsLoading ? '…' : avgLatency == null ? '—' : `${avgLatency.toFixed(2)}s`}
          meta={avgLatency == null ? 'No timed runs yet' : 'End-to-end execution time'}
        />
        <StatCard
          label="API health"
          value={health?.status === 'healthy' ? 'OK' : health?.status === 'degraded' ? 'Degraded' : '—'}
          meta={
            health
              ? `DB: ${health.database} · GCP: ${health.gcp_auth}`
              : 'Checking…'
          }
        />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <Card>
          <CardHeader title="Agent health">
            <Btn onClick={() => nav('/agents')} style={{ fontSize: 11 }}>View all</Btn>
          </CardHeader>
          {loading ? (
            <div className="flex justify-center py-10 text-gray-500">
              <Loader2 size={20} className="animate-spin" />
            </div>
          ) : agents.length === 0 ? (
            <EmptyState message="No agents discovered yet." />
          ) : (
            <Table>
              <THead>
                <Th>Agent</Th><Th>Type</Th><Th>Status</Th><Th>Last active</Th>
              </THead>
              <tbody>
                {/* Unreachable agents were taking the top of the list from the
                    ones the user can actually run against. */}
                {[...agents]
                  .sort(
                    (a, b) =>
                      (a.status === 'Inactive' ? 1 : 0) - (b.status === 'Inactive' ? 1 : 0),
                  )
                  .slice(0, 4)
                  .map((a) => (
                  <TRow key={a.id} onClick={() => nav(`/agents/${a.id}`)}>
                    <Td>
                      <div className="flex items-center gap-2 font-medium">
                        <AgentIcon color={a.iconColor} />
                        {a.name}
                      </div>
                    </Td>
                    <Td>{platformBadge(a.platform)}</Td>
                    <Td>{statusBadge(a.status)}</Td>
                    <Td style={{ color: '#6B7280', fontSize: 12 }}>{a.lastActive}</Td>
                  </TRow>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        <Card>
          <CardHeader title="Recent eval runs">
            <Btn onClick={() => nav('/history')} style={{ fontSize: 11 }}>View history</Btn>
          </CardHeader>
          {runsLoading ? (
            <div className="flex justify-center py-10 text-gray-500">
              <Loader2 size={20} className="animate-spin" />
            </div>
          ) : runs.length === 0 ? (
            <EmptyState message="No evaluations run yet." />
          ) : (
            <Table>
              <THead>
                <Th>Run</Th><Th>Agent</Th><Th>Score</Th><Th>Status</Th>
              </THead>
              <tbody>
                {runs.slice(0, 4).map((r) => {
                  // total_passed is absent on runs that never scored, which
                  // divided out to a literal "NaN" on screen.
                  const total = r.aggregate_scores?.total_samples || 0
                  const passed = r.aggregate_scores?.total_passed
                  const score =
                    total > 0 && typeof passed === 'number' ? (passed / total).toFixed(2) : '—'
                  return (
                    <TRow key={r.id} onClick={() => nav(`/results/${r.id}`)}>
                      <Td>
                        <div className="font-medium">{r.name || shortId(r.id)}</div>
                        <div style={{ fontSize: 10, color: '#9CA3AF' }}>
                          {formatRelativeTime(r.created_at)}
                        </div>
                      </Td>
                      <Td>{agentNameById[String(r.agent_id)] || shortId(r.agent_id)}</Td>
                      <Td>{score}</Td>
                      <Td>{statusBadge(getRunStatusLabel(r))}</Td>
                    </TRow>
                  )
                })}
              </tbody>
            </Table>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Pass rate and latency (7d)" />
        {!trendsHaveData ? (
          <EmptyState message="No runs completed in the last 7 days. Run an evaluation to start a trend." />
        ) : (
          <>
            <ResponsiveContainer width="100%" height={90}>
              <LineChart data={metricTrendsData} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="left" domain={[0, 1]} hide />
                <YAxis yAxisId="right" orientation="right" hide />
                <Tooltip
                  contentStyle={{ fontSize: 11, background: '#fff', border: '0.5px solid #E5E7EB', borderRadius: 6 }}
                  labelStyle={{ color: '#6B7280' }}
                  formatter={(v, name) =>
                    name === 'latency' ? [`${v}s`, 'Avg latency'] : [v, 'Pass rate']
                  }
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="passRate"
                  stroke="#4F46E5"
                  strokeWidth={2}
                  connectNulls
                  dot={{ r: 2 }}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="latency"
                  stroke="#F59E0B"
                  strokeWidth={1.5}
                  connectNulls
                  dot={{ r: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
            <div className="flex gap-4 mt-1">
              <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
                <div className="w-4 h-0.5 bg-indigo-600 rounded" />Pass rate
              </div>
              <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
                <div className="w-4 h-0.5 bg-[#F59E0B] rounded" />Avg latency (s)
              </div>
              <div className="text-[11px] text-gray-400">Gaps are days with no completed runs.</div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

