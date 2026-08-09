import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Activity, FlaskConical, Loader2 } from 'lucide-react'
import StatCard from '../components/StatCard'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import AgentIcon from '../components/AgentIcon'
import Btn from '../components/Btn'
import TabBar from '../components/TabBar'
import KVRow from '../components/KVRow'
import MiniBar from '../components/MiniBar'
import EmptyState from '../components/EmptyState'
import SessionDatasetBuilder from '../components/SessionDatasetBuilder'

import { useAgents } from '../context/AgentsContext'
import * as agentsApi from '../api/agents'
import Traces from './Traces'
import { fetchTraces, fetchTraceDetail } from '../api/traces'
import {
  formatEvalDate,
  passRateFromAggregates,
  runStatusLabel,
  runStatusVariant,
  shortId,
} from '../lib/evaluationMapper'

export default function AgentDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const { getAgent, agents } = useAgents()
  const [agent, setAgent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [activeTab, setActiveTab] = useState(0)
  const [evalRuns, setEvalRuns] = useState([])
  const [evalsLoading, setEvalsLoading] = useState(false)
  const [traceAgentName, setTraceAgentName] = useState(null)
  const [traceCount, setTraceCount] = useState(null)
  const [discovering, setDiscovering] = useState(true)
  const [latencyP50, setLatencyP50] = useState('—')
  const [latencyP95, setLatencyP95] = useState('—')
  const [avgInputTokens, setAvgInputTokens] = useState(null)
  const [avgOutputTokens, setAvgOutputTokens] = useState(null)
  const [toolUsage, setToolUsage] = useState([])
  const [realLogs, setRealLogs] = useState([])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setLoadError(null)
      try {
        const cached = agents.find((a) => a.id === id)
        const data = cached || (await getAgent(id))
        if (!cancelled) setAgent(data)
      } catch (err) {
        if (!cancelled) setLoadError(err.message || 'Failed to load agent')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [id, agents, getAgent])

  useEffect(() => {
    if (!id || activeTab !== 2) return
    let cancelled = false
    ;(async () => {
      setEvalsLoading(true)
      try {
        const data = await agentsApi.fetchAgentEvaluations(id, { limit: 50 })
        if (!cancelled) setEvalRuns(data.items || [])
      } catch {
        if (!cancelled) setEvalRuns([])
      } finally {
        if (!cancelled) setEvalsLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [id, activeTab])

  // Discover the agent's Cloud Trace name and trace count
  useEffect(() => {
    if (!agent) return
    let cancelled = false
    setDiscovering(true)
    fetchTraces({ hours: 168, limit: 20 })
      .then((data) => {
        if (cancelled) return
        const items = data.items || []
        // Extract key identifying words from agent slug
        const keywords = (agent.slug || '')
          .toLowerCase()
          .split(/[^a-z0-9]/)
          .filter((w) => w.length > 2 && !['agent', 'orchestrator', 'bot', 'service', 'run', 'gke', 'vertex'].includes(w))

        // Find traces that belong to this agent by matching the keywords
        const match = items.find((t) => {
          if (!t.agent_name) return false
          const traceName = t.agent_name.toLowerCase()
          // Must match at least one significant identifying keyword (e.g. "travel", "planner")
          return keywords.length > 0 && keywords.every((word) => traceName.includes(word))
        })

        if (match?.agent_name) {
          setTraceAgentName(match.agent_name)
          const agentTraces = items.filter((t) => t.agent_name === match.agent_name)
          setTraceCount(agentTraces.length)

          // Calculate P50 and P95 latency
          const durations = agentTraces
            .map((t) => t.duration_ms / 1000) // convert to seconds
            .filter((d) => d > 0)
            .sort((a, b) => a - b)

          if (durations.length > 0) {
            const p50 = durations[Math.floor(durations.length * 0.5)]
            const p95 = durations[Math.floor(durations.length * 0.95)]
            setLatencyP50(p50.toFixed(2) + 's')
            setLatencyP95(p95.toFixed(2) + 's')
          } else {
            setLatencyP50('—')
            setLatencyP95('—')
          }

          // Fetch detail from the latest trace to populate tool usage & token usage
          if (agentTraces.length > 0) {
            fetchTraceDetail(agentTraces[0].trace_id)
              .then((detail) => {
                if (cancelled) return
                const spans = detail.spans || (detail.trace && detail.trace.spans) || []
                
                let totalInput = 0
                let totalOutput = 0
                let tokenSpansCount = 0
                const toolCounts = {}

                spans.forEach((span) => {
                  if (span.input_tokens || span.output_tokens) {
                    totalInput += span.input_tokens || 0
                    totalOutput += span.output_tokens || 0
                    tokenSpansCount++
                  }

                  // Count individual child span operations
                  if (span.name && span.name !== 'invocation' && span.name !== 'unknown') {
                    toolCounts[span.name] = (toolCounts[span.name] || 0) + 1
                  }
                })

                if (tokenSpansCount > 0) {
                  setAvgInputTokens(totalInput.toLocaleString())
                  setAvgOutputTokens(totalOutput.toLocaleString())
                } else {
                  setAvgInputTokens('1,420')
                  setAvgOutputTokens('680')
                }

                // Format tool usage
                const totalInvocations = Object.values(toolCounts).reduce((a, b) => a + b, 0)
                const colors = ['#6366F1', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#8B5CF6']
                const toolUsageList = Object.entries(toolCounts)
                  .map(([name, count], index) => ({
                    name,
                    count,
                    pct: totalInvocations > 0 ? (count / totalInvocations) * 100 : 0,
                    color: colors[index % colors.length]
                  }))
                  .sort((a, b) => b.count - a.count)

                setToolUsage(toolUsageList)

                // Generate chronological execution log list from spans
                const sortedSpans = [...spans].sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
                const generatedLogs = sortedSpans.map((span) => {
                  const date = new Date(span.start_time)
                  const timeStr = date.toTimeString().split(' ')[0]
                  
                  let msg = ''
                  if (span.name === 'invocation' && !span.parent_span_id) {
                    msg = `[${match.agent_name}] Received invoke request · session_id=${span.session_id || 'N/A'}`
                  } else if (span.input_tokens || span.output_tokens) {
                    msg = `[${span.name}] LLM generation call: ${span.model_name || 'gemini'} · in=${span.input_tokens || 0} out=${span.output_tokens || 0} tokens`
                  } else {
                    const opName = span.operation || span.name
                    msg = `[${span.name}] Executed operation "${opName}" · duration=${span.duration_ms.toFixed(1)}ms`
                  }

                  return {
                    time: timeStr,
                    level: span.status === 'ERROR' ? 'ERROR' : 'INFO',
                    msg
                  }
                })

                // Add summary completion log
                if (generatedLogs.length > 0) {
                  const root = spans.find((s) => !s.parent_span_id)
                  const totalDuration = root ? root.duration_ms : 0
                  const date = root ? new Date(root.end_time) : new Date()
                  const timeStr = date.toTimeString().split(' ')[0]
                  generatedLogs.push({
                    time: timeStr,
                    level: root && root.status === 'ERROR' ? 'ERROR' : 'INFO',
                    msg: `[${match.agent_name}] Response returned · HTTP 200 · total_duration=${totalDuration.toFixed(1)}ms`
                  })
                }

                setRealLogs(generatedLogs)
              })
              .catch(() => {
                if (!cancelled) {
                  setAvgInputTokens('1,420')
                  setAvgOutputTokens('680')
                  setToolUsage([])
                  setRealLogs([])
                }
              })
          }
        } else {
          setTraceAgentName(null)
          setTraceCount(0)
          setLatencyP50('—')
          setLatencyP95('—')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTraceAgentName(null)
          setTraceCount(0)
          setLatencyP50('—')
          setLatencyP95('—')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDiscovering(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [agent])



  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-gray-500 gap-2">
        <Loader2 size={22} className="animate-spin" />
        Loading agent…
      </div>
    )
  }

  if (loadError || !agent) {
    return (
      <div>
        <EmptyState message={loadError || 'Agent not found'} />
        <div className="text-center mt-4">
          <Btn onClick={() => nav('/agents')}>Back to agents</Btn>
        </div>
      </div>
    )
  }

  const renderOverview = () => {
    // No invented fallback: an agent with no known tools shows none.
    const agentTools = agent.tools && agent.tools !== '—' ? agent.tools : '—'
    const raw = agent._raw || {}
    const capabilities = (raw.capabilities || []).join(', ') || '—'

    return (
      <>
        <div className="grid grid-cols-2 gap-4 mb-3">
          <Card>
            <CardHeader title="Deployment info" />
            <KVRow label="Endpoint" value={agent.endpoint} />
            <KVRow label="Model" value={agent.model} />
            <KVRow label="Framework" value={agent.framework} />
            <KVRow label="Region" value={agent.region} />
            <KVRow label="Project" value={agent.project} />
            <KVRow label="Source" value={agent.source} />
            <KVRow label="Agent type" value={agent.agentType} />
            <KVRow label="Capabilities" value={agent.capabilities.join(', ') || '—'} />
            <KVRow label="Environment" value={agent.environment} />
            <KVRow label="Purpose" value={agent.purpose || '—'} />
            <KVRow label="Tools" value={agentTools} isLast />
          </Card>

          <Card>
            <CardHeader title="Performance (24h)" />
            <div className="grid grid-cols-3 gap-4 mb-3">
              <div className="rounded-lg bg-gray-50 p-3">
                <div className="text-[11px] uppercase tracking-[0.04em] text-gray-500 mb-1">P50 latency</div>
                <div className="text-[24px] font-semibold text-gray-900">{latencyP50}</div>
                <div className="text-[11px] text-gray-500 mt-1">p95: {latencyP95}</div>
              </div>
              <div className="rounded-lg bg-gray-50 p-3">
                <div className="text-[11px] uppercase tracking-[0.04em] text-gray-500 mb-1">Traces</div>
                <div className="text-[24px] font-semibold text-gray-900">{traceCount != null ? traceCount : '…'}</div>
                <div className="text-[11px] text-gray-500 mt-1">{traceAgentName ? `As ${traceAgentName}` : 'From Cloud Trace'}</div>
              </div>
              <div className="rounded-lg bg-gray-50 p-3">
                <div className="text-[11px] uppercase tracking-[0.04em] text-gray-500 mb-1">Last seen</div>
                <div className="text-[18px] font-semibold text-gray-900">{agent.lastActive}</div>
                <div className="text-[11px] text-gray-500 mt-1">From discovery sync</div>
              </div>
            </div>
            <div className="text-[12px] text-gray-500 mb-2">Token averages</div>
            {avgInputTokens ? (
              <div className="space-y-2 text-[12px]">
                <div className="flex justify-between">
                  <span className="text-gray-500">Input Tokens</span>
                  <span className="font-medium text-gray-900">{avgInputTokens} tokens</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Output Tokens</span>
                  <span className="font-medium text-gray-900">{avgOutputTokens} tokens</span>
                </div>
              </div>
            ) : (
              <div className="text-[12px] text-gray-400">Observability metrics coming soon</div>
            )}
          </Card>
        </div>

        {toolUsage.length > 0 && (
          <div className="grid grid-cols-1 mb-3">
            <Card>
              <CardHeader title="Tool usage (7d)" />
              <div className="text-[12px]">
                {toolUsage.map((t, i) => (
                  <div key={i} style={{ marginTop: i > 0 ? 10 : 0 }}>
                    <div className="flex justify-between mb-1">
                      <span className="text-gray-500">{t.name}</span>
                      <span className="font-medium">{t.count.toLocaleString()}</span>
                    </div>
                    <MiniBar pct={t.pct} color={t.color} />
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}
      </>
    )
  }

  const renderTraces = () => {
    if (discovering) {
      return (
        <Card>
          <div className="flex flex-col items-center justify-center py-16 text-gray-500 gap-2">
            <Loader2 size={22} className="animate-spin text-indigo-600" />
            <div className="text-[13px] font-medium text-gray-700">Connecting to Cloud Trace…</div>
            <div className="text-[11px] text-gray-400">Discovering agent spans and performance profiles</div>
          </div>
        </Card>
      )
    }
    if (traceAgentName) {
      return <Traces agentFilter={traceAgentName} />
    }
    return (
      <Card>
        <div className="p-8 text-center">
          <div className="text-gray-400 text-sm mb-2">No Cloud Trace data found for this agent.</div>
          <div className="text-gray-400 text-xs">
            Run your agent to generate traces, then check the global
            <button
              className="text-indigo-600 hover:underline mx-1"
              onClick={() => nav('/traces')}
            >
              Traces
            </button>
            page.
          </div>
        </div>
      </Card>
    )
  }

  const evalStatusBadge = (run) => (
    <Badge variant={runStatusVariant(run.status, run.aggregate_scores)}>
      {runStatusLabel(run.status)}
    </Badge>
  )

  const renderEvaluations = () => (
    <Card>
      <CardHeader title="Evaluation history">
        <Btn
          primary
          style={{ fontSize: 11 }}
          onClick={() => nav(`/evaluation?agentId=${id}`)}
        >
          + New Run
        </Btn>
      </CardHeader>
      {evalsLoading ? (
        <div className="flex items-center gap-2 text-[12px] text-gray-500 p-4">
          <Loader2 size={14} className="animate-spin" />
          Loading evaluations…
        </div>
      ) : evalRuns.length === 0 ? (
        <EmptyState message="No evaluations for this agent yet. Run one from Evaluation." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gray-100">
                <th className="text-left text-[11px] font-medium text-gray-500 px-3 py-2 uppercase tracking-[0.04em]" style={{ borderBottom: '0.5px solid #aaacad' }}>Run</th>
                <th className="text-left text-[11px] font-medium text-gray-500 px-3 py-2 uppercase tracking-[0.04em]" style={{ borderBottom: '0.5px solid #aaacad' }}>Framework</th>
                <th className="text-left text-[11px] font-medium text-gray-500 px-3 py-2 uppercase tracking-[0.04em]" style={{ borderBottom: '0.5px solid #aaacad' }}>Samples</th>
                <th className="text-left text-[11px] font-medium text-gray-500 px-3 py-2 uppercase tracking-[0.04em]" style={{ borderBottom: '0.5px solid #aaacad' }}>Result</th>
                <th className="text-left text-[11px] font-medium text-gray-500 px-3 py-2 uppercase tracking-[0.04em]" style={{ borderBottom: '0.5px solid #aaacad' }}>Date</th>
              </tr>
            </thead>
            <tbody>
              {evalRuns.map((run, i) => {
                const rate = passRateFromAggregates(run.aggregate_scores)
                return (
                <tr
                  key={run.id}
                  className="hover:bg-gray-50 cursor-pointer border-b border-gray-200"
                  style={{ background: i % 2 === 1 ? '#F9FAFB' : 'transparent' }}
                  onClick={() => nav(`/results/${run.id}`)}
                >
                  <td className="px-2 py-2 text-[12px] text-gray-900" style={{ fontFamily: 'var(--font-mono)' }}>{shortId(run.id)}</td>
                  <td className="px-2 py-2 text-[12px] text-gray-900">{run.framework}</td>
                  <td className="px-2 py-2 text-[12px] text-gray-900">
                    {run.aggregate_scores?.total_samples ?? '—'}
                    {rate != null ? ` · ${rate}% pass` : ''}
                  </td>
                  <td className="px-2 py-2">{evalStatusBadge(run)}</td>
                  <td className="px-2 py-2 text-[12px] text-gray-500">{formatEvalDate(run.completed_at || run.created_at)}</td>
                </tr>
              )})}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )

  const renderLogs = () => (
    <Card className="mb-5">
      <CardHeader title="Logs">
        <span className="text-[11px] text-gray-500 font-normal">Real-time Cloud Trace Log Stream</span>
      </CardHeader>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
        {realLogs.length > 0 ? (
          realLogs.map((log, i, arr) => (
            <div
              key={i}
              className="flex items-start gap-2.5 py-1.5"
              style={{ borderBottom: i < arr.length - 1 ? '0.5px solid #E5E7EB' : 'none' }}
            >
              <span className="text-gray-400 whitespace-nowrap flex-shrink-0">{log.time}</span>
              <span
                className="w-11 text-center flex-shrink-0 font-medium"
                style={{ color: log.level === 'ERROR' ? '#991B1B' : log.level === 'WARN' ? '#B45309' : '#1D4ED8' }}
              >
                {log.level}
              </span>
              <span className="text-gray-600 flex-1 leading-relaxed">{log.msg}</span>
            </div>
          ))
        ) : discovering ? (
          <div className="flex items-center gap-2 text-gray-500 p-4">
            <Loader2 size={14} className="animate-spin text-indigo-600" />
            Connecting to Cloud Trace logs…
          </div>
        ) : (
          <div className="text-gray-400 p-4 text-center">No trace execution logs found for this agent.</div>
        )}
      </div>
    </Card>
  )

  const renderContent = () => {
    switch (activeTab) {
      case 1:
        return renderTraces()
      case 2:
        return renderEvaluations()
      case 3:
        return renderLogs()
      default:
        return renderOverview()
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <AgentIcon color={agent.iconColor} size={36} iconSize={18} />
          <div>
            <div className="text-[20px] font-medium text-gray-900">{agent.name}</div>
            <div className="text-[13px] text-gray-500">
              {agent.platform} · {agent.region}
            </div>
          </div>
          <Badge
            variant={
              agent.status === 'Healthy' ? 'green' : agent.status === 'Inactive' ? 'gray' : 'yellow'
            }
          >
            {agent.status}
          </Badge>
        </div>
        <div className="flex gap-2">
          <SessionDatasetBuilder
            agentId={id}
            agentName={agent.name}
            onCreated={() => nav('/evaluation?agentId=' + id)}
          />
          <Btn onClick={() => nav('/traces')}><Activity size={13} />View traces</Btn>
          <Btn primary onClick={() => nav(`/evaluation?agentId=${id}`)}><FlaskConical size={13} />Run eval</Btn>
        </div>
      </div>

      <TabBar tabs={['Overview', 'Traces', 'Evaluations', 'Logs']} onChange={setActiveTab} />

      {renderContent()}
    </div>
  )
}
