import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import Btn from '../components/Btn'
import EmptyState from '../components/EmptyState'
import PageHeader from '../components/PageHeader'
import StatCard from '../components/StatCard'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import { CheckCircle2, Loader2, Play, RefreshCw, Rocket, X } from 'lucide-react'
import {
  AGENT_TYPES,
  CAPABILITIES,
  ENVIRONMENTS,
  fetchDeployments,
  onboardDeployment,
  testInvokeDeployment,
} from '../api/deployments'
import { useAgents } from '../context/AgentsContext'

const relativeTime = (iso) => {
  if (!iso) return 'never used'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return '—'
  const mins = Math.round((Date.now() - then) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

const typeBadge = (t) => {
  const variant =
    t === 'multi_agent' ? 'purple' : t === 'rag' ? 'blue' : t === 'unknown' ? 'gray' : 'green'
  return <Badge variant={variant}>{t}</Badge>
}

function OnboardDrawer({ deployment, onClose, onDone }) {
  const [agentType, setAgentType] = useState(deployment.agent_type_guess || 'unknown')
  const [capabilities, setCapabilities] = useState(deployment.capabilities_guess || [])
  const [purpose, setPurpose] = useState(deployment.purpose_guess || '')
  const [environment, setEnvironment] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [onboarded, setOnboarded] = useState(Boolean(deployment.onboarded_agent_id))
  const [testPrompt, setTestPrompt] = useState('')

  const toggleCap = (cap) =>
    setCapabilities((prev) =>
      prev.includes(cap) ? prev.filter((c) => c !== cap) : [...prev, cap],
    )

  const save = async () => {
    if (!environment) {
      setError('Pick an environment. Red-team gating keys off this field.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const agent = await onboardDeployment({
        engine_id: deployment.engine_id,
        region: deployment.region,
        environment,
        agent_type: agentType,
        capabilities,
        purpose: purpose || null,
      })
      setOnboarded(true)
      onDone(agent, { keepOpen: true })
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  // Testing must not require onboarding first: the point of the test is to
  // decide whether to onboard.
  const runTest = async () => {
    setTesting(true)
    setError(null)
    setTestResult(null)
    try {
      setTestResult(
        await testInvokeDeployment(
          deployment.engine_id,
          testPrompt.trim() || 'Reply with: ok',
          deployment.region,
        ),
      )
    } catch (e) {
      setError(e.message)
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end" style={{ background: 'rgba(0,0,0,0.25)' }}>
      <div
        className="w-[460px] h-full overflow-y-auto p-5"
        style={{ background: 'var(--color-background-primary)', borderLeft: '0.5px solid #E5E7EB' }}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="text-[15px] font-medium text-gray-900">Onboard deployment</div>
            <div className="text-[12px] text-gray-500 mt-0.5">{deployment.display_name}</div>
          </div>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X size={18} />
          </button>
        </div>

        <div className="text-[11px] text-gray-500 mb-4" style={{ fontFamily: 'var(--font-mono)' }}>
          {deployment.resource_name}
        </div>

        <label className="block text-[12px] font-medium text-gray-700 mb-1">Agent type</label>
        <select
          className="w-full mb-1"
          value={agentType}
          onChange={(e) => setAgentType(e.target.value)}
        >
          {AGENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <div className="text-[11px] text-gray-400 mb-3">
          {deployment.agent_type_guess !== 'unknown'
            ? `Proposed from ${deployment.sessions_inspected} recent session(s).`
            : 'No tool calls observed — classify manually.'}
        </div>

        <label className="block text-[12px] font-medium text-gray-700 mb-1.5">Capabilities</label>
        <div className="flex flex-wrap gap-1.5 mb-4">
          {CAPABILITIES.map((cap) => (
            <button
              key={cap}
              type="button"
              onClick={() => toggleCap(cap)}
              className={`px-2 py-1 rounded-md text-[11px] border transition-colors ${
                capabilities.includes(cap)
                  ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
                  : 'bg-white border-gray-200 text-gray-500 hover:bg-gray-50'
              }`}
            >
              {cap}
            </button>
          ))}
        </div>

        <label className="block text-[12px] font-medium text-gray-700 mb-1">Purpose</label>
        <textarea
          className="w-full mb-4"
          rows={4}
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
          placeholder="What is this agent supposed to do?"
        />

        <label className="block text-[12px] font-medium text-gray-700 mb-1">
          Environment <span className="text-red-500">*</span>
        </label>
        <select
          className="w-full mb-1"
          value={environment}
          onChange={(e) => setEnvironment(e.target.value)}
        >
          <option value="">Select…</option>
          {ENVIRONMENTS.map((e) => (
            <option key={e.value} value={e.value}>
              {e.label}
            </option>
          ))}
        </select>
        <div className="text-[11px] text-gray-400 mb-4">
          Required. Red-team scans against production are gated on this.
        </div>

        {error && (
          <div className="mb-3 px-3 py-2 rounded-lg text-[12px] bg-red-50 text-red-800 border border-red-200">
            {error}
          </div>
        )}

        <div className="border-t pt-3 mb-3" style={{ borderColor: '#E5E7EB' }}>
          <label className="block text-[12px] font-medium text-gray-700 mb-1">
            Test invoke
          </label>
          <div className="text-[11px] text-gray-400 mb-1.5">
            Runs one real prompt against the live agent. Costs one invocation and
            takes ~30-45s for a retrieval agent. No data is saved.
          </div>
          <input
            className="w-full mb-1.5 text-[12px]"
            placeholder="Reply with: ok"
            value={testPrompt}
            onChange={(e) => setTestPrompt(e.target.value)}
          />
          <Btn onClick={runTest} disabled={testing}>
            {testing ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            {testing ? 'Invoking…' : 'Run test'}
          </Btn>
        </div>

        {testResult && (
          <div
            className="mb-3 px-3 py-2 rounded-lg text-[12px] border"
            style={
              testResult.state === 'SUCCESS'
                ? { background: '#F0FDF4', borderColor: '#BBF7D0' }
                : { background: '#FEF2F2', borderColor: '#FECACA' }
            }
          >
            <div className="font-medium mb-1">
              {testResult.state} · {testResult.latency_ms} ms · {testResult.tokens_in}/
              {testResult.tokens_out} tokens
            </div>
            {testResult.agent_path?.length > 0 && (
              <div className="text-gray-600 mb-0.5">
                path: {testResult.agent_path.join(' → ')}
              </div>
            )}
            {testResult.trajectory?.length > 0 && (
              <div className="text-gray-600 mb-0.5">
                tools: {testResult.trajectory.map((t) => t.name).join(', ')}
              </div>
            )}
            <div className="text-gray-600 mb-1">
              retrieved: {testResult.retrieval_context?.length || 0} document(s)
              {(testResult.retrieval_context?.length || 0) === 0 && (
                // Zero here is the signal that RAG metrics will be unavailable.
                <span className="text-amber-700">
                  {' '}
                  — RAG metrics will report unavailable
                </span>
              )}
            </div>
            <div className="text-gray-800 whitespace-pre-wrap">
              {(testResult.output || testResult.error || '').slice(0, 500)}
            </div>
          </div>
        )}

        <div className="flex gap-2 items-center">
          <Btn primary onClick={save} disabled={saving}>
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Rocket size={13} />}
            {saving ? 'Saving…' : onboarded ? 'Update agent' : 'Onboard'}
          </Btn>
          {onboarded && (
            <span className="flex items-center gap-1 text-[11px] text-green-700">
              <CheckCircle2 size={13} />
              saved
            </span>
          )}
          <Btn onClick={onClose} style={{ marginLeft: 'auto' }}>
            Close
          </Btn>
        </div>
      </div>
    </div>
  )
}

export default function Deployments() {
  const nav = useNavigate()
  const { refreshAgents } = useAgents()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [drawer, setDrawer] = useState(null)

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true)
    setError(null)
    try {
      setData(await fetchDeployments({ refresh }))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const items = data?.items || []
  const onboardedCount = useMemo(
    () => items.filter((d) => d.onboarded_agent_id).length,
    [items],
  )

  return (
    <div>
      <PageHeader
        title="Deployments"
        subtitle={
          data
            ? `Agent Engine · ${data.project || 'no project set'} · ${data.regions.join(', ')}`
            : 'Reading live inventory from Vertex AI'
        }
      >
        <Btn primary onClick={() => load(true)} disabled={refreshing}>
          {refreshing ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <RefreshCw size={13} />
          )}
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </Btn>
      </PageHeader>

      {error && (
        <div className="mb-4 px-3 py-2 rounded-lg text-[13px] bg-red-50 text-red-800 border border-red-200">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => load(true)}>
            Retry
          </button>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3 mb-5">
        <StatCard label="Deployed" value={String(items.length)} />
        <StatCard label="Onboarded" value={String(onboardedCount)} />
        <StatCard label="Not onboarded" value={String(items.length - onboardedCount)} />
      </div>

      <Card>
        <CardHeader title="Agent Engine deployments" />
        {loading ? (
          <div className="flex items-center justify-center py-16 text-gray-500 gap-2">
            <Loader2 size={18} className="animate-spin" />
            Reading deployments…
          </div>
        ) : items.length === 0 ? (
          <EmptyState message="No Agent Engines found in this project. Check GCP_PROJECT_ID and GCP_REGION." />
        ) : (
          <Table>
            <THead>
              <Th>Deployment</Th>
              <Th>Framework</Th>
              <Th>Proposed type</Th>
              <Th>Observed tools</Th>
              <Th>Activity</Th>
              <Th></Th>
            </THead>
            <tbody>
              {items.map((d) => (
                <TRow key={`${d.region}/${d.engine_id}`}>
                  <Td>
                    <div className="font-medium">{d.display_name}</div>
                    <div style={{ fontSize: 10, color: '#9CA3AF', fontFamily: 'var(--font-mono)' }}>
                      {d.region} · {d.engine_id}
                    </div>
                  </Td>
                  <Td>
                    <Badge variant="gray">{d.framework || 'unknown'}</Badge>
                  </Td>
                  <Td>
                    {typeBadge(d.agent_type_guess)}
                    {d.capabilities_guess.length > 0 && (
                      <div style={{ fontSize: 10, color: '#9CA3AF', marginTop: 2 }}>
                        {d.capabilities_guess.join(', ')}
                      </div>
                    )}
                  </Td>
                  <Td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    {d.observed_tools.length > 0 ? (
                      d.observed_tools.join(', ')
                    ) : (
                      <span style={{ color: '#9CA3AF' }}>
                        none in {d.sessions_inspected} session(s)
                      </span>
                    )}
                  </Td>
                  <Td style={{ color: '#6B7280' }}>
                    <div>{relativeTime(d.last_activity_at)}</div>
                    <div style={{ fontSize: 10, color: '#9CA3AF' }}>
                      {d.session_count}
                      {d.session_count_capped ? '+' : ''} sessions
                    </div>
                  </Td>
                  <Td>
                    {d.onboarded_agent_id ? (
                      <div className="flex items-center gap-2">
                        <span className="flex items-center gap-1 text-[11px] text-green-700">
                          <CheckCircle2 size={13} />
                          onboarded
                        </span>
                        <Btn
                          style={{ fontSize: 11 }}
                          onClick={() => nav(`/agents/${d.onboarded_agent_id}`)}
                        >
                          Open
                        </Btn>
                      </div>
                    ) : (
                      <Btn style={{ fontSize: 11 }} onClick={() => setDrawer(d)}>
                        Onboard
                      </Btn>
                    )}
                  </Td>
                </TRow>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {drawer && (
        <OnboardDrawer
          deployment={drawer}
          onClose={() => setDrawer(null)}
          onDone={async (agent, opts) => {
            // Stay open after onboarding so the user can test the agent they
            // just saved without hunting for it in another page.
            if (!opts?.keepOpen) setDrawer(null)
            await load(true)
            refreshAgents()
          }}
        />
      )}
    </div>
  )
}
