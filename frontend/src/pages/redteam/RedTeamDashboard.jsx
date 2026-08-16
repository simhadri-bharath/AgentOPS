import React from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Shield, AlertTriangle, Loader2 } from 'lucide-react'
import { Card, CardHeader } from '../../components/Card'
import Badge from '../../components/Badge'
import Btn from '../../components/Btn'
import StatCard from '../../components/StatCard'
import PageHeader from '../../components/PageHeader'
import { Table, THead, Th, Td, TRow } from '../../components/Table'
import * as redteamApi from '../../api/redteam'
import { fetchRedTeamRuns } from '../../api/redteam'
import { runStatusVariant, shortId } from '../../lib/redteamMapper'
import { useAgents } from '../../context/AgentsContext'
import { formatRelativeTime } from '../../lib/agentMapper'

const statusLabel = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : 'Unknown')

export default function RedTeamDashboard() {
  const { agents } = useAgents()
  // A scan has no name of its own, so it is identified by what it tested.
  const agentName = (id) =>
    agents.find((a) => String(a.id) === String(id))?.name || shortId(id)
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['redteam', 'dashboard'],
    queryFn: redteamApi.fetchRedTeamDashboard,
    refetchInterval: 15000,
  })

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['redteam', 'runs', { limit: 10 }],
    queryFn: () => fetchRedTeamRuns({ limit: 10 }),
    refetchInterval: 10000,
  })

  const runs = runsData?.items || []

  return (
    <div>
      <PageHeader
        title="Red team scanner"
        subtitle="AI vulnerability scanning for agents — injection, jailbreak, PII, and boundary tests"

      >
        <Link to="/red-team/scan">
          <Btn primary>
            <Shield size={13} />
            New scan
          </Btn>
        </Link>
      </PageHeader>

      <div
        className="flex items-center gap-2 px-3.5 py-2.5 rounded-md text-[12px] mb-4"
        style={{ background: '#FEF3C7', border: '0.5px solid #FCD34D', color: '#92400E' }}
      >
        <AlertTriangle size={16} className="flex-shrink-0" />
        Security scans run against live agent endpoints. Review failures before production changes.
      </div>

      {statsLoading ? (
        <div className="flex items-center gap-2 text-gray-500 text-[12px] p-4">
          <Loader2 size={14} className="animate-spin" /> Loading dashboard…
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-3 mb-4">
          <StatCard label="Total scans" value={String(stats?.total_runs ?? 0)} />
          <StatCard
            label="Vulnerabilities"
            value={String(stats?.total_vulnerabilities ?? 0)}
            valueStyle={{ color: '#EF4444' }}
          />
          <StatCard label="Recent failures" value={String(stats?.recent_failure_count ?? 0)} />
          <StatCard
            label="Categories at risk"
            value={String(Object.keys(stats?.category_breakdown || {}).length)}
          />
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Recent scans" />
          {runsLoading ? (
            <p className="text-[12px] text-gray-500 p-4">Loading…</p>
          ) : runs.length === 0 ? (
            <p className="text-[12px] text-gray-500 p-4">No scans yet.</p>
          ) : (
            <Table>
              <THead>
                <Th>Scan</Th>
                <Th>Mode</Th>
                <Th>Status</Th>
                <Th>Findings</Th>
                <Th></Th>
              </THead>
              <tbody>
                {runs.map((r) => {
                  const mode = (r.config?.scan_mode) || 'custom'
                  return (
                    <TRow key={r.id}>
                      <Td>
                        <div className="font-medium">{agentName(r.agent_id)}</div>
                        <div style={{ fontSize: 10, color: '#9CA3AF' }}>
                          {(r.categories || []).join(', ') || 'no categories'}
                          {r.created_at ? ` · ${formatRelativeTime(r.created_at)}` : ''}
                        </div>
                      </Td>
                      <Td>
                        <span
                          className="text-[10px] font-medium px-1.5 py-0.5 rounded"
                          style={{
                            background: mode === 'dynamic' ? '#EEF2FF' : '#F3F4F6',
                            color: mode === 'dynamic' ? '#4F46E5' : '#6B7280',
                          }}
                        >
                          {mode === 'dynamic' ? 'Dynamic' : 'Custom'}
                        </span>
                      </Td>
                      <Td>
                        <Badge variant={runStatusVariant(r.status)}>
                          {statusLabel(r.status)}
                        </Badge>
                      </Td>
                      <Td>
                        {/* "0 failed" reads as a clean bill of health even when a
                            scan was cancelled before it tested anything. */}
                        {r.total_tests
                          ? `${r.failed} of ${r.total_tests}`
                          : <span style={{ color: '#9CA3AF' }}>not run</span>}
                      </Td>
                      <Td>
                        <Link to={`/red-team/runs/${r.id}`} className="text-indigo-600 text-[12px]">
                          View
                        </Link>
                      </Td>
                    </TRow>
                  )
                })}
              </tbody>
            </Table>
          )}
        </Card>

        <Card>
          {/* Called a "trend" while listing one row per scan with no time axis. */}
          <CardHeader title="Pass rate by scan" />
          {(stats?.pass_rate_trend || []).length === 0 ? (
            <p className="text-[12px] text-gray-500 p-4">
              Complete a scan to see pass rates.
            </p>
          ) : (
            <ul className="p-3 space-y-2">
              {stats.pass_rate_trend.map((t) => (
                <li key={t.run_id}>
                  <Link
                    to={`/red-team/runs/${t.run_id}`}
                    className="flex items-center gap-2 text-[12px]"
                  >
                    <span className="text-gray-600 truncate" style={{ minWidth: 78 }}>
                      {formatRelativeTime(t.created_at)}
                    </span>
                    {/* A scan can be 20% pass with 0 failed: the rest were
                        judged uncertain or errored before they were scored. */}
                    <span
                      style={{ fontSize: 11, color: '#9CA3AF', minWidth: 62 }}
                      title="Attacks the judge confirmed as failures. Any remainder was uncertain or did not complete."
                    >
                      {t.failed} failed
                    </span>
                    <span className="flex-1 h-1.5 rounded bg-gray-100 overflow-hidden">
                      <span
                        className="block h-full rounded"
                        style={{
                          width: `${Math.max(0, Math.min(100, t.pass_rate))}%`,
                          background:
                            t.pass_rate >= 100
                              ? '#22C55E'
                              : t.pass_rate >= 70
                                ? '#F59E0B'
                                : '#EF4444',
                        }}
                      />
                    </span>
                    <span className="font-medium tabular-nums">{t.pass_rate}%</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-4 flex gap-2">
        <Link to="/red-team/library">
          <Btn>Attack library</Btn>
        </Link>
        <Link to="/red-team/scan">
          <Btn primary>Configure scan</Btn>
        </Link>
      </div>
    </div>
  )
}
