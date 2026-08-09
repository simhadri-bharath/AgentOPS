import React, { useState } from 'react'
import { Database, Loader2, X } from 'lucide-react'
import Btn from './Btn'
import Badge from './Badge'
import { createDatasetFromSessions, previewSessionDataset } from '../api/datasets'

const CATEGORY_VARIANT = {
  happy_path: 'green',
  multi_turn: 'blue',
  long_context: 'purple',
  edge_case: 'amber',
  tool_failure: 'red',
  retrieval_failure: 'red',
  failure_case: 'red',
}

/**
 * Build an evaluation dataset from an agent's production sessions.
 *
 * Every row starts unapproved on purpose: a captured trajectory is what the
 * agent did, not what it should have done.
 */
export default function SessionDatasetBuilder({ agentId, agentName, onCreated }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [selected, setSelected] = useState(() => new Set())
  const [expected, setExpected] = useState({})
  const [name, setName] = useState('')

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await previewSessionDataset({ agent_id: agentId, limit_sessions: 25, max_cases: 50 })
      setResult(data)
      setSelected(new Set(data.preview.map((_, i) => i)))
      setName(`${agentName || 'agent'} from sessions`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const openBuilder = () => {
    setOpen(true)
    setResult(null)
    setExpected({})
    load()
  }

  const toggle = (i) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })

  const save = async () => {
    const cases = result.preview
      .map((c, i) => ({ ...c, expected_output: expected[i] ?? c.expected_output }))
      .filter((_, i) => selected.has(i))
    if (!cases.length) {
      setError('Select at least one case.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const created = await createDatasetFromSessions({
        agent_id: agentId,
        name,
        cases,
      })
      setOpen(false)
      onCreated?.(created)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <Btn onClick={openBuilder}>
        <Database size={13} />
        Build dataset from sessions
      </Btn>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-center items-start p-8" style={{ background: 'rgba(0,0,0,0.3)' }}>
      <div
        className="w-full max-w-4xl max-h-full overflow-y-auto rounded-lg p-5"
        style={{ background: 'var(--color-background-primary)', border: '0.5px solid #E5E7EB' }}
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="text-[15px] font-medium text-gray-900">Build dataset from sessions</div>
            <div className="text-[12px] text-gray-500 mt-0.5">
              Cases extracted from real traffic. Retrieval context and tool trajectory come from
              what the agent actually did.
            </div>
          </div>
          <button type="button" onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-700">
            <X size={18} />
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-16 text-gray-500 gap-2">
            <Loader2 size={18} className="animate-spin" />
            Reading sessions…
          </div>
        )}

        {error && (
          <div className="mb-3 px-3 py-2 rounded-lg text-[12px] bg-red-50 text-red-800 border border-red-200">
            {error}
          </div>
        )}

        {result && (
          <>
            <div className="mb-3 px-3 py-2 rounded-lg text-[12px] bg-amber-50 text-amber-900 border border-amber-200">
              {result.notice}
            </div>

            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="text-[12px] text-gray-500">
                {result.total} case(s) · {selected.size} selected
              </span>
              {Object.entries(result.category_distribution).map(([cat, n]) => (
                <Badge key={cat} variant={CATEGORY_VARIANT[cat] || 'gray'}>
                  {cat} {n}
                </Badge>
              ))}
            </div>

            {result.errors.length > 0 && (
              <ul className="mb-3 text-[11px] text-gray-500 list-disc pl-4">
                {result.errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}

            <input
              className="w-full mb-3"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Dataset name"
            />

            <div className="space-y-2 mb-4">
              {result.preview.map((c, i) => (
                <div
                  key={`${c.session_id}-${c.invocation_id}-${i}`}
                  className="border rounded-md p-3"
                  style={{ borderColor: selected.has(i) ? '#C7D2FE' : '#E5E7EB' }}
                >
                  <div className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={selected.has(i)}
                      onChange={() => toggle(i)}
                      className="mt-1"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant={CATEGORY_VARIANT[c.category] || 'gray'}>{c.category}</Badge>
                        <span className="text-[10px] text-gray-400">
                          {c.retrieval_context.length} docs · {c.reference_trajectory.length} tool
                          call(s) · {c.conversation.length} prior turn(s)
                        </span>
                      </div>
                      <div className="text-[12px] text-gray-900 mb-1 line-clamp-2">{c.input}</div>
                      <div className="text-[11px] text-gray-500 mb-2 line-clamp-2">
                        {c.actual_output}
                      </div>
                      {c.notes.length > 0 && (
                        <div className="text-[11px] text-amber-700 mb-1">{c.notes.join(' · ')}</div>
                      )}
                      <textarea
                        rows={2}
                        className="w-full text-[12px]"
                        placeholder="expected_output — what a correct answer should say (required before this set can become golden)"
                        value={expected[i] ?? ''}
                        onChange={(e) => setExpected((p) => ({ ...p, [i]: e.target.value }))}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex gap-2">
              <Btn primary onClick={save} disabled={saving}>
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Database size={13} />}
                {saving ? 'Saving…' : `Save ${selected.size} case(s)`}
              </Btn>
              <Btn onClick={() => setOpen(false)}>Cancel</Btn>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
