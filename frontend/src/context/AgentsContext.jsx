import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import * as agentsApi from '../api/agents'
import * as discoveryApi from '../api/discovery'
import * as healthApi from '../api/health'
import { mapApiAgent } from '../lib/agentMapper'

const AgentsContext = createContext(null)

export function AgentsProvider({ children }) {
  const [agents, setAgents] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState(null)
  const [lastSyncedAt, setLastSyncedAt] = useState(null)
  const [health, setHealth] = useState(null)
  const [discoveryTest, setDiscoveryTest] = useState(null)

  const refreshAgents = useCallback(async () => {
    setError(null)
    try {
      const data = await agentsApi.fetchAgents({ limit: 500 })
      const mapped = (data.items || []).map((a, i) => mapApiAgent(a, i))
      setAgents(mapped)
      setTotal(data.total ?? mapped.length)
      return mapped
    } catch (err) {
      setError(err.message || 'Failed to load agents')
      throw err
    }
  }, [])

  const refreshHealth = useCallback(async () => {
    try {
      const data = await healthApi.fetchHealth()
      setHealth(data)
      return data
    } catch (err) {
      setHealth({ status: 'unhealthy', database: `error: ${err.message}`, gcp_auth: 'error' })
      return null
    }
  }, [])

  const testDiscovery = useCallback(async () => {
    const data = await discoveryApi.testVertexAI()
    setDiscoveryTest(data)
    return data
  }, [])

  const syncDiscovery = useCallback(async () => {
    setSyncing(true)
    setError(null)
    try {
      const summary = await discoveryApi.syncVertexAI()
      await refreshAgents()
      setLastSyncedAt(new Date())
      return summary
    } catch (err) {
      setError(err.message || 'Discovery sync failed')
      throw err
    } finally {
      setSyncing(false)
    }
  }, [refreshAgents])

  const getAgent = useCallback(
    async (id) => {
      const cached = agents.find((a) => a.id === id)
      if (cached) return cached
      const data = await agentsApi.fetchAgent(id)
      return mapApiAgent(data)
    },
    [agents]
  )

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        await Promise.all([refreshAgents(), refreshHealth()])
      } catch {
        /* error stored in state */
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshAgents, refreshHealth])

  const value = useMemo(
    () => ({
      agents,
      total,
      loading,
      syncing,
      error,
      lastSyncedAt,
      health,
      discoveryTest,
      refreshAgents,
      refreshHealth,
      syncDiscovery,
      testDiscovery,
      getAgent,
      setError,
    }),
    [
      agents,
      total,
      loading,
      syncing,
      error,
      lastSyncedAt,
      health,
      discoveryTest,
      refreshAgents,
      refreshHealth,
      syncDiscovery,
      testDiscovery,
      getAgent,
    ]
  )

  return <AgentsContext.Provider value={value}>{children}</AgentsContext.Provider>
}

export function useAgents() {
  const ctx = useContext(AgentsContext)
  if (!ctx) {
    throw new Error('useAgents must be used within AgentsProvider')
  }
  return ctx
}
