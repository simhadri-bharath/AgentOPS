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
import { RefreshCw, Loader2 } from 'lucide-react'
import { useAgents } from '../context/AgentsContext'

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

  // Inactive is not unhealthy: these are engines the configured project can no
  // longer reach, not agents that are failing.
  const inactive = agents.filter((a) => a.status === 'Inactive').length
  const degraded = agents.filter((a) => a.status !== 'Healthy' && a.status !== 'Inactive').length

  const filtered = useMemo(() => {
    const list = agents.filter((a) => {
      const q = search.trim().toLowerCase()
      const matchesSearch =
        !q ||
        a.name.toLowerCase().includes(q) ||
        a.slug?.toLowerCase().includes(q) ||
        a.region.toLowerCase().includes(q)
      const matchesStatus =
        typeFilter === 'all' ||
        (typeFilter === 'active' && a.status !== 'Inactive') ||
        (typeFilter === 'inactive' && a.status === 'Inactive')
      return matchesSearch && matchesStatus
    })
    // Agents you can actually run against come first.
    return [...list].sort(
      (a, b) => (a.status === 'Inactive' ? 1 : 0) - (b.status === 'Inactive' ? 1 : 0),
    )
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
      <PageHeader
        title="All Agents"
        subtitle="Agent Engine deployments discovered in the configured GCP project"
      >
        {/* A "Filter" button with no handler; the registry card filters. */}
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

      {/* Cloud Run and GKE discovery does not exist, so those cards could only
          ever read 0. */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <StatCard
          label="Evaluable"
          value={String(agents.length - inactive)}
          meta="Reachable in the configured project"
        />
        <StatCard
          label="Inactive"
          value={String(inactive)}
          meta={inactive ? 'Not reachable — cannot be evaluated' : 'All agents reachable'}
        />
        <StatCard
          label="Degraded"
          value={String(degraded)}
          valueStyle={{ color: degraded ? '#EF4444' : undefined }}
          meta="Reachable but reporting errors"
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
            <option value="all">All agents</option>
            <option value="active">Evaluable only</option>
            <option value="inactive">Inactive only</option>
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
              {/* Agent Engine does not report a model name, so this column read
                  "—" for every agent that could actually be evaluated. Type and
                  environment are what select metrics and gate red-team runs. */}
              <Th>Type</Th>
              <Th>Environment</Th>
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
                  <Td style={{ fontSize: 12 }}>{(a.agentType || 'unknown').replace(/_/g, ' ')}</Td>
                  <Td style={{ fontSize: 12, color: '#6B7280' }}>{a.environment}</Td>
                  <Td>{statusBadge(a.status)}</Td>
                  <Td style={{ color: '#6B7280' }}>{a.lastActive}</Td>
                  <Td>
                    {/* The wizard only offers reachable agents, so this button
                        used to land an inactive agent on a picker that would
                        never list it. */}
                    <Btn
                      style={{ fontSize: 11 }}
                      disabled={a.status === 'Inactive'}
                      title={
                        a.status === 'Inactive'
                          ? 'This agent is not reachable in the configured project, so it cannot be evaluated.'
                          : undefined
                      }
                      onClick={(e) => {
                        e.stopPropagation()
                        if (a.status === 'Inactive') return
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
