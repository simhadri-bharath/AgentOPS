import React, { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Loader2, RefreshCw, ShieldCheck } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import Btn from '../components/Btn'
import EmptyState from '../components/EmptyState'
import PageHeader from '../components/PageHeader'
import StatCard from '../components/StatCard'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import {
  fetchDatasetRows,
  fetchDatasets,
  setDatasetReviewStatus,
  updateDatasetRow,
} from '../api/datasets'

const STATUS_VARIANT = {
  bootstrapped: 'amber',
  needs_review: 'amber',
  human_reviewed: 'blue',
  golden: 'green',
  upload: 'gray',
}

const CATEGORIES = [
  'happy_path',
  'edge_case',
  'failure_case',
  'adversarial',
  'long_context',
  'multi_turn',
  'tool_failure',
  'retrieval_failure',
  'ambiguous_request',
  'uncategorized',
]

/**
 * Dataset review.
 *
 * Promotion to golden is refused until every row has an expected_output. This
 * is the screen that makes that reachable — without it the gate cannot be
 * satisfied at all.
 */
export default function Datasets() {
  const [datasets, setDatasets] = useState([])
  const [selected, setSelected] = useState(null)
  const [rows, setRows] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [unreviewedOnly, setUnreviewedOnly] = useState(false)
  const [drafts, setDrafts] = useState({})

  const loadDatasets = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchDatasets({ limit: 100 })
      setDatasets(data.items || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadRows = useCallback(
    async (datasetId, only = unreviewedOnly) => {
      setBusy(true)
      setError(null)
      try {
        const data = await fetchDatasetRows(datasetId, { limit: 200, unreviewedOnly: only })
        setRows(data)
        setDrafts(
          Object.fromEntries(data.items.map((r) => [r.index, r.expected_output || ''])),
        )
      } catch (e) {
        setError(e.message)
      } finally {
        setBusy(false)
      }
    },
    [unreviewedOnly],
  )

  useEffect(() => {
    loadDatasets()
  }, [loadDatasets])

  const open = (d) => {
    setSelected(d)
    setRows(null)
    loadRows(d.id)
  }

  const saveRow = async (index) => {
    setBusy(true)
    setError(null)
    try {
      await updateDatasetRow(selected.id, index, { expected_output: drafts[index] })
      await Promise.all([loadRows(selected.id), loadDatasets()])
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const setCategory = async (index, category) => {
    setBusy(true)
    try {
      await updateDatasetRow(selected.id, index, { category })
      await loadRows(selected.id)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const promote = async (status) => {
    setBusy(true)
    setError(null)
    try {
      const updated = await setDatasetReviewStatus(selected.id, status)
      setSelected(updated)
      await Promise.all([loadDatasets(), loadRows(selected.id)])
    } catch (e) {
      // The 400 from the golden gate names exactly how many rows are missing.
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Datasets"
        subtitle="Review captured cases before they become a regression baseline"
      >
        <Btn onClick={loadDatasets} disabled={loading}>
          <RefreshCw size={13} />
          Refresh
        </Btn>
      </PageHeader>

      {error && (
        <div className="mb-4 px-3 py-2 rounded-lg text-[13px] bg-red-50 text-red-800 border border-red-200">
          {error}
        </div>
      )}

      <Card className="mb-5">
        <CardHeader title="All datasets" />
        {loading ? (
          <div className="flex items-center justify-center py-10 text-gray-500 gap-2">
            <Loader2 size={18} className="animate-spin" />
            Loading…
          </div>
        ) : datasets.length === 0 ? (
          <EmptyState message="No datasets yet. Build one from an agent's sessions or upload a CSV." />
        ) : (
          <Table>
            <THead>
              <Th>Name</Th>
              <Th>Source</Th>
              <Th>Status</Th>
              <Th>Rows</Th>
              <Th>Version</Th>
              <Th>Categories</Th>
              <Th></Th>
            </THead>
            <tbody>
              {datasets.map((d) => (
                <TRow key={d.id}>
                  <Td>
                    <div className="font-medium">{d.name}</div>
                    <div style={{ fontSize: 10, color: '#9CA3AF' }}>{d.description}</div>
                  </Td>
                  <Td>
                    <Badge variant={STATUS_VARIANT[d.source] || 'gray'}>{d.source}</Badge>
                  </Td>
                  <Td>
                    <Badge variant={STATUS_VARIANT[d.review_status] || 'gray'}>
                      {d.review_status}
                    </Badge>
                  </Td>
                  <Td>{d.row_count}</Td>
                  <Td>v{d.version}</Td>
                  <Td style={{ fontSize: 11, color: '#6B7280' }}>
                    {Object.entries(d.category_distribution || {})
                      .map(([k, v]) => `${k} ${v}`)
                      .join(' · ') || '—'}
                  </Td>
                  <Td>
                    <Btn style={{ fontSize: 11 }} onClick={() => open(d)}>
                      Review
                    </Btn>
                  </Td>
                </TRow>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {selected && rows && (
        <>
          <div className="grid grid-cols-4 gap-3 mb-4">
            <StatCard label="Rows" value={String(rows.total)} />
            <StatCard
              label="Unreviewed"
              value={String(rows.unreviewed)}
              valueStyle={{ color: rows.unreviewed ? '#F59E0B' : '#10B981' }}
            />
            <StatCard label="Version" value={`v${rows.version}`} />
            <StatCard label="Status" value={rows.review_status} />
          </div>

          <Card>
            <CardHeader title={`Review — ${selected.name}`}>
              <label className="flex items-center gap-1.5 text-[12px] text-gray-600">
                <input
                  type="checkbox"
                  checked={unreviewedOnly}
                  onChange={(e) => {
                    setUnreviewedOnly(e.target.checked)
                    loadRows(selected.id, e.target.checked)
                  }}
                />
                Unreviewed only
              </label>
              <Btn
                onClick={() => promote('human_reviewed')}
                disabled={busy || rows.review_status === 'human_reviewed'}
              >
                Mark reviewed
              </Btn>
              <Btn primary onClick={() => promote('golden')} disabled={busy}>
                <ShieldCheck size={13} />
                Promote to golden
              </Btn>
            </CardHeader>

            {rows.unreviewed > 0 && (
              <div className="mx-3 mb-3 px-3 py-2 rounded-lg text-[12px] bg-amber-50 text-amber-900 border border-amber-200">
                {rows.unreviewed} row(s) still have no expected output. A captured
                trajectory records what the agent did, not what it should have done, so
                this set cannot become golden until each one is decided.
              </div>
            )}

            <div className="px-3 pb-3 space-y-3">
              {rows.items.map((r) => (
                <div
                  key={r.index}
                  className="border rounded-md p-3"
                  style={{ borderColor: r.blocks_golden ? '#FDE68A' : '#E5E7EB' }}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-[11px] text-gray-400">#{r.index}</span>
                    <select
                      className="text-[11px]"
                      value={r.category}
                      onChange={(e) => setCategory(r.index, e.target.value)}
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                    <span className="text-[10px] text-gray-400">
                      {r.retrieval_context.length} docs ·{' '}
                      {r.reference_trajectory.map((t) => t.name).join(', ') || 'no tools'}
                    </span>
                    {r.reviewed ? (
                      <span className="ml-auto flex items-center gap-1 text-[11px] text-green-700">
                        <CheckCircle2 size={12} />
                        reviewed
                      </span>
                    ) : (
                      <Badge variant="amber">needs expected output</Badge>
                    )}
                  </div>

                  <div className="text-[12px] text-gray-900 mb-1">{r.input}</div>
                  <div className="text-[11px] text-gray-500 mb-2">
                    Agent said: {r.actual_output?.slice(0, 300) || '—'}
                  </div>

                  <textarea
                    rows={2}
                    className="w-full text-[12px] mb-1.5"
                    placeholder="What should a correct answer say?"
                    value={drafts[r.index] ?? ''}
                    onChange={(e) =>
                      setDrafts((p) => ({ ...p, [r.index]: e.target.value }))
                    }
                  />
                  <Btn
                    style={{ fontSize: 11 }}
                    onClick={() => saveRow(r.index)}
                    disabled={busy || !(drafts[r.index] || '').trim()}
                  >
                    Save
                  </Btn>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
