import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Play, RotateCcw, Save, Upload } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import Btn from '../components/Btn'
import EmptyState from '../components/EmptyState'
import PageHeader from '../components/PageHeader'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import { useAgents } from '../context/AgentsContext'
import * as datasetsApi from '../api/datasets'
import * as evaluationsApi from '../api/evaluations'
import {
  frameworkLabel,
  FRAMEWORKS,
  FRAMEWORK_METRICS,
  metricLabel,
  normalizeFramework,
} from '../lib/evaluationConstants'
import {
  formatEvalDate,
  formatLatencyMs,
  passRateFromAggregates,
  runStatusLabel,
  runStatusVariant,
  samplePassed,
} from '../lib/evaluationMapper'

const POLL_MS = 3000
const TERMINAL = new Set(['completed', 'failed', 'draft'])

function jobToForm(jobData) {
  const framework = normalizeFramework(jobData.framework)
  return {
    agent_id: String(jobData.agent_id),
    dataset_id: String(jobData.dataset_id),
    framework,
    metrics: Array.isArray(jobData.metrics) ? [...jobData.metrics] : [],
  }
}

export default function JobDetailsPage() {
  const { jobId } = useParams()
  const nav = useNavigate()
  const { agents } = useAgents()

  const [job, setJob] = useState(null)
  const [dataset, setDataset] = useState(null)
  const [datasets, setDatasets] = useState([])
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [running, setRunning] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [form, setForm] = useState({
    agent_id: '',
    dataset_id: '',
    framework: 'vertex',
    metrics: [],
  })

  const isDraft = job?.status === 'draft'

  const agent = useMemo(
    () => agents.find((a) => a.id === String(form.agent_id)),
    [agents, form.agent_id]
  )

  const frameworkMetrics = FRAMEWORK_METRICS[form.framework] || []

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (!jobId) return null

      if (!silent) setLoading(true)

      try {
        const jobData = await evaluationsApi.fetchEvaluation(jobId)
        setJob(jobData)
        setForm(jobToForm(jobData))

        const ds = await datasetsApi.fetchDataset(jobData.dataset_id).catch(() => null)
        setDataset(ds)

        const dsList = await datasetsApi.fetchDatasets({ limit: 100 }).catch(() => ({ items: [] }))
        const items = dsList.items || []
        if (ds && !items.some((d) => String(d.id) === String(ds.id))) {
          setDatasets([ds, ...items])
        } else {
          setDatasets(items)
        }

        if (jobData.status !== 'draft') {
          const resultsData = await evaluationsApi.fetchEvaluationResults(jobId)
          setResults(resultsData)
        } else {
          setResults(null)
        }

        setError(null)
        return jobData
      } catch (err) {
        setError(err.message || 'Failed to load job')
        throw err
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [jobId]
  )

  useEffect(() => {
    let cancelled = false
    let timer = null

    async function poll(initial = false) {
      try {
        const jobData = await load({ silent: !initial })
        if (cancelled || !jobData) return

        if (!TERMINAL.has(jobData.status)) {
          timer = setTimeout(() => poll(false), POLL_MS)
        }
      } catch {
        /* error set in load */
      }
    }

    poll(true)

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [load])

  const handleSave = async () => {
    if (!form.metrics.length) {
      setError('Select at least one metric')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await evaluationsApi.updateEvaluationJob(jobId, form)
      await load({ silent: true })
    } catch (err) {
      setError(err.message || 'Failed to save changes')
    } finally {
      setSaving(false)
    }
  }

  const handleRun = async () => {
    setRunning(true)
    setError(null)
    try {
      if (isDraft) {
        await evaluationsApi.updateEvaluationJob(jobId, form)
      }
      await evaluationsApi.runEvaluationJob(jobId)
      await load({ silent: true })
    } catch (err) {
      setError(err.message || 'Failed to run evaluation')
    } finally {
      setRunning(false)
    }
  }

  const handleRetry = async () => {
    setRunning(true)
    setError(null)
    try {
      await evaluationsApi.retryEvaluation(jobId)
      await load({ silent: true })
    } catch (err) {
      setError(err.message || 'Failed to retry evaluation')
    } finally {
      setRunning(false)
    }
  }

  const toggleMetric = (metric) => {
    setForm((prev) => ({
      ...prev,
      metrics: prev.metrics.includes(metric)
        ? prev.metrics.filter((m) => m !== metric)
        : [...prev.metrics, metric],
    }))
  }

  const handleDatasetUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)
    try {
      const uploaded = await datasetsApi.uploadDataset(file, { name: file.name })
      const ds = uploaded.dataset
      setDatasets((prev) => {
        const exists = prev.some((d) => String(d.id) === String(ds.id))
        return exists ? prev : [ds, ...prev]
      })
      setDataset(ds)
      setForm((prev) => ({ ...prev, dataset_id: String(ds.id) }))
    } catch (err) {
      setError(err.message || 'Failed to upload dataset')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const passRate = passRateFromAggregates(job?.aggregate_scores)
  const resultRows = results?.items || []

  if (loading && !job) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-gray-500">
        <Loader2 size={18} className="animate-spin" />
        Loading job…
      </div>
    )
  }

  if (!job) {
    return (
      <div>
        <EmptyState message={error || 'Job not found'} />
        <div className="mt-2 text-center">
          <Btn onClick={() => nav('/jobs')}>Back to jobs</Btn>
        </div>
      </div>
    )
  }

  const statusBadge = (
    <Badge variant={runStatusVariant(job.status, job.aggregate_scores)}>
      {runStatusLabel(job.status)}
    </Badge>
  )

  return (
    <div>
      <PageHeader
        title={job.name}
        subtitle={`Evaluation job · ${frameworkLabel(job.framework)}`}
      >
        <Btn onClick={() => nav('/jobs')}>
          <ArrowLeft size={13} />
          Jobs
        </Btn>
      </PageHeader>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        {statusBadge}
        <div className="text-[13px] text-gray-500">
          Created {formatEvalDate(job.created_at)}
        </div>
        {passRate != null && (
          <div className="text-[13px] text-gray-500">
            Pass rate:
            <span className="ml-1 font-medium text-gray-900">{passRate}%</span>
          </div>
        )}
        {!isDraft && (
          <span className="text-[12px] text-gray-400">Configuration is read-only after run</span>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-800">
          {error}
        </div>
      )}

      {job.error_message && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
          {job.error_message}
        </div>
      )}

      <div className="mb-4 grid grid-cols-[1.2fr_0.8fr] gap-4">
        <Card>
          <CardHeader title="Configuration" />
          <div className="space-y-4 px-4 pb-4">
            <div>
              <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-gray-500">
                Agent
              </label>
              <select
                value={form.agent_id}
                disabled={!isDraft}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, agent_id: e.target.value }))
                }
                className="w-full disabled:cursor-not-allowed disabled:bg-gray-50"
              >
                {agents.length === 0 && <option value="">No agents</option>}
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-gray-500">
                Dataset
              </label>
              <select
                value={form.dataset_id}
                disabled={!isDraft}
                onChange={(e) => {
                  const selected = datasets.find(
                    (d) => String(d.id) === e.target.value
                  )
                  setDataset(selected || null)
                  setForm((prev) => ({ ...prev, dataset_id: e.target.value }))
                }}
                className="w-full disabled:cursor-not-allowed disabled:bg-gray-50"
              >
                {datasets.length === 0 && <option value="">No datasets</option>}
                {datasets.map((d) => (
                  <option key={d.id} value={String(d.id)}>
                    {d.name} ({d.row_count} rows)
                  </option>
                ))}
              </select>

              {isDraft && (
                <div className="mt-3 flex items-center gap-3">
                  <input
                    id="job-upload-dataset"
                    type="file"
                    accept=".csv,.json"
                    className="hidden"
                    onChange={handleDatasetUpload}
                  />
                  <button
                    type="button"
                    onClick={() =>
                      document.getElementById('job-upload-dataset')?.click()
                    }
                    className="flex items-center gap-2 rounded-lg border border-dashed border-gray-300 px-4 py-2 text-[12px] text-gray-600 transition-all hover:border-indigo-400 hover:bg-indigo-50"
                  >
                    {uploading ? (
                      <>
                        <Loader2 size={13} className="animate-spin" />
                        Uploading…
                      </>
                    ) : (
                      <>
                        <Upload size={13} />
                        Upload dataset
                      </>
                    )}
                  </button>
                  <span className="text-[12px] text-gray-500">CSV or JSON</span>
                </div>
              )}
            </div>

            <div>
              <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-gray-500">
                Framework
              </label>
              <select
                value={form.framework}
                disabled={!isDraft}
                onChange={(e) => {
                  const fw = e.target.value
                  setForm((prev) => ({
                    ...prev,
                    framework: fw,
                    metrics: FRAMEWORK_METRICS[fw] || [],
                  }))
                }}
                className="w-full disabled:cursor-not-allowed disabled:bg-gray-50"
              >
                {FRAMEWORKS.map((fw) => (
                  <option key={fw.id} value={fw.id}>
                    {fw.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-[11px] font-medium uppercase tracking-wide text-gray-500">
                Metrics
              </label>
              {frameworkMetrics.length === 0 ? (
                <p className="text-[13px] text-gray-500">Select a framework to see metrics.</p>
              ) : (
                <div className="space-y-2">
                  {frameworkMetrics.map((metric) => (
                    <label
                      key={metric}
                      className={`flex items-center gap-2 text-[13px] text-gray-700 ${
                        !isDraft ? 'opacity-60' : ''
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={form.metrics.includes(metric)}
                        disabled={!isDraft}
                        onChange={() => toggleMetric(metric)}
                      />
                      {metricLabel(metric)}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Card>

       
        <Card>
  <CardHeader title="Execution" />

  <div className="flex h-full min-h-[360px] flex-col justify-between px-3 pb-3">

    {/* TOP CONTENT */}

    <div>

      {/* STATUS */}

      <div className="mb-2">
        {statusBadge}
      </div>

      {/* CONFIG CARD */}

      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">

        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          Current configuration
        </div>

        <div className="space-y-2 text-[12px]">

          {/* AGENT */}

          <div className="flex items-center justify-between gap-3">
            <span className="text-gray-500">
              Agent
            </span>

            <span className="truncate font-medium text-gray-900">
              {agent?.name || '—'}
            </span>
          </div>

          {/* DATASET */}

          <div className="flex items-center justify-between gap-3">
            <span className="text-gray-500">
              Dataset
            </span>

            <span className="truncate font-medium text-gray-900">
              {dataset?.name || '—'}
            </span>
          </div>

          {/* FRAMEWORK */}

          <div className="flex items-center justify-between gap-3">
            <span className="text-gray-500">
              Framework
            </span>

            <span className="font-medium text-gray-900">
              {frameworkLabel(form.framework)}
            </span>
          </div>

          {/* METRICS */}

          <div>

            <div className="mb-2 text-gray-500">
              Metrics
            </div>

            <div className="grid grid-cols-2 gap-1.5">

              {form.metrics.length === 0 ? (
                <span className="text-gray-400">
                  None selected
                </span>
              ) : (
                form.metrics.map((m) => (
                  <span
                    key={m}
                    className="
                    inline-flex
                    w-fit
                    rounded-full
                    bg-indigo-100
                    px-2
                    py-0.5
                    text-[11px]
                    font-medium
                    text-indigo-700
                  "
                  >
                    {metricLabel(m)}
                  </span>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>

    {/* FIXED BUTTON SECTION */}

    <div className="mb-2 mt-2 flex items-center justify-between border-t border-gray-100 pt-1">

      {isDraft ? (
        <>

          {/* SAVE */}

          <Btn
            disabled={saving}
            onClick={handleSave}
            style={{
              padding: '7px 12px',
              fontSize: 12,
            }}
          >
            {saving ? (
              <>
                <Loader2
                  size={12}
                  className="animate-spin"
                />
                Saving...
              </>
            ) : (
              <>
                <Save size={12} />
                Save
              </>
            )}
          </Btn>

          {/* RUN */}

          <Btn
            primary
            disabled={
              running ||
              !form.metrics.length
            }
            onClick={handleRun}
            style={{
              padding: '7px 14px',
              fontSize: 12,
            }}
          >
            {running ? (
              <>
                <Loader2
                  size={12}
                  className="animate-spin"
                />
                Running...
              </>
            ) : (
              <>
                <Play size={12} />
                Run Evaluation
              </>
            )}
          </Btn>
        </>
      ) : (
        <>
          <div />

          {(job.status === 'failed' ||
            job.status === 'queued') && (
            <Btn
              disabled={running}
              onClick={handleRetry}
              style={{
                padding: '7px 12px',
                fontSize: 12,
              }}
            >
              <RotateCcw size={12} />
              Retry
            </Btn>
          )}
        </>
      )}
    </div>
  </div>

        </Card>
      </div>

      {job.status !== 'draft' && (
        <Card>
          <CardHeader title="Traces & results" />
          {resultRows.length === 0 ? (
            <div className="px-4 pb-4 text-[12px] text-gray-500">
              {job.status === 'running' || job.status === 'queued' ? (
                <span className="flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin" />
                  Evaluation in progress…
                </span>
              ) : (
                'No results yet.'
              )}
            </div>
          ) : (
            <Table className="text-[12px]">
              <THead>
                <Th>#</Th>
                <Th>Input</Th>
                <Th>Output</Th>
                <Th>Latency</Th>
                <Th>Result</Th>
              </THead>
              <tbody>
                {resultRows.map((row) => (
                  <TRow key={row.id}>
                    <Td>{row.sample_index + 1}</Td>
                    <Td style={{ maxWidth: 220 }} className="truncate">
                      {row.input}
                    </Td>
                    <Td style={{ maxWidth: 260 }} className="truncate">
                      {row.actual_output || row.scores?.invocation_error || '—'}
                    </Td>
                    <Td>{formatLatencyMs(row.latency_ms)}</Td>
                    <Td>
                      {samplePassed(row.scores) ? (
                        <Badge variant="green">Pass</Badge>
                      ) : (
                        <Badge variant="red">Fail</Badge>
                      )}
                    </Td>
                  </TRow>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      )}
    </div>
  )
}
