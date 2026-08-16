import React, { useState } from 'react'
import { Loader2, Pencil, Save, X } from 'lucide-react'
import Btn from './Btn'
import Badge from './Badge'
import KVRow from './KVRow'
import { AGENT_TYPES, CAPABILITIES, ENVIRONMENTS, patchAgent } from '../api/deployments'

/**
 * Edit what an agent is for.
 *
 * Type inference only reports what is observable, so an agent whose retrieval
 * happens internally (Discovery Engine grounding, no functionCall event) is
 * proposed as conversational. Correcting that is what selects the RAG metric
 * pack — and until now there was no screen to do it on.
 */
export default function AgentProfileEditor({ agent, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [agentType, setAgentType] = useState(agent.agentType || 'unknown')
  const [capabilities, setCapabilities] = useState(agent.capabilities || [])
  const [environment, setEnvironment] = useState(agent.environment || 'unknown')
  const [purpose, setPurpose] = useState(agent.purpose || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const toggleCap = (cap) =>
    setCapabilities((prev) =>
      prev.includes(cap) ? prev.filter((c) => c !== cap) : [...prev, cap],
    )

  const cancel = () => {
    setAgentType(agent.agentType || 'unknown')
    setCapabilities(agent.capabilities || [])
    setEnvironment(agent.environment || 'unknown')
    setPurpose(agent.purpose || '')
    setError(null)
    setEditing(false)
  }

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await patchAgent(agent.id, {
        agent_type: agentType,
        capabilities,
        environment,
        purpose: purpose || null,
      })
      setEditing(false)
      onSaved?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    return (
      <>
        <KVRow label="Agent type" value={agent.agentType || 'unknown'} />
        <KVRow
          label="Capabilities"
          value={(agent.capabilities || []).join(', ') || '—'}
        />
        <KVRow label="Environment" value={agent.environment || 'unknown'} />
        <KVRow label="Purpose" value={agent.purpose || '—'} />
        {(agent.agentType === 'unknown' || !(agent.capabilities || []).length) && (
          <div className="px-3 py-2 my-2 rounded-lg text-[11px] bg-amber-50 text-amber-900 border border-amber-200">
            This agent is unclassified, so only baseline metrics are recommended.
            If it retrieves documents internally, no tool call is visible to infer
            from — set the type and capabilities here.
          </div>
        )}
        <div className="pt-2">
          <Btn style={{ fontSize: 11 }} onClick={() => setEditing(true)}>
            <Pencil size={12} />
            Edit profile
          </Btn>
        </div>
      </>
    )
  }

  return (
    <div className="pt-1">
      <label className="block text-[12px] font-medium text-gray-700 mb-1">Agent type</label>
      <select
        className="w-full mb-3"
        value={agentType}
        onChange={(e) => setAgentType(e.target.value)}
      >
        {AGENT_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label} — {t.hint}
          </option>
        ))}
      </select>

      <label className="block text-[12px] font-medium text-gray-700 mb-1.5">Capabilities</label>
      <div className="flex flex-wrap gap-1.5 mb-3">
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

      <label className="block text-[12px] font-medium text-gray-700 mb-1">Environment</label>
      <select
        className="w-full mb-3"
        value={environment}
        onChange={(e) => setEnvironment(e.target.value)}
      >
        {[...ENVIRONMENTS, { value: 'unknown', label: 'Unknown' }].map((e) => (
          <option key={e.value} value={e.value}>
            {e.label}
          </option>
        ))}
      </select>

      <label className="block text-[12px] font-medium text-gray-700 mb-1">Purpose</label>
      <textarea
        className="w-full mb-3"
        rows={3}
        value={purpose}
        onChange={(e) => setPurpose(e.target.value)}
        placeholder="What is this agent supposed to do?"
      />

      {error && (
        <div className="mb-2 px-3 py-2 rounded-lg text-[12px] bg-red-50 text-red-800 border border-red-200">
          {error}
        </div>
      )}

      <div className="flex gap-2">
        <Btn primary onClick={save} disabled={saving}>
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
          Save
        </Btn>
        <Btn onClick={cancel} disabled={saving}>
          <X size={13} />
          Cancel
        </Btn>
      </div>
      <div className="text-[11px] text-gray-400 mt-2">
        Changing type or capabilities changes which metrics are recommended.
      </div>
    </div>
  )
}
