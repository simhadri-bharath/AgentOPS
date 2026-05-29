import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Upload, Play, Loader2 } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import TabBar from '../components/TabBar'
import MetricToggle from '../components/MetricToggle'
import Btn from '../components/Btn'
import PageHeader from '../components/PageHeader'
import { useAgents } from '../context/AgentsContext'
import * as datasetsApi from '../api/datasets'
import * as evaluationsApi from '../api/evaluations'

const DATASET_TABS = ['Upload file', 'Past datasets']

export default function Evaluation() {
  const nav = useNavigate()
  const [searchParams] = useSearchParams()
  const { agents, loading: agentsLoading } = useAgents()

  const [selectedAgentId, setSelectedAgentId] = useState(searchParams.get('agentId') || '')
  const [datasetTab, setDatasetTab] = useState(0)
  const [datasets, setDatasets] = useState([])
  const [datasetsLoading, setDatasetsLoading] = useState(false)
  const [selectedDatasetId, setSelectedDatasetId] = useState('')
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadName, setUploadName] = useState('')
  const [metricsOn, setMetricsOn] = useState(() =>
    Object.fromEntries(
      evaluationsApi.SUPPORTED_METRICS.map((m) => [m.id, m.defaultOn])
    )
  )
  const [launching, setLaunching] = useState(false)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    const fromUrl = searchParams.get('agentId')
    if (fromUrl) setSelectedAgentId(fromUrl)
  }, [searchParams])

  const loadDatasets = useCallback(async () => {
    setDatasetsLoading(true)
    try {
      const data = await datasetsApi.fetchDatasets({ limit: 100 })
      setDatasets(data.items || [])
    } catch (err) {
      setError(err.message || 'Failed to load datasets')
    } finally {
      setDatasetsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (datasetTab === 1) loadDatasets()
  }, [datasetTab, loadDatasets])

  const toggleMetric = (id, on) => {
    setMetricsOn((prev) => ({ ...prev, [id]: on }))
  }

  const selectedMetrics = Object.entries(metricsOn)
    .filter(([, on]) => on)
    .map(([id]) => id)

  const resolveDatasetId = async () => {
    if (datasetTab === 1) {
      if (!selectedDatasetId) throw new Error('Select a dataset from the list')
      return selectedDatasetId
    }
    if (!uploadFile) throw new Error('Choose a CSV or JSON file to upload')
    const res = await datasetsApi.uploadDataset(uploadFile, {
      name: uploadName || uploadFile.name,
    })
    return res.dataset.id
  }

  const handleLaunch = async () => {
    setError(null)
    if (!selectedAgentId) {
      setError('Select an agent')
      return
    }
    if (selectedMetrics.length === 0) {
      setError('Select at least one metric')
      return
    }

    setLaunching(true)
    try {
      const datasetId = await resolveDatasetId()
      const queued = await evaluationsApi.startEvaluation({
        agent_id: selectedAgentId,
        dataset_id: datasetId,
        framework: 'vertex_ai',
        metrics: selectedMetrics,
      })
      nav(`/results/${queued.evaluation_id}`)
    } catch (err) {
      setError(err.message || 'Failed to start evaluation')
    } finally {
      setLaunching(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Run evaluation"
        subtitle="Upload a dataset and run Vertex AI Reasoning Engine evals against a deployed agent"
      />

      {error && (
        <div
          className="mb-4 px-3 py-2 rounded-md text-[12px]"
          style={{ background: '#FEF2F2', color: '#991B1B', border: '0.5px solid #FECACA' }}
        >
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 items-start">
        <div>
          <Card className="mb-4">
            <CardHeader title="1 · Select agent" />
            <div className="mb-3">
              <label className="block text-[11px] font-medium text-gray-500 uppercase tracking-[0.04em] mb-1 mt-2">
                Agent
              </label>
              <select
                style={{ width: '100%' }}
                value={selectedAgentId}
                onChange={(e) => setSelectedAgentId(e.target.value)}
                disabled={agentsLoading || agents.length === 0}
              >
                <option value="">
                  {agentsLoading
                    ? 'Loading agents…'
                    : agents.length === 0
                      ? 'No agents — run discovery first'
                      : 'Select an agent'}
                </option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.platform})
                  </option>
                ))}
              </select>
            </div>
          </Card>

          <Card className="mb-4">
            <CardHeader title="2 · Dataset / prompts" />
            <TabBar tabs={DATASET_TABS} activeTab={datasetTab} onChange={setDatasetTab} />

            {datasetTab === 0 && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.json"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    setUploadFile(f || null)
                    if (f && !uploadName) setUploadName(f.name)
                  }}
                />
                <div
                  className="upload-zone cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault()
                    const f = e.dataTransfer.files?.[0]
                    if (f) {
                      setUploadFile(f)
                      if (!uploadName) setUploadName(f.name)
                    }
                  }}
                >
                  <Upload size={28} className="mx-auto mb-2 text-gray-400" />
                  {uploadFile ? (
                    <span className="text-[12px] text-gray-900">{uploadFile.name}</span>
                  ) : (
                    <>Drop a CSV or JSON file here</>
                  )}
                  <span className="block text-[11px] mt-1" style={{ color: '#9CA3AF' }}>
                    Columns: input (required), expected_output, context (optional)
                  </span>
                  <Btn
                    style={{ marginTop: 10, fontSize: 11 }}
                    onClick={(e) => {
                      e.stopPropagation()
                      fileInputRef.current?.click()
                    }}
                  >
                    Browse files
                  </Btn>
                </div>
                <div className="mt-2">
                  <label className="block text-[11px] font-medium text-gray-500 uppercase tracking-[0.04em] mb-1">
                    Dataset name (optional)
                  </label>
                  <input
                    type="text"
                    value={uploadName}
                    onChange={(e) => setUploadName(e.target.value)}
                    placeholder="e.g. travel-planner-prompts"
                    style={{ width: '100%' }}
                  />
                </div>
              </>
            )}

            {datasetTab === 1 && (
              <div>
                {datasetsLoading ? (
                  <div className="flex items-center gap-2 text-[12px] text-gray-500 py-4">
                    <Loader2 size={14} className="animate-spin" />
                    Loading datasets…
                  </div>
                ) : datasets.length === 0 ? (
                  <p className="text-[12px] text-gray-500 py-2">
                    No datasets yet. Upload a file on the first tab.
                  </p>
                ) : (
                  <select
                    style={{ width: '100%' }}
                    value={selectedDatasetId}
                    onChange={(e) => setSelectedDatasetId(e.target.value)}
                  >
                    <option value="">Select a dataset</option>
                    {datasets.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} ({d.row_count} rows · {d.format})
                      </option>
                    ))}
                  </select>
                )}
                <Btn style={{ marginTop: 8, fontSize: 11 }} onClick={loadDatasets}>
                  Refresh list
                </Btn>
              </div>
            )}
          </Card>
        </div>

        <div>
          <Card className="mb-4">
            <CardHeader title="3 · Metrics" />
            {evaluationsApi.SUPPORTED_METRICS.map((m, i) => (
              <MetricToggle
                key={m.id}
                label={m.label}
                checked={metricsOn[m.id]}
                onChange={(on) => toggleMetric(m.id, on)}
                isLast={i === evaluationsApi.SUPPORTED_METRICS.length - 1}
              />
            ))}
            <p className="text-[11px] text-gray-500 mt-2">
              Prompt-only datasets (no expected_output) automatically use response_nonempty,
              response_length, and latency_ms.
            </p>
          </Card>

          <Card className="mb-4">
            <CardHeader title="4 · Framework" />
            <div className="mb-3">
              <label className="block text-[11px] font-medium text-gray-500 uppercase tracking-[0.04em] mb-1 mt-2">
                Evaluation engine
              </label>
              <select style={{ width: '100%' }} value="vertex_ai" disabled>
                <option value="vertex_ai">Vertex AI (Reasoning Engine)</option>
              </select>
            </div>
          </Card>

          <Btn
            primary
            disabled={launching}
            onClick={handleLaunch}
            style={{ width: '100%', justifyContent: 'center', padding: '10px' }}
          >
            {launching ? (
              <>
                <Loader2 size={13} className="animate-spin" />
                Starting…
              </>
            ) : (
              <>
                <Play size={13} />
                Launch evaluation
              </>
            )}
          </Btn>
        </div>
      </div>
    </div>
  )
}
