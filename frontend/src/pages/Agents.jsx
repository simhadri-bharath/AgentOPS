import React, { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import StatCard from '../components/StatCard'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import AgentIcon from '../components/AgentIcon'
import Btn from '../components/Btn'
import EmptyState from '../components/EmptyState'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import PageHeader from '../components/PageHeader'
import { Filter, RefreshCw, Loader2 } from 'lucide-react'
import { useAgents } from '../context/AgentsContext'
import { countByDeploymentType } from '../lib/agentMapper'

const platformBadge = (p) => {
  if (p === 'Vertex AI') return <Badge variant="purple">{p}</Badge>
  if (p === 'GKE') return <Badge variant="amber">{p}</Badge>
  return <Badge variant="blue">{p}</Badge>
}
const statusBadge = (s) => {
  if (s === 'Healthy') return <Badge variant="green">{s}</Badge>
  if (s === 'Degraded') return <Badge variant="amber">{s}</Badge>
  if (s === 'Inactive') return <Badge variant="gray">{s}</Badge>
  return <Badge variant="red">{s}</Badge>
}

export default function Agents() {
  const nav = useNavigate()
  const { agents, loading, syncing, error, syncDiscovery, refreshAgents } = useAgents()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')

  const counts = useMemo(() => countByDeploymentType(agents), [agents])
  const unhealthy = agents.filter((a) => a.status !== 'Healthy').length

  const filtered = useMemo(() => {
    return agents.filter((a) => {
      const q = search.trim().toLowerCase()
      const matchesSearch =
        !q ||
        a.name.toLowerCase().includes(q) ||
        a.slug?.toLowerCase().includes(q) ||
        a.region.toLowerCase().includes(q)
      const matchesType =
        typeFilter === 'all' ||
        (typeFilter === 'Vertex AI' && a.platform === 'Vertex AI') ||
        (typeFilter === 'Cloud Run' && a.platform === 'Cloud Run') ||
        (typeFilter === 'GKE' && a.platform === 'GKE')
      return matchesSearch && matchesType
    })
  }, [agents, search, typeFilter])

  const handleSync = async () => {
    try {
      await syncDiscovery()
    } catch {
      /* error in context */
    }
  }

  return (
    <div>
      <PageHeader title="All Agents" subtitle="Discovered from Vertex AI, Cloud Run, and GKE">
        <Btn><Filter size={13} />Filter</Btn>
        <Btn primary onClick={handleSync} disabled={syncing}>
          {syncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          {syncing ? 'Syncing…' : 'Re-discover'}
        </Btn>
      </PageHeader>

      {error && (
        <div className="mb-4 px-3 py-2 rounded-lg text-[13px] bg-red-50 text-red-800 border border-red-200">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => refreshAgents()}>
            Retry
          </button>
        </div>
      )}

      <div className="grid grid-cols-4 gap-3 mb-5">
        <StatCard label="Vertex AI" value={String(counts.vertex_ai)} />
        <StatCard label="Cloud Run" value={String(counts.cloud_run)} />
        <StatCard label="GKE" value={String(counts.gke)} />
        <StatCard
          label="Unhealthy"
          value={String(unhealthy)}
          valueStyle={{ color: unhealthy ? '#EF4444' : undefined }}
        />
      </div>

      <Card>
        <CardHeader title="Agent registry">
          <input
            type="search"
            placeholder="Filter agents..."
            style={{ width: 180 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            style={{ width: 130 }}
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="all">All types</option>
            <option value="Vertex AI">Vertex AI</option>
            <option value="Cloud Run">Cloud Run</option>
            <option value="GKE">GKE</option>
          </select>
        </CardHeader>
        {loading ? (
          <div className="flex items-center justify-center py-16 text-gray-500 gap-2">
            <Loader2 size={18} className="animate-spin" />
            Loading agents…
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            message={
              agents.length === 0
                ? 'No agents yet. Click Re-discover to sync from Vertex AI.'
                : 'No agents match your filters.'
            }
          />
        ) : (
          <Table>
            <THead>
              <Th>Name</Th>
              <Th>Platform</Th>
              <Th>Model</Th>
              <Th>Status</Th>
              <Th>Last active</Th>
              <Th></Th>
            </THead>
            <tbody>
              {filtered.map((a) => (
                <TRow key={a.id} onClick={() => nav(`/agents/${a.id}`)}>
                  <Td>
                    <div className="flex items-center gap-2 font-medium">
                      <AgentIcon color={a.iconColor} />
                      <div>
                        <div>{a.name}</div>
                        <div style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 400 }}>
                          {a.region}
                        </div>
                      </div>
                    </div>
                  </Td>
                  <Td>{platformBadge(a.platform)}</Td>
                  <Td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{a.model}</Td>
                  <Td>{statusBadge(a.status)}</Td>
                  <Td style={{ color: '#6B7280' }}>{a.lastActive}</Td>
                  <Td>
                    <Btn
                      style={{ fontSize: 11 }}
                      onClick={(e) => {
                        e.stopPropagation()
                        nav(`/evaluation?agentId=${a.id}`)
                      }}
                    >
                      Evaluate
                    </Btn>
                  </Td>
                </TRow>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  )
}
