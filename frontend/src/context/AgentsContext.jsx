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
    try {
      const [vertexData, cloudRunData] = await Promise.all([
        discoveryApi.testVertexAI().catch((err) => ({
          authenticated: false,
          message: err.message || 'Vertex AI test failed',
          engine_count: 0,
        })),
        discoveryApi.testCloudRun().catch((err) => ({
          authenticated: false,
          message: err.message || 'Cloud Run test failed',
          service_count: 0,
        })),
      ])

      const authenticated = vertexData.authenticated || cloudRunData.authenticated
      const project_id = vertexData.project_id || cloudRunData.project_id
      const region = vertexData.region || cloudRunData.region

      let message = ''
      if (vertexData.authenticated && cloudRunData.authenticated) {
        message = `Successfully connected. Found ${vertexData.engine_count} Reasoning Engine(s) and ${cloudRunData.service_count} Cloud Run service(s).`
      } else if (vertexData.authenticated) {
        message = `Connected to Vertex AI (${vertexData.engine_count} engines). Cloud Run test failed: ${cloudRunData.message}`
      } else if (cloudRunData.authenticated) {
        message = `Connected to Cloud Run (${cloudRunData.service_count} services). Vertex AI test failed: ${vertexData.message}`
      } else {
        message = `Connection failed. Vertex AI: ${vertexData.message} | Cloud Run: ${cloudRunData.message}`
      }

      const combined = {
        authenticated,
        project_id,
        region,
        engine_count: vertexData.engine_count,
        service_count: cloudRunData.service_count,
        message,
        vertex: vertexData,
        cloudRun: cloudRunData,
      }

      setDiscoveryTest(combined)
      return combined
    } catch (err) {
      const failed = {
        authenticated: false,
        message: err.message || 'Discovery connection test failed',
      }
      setDiscoveryTest(failed)
      return failed
    }
  }, [])

  const syncDiscovery = useCallback(async () => {
    setSyncing(true)
    setError(null)
    try {
      const summary = await discoveryApi.syncAll()
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
