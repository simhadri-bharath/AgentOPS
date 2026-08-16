import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import RunComparison from '../components/RunComparison'
import { useAgents } from '../context/AgentsContext'
import * as evaluationsApi from '../api/evaluations'
import {
  formatEvalDate,
  passRateFromAggregates,
  runStatusLabel,
  runStatusVariant,
  shortId,
} from '../lib/evaluationMapper'

export default function History() {
  const nav = useNavigate()
  const { agents } = useAgents()
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [agentFilter, setAgentFilter] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit: 100 }
      if (agentFilter) params.agent_id = agentFilter
      const data = await evaluationsApi.fetchEvaluations(params)
      setRuns(data.items || [])
    } catch (err) {
      setError(err.message || 'Failed to load evaluations')
    } finally {
      setLoading(false)
    }
  }, [agentFilter])

  useEffect(() => {
    load()
  }, [load])

  const agentNameById = useMemo(() => {
    const map = {}
    for (const a of agents) map[a.id] = a.name
    return map
  }, [agents])

  const statusBadge = (run) => (
    <Badge variant={runStatusVariant(run.status)}>
      {runStatusLabel(run.status)}
    </Badge>
  )

  return (
    <div>
      <PageHeader
        title="Evaluation history"
        subtitle="Past evaluation runs from the AgentOPS backend"
      />

      {error && (
        <div
          className="mb-4 px-3 py-2 rounded-md text-[12px]"
          style={{ background: '#FEF2F2', color: '#991B1B' }}
        >
          {error}
        </div>
      )}

      <RunComparison runs={runs} />

      <Card>
        <CardHeader title="All runs">
          <select
            style={{ width: 180 }}
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
          >
            <option value="">All agents</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </CardHeader>

        {loading ? (
          <div className="flex items-center gap-2 text-[12px] text-gray-500 p-4">
            <Loader2 size={14} className="animate-spin" />
            Loading…
          </div>
        ) : runs.length === 0 ? (
          <EmptyState message="No evaluation runs yet. Start one from Run Evaluation." />
        ) : (
          <Table>
            <THead>
              <Th>Run ID</Th>
              <Th>Agent</Th>
              <Th>Pass rate</Th>
              <Th>Samples</Th>
              <Th>Date</Th>
              <Th>Status</Th>
            </THead>
            <tbody>
              {runs.map((r) => {
                const rate = passRateFromAggregates(r.aggregate_scores)
                return (
                  <TRow key={r.id} onClick={() => nav(`/results/${r.id}`)}>
                    <Td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                      {shortId(r.id)}
                    </Td>
                    <Td>{agentNameById[String(r.agent_id)] || shortId(r.agent_id)}</Td>
                    <Td>{rate != null ? `${rate}%` : '—'}</Td>
                    <Td>{r.aggregate_scores?.total_samples ?? '—'}</Td>
                    <Td style={{ color: '#6B7280' }}>
                      {formatEvalDate(r.completed_at || r.created_at)}
                    </Td>
                    <Td>{statusBadge(r)}</Td>
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
