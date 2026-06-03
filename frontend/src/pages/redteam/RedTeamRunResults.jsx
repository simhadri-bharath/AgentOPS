import React from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Card, CardHeader } from '../../components/Card'
import Badge from '../../components/Badge'
import StatCard from '../../components/StatCard'
import PageHeader from '../../components/PageHeader'
import { Table, THead, Th, Td, TRow } from '../../components/Table'
import { fetchRedTeamRun, fetchRedTeamResults } from '../../api/redteam'
import {
  classificationVariant,
  categoryLabel,
  runStatusVariant,
  severityVariant,
  shortId,
  traceUrl,
} from '../../lib/redteamMapper'

export default function RedTeamRunResults() {
  const { runId } = useParams()

  const { data: run, isLoading: runLoading } = useQuery({
    queryKey: ['redteam', 'run', runId],
    queryFn: () => fetchRedTeamRun(runId),
    refetchInterval: (q) =>
      q.state.data?.status === 'running' || q.state.data?.status === 'queued' ? 3000 : false,
  })

  const { data: results, isLoading: resLoading } = useQuery({
    queryKey: ['redteam', 'results', runId],
    queryFn: () => fetchRedTeamResults(runId, { limit: 500 }),
    enabled: !!runId,
    refetchInterval: run?.status === 'running' ? 3000 : false,
  })

  if (runLoading) {
    return (
      <div className="flex items-center gap-2 text-gray-500 p-8">
        <Loader2 className="animate-spin" size={16} /> Loading scan…
      </div>
    )
  }

  const items = results?.items || []
  const failures = items.filter((r) => r.classification === 'FAIL')
  const completed = items.length
  const total = run?.total_tests ?? 0
  const categoryProgress = items.reduce((acc, r) => {
    acc[r.category] = (acc[r.category] || 0) + 1
    return acc
  }, {})

  return (
    <div>
      <PageHeader
        title={`${run?.agent_name || 'Agent'} - Scan ${shortId(runId)}`}
        subtitle={`Status: ${run?.status || '—'} · Progress: ${completed}/${total} · Judge: ${run?.judge_model || '—'}`}
      >
        <Link to="/red-team/scan">
          <span className="text-[12px] text-indigo-600">New scan</span>
        </Link>
      </PageHeader>

      {(run?.categories?.length ?? 0) > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {run.categories.map((cat) => (
            <span
              key={cat}
              className="text-[11px] px-2 py-1 rounded-md bg-gray-100 text-gray-700"
            >
              {categoryLabel(cat)}: {categoryProgress[cat] || 0} done
            </span>
          ))}
        </div>
      )}

      {/* {run?.status === 'running' && total > 0 && (
        <p className="text-[12px] text-amber-800 mb-3 px-1">
          Scan in progress — tests run in mixed category order (not prompt-injection only).
          DeepEval + agent calls can take several minutes per test.
        </p>
      )} */}

      <div className="grid grid-cols-4 gap-3 mb-4">
        <StatCard label="Tests" value={`${completed}/${total || '—'}`} />
        <StatCard label="Passed" value={String(run?.passed ?? 0)} valueStyle={{ color: '#22C55E' }} />
        <StatCard label="Failed" value={String(run?.failed ?? 0)} valueStyle={{ color: '#EF4444' }} />
        <StatCard label="Uncertain" value={String(run?.uncertain ?? 0)} />
      </div>

      {run?.report?.summary && (
        <Card className="mb-4">
          <CardHeader title="Report summary">
            <Badge variant={runStatusVariant(run.status)}>{run.status}</Badge>
          </CardHeader>
          <div className="p-3 text-[12px] text-gray-700">
            Risk level: <strong>{run.report.summary.risk_level}</strong> · Pass rate:{' '}
            {run.report.summary.pass_rate_percent}%
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Results">
          <Badge variant="red">{failures.length} vulnerabilities</Badge>
        </CardHeader>
        {resLoading ? (
          <p className="p-4 text-[12px] text-gray-500">Loading results…</p>
        ) : (
          <Table>
            <THead>
              <Th>Category</Th>
              <Th>Result</Th>
              <Th>Severity</Th>
              <Th>Trace</Th>
              <Th></Th>
            </THead>
            <tbody>
              {items.map((r) => (
                <TRow key={r.id}>
                  <Td>{r.category}</Td>
                  <Td>
                    <Badge variant={classificationVariant(r.classification)}>
                      {r.classification}
                    </Badge>
                  </Td>
                  <Td>
                    <Badge variant={severityVariant(r.severity)}>{r.severity}</Badge>
                  </Td>
                  <Td>
                    {r.trace_id ? (
                      <Link to={traceUrl(r.trace_id)} className="text-indigo-600 text-[11px]">
                        {shortId(r.trace_id)}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </Td>
                  <Td>
                    <Link
                      to={`/red-team/runs/${runId}/vulnerabilities/${r.id}`}
                      className="text-[12px] text-indigo-600"
                    >
                      Detail
                    </Link>
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
