import React, { useState, useEffect, useCallback } from 'react'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import PageHeader from '../components/PageHeader'
import TraceGraph from '../components/TraceGraph'
import { useTraces } from '../context/TracesContext'

/* ─── helpers ──────────────────────────────────────────────────────────────── */
function formatDuration(ms) {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + formatTime(iso)
}

function shortId(id) {
  if (!id) return '—'
  return id.length > 12 ? id.slice(0, 6) + '…' + id.slice(-4) : id
}

const STATUS_COLORS = {
  OK: 'green',
  ERROR: 'red',
  UNSET: 'amber',
}

const OP_COLORS = {
  invoke_agent: '#4F46E5',
  call_llm: '#F59E0B',
  execute_tool: '#22C55E',
  send_data: '#06B6D4',
  receive_data: '#8B5CF6',
}

function opColor(name) {
  if (!name) return '#6B7280'
  for (const [key, color] of Object.entries(OP_COLORS)) {
    if (name.toLowerCase().includes(key)) return color
  }
  return '#6B7280'
}

/* ─── Trace List Item ──────────────────────────────────────────────────────── */
function TraceListItem({ trace, isActive, onClick }) {
  return (
    <div
      onClick={onClick}
      className="cursor-pointer transition-colors"
      style={{
        padding: '10px 14px',
        borderBottom: '0.5px solid var(--color-border-primary)',
        background: isActive ? 'var(--color-background-secondary)' : 'transparent',
      }}
      onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = '#F9FAFB' }}
      onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{ background: trace.status === 'ERROR' ? '#EF4444' : '#22C55E' }}
          />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4F46E5' }}>
            {shortId(trace.trace_id)}
          </span>
        </div>
        <Badge variant={STATUS_COLORS[trace.status] || 'green'}>
          {trace.status}
        </Badge>
      </div>

      <div className="flex items-center justify-between mt-1.5">
        <span className="text-xs text-gray-700 font-medium truncate">
          {trace.agent_name || trace.root_span_name || 'Agent'}
        </span>
        <span className="text-xs text-gray-400 whitespace-nowrap ml-2">
          {formatDuration(trace.duration_ms)}
        </span>
      </div>

      <div className="flex items-center justify-between mt-1">
        <span className="text-[10px] text-gray-400">
          {trace.span_count} span{trace.span_count !== 1 ? 's' : ''}
          {trace.session_id ? ` · Session ${shortId(trace.session_id)}` : ''}
        </span>
        <span className="text-[10px] text-gray-400">{formatDate(trace.start_time)}</span>
      </div>
    </div>
  )
}

/* ─── Span Waterfall Bar ───────────────────────────────────────────────────── */
function SpanWaterfallRow({ span, traceStart, traceDuration, depth = 0, isSelected, onClick }) {
  const spanStart = new Date(span.start_time).getTime()
  const traceStartMs = new Date(traceStart).getTime()
  const offsetPct = traceDuration > 0 ? ((spanStart - traceStartMs) / traceDuration) * 100 : 0
  const widthPct = traceDuration > 0 ? Math.max((span.duration_ms / traceDuration) * 100, 0.5) : 100

  const color = opColor(span.operation || span.name)

  return (
    <div
      onClick={onClick}
      className="cursor-pointer transition-colors"
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '4px 12px 4px 0',
        borderBottom: '0.5px solid #F3F4F6',
        background: isSelected ? '#EEF2FF' : 'transparent',
        minHeight: 32,
      }}
      onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = '#FAFAFE' }}
      onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = isSelected ? '#EEF2FF' : 'transparent' }}
    >
      {/* Label */}
      <div
        className="flex-shrink-0 truncate"
        style={{ width: 220, paddingLeft: 12 + depth * 16, fontSize: 11 }}
      >
        <span className="font-medium text-gray-800">{span.name}</span>
        {span.agent_name && (
          <span className="text-gray-400 ml-1">· {span.agent_name}</span>
        )}
      </div>

      {/* Waterfall bar */}
      <div className="flex-1 relative" style={{ height: 18 }}>
        <div
          style={{
            position: 'absolute',
            left: `${Math.min(offsetPct, 99)}%`,
            width: `${Math.min(widthPct, 100 - offsetPct)}%`,
            height: 14,
            top: 2,
            borderRadius: 3,
            background: color,
            opacity: 0.85,
            minWidth: 3,
            transition: 'opacity 0.15s',
          }}
          title={`${span.name}: ${formatDuration(span.duration_ms)}`}
        />
      </div>

      {/* Duration */}
      <span
        className="flex-shrink-0 text-right"
        style={{ width: 60, fontSize: 10, color: '#9CA3AF', fontFamily: 'var(--font-mono)' }}
      >
        {formatDuration(span.duration_ms)}
      </span>
    </div>
  )
}

