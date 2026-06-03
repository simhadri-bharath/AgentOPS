import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { RefreshCw, Plus, Search, Loader2 } from 'lucide-react'
import Btn from './Btn'
import { useAgents } from '../context/AgentsContext'

const breadcrumbMap = {
  '/dashboard': 'Dashboard',
  '/agents': 'Agents',
  '/evaluation': 'Evaluation → New Run',
  '/results': 'Evaluation → Results',
  '/history': 'Evaluation → History',
  '/traces': 'Observability → Traces',
  '/logs': 'Observability → Logs',
  '/red-team': 'Testing → Red Teaming',
  '/onboarding': 'Setup → Onboarding',
  '/settings': 'Setup → Settings',
}

export default function Topbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { syncing, syncDiscovery } = useAgents()

  const handleSync = async () => {
    try {
      await syncDiscovery()
    } catch {
      /* error in context */
    }
  }
  const label = Object.entries(breadcrumbMap).find(([k]) => pathname.startsWith(k))?.[1] || 'Dashboard'

  return (
    <div
      className="h-[52px] flex items-center px-5 gap-3 flex-shrink-0"
      style={{ background: 'var(--color-background-primary)', borderBottom: '0.5px solid #E5E7EB' }}
    >
      <div className="flex items-center gap-1.5 text-[13px] text-gray-500">
        <span className="font-medium text-gray-900">{label}</span>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
          <input
            type="search"
            placeholder="Search agents, runs..."
            style={{ width: 200, paddingLeft: 28 }}
          />
        </div>
        <Btn onClick={handleSync} disabled={syncing}>
          {syncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          {syncing ? 'Syncing…' : 'Sync GCP'}
        </Btn>
        <Btn primary onClick={() => navigate('/evaluation')}>
          <Plus size={13} />
          New Eval
        </Btn>
      </div>
    </div>
  )
}
