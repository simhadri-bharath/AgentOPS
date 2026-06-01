/**
 * TracesContext — Global cache for Cloud Trace data.
 *
 * Implements a stale-while-revalidate pattern:
 *   1. On first request  → fetch from GCP, cache result
 *   2. On subsequent hit → return cached data instantly,
 *      then silently re-fetch in the background
 *   3. Cache entries older than STALE_MS trigger a background refresh
 *
 * Cache keys:
 *   - Trace list:   "list:{hours}:{agent}"
 *   - Trace detail:  trace_id string
 */

import React, { createContext, useCallback, useContext, useRef } from 'react'
import { fetchTraces as apiFetchTraces, fetchTraceDetail as apiFetchDetail } from '../api/traces'

const TracesContext = createContext(null)

/** Entries older than 30 seconds are considered stale. */
const STALE_MS = 30_000

/**
 * Build a unique string key for a trace-list query.
 */
function listKey(hours, agent) {
  return `list:${hours || 24}:${agent || '_all'}`
}

export function TracesProvider({ children }) {
  // Separate caches for list queries, details, compiled global logs, and agent discovery profiles
  const listCache = useRef({})   // { [key]: { data, fetchedAt } }
  const detailCache = useRef({}) // { [traceId]: { data, fetchedAt } }
  const globalLogsCache = useRef({}) // { [timeWindow]: { data, fetchedAt } }
  const agentDiscoveryCache = useRef({}) // { [agentId]: { data, fetchedAt } }

  // ─── Trace List ──────────────────────────────────────────────
  const getTraceList = useCallback(
    /**
     * @param {{ hours?: number, limit?: number, agent?: string }} params
     * @param {{ force?: boolean }} opts
     * @returns {Promise<{ items: any[], total: number, fromCache: boolean }>}
     */
    async (params = {}, opts = {}) => {
      const key = listKey(params.hours, params.agent)
      const cached = listCache.current[key]
      const now = Date.now()

      // Return cached data if fresh and not forced
      if (cached && !opts.force && now - cached.fetchedAt < STALE_MS) {
        return { ...cached.data, fromCache: true }
      }

      // If we have stale data, return it immediately but refresh in background
      if (cached && !opts.force) {
        // Background refresh (fire & forget)
        apiFetchTraces(params)
          .then((freshData) => {
            listCache.current[key] = { data: freshData, fetchedAt: Date.now() }
          })
          .catch(() => { /* keep stale data on error */ })

        return { ...cached.data, fromCache: true }
      }

      // No cache at all or forced — fetch synchronously
      const data = await apiFetchTraces(params)
      listCache.current[key] = { data, fetchedAt: Date.now() }
      return { ...data, fromCache: false }
    },
    []
  )

  // ─── Trace Detail ────────────────────────────────────────────
  const getTraceDetail = useCallback(
    /**
     * @param {string} traceId
     * @param {{ force?: boolean }} opts
     * @returns {Promise<{ detail: any, fromCache: boolean }>}
     */
    async (traceId, opts = {}) => {
      if (!traceId) return { detail: null, fromCache: false }

      const cached = detailCache.current[traceId]
      const now = Date.now()

      // Fresh cache hit
      if (cached && !opts.force && now - cached.fetchedAt < STALE_MS) {
        return { detail: cached.data, fromCache: true }
      }

      // Stale hit — return immediately, refresh silently
      if (cached && !opts.force) {
        apiFetchDetail(traceId)
          .then((freshData) => {
            detailCache.current[traceId] = { data: freshData, fetchedAt: Date.now() }
          })
          .catch(() => {})

        return { detail: cached.data, fromCache: true }
      }

      // No cache — fetch synchronously
      const data = await apiFetchDetail(traceId)
      detailCache.current[traceId] = { data, fetchedAt: Date.now() }
      return { detail: data, fromCache: false }
    },
    []
  )

  // Synchronous getters for immediate initialization (no layout flash)
  const getCachedTraceList = useCallback((params = {}) => {
    const key = listKey(params.hours, params.agent)
    const cached = listCache.current[key]
    return cached ? cached.data.items : null
  }, [])

  const getCachedTraceDetail = useCallback((traceId) => {
    if (!traceId) return null
    const cached = detailCache.current[traceId]
    return cached ? cached.data : null
  }, [])

  // ─── Compiled Global Logs Cache ──────────────────────────────
  const getCompiledGlobalLogs = useCallback(async (timeWindow, force = false) => {
    const cached = globalLogsCache.current[timeWindow]
    const now = Date.now()

    if (cached && !force && now - cached.fetchedAt < STALE_MS) {
      return { logs: cached.data, fromCache: true }
    }

    // Fetch and compile global logs
    const res = await apiFetchTraces({ limit: 40, hours: parseInt(timeWindow) })
    const items = res.items || []

    const detailsPromises = items.map((t) =>
      apiFetchDetail(t.trace_id)
        .then((detail) => ({ trace: t, detail }))
        .catch(() => ({ trace: t, detail: null }))
    )

    const results = await Promise.all(detailsPromises)
    const allLogLines = []

    results.forEach(({ trace, detail }) => {
      if (!detail) {
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

    allLogLines.sort((a, b) => b.timestamp - a.timestamp)
    globalLogsCache.current[timeWindow] = { data: allLogLines, fetchedAt: Date.now() }

    return { logs: allLogLines, fromCache: false }
  }, [])

  const getCachedCompiledGlobalLogs = useCallback((timeWindow) => {
    const cached = globalLogsCache.current[timeWindow]
    return cached ? cached.data : null
  }, [])

  // ─── Agent Discovery Profile Cache ──────────────────────────
  const getCachedAgentDiscovery = useCallback((agentId) => {
    if (!agentId) return null
    const cached = agentDiscoveryCache.current[agentId]
    return cached ? cached.data : null
  }, [])

  const setAgentDiscoveryCache = useCallback((agentId, data) => {
    if (!agentId) return
    agentDiscoveryCache.current[agentId] = { data, fetchedAt: Date.now() }
  }, [])

  // ─── Invalidation ──────────────────────────────────────────
  const invalidateAll = useCallback(() => {
    listCache.current = {}
    detailCache.current = {}
    globalLogsCache.current = {}
    agentDiscoveryCache.current = {}
  }, [])

  const value = {
    getTraceList,
    getTraceDetail,
    getCachedTraceList,
    getCachedTraceDetail,
    getCompiledGlobalLogs,
    getCachedCompiledGlobalLogs,
    getCachedAgentDiscovery,
    setAgentDiscoveryCache,
    invalidateAll,
  }

  return <TracesContext.Provider value={value}>{children}</TracesContext.Provider>
}

export function useTraces() {
  const ctx = useContext(TracesContext)
  if (!ctx) throw new Error('useTraces must be used within a <TracesProvider>')
  return ctx
}
