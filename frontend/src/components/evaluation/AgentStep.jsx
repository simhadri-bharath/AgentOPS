import React, { useMemo, useState } from 'react'
import { Loader2, Search } from 'lucide-react'
import Badge from '../Badge'
import AgentIcon from '../AgentIcon'
import EmptyState from '../EmptyState'

const platformVariant = (platform) => {
  if (platform === 'Vertex AI') return 'purple'
  if (platform === 'GKE') return 'amber'
  return 'blue'
}

const statusVariant = (s) => {
  if (s === 'Healthy') return 'green'
  if (s === 'Degraded') return 'amber'
  if (s === 'Inactive') return 'gray'
  return 'red'
}

export default function AgentStep({ agents, loading, selectedAgent, onSelect }) {
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return agents
    return agents.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        a.platform.toLowerCase().includes(q) ||
        a.region.toLowerCase().includes(q)
    )
  }, [agents, search])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-500 gap-2">
        <Loader2 size={18} className="animate-spin" />
        Loading agents…
      </div>
    )
  }

  if (agents.length === 0) {
    return (
      <EmptyState message="No agents found. Run discovery from the Agents page first." />
    )
  }

  return (
    <div>
      <div className="relative mb-3 max-w-sm">

<Search
  size={15}
  className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400"
/>

<span className="absolute left-10 top-1/2 -translate-y-1/2 text-[13px] font-medium text-gray-500 pointer-events-none">
  Search
</span>

<input
  type="search"
  value={search}
  onChange={(e) => setSearch(e.target.value)}
  className="
    h-9
    w-full
    rounded-xl
    border
    border-gray-200
    bg-white
    pl-28
    pr-4
    text-[14px]
    text-gray-700
    outline-none
    transition-all
    focus:border-blue-500
    focus:ring-2
    focus:ring-blue-100
  "
/>
</div>

      <div
        className="overflow-hidden rounded-lg border border-gray-200"
        style={{ borderWidth: '0.5px' }}
      >
        <div className="grid grid-cols-12 border-b border-gray-200 bg-gray-50 px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide text-gray-500">
          <div className="col-span-1" />
          <div className="col-span-5">Agent</div>
          <div className="col-span-3">Platform</div>
          <div className="col-span-3">Status</div>
        </div>

        <div className="divide-y divide-gray-100">
          {filtered.length === 0 ? (
            <div className="px-4 py-8 text-center text-[13px] text-gray-500">
              No agents match your search.
            </div>
          ) : (
            filtered.map((agent) => {
              const selected = selectedAgent?.id === agent.id
              return (
                <button
                  key={agent.id}
                  type="button"
                  onClick={() => onSelect(agent)}
                  className={`grid w-full grid-cols-12 items-center px-4 py-3.5 text-left transition-colors ${
                    selected ? 'bg-indigo-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="col-span-1 flex justify-center">
                    <span
                      className={`flex h-4 w-4 items-center justify-center rounded-full border ${
                        selected
                          ? 'border-indigo-600 bg-indigo-600'
                          : 'border-gray-300 bg-white'
                      }`}
                    >
                      {selected && (
                        <span className="h-1.5 w-1.5 rounded-full bg-white" />
                      )}
                    </span>
                  </div>

                  <div className="col-span-5 flex items-center gap-3 min-w-0">
                    <AgentIcon color={agent.iconColor} />
                    <div className="min-w-0">
                      <div className="truncate text-[14px] font-medium text-gray-900">
                        {agent.name}
                      </div>
                      <div className="text-[12px] text-gray-500">{agent.region}</div>
                    </div>
                  </div>

                  <div className="col-span-3">
                    <Badge variant={platformVariant(agent.platform)}>
                      {agent.platform}
                    </Badge>
                  </div>

                  <div className="col-span-3">
                    <Badge variant={statusVariant(agent.status)}>{agent.status}</Badge>
                  </div>
                </button>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
