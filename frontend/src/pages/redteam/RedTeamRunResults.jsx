import React, { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Card, CardHeader } from '../../components/Card'
import Badge from '../../components/Badge'
import StatCard from '../../components/StatCard'
import PageHeader from '../../components/PageHeader'
import { Table, THead, Th, Td, TRow } from '../../components/Table'
import {
  fetchRedTeamRun,
  fetchRedTeamResults,
  fetchRunVulnerabilities,
  fetchRunVulnerabilityDetail,
} from '../../api/redteam'
import {
  classificationVariant,
  categoryLabel,
  runStatusVariant,
  severityVariant,
  shortId,
  traceUrl,
} from '../../lib/redteamMapper'

const isRunActive = (status) => {
  if (!status) return false
  const activeStatuses = [
    'running', 'queued', 'pending',
    'PENDING', 'INITIALIZING', 'GENERATING_ATTACKS',
    'RUNNING_ATTACKS', 'EVALUATING', 'AGGREGATING_RESULTS'
  ]
  return activeStatuses.includes(status) || activeStatuses.includes(status.toUpperCase())
}

const riskVariant = (risk) => {
  const r = (risk || '').toLowerCase()
  if (r === 'high') return 'red'
  if (r === 'medium') return 'amber'
  return 'green'
}

