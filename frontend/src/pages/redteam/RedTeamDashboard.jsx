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

export default function RedTeamDashboard() {
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
                <Th>Run</Th>
                <Th>Mode</Th>
                <Th>Status</Th>
                <Th>Failed</Th>
                <Th></Th>
              </THead>
              <tbody>
                {runs.map((r) => {
                  const mode = (r.config?.scan_mode) || 'custom'
                  return (
                    <TRow key={r.id}>
                      <Td>{shortId(r.id)}</Td>
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
                        <Badge variant={runStatusVariant(r.status)}>{r.status}</Badge>
                      </Td>
                      <Td>{r.failed}</Td>
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
          <CardHeader title="Pass rate trend" />
          {(stats?.pass_rate_trend || []).length === 0 ? (
            <p className="text-[12px] text-gray-500 p-4">Complete a scan to see trends.</p>
          ) : (
            <ul className="p-3 space-y-2">
              {stats.pass_rate_trend.map((t) => (
                <li key={t.run_id} className="flex justify-between text-[12px]">
                  <span className="text-gray-600">{shortId(t.run_id)}</span>
                  <span className="font-medium">{t.pass_rate}% pass</span>
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
