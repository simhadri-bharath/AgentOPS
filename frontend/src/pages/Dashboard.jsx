import React, { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Loader2 } from 'lucide-react'
import StatCard from '../components/StatCard'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import AgentIcon from '../components/AgentIcon'
import Btn from '../components/Btn'
import EmptyState from '../components/EmptyState'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import { evalRuns, metricTrends } from '../data/mockData'
import { useAgents } from '../context/AgentsContext'
import { formatRelativeTime } from '../lib/agentMapper'

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

  const healthyCount = agents.filter((a) => a.status === 'Healthy').length
  const degradedCount = agents.length - healthyCount

  const syncLabel = useMemo(() => {
    if (lastSyncedAt) return `Last synced ${formatRelativeTime(lastSyncedAt.toISOString())}`
    return health?.status === 'healthy' ? 'Connected to backend' : 'Connect backend & run discovery'
  }, [lastSyncedAt, health])

  return (
    <div>
      <div className="mb-5">
        <div className="text-[20px] font-medium text-gray-900 mb-1">Platform Overview</div>
        <div className="text-[13px] text-gray-500">
          All agents across your GCP environment — {syncLabel}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-5">
        <StatCard
          label="Total agents"
          value={loading ? '…' : String(agents.length)}
          meta={
            loading ? null : (
              <>
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 mr-1" />
                {healthyCount} healthy · {degradedCount} other
              </>
            )
          }
        />
        <StatCard
          label="Eval runs (7d)"
          value="24"
          meta={<><span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-600 mr-1" />Mock data</>}
        />
        <StatCard
          label="Avg faithfulness"
          value="0.84"
          meta={<><span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 mr-1" />Mock data</>}
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
                {agents.slice(0, 4).map((a) => (
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
          <Table>
            <THead>
              <Th>Run</Th><Th>Agent</Th><Th>Score</Th><Th>Status</Th>
            </THead>
            <tbody>
              {evalRuns.slice(0, 4).map((r) => (
                <TRow key={r.id} onClick={() => nav('/results')}>
                  <Td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{r.id}</Td>
                  <Td>{r.agent}</Td>
                  <Td>{r.score}</Td>
                  <Td>{statusBadge(r.status)}</Td>
                </TRow>
              ))}
            </tbody>
          </Table>
        </Card>
      </div>

      <Card>
        <CardHeader title="Metric trends (7d)">
          <Badge variant="gray">Faithfulness</Badge>
          <Badge variant="gray">Relevancy</Badge>
          <Badge variant="gray">Latency</Badge>
        </CardHeader>
        <ResponsiveContainer width="100%" height={90}>
          <LineChart data={metricTrends} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
            <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ fontSize: 11, background: '#fff', border: '0.5px solid #E5E7EB', borderRadius: 6 }}
              labelStyle={{ color: '#6B7280' }}
            />
            <Line type="monotone" dataKey="faithfulness" stroke="#4F46E5" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="relevancy" stroke="#22C55E" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />
          </LineChart>
        </ResponsiveContainer>
        <div className="flex gap-4 mt-1">
          <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
            <div className="w-4 h-0.5 bg-indigo-600 rounded" />Faithfulness
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
            <div className="w-4 h-0.5 bg-green-500 rounded" style={{ borderTop: '1.5px dashed #22C55E' }} />Relevancy
          </div>
        </div>
      </Card>
    </div>
  )
}
