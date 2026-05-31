import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw, Loader2 } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import Btn from '../components/Btn'
import PageHeader from '../components/PageHeader'
import { useAgents } from '../context/AgentsContext'
import { fetchTraces, fetchTraceDetail } from '../api/traces'

const levelColor = { INFO: '#1D4ED8', WARN: '#B45309', ERROR: '#991B1B' }

export default function Logs() {
  const { agents } = useAgents()
  const [logsList, setLogsList] = useState([])
  const [loading, setLoading] = useState(true)
  const [logSearch, setLogSearch] = useState('')
  const [selectedAgent, setSelectedAgent] = useState('all')
  const [selectedLevel, setSelectedLevel] = useState('all')
  const [timeWindow, setTimeWindow] = useState('168') // default to 7d (168h)

  const fetchAllLogs = useCallback(() => {
    setLoading(true)
    fetchTraces({ limit: 40, hours: parseInt(timeWindow) })
      .then(async (res) => {
        const items = res.items || []
        
        // Fetch details for each trace to extract child spans
        const detailsPromises = items.map((t) =>
          fetchTraceDetail(t.trace_id)
            .then((detail) => ({ trace: t, detail }))
            .catch(() => ({ trace: t, detail: null }))
        )
        
        const results = await Promise.all(detailsPromises)
        const allLogLines = []

        results.forEach(({ trace, detail }) => {
          if (!detail) {
            // Fallback high level logs if detail failed
            const date = new Date(trace.start_time)
            const timeStr = date.toTimeString().split(' ')[0]
            allLogLines.push({
              time: timeStr,
              timestamp: date,
              agentName: trace.agent_name || 'unknown',
              level: trace.status === 'ERROR' ? 'ERROR' : 'INFO',
              msg: `[${trace.agent_name || 'unknown'}] Executed trace run · duration=${(trace.duration_ms / 1000).toFixed(2)}s · trace_id=${trace.trace_id}`
            })
            return
          }
          
          const spans = detail.spans || (detail.trace && detail.trace.spans) || []
          const sortedSpans = [...spans].sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
          
          sortedSpans.forEach((span) => {
            const date = new Date(span.start_time)
            const timeStr = date.toTimeString().split(' ')[0]
            
            let msg = ''
            if (span.name === 'invocation' && !span.parent_span_id) {
              msg = `[${trace.agent_name || 'unknown'}] Received invoke request · session_id=${span.session_id || 'N/A'}`
            } else if (span.input_tokens || span.output_tokens) {
              msg = `[${span.name}] LLM generation call: ${span.model_name || 'gemini'} · in=${span.input_tokens || 0} out=${span.output_tokens || 0} tokens`
            } else {
              const opName = span.operation || span.name
              msg = `[${span.name}] Executed operation "${opName}" · duration=${span.duration_ms.toFixed(1)}ms`
            }
            
            allLogLines.push({
              time: timeStr,
              timestamp: date,
              agentName: trace.agent_name || 'unknown',
              level: span.status === 'ERROR' ? 'ERROR' : 'INFO',
              msg
            })
          })
          
          // Summary completion log
          if (spans.length > 0) {
            const root = spans.find((s) => !s.parent_span_id)
            const totalDuration = root ? root.duration_ms : trace.duration_ms
            const date = root ? new Date(root.end_time) : new Date(trace.end_time)
            const timeStr = date.toTimeString().split(' ')[0]
            allLogLines.push({
              time: timeStr,
              timestamp: date,
              agentName: trace.agent_name || 'unknown',
              level: root && root.status === 'ERROR' ? 'ERROR' : 'INFO',
              msg: `[${trace.agent_name || 'unknown'}] Response returned · HTTP 200 · total_duration=${totalDuration.toFixed(1)}ms`
            })
          }
        })
        
        // Sort all logs globally by timestamp descending (newest at top)
        allLogLines.sort((a, b) => b.timestamp - a.timestamp)
        setLogsList(allLogLines)
      })
      .catch((err) => {
        console.error('Failed to fetch global logs:', err)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [timeWindow])

  useEffect(() => {
    fetchAllLogs()
  }, [fetchAllLogs])

  const filteredLogs = useMemo(() => {
    return logsList.filter((log) => {
      // 1. Search filter
      if (logSearch.trim()) {
        const query = logSearch.toLowerCase()
        const matchMsg = log.msg.toLowerCase().includes(query)
        const matchAgent = log.agentName.toLowerCase().includes(query)
        if (!matchMsg && !matchAgent) return false
      }
      
      // 2. Agent filter
      if (selectedAgent !== 'all') {
        const targetAgent = agents.find((a) => a.id === selectedAgent)
        if (targetAgent) {
          const keywords = targetAgent.slug
            .toLowerCase()
            .split(/[^a-z0-9]/)
            .filter((w) => w.length > 2 && !['agent', 'orchestrator'].includes(w))
          
          const match = keywords.every((kw) => log.agentName.toLowerCase().includes(kw))
          if (!match) return false
        }
      }
      
      // 3. Level filter
      if (selectedLevel !== 'all' && log.level !== selectedLevel) {
        return false
      }
      
      return true
    })
  }, [logsList, logSearch, selectedAgent, selectedLevel, agents])

  return (
    <div>
      <PageHeader title="Logs" subtitle="Centralized logs from Cloud Run, GKE, and Vertex AI — via Cloud Logging" />

      <Card>
        <div className="flex items-center gap-2 flex-wrap mb-4">
          <input
            type="search"
            placeholder="Search logs..."
            style={{ flex: 1, minWidth: 180 }}
            value={logSearch}
            onChange={(e) => setLogSearch(e.target.value)}
          />
          <select style={{ width: 130 }} value={selectedAgent} onChange={(e) => setSelectedAgent(e.target.value)}>
            <option value="all">All agents</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          <select style={{ width: 100 }} value={selectedLevel} onChange={(e) => setSelectedLevel(e.target.value)}>
            <option value="all">All levels</option>
            <option value="INFO">INFO</option>
            <option value="WARN">WARN</option>
            <option value="ERROR">ERROR</option>
          </select>
          <select style={{ width: 110 }} value={timeWindow} onChange={(e) => setTimeWindow(e.target.value)}>
            <option value="1">Last 1 hour</option>
            <option value="24">Last 24h</option>
            <option value="168">Last 7d</option>
          </select>
          <Btn onClick={fetchAllLogs} disabled={loading}>
            {loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
            Refresh
          </Btn>
        </div>

        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
          {loading && logsList.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-gray-500 gap-2">
              <Loader2 size={18} className="animate-spin text-indigo-600" />
              Loading logs from Cloud Trace streams…
            </div>
          ) : filteredLogs.length > 0 ? (
            filteredLogs.map((log, i, arr) => (
              <div
                key={i}
                className="flex items-start gap-2.5 py-1.5 border-b border-gray-100 last:border-b-0 hover:bg-gray-50 px-2 rounded"
              >
                <span className="text-gray-400 whitespace-nowrap flex-shrink-0">{log.time}</span>
                <span
                  className="w-11 text-center flex-shrink-0 font-medium"
                  style={{ color: levelColor[log.level] || '#6B7280' }}
                >
                  {log.level}
                </span>
                <span className="text-gray-600 flex-1 leading-relaxed">{log.msg}</span>
              </div>
            ))
          ) : (
            <div className="text-center py-12 text-gray-400">No logs found matching your filters.</div>
          )}
        </div>
      </Card>
    </div>
  )
}