/* ─── Span Detail Panel ────────────────────────────────────────────────────── */
function SpanDetail({ span }) {
  if (!span) return null

  const importantLabels = [
    'gen_ai.agent.name', 'gen_ai.operation.name', 'gen_ai.request.model',
    'gen_ai.usage.input_tokens', 'gen_ai.usage.output_tokens',
    'gen_ai.usage.experimental.reasoning_tokens',
    'gen_ai.conversation.id', 'gcp.vertex.agent.session_id',
    'gen_ai.response.finish_reasons', 'gen_ai.agent.description',
    'cloud.platform', 'cloud.region', 'service.name',
  ]

  const llmRequest = span.labels?.['gcp.vertex.agent.llm_request']
  const otherLabels = Object.entries(span.labels || {}).filter(
    ([k]) => !importantLabels.includes(k) && k !== 'gcp.vertex.agent.llm_request'
  )

  return (
    <div style={{ borderTop: '1px solid var(--color-border-primary)', padding: '14px 16px' }}>
      <div className="text-xs font-semibold text-gray-700 mb-3">
        Span Detail — {span.name}
      </div>

      <div className="grid gap-2" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <KV label="Span ID" value={span.span_id} mono />
        <KV label="Parent" value={span.parent_span_id || '(root)'} mono />
        <KV label="Operation" value={span.operation} />
        <KV label="Kind" value={span.kind} />
        <KV label="Start" value={formatTime(span.start_time)} />
        <KV label="Duration" value={formatDuration(span.duration_ms)} />
        {span.model_name && <KV label="Model" value={span.model_name} />}
        {span.agent_name && <KV label="Agent" value={span.agent_name} />}
        {span.input_tokens != null && <KV label="Input Tokens" value={String(span.input_tokens)} />}
        {span.output_tokens != null && <KV label="Output Tokens" value={String(span.output_tokens)} />}
        {span.session_id && <KV label="Session" value={span.session_id} mono />}
      </div>

      {/* LLM Request payload */}
      {llmRequest && (
        <div className="mt-3">
          <div className="text-[10px] font-medium text-gray-500 mb-1">LLM Request</div>
          <pre
            className="text-[10px] leading-relaxed overflow-auto rounded-md p-2.5"
            style={{
              fontFamily: 'var(--font-mono)',
              background: 'var(--color-background-secondary)',
              maxHeight: 200,
              color: '#374151',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {(() => {
              try { return JSON.stringify(JSON.parse(llmRequest), null, 2) } catch { return llmRequest }
            })()}
          </pre>
        </div>
      )}

      {/* Other labels */}
      {otherLabels.length > 0 && (
        <details className="mt-3">
          <summary className="text-[10px] font-medium text-gray-500 cursor-pointer hover:text-gray-700">
            All Labels ({otherLabels.length})
          </summary>
          <div className="mt-1.5 grid gap-1">
            {otherLabels.map(([k, v]) => (
              <div key={k} className="flex gap-2 text-[10px]">
                <span className="text-gray-400 flex-shrink-0" style={{ fontFamily: 'var(--font-mono)' }}>{k}</span>
                <span className="text-gray-600 truncate">{v}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

function KV({ label, value, mono }) {
  return (
    <div>
      <div className="text-[10px] text-gray-400 mb-0.5">{label}</div>
      <div
        className="text-[11px] text-gray-700 truncate"
        style={mono ? { fontFamily: 'var(--font-mono)' } : {}}
        title={value}
      >
        {value || '—'}
      </div>
    </div>
  )
}

/* ─── Main Traces Page ─────────────────────────────────────────────────────── */
export default function Traces({ agentFilter } = {}) {
  const { getTraceList, getTraceDetail, getCachedTraceList, getCachedTraceDetail } = useTraces()

  const initialTraces = getCachedTraceList({ hours: 24, agent: agentFilter })
  const [traces, setTraces] = useState(initialTraces || [])
  const [loading, setLoading] = useState(!initialTraces)
  const [error, setError] = useState(null)
  const [hours, setHours] = useState(24)
  const [selectedTraceId, setSelectedTraceId] = useState(() => {
    return initialTraces?.length > 0 ? initialTraces[0].trace_id : null
  })
  const [traceDetail, setTraceDetail] = useState(() => {
    return initialTraces?.length > 0 ? getCachedTraceDetail(initialTraces[0].trace_id) : null
  })
  const [detailLoading, setDetailLoading] = useState(() => {
    return initialTraces?.length > 0 && !getCachedTraceDetail(initialTraces[0].trace_id)
  })
  const [selectedSpan, setSelectedSpan] = useState(null)
  const [viewMode, setViewMode] = useState('graph') // 'graph' | 'timeline'

  // Load trace list
  const loadTraces = useCallback(async (opts = {}) => {
    setLoading(true)
    setError(null)
    try {
      const params = { hours, limit: 50 }
      if (agentFilter) params.agent = agentFilter
      const data = await getTraceList(params, opts)
      setTraces(data.items || [])
      // Auto-select first trace
      if (data.items?.length > 0 && !selectedTraceId) {
        setSelectedTraceId(data.items[0].trace_id)
      }
    } catch (err) {
      setError(err.message || 'Failed to load traces')
    } finally {
      setLoading(false)
    }
  }, [hours, agentFilter, getTraceList])

  useEffect(() => { loadTraces() }, [loadTraces])

  // Load trace detail
  useEffect(() => {
    if (!selectedTraceId) {
      setTraceDetail(null)
      return
    }
    let cancelled = false
    setDetailLoading(true)
    setSelectedSpan(null)
    getTraceDetail(selectedTraceId)
      .then(({ detail }) => {
        if (!cancelled) setTraceDetail(detail)
      })
      .catch((err) => {
        if (!cancelled) setTraceDetail(null)
        console.error('Failed to load trace detail:', err)
      })
      .finally(() => { if (!cancelled) setDetailLoading(false) })
    return () => { cancelled = true }
  }, [selectedTraceId, getTraceDetail])

  // Flatten span tree for waterfall display
  const flattenTree = (nodes, depth = 0) => {
    const result = []
    for (const node of nodes || []) {
      result.push({ ...node.span, _depth: depth })
      result.push(...flattenTree(node.children, depth + 1))
    }
    return result
  }

  const flatSpans = traceDetail ? flattenTree(traceDetail.span_tree) : []
  const activeTrace = traceDetail?.trace

  const isEmbedded = !!agentFilter

  return (
    <div>
      {!isEmbedded && (
        <PageHeader
          title="Traces"
          subtitle="Real-time execution traces from Google Cloud Trace — Vertex AI agents"
        />
      )}

      {/* Controls */}
      <div className="flex items-center gap-3 mb-4">
        <select
          value={hours}
          onChange={(e) => setHours(Number(e.target.value))}
          style={{ width: 140 }}
        >
          <option value={1}>Last 1 hour</option>
          <option value={6}>Last 6 hours</option>
          <option value={24}>Last 24 hours</option>
          <option value={72}>Last 3 days</option>
          <option value={168}>Last 7 days</option>
        </select>
        <button
          onClick={() => loadTraces({ force: true })}
          className="text-xs font-medium px-3 py-1.5 rounded-md transition-colors"
          style={{
            background: '#4F46E5',
            color: '#fff',
            border: 'none',
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#4338CA'}
          onMouseLeave={(e) => e.currentTarget.style.background = '#4F46E5'}
        >
          Refresh
        </button>
        {!loading && (
          <span className="text-[11px] text-gray-400">
            {traces.length} trace{traces.length !== 1 ? 's' : ''} found
          </span>
        )}
      </div>

      {error && (
        <div
          className="mb-4 text-xs text-red-700 rounded-md px-3 py-2"
          style={{ background: '#FEF2F2', border: '1px solid #FEE2E2' }}
        >
          {error}
        </div>
      )}

      <div className="grid gap-4" style={{ gridTemplateColumns: '320px 1fr' }}>
        {/* ─── Left: Trace List ──────────────────────────────────────── */}
        <Card>
          <CardHeader title="Trace List" />
          <div style={{ maxHeight: 'calc(100vh - 240px)', overflowY: 'auto' }}>
            {loading ? (
              <div className="text-xs text-gray-400 p-6 text-center">
                <div className="inline-block w-4 h-4 border-2 border-gray-200 border-t-indigo-500 rounded-full animate-spin mb-2" />
                <div>Loading traces…</div>
              </div>
            ) : traces.length === 0 ? (
              <div className="text-xs text-gray-400 p-6 text-center">
                No traces found in the last {hours}h.
                <br />
                Try increasing the time range or invoke your agent.
              </div>
            ) : (
              traces.map((t) => (
                <TraceListItem
                  key={t.trace_id}
                  trace={t}
                  isActive={t.trace_id === selectedTraceId}
                  onClick={() => setSelectedTraceId(t.trace_id)}
                />
              ))
            )}
          </div>
        </Card>

        {/* ─── Right: Trace Detail ──────────────────────────────────── */}
        <Card>
          {!selectedTraceId ? (
            <div className="text-xs text-gray-400 p-8 text-center">
              Select a trace to view its spans
            </div>
          ) : detailLoading ? (
            <div className="text-xs text-gray-400 p-8 text-center">
              <div className="inline-block w-4 h-4 border-2 border-gray-200 border-t-indigo-500 rounded-full animate-spin mb-2" />
              <div>Loading trace detail…</div>
            </div>
          ) : !activeTrace ? (
            <div className="text-xs text-gray-400 p-8 text-center">
              Trace not found
            </div>
          ) : (
            <>
              {/* Trace header */}
              <CardHeader title={`Trace · ${shortId(activeTrace.trace_id)}`}>
                <Badge variant={STATUS_COLORS[activeTrace.status] || 'green'}>
                  {activeTrace.status}
                </Badge>
                <Badge variant="blue">{formatDuration(activeTrace.duration_ms)}</Badge>
                <Badge variant="purple">{activeTrace.span_count} spans</Badge>
              </CardHeader>

              {/* Trace summary + view toggle */}
              <div
                className="flex items-center justify-between px-4 py-3"
                style={{
                  borderBottom: '0.5px solid var(--color-border-primary)',
                  background: 'var(--color-background-secondary)',
                }}
              >
                <div className="grid gap-3 flex-1" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                  <KV label="Agent" value={activeTrace.agent_name} />
                  <KV label="Session" value={activeTrace.session_id ? shortId(activeTrace.session_id) : null} mono />
                  <KV label="Started" value={formatDate(activeTrace.start_time)} />
                  <KV label="Total Duration" value={formatDuration(activeTrace.duration_ms)} />
                </div>

                {/* Graph / Timeline toggle */}
                <div
                  style={{
                    display: 'flex',
                    borderRadius: 6,
                    overflow: 'hidden',
                    border: '1px solid var(--color-border-secondary)',
                    marginLeft: 12,
                    flexShrink: 0,
                  }}
                >
                  {['graph', 'timeline'].map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setViewMode(mode)}
                      style={{
                        padding: '4px 12px',
                        fontSize: 11,
                        fontWeight: 500,
                        border: 'none',
                        cursor: 'pointer',
                        background: viewMode === mode ? '#4F46E5' : '#fff',
                        color: viewMode === mode ? '#fff' : '#6B7280',
                        transition: 'all 0.15s',
                      }}
                    >
                      {mode === 'graph' ? 'Graph' : 'Timeline'}
                    </button>
                  ))}
                </div>
              </div>

              {/* ─── Graph View ─── */}
              {viewMode === 'graph' && (
                <TraceGraph
                  spanTree={traceDetail?.span_tree}
                  selectedSpanId={selectedSpan?.span_id}
                  onSpanClick={(spanId) => {
                    const span = flatSpans.find((s) => s.span_id === spanId)
                    setSelectedSpan(
                      selectedSpan?.span_id === spanId ? null : span || null
                    )
                  }}
                />
              )}

              {/* ─── Timeline View ─── */}
              {viewMode === 'timeline' && (
                <>
                  {/* Waterfall header */}
                  <div
                    className="flex items-center px-3 py-2"
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: '#9CA3AF',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      borderBottom: '0.5px solid var(--color-border-primary)',
                    }}
                  >
                    <span style={{ width: 220, paddingLeft: 12 }}>Span</span>
                    <span className="flex-1">Timeline</span>
                    <span style={{ width: 60, textAlign: 'right' }}>Duration</span>
                  </div>

                  {/* Waterfall spans */}
                  <div style={{ maxHeight: 'calc(100vh - 440px)', overflowY: 'auto' }}>
                    {flatSpans.map((span) => (
                      <SpanWaterfallRow
                        key={span.span_id}
                        span={span}
                        depth={span._depth}
                        traceStart={activeTrace.start_time}
                        traceDuration={activeTrace.duration_ms}
                        isSelected={selectedSpan?.span_id === span.span_id}
                        onClick={() => setSelectedSpan(
                          selectedSpan?.span_id === span.span_id ? null : span
                        )}
                      />
                    ))}
                  </div>
                </>
              )}

              {/* Selected span detail */}
              {selectedSpan && <SpanDetail span={selectedSpan} />}
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