function VulnerabilityRow({ runId, vuln, isRunActive }) {
  const [expanded, setExpanded] = useState(false)

  const { data: details, isLoading } = useQuery({
    queryKey: ['redteam', 'vulnerability-detail', runId, vuln.vulnerability],
    queryFn: () => fetchRunVulnerabilityDetail(runId, vuln.vulnerability),
    enabled: expanded && !!runId,
    refetchInterval: isRunActive && expanded ? 3000 : false,
  })

  return (
    <>
      <TRow
        onClick={() => setExpanded(!expanded)}
        className="cursor-pointer hover:bg-gray-55/40 transition-colors"
      >
        <Td style={{ width: '32px', textAlign: 'center' }}>
          <span className="text-gray-400 font-mono text-[14px]">
            {expanded ? '▼' : '▶'}
          </span>
        </Td>
        <Td>
          <div className="font-semibold text-gray-800 text-[12px]">
            {categoryLabel(vuln.vulnerability)}
          </div>
        </Td>
        <Td>
          <Badge variant={riskVariant(vuln.risk_level)}>{vuln.risk_level}</Badge>
        </Td>
        <Td>
          <span className="font-mono font-medium text-gray-700 text-[11px]">
            {isRunActive && !vuln.total_attacks
              ? '—'
              : vuln.average_score != null
                ? vuln.average_score.toFixed(4)
                : '—'}
          </span>
        </Td>
        <Td>
          <span className="text-gray-600 text-[12px]">
            {isRunActive && !vuln.total_attacks ? (
              'Pending'
            ) : (
              <><strong>{vuln.failed_attacks}</strong> / {vuln.total_attacks}</>
            )}
          </span>
        </Td>
        <Td>
          <span className="text-[12px] text-indigo-600 font-medium hover:underline">
            {expanded ? 'Hide detail' : 'View detail'}
          </span>
        </Td>
      </TRow>
      {expanded && (
        <TRow className="bg-gray-50/20">
          <td colSpan={6} className="px-4 py-3 border-t border-b border-gray-150">
            {isLoading ? (
              <div className="flex items-center gap-2 text-gray-500 py-3 text-[12px]">
                <Loader2 className="animate-spin text-indigo-600" size={14} /> Loading case details…
              </div>
            ) : details && details.length > 0 ? (
              <div className="space-y-4 py-1">
                <div className="text-[11px] uppercase tracking-wider font-semibold text-gray-400 mb-2">
                  Adversarial Attack Cases ({details.length})
                </div>
                {details.map((item, idx) => {
                  const hasFailed = item.classification === 'FAIL'
                  const enhancement = item.metadata?.enhancement_used || 'None'
                  const semanticReasoning = item.metadata?.semantic_reasoning || item.reason
                  
                  return (
                    <div
                      key={item.id}
                      className="border border-gray-200 rounded-lg bg-white overflow-hidden shadow-sm hover:shadow-md transition-shadow"
                    >
                      {/* Case Header */}
                      <div className="bg-gray-50 px-3 py-2 border-b border-gray-200 flex items-center justify-between gap-3 flex-wrap">
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-mono text-gray-400 font-bold">
                            #{idx + 1}
                          </span>
                          <Badge variant={hasFailed ? 'red' : 'green'}>
                            {item.classification}
                          </Badge>
                          <span className="text-[11px] text-gray-500">
                            Enhancement: <strong className="text-gray-700">{enhancement.replace('_', ' ')}</strong>
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          {item.score != null && (
                            <span className="text-[11px] text-gray-500">
                              Vulnerability Score: <strong className={hasFailed ? 'text-red-600' : 'text-gray-700'}>{item.score.toFixed(3)}</strong>
                              <span className="text-gray-400 ml-1">(0 = safe, 1 = vulnerable)</span>
                            </span>
                          )}
                          {item.trace_id && (
                            <Link
                              to={traceUrl(item.trace_id)}
                              className="text-[11px] text-indigo-600 font-semibold hover:underline flex items-center gap-0.5"
                            >
                              Trace ↗
                            </Link>
                          )}
                          <Link
                            to={`/red-team/runs/${runId}/vulnerabilities/${item.id}`}
                            className="text-[11px] text-indigo-600 font-semibold hover:underline"
                          >
                            Full Detail
                          </Link>
                        </div>
                      </div>

                      {/* Case Body */}
                      <div className="p-3 space-y-2.5 text-[12px]">
                        <div>
                          <div className="text-[10px] font-semibold text-gray-400 uppercase mb-0.5">Adversarial Input (Attack Prompt)</div>
                          <div className="bg-gray-50/50 p-2 rounded border border-gray-150 text-gray-800 font-mono whitespace-pre-wrap leading-relaxed max-h-32 overflow-y-auto">
                            {item.prompt}
                          </div>
                        </div>

                        <div>
                          <div className="text-[10px] font-semibold text-gray-400 uppercase mb-0.5">Agent Output (Response)</div>
                          <div className="bg-gray-50/50 p-2 rounded border border-gray-150 text-gray-800 font-mono whitespace-pre-wrap leading-relaxed max-h-32 overflow-y-auto">
                            {item.response || <span className="italic text-gray-400">(Empty response)</span>}
                          </div>
                        </div>

                        {semanticReasoning && (
                          <div className="pt-2 border-t border-gray-100">
                            <div className="text-[10px] font-semibold text-gray-400 uppercase mb-0.5">Evaluation Semantic Reasoning</div>
                            <p className="text-gray-600 leading-relaxed italic bg-indigo-50/20 p-2 rounded border border-indigo-100/50">
                              {semanticReasoning}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-gray-500 py-3 text-[12px] text-center italic">
                No detailed attack cases found for this category.
              </div>
            )}
          </td>
        </TRow>
      )}
    </>
  )
}

export default function RedTeamRunResults() {
  const { runId } = useParams()

  const { data: run, isLoading: runLoading } = useQuery({
    queryKey: ['redteam', 'run', runId],
    queryFn: () => fetchRedTeamRun(runId),
    refetchInterval: (q) =>
      isRunActive(q.state.data?.status) ? 3000 : false,
  })

  const isDeepeval = run?.config?.scan_mode === 'deepeval'

  const { data: results, isLoading: resLoading } = useQuery({
    queryKey: ['redteam', 'results', runId],
    queryFn: () => fetchRedTeamResults(runId, { limit: 500 }),
    enabled: !!runId && !isDeepeval,
    refetchInterval: isRunActive(run?.status) ? 3000 : false,
  })

  const { data: vulnerabilities, isLoading: vulsLoading } = useQuery({
    queryKey: ['redteam', 'run-vulnerabilities', runId],
    queryFn: () => fetchRunVulnerabilities(runId),
    enabled: !!runId && isDeepeval,
    refetchInterval: isRunActive(run?.status) ? 3000 : false,
  })

  if (runLoading) {
    return (
      <div className="flex items-center gap-2 text-gray-500 p-8">
        <Loader2 className="animate-spin" size={16} /> Loading scan…
      </div>
    )
  }

  const items = results?.items || []
  const progress = run?.config?.progress
  const cost = run?.config?.cost

  const completed = isDeepeval && progress ? progress.completed_attacks : (items.length || (run?.passed ?? 0) + (run?.failed ?? 0))
  const total = isDeepeval && progress ? progress.total_attacks : (run?.total_tests ?? 0)

  // In deepeval mode, failures count is the sum of failed attacks in summaries
  const failuresCount = isDeepeval
    ? vulnerabilities?.reduce((sum, v) => sum + (v.failed_attacks || 0), 0) || 0
    : items.filter((r) => r.classification === 'FAIL').length

  const categoryProgress = isDeepeval
    ? {}
    : items.reduce((acc, r) => {
        acc[r.category] = (acc[r.category] || 0) + 1
        return acc
      }, {})

  return (
    <div>
      <PageHeader
        title={`Scan ${shortId(runId)}`}
        subtitle={`Status: ${run?.status || '—'} · Progress: ${completed}/${total} · Judge: ${run?.judge_model || '—'}`}
      >
        <Link to="/red-team/scan">
          <span className="text-[12px] text-indigo-600">New scan</span>
        </Link>
      </PageHeader>

      {/* Progress Bar & Cost estimation for active scan */}
      {isRunActive(run?.status) && (
        <div className="mb-4 p-4 rounded-lg bg-indigo-50/40 border border-indigo-100 shadow-sm transition-all duration-300">
          <div className="flex justify-between items-center mb-2">
            <div className="flex items-center gap-2">
              <Loader2 className="animate-spin text-indigo-600" size={16} />
              <span className="font-semibold text-[13px] text-gray-800 uppercase tracking-wider">
                Active Scan: {run.status.replace('_', ' ')}
              </span>
            </div>
            {progress && (
              <span className="text-[11px] font-mono text-indigo-700 bg-indigo-100/70 px-2 py-0.5 rounded-full font-semibold">
                {progress.completed_attacks} / {progress.total_attacks} attacks
              </span>
            )}
          </div>

          {progress && (
            <div className="w-full bg-gray-200 h-2 rounded-full overflow-hidden mb-2.5">
              <div
                className="bg-indigo-600 h-full rounded-full transition-all duration-500 ease-out"
                style={{ width: `${Math.min(100, Math.max(0, (progress.estimated_progress || 0) * 100))}%` }}
              />
            </div>
          )}

          <div className="flex justify-between items-center text-[11px] text-gray-500 flex-wrap gap-2 pt-1 border-t border-indigo-100/35">
            <div>
              {progress?.current_vulnerability && (
                <span>Evaluating vulnerability: <strong className="text-gray-700">{categoryLabel(progress.current_vulnerability)}</strong></span>
              )}
            </div>
            {cost && (
              <div className="flex gap-4 font-mono text-gray-500">
                <span>Evaluators: <strong className="text-gray-700">{cost.evaluator_calls}</strong></span>
                <span>Synthesizers: <strong className="text-gray-700">{cost.synthesizer_calls}</strong></span>
                <span>Est. Cost: <strong className="text-indigo-700">${cost.estimated_cost?.toFixed(4)}</strong></span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Categories lists if present (Custom mode) */}
      {!isDeepeval && (run?.categories?.length ?? 0) > 0 && (
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

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <StatCard label="Tests Run" value={`${completed}/${total || '—'}`} />
        <StatCard label="Passed" value={String(run?.passed ?? 0)} valueStyle={{ color: '#22C55E' }} />
        <StatCard label="Failed" value={String(run?.failed ?? 0)} valueStyle={{ color: '#EF4444' }} />
        <StatCard label="Uncertain" value={String(run?.uncertain ?? 0)} />
      </div>

      {run?.report?.summary && (
        <Card className="mb-4 shadow-sm border border-gray-150">
          <CardHeader title="Scan Report Summary">
            <Badge variant={runStatusVariant(run.status)}>{run.status}</Badge>
          </CardHeader>
          <div className="p-3 text-[12px] text-gray-700 space-y-1.5">
            <div>
              Risk level: <strong className={run.report.summary.risk_level === 'High' ? 'text-red-600' : 'text-green-600'}>{run.report.summary.risk_level}</strong>
            </div>
            <div>
              Pass rate: <strong>{run.report.summary.pass_rate_percent}%</strong>
            </div>
            {isDeepeval && run.report.cost_metadata && (
              <div className="pt-2 border-t border-gray-100 flex gap-4 text-[11px] text-gray-500 font-mono">
                <span>Evaluator Calls: <strong>{run.report.cost_metadata.evaluator_calls}</strong></span>
                <span>Synthesizer Calls: <strong>{run.report.cost_metadata.synthesizer_calls}</strong></span>
                <span>Estimated cost: <strong className="text-indigo-600">${run.report.cost_metadata.estimated_cost?.toFixed(4)}</strong></span>
              </div>
            )}
          </div>
        </Card>
      )}

      <Card className="shadow-sm border border-gray-150">
        <CardHeader title="Results Analysis">
          <Badge variant={isRunActive(run?.status) ? 'blue' : 'red'}>
            {isRunActive(run?.status) ? 'Scan in progress' : `${failuresCount} vulnerabilities found`}
          </Badge>
        </CardHeader>
        {isDeepeval ? (
          vulsLoading ? (
            <p className="p-4 text-[12px] text-gray-500">Loading vulnerability summaries…</p>
          ) : (
            <Table>
              <THead>
                <Th></Th>
                <Th>Vulnerability</Th>
                <Th>Risk Level</Th>
                <Th>Average Score</Th>
                <Th>Failed / Total</Th>
                <Th>Actions</Th>
              </THead>
              <tbody>
                {vulnerabilities && vulnerabilities.length > 0 ? (
                  vulnerabilities.map((vuln) => (
                    <VulnerabilityRow
                      key={vuln.vulnerability}
                      runId={runId}
                      vuln={vuln}
                      isRunActive={isRunActive(run?.status)}
                    />
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="text-center p-4 text-[12px] text-gray-500">
                      No vulnerability results available.
                    </td>
                  </tr>
                )}
              </tbody>
            </Table>
          )
        ) : resLoading ? (
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
                  <Td>{categoryLabel(r.category)}</Td>
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
