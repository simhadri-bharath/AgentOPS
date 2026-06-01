import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, Loader2, RefreshCw, Upload } from 'lucide-react'
import TabBar from '../TabBar'
import Btn from '../Btn'
import * as datasetsApi from '../../api/datasets'
import { formatRelativeTime } from '../../lib/agentMapper'

const DATASET_TABS = ['Upload file', 'Existing datasets']
const PAGE_SIZE = 3

export default function DatasetStep({ selectedDataset, onSelect }) {
  const [tab, setTab] = useState(0)
  const [datasets, setDatasets] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadName, setUploadName] = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)

  const loadDatasets = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await datasetsApi.fetchDatasets({ limit: 100 })
      setDatasets(data.items || [])
      setTotal(data.total ?? (data.items || []).length)
      setPage(1)
    } catch (err) {
      setError(err.message || 'Failed to load datasets')
      setDatasets([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (tab === 1) loadDatasets()
  }, [tab, loadDatasets])

  const totalPages = Math.max(1, Math.ceil(datasets.length / PAGE_SIZE))

  const paginatedDatasets = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return datasets.slice(start, start + PAGE_SIZE)
  }, [datasets, page])

  useEffect(() => {
    if (page > totalPages) setPage(totalPages)
  }, [page, totalPages])

  const handleTabChange = (nextTab) => {
    setTab(nextTab)
    setError(null)
    if (nextTab === 1) setPage(1)
  }

  const handleUpload = async () => {
    if (!uploadFile) {
      setError('Choose a CSV or JSON file')
      return
    }
    setUploading(true)
    setError(null)
    try {
      const res = await datasetsApi.uploadDataset(uploadFile, {
        name: uploadName || uploadFile.name,
      })
      onSelect(res.dataset)
      setTab(1)
      await loadDatasets()
    } catch (err) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const rangeStart = datasets.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const rangeEnd = Math.min(page * PAGE_SIZE, datasets.length)

  return (
    <div>
      {error && (
        <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-800">
          {error}
        </div>
      )}

      <TabBar tabs={DATASET_TABS} activeTab={tab} onChange={handleTabChange} />

      {tab === 0 && (
        <div className="mt-2">
          <div
            className="flex h-12 cursor-pointer items-center gap-3 rounded-xl border border-dashed border-gray-300 bg-gray-50 px-2 transition-all hover:border-indigo-400 hover:bg-indigo-50"
            onClick={() => document.getElementById('eval-dataset-input')?.click()}
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
            <input
              id="eval-dataset-input"
              type="file"
              accept=".csv,.json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                setUploadFile(f || null)
                if (f && !uploadName) setUploadName(f.name)
              }}
            />
            <Upload size={16} className="text-gray-400" />
            <div className="min-w-0 flex-1">
              {uploadFile ? (
                <div className="truncate text-[13px] font-medium text-gray-800">
                  {uploadFile.name}
                </div>
              ) : (
                <div className="text-[13px] text-gray-500">Upload CSV or JSON dataset</div>
              )}
            </div>
          </div>

          <div className="mt-4 flex items-end justify-between gap-3">
            <div className="w-[320px]">
              <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-[0.04em] text-gray-500">
                Dataset name (optional)
              </label>
              <input
                type="text"
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
                placeholder="e.g. customer-support-eval"
                className="h-11 w-full rounded-xl border border-gray-200 bg-white px-4 text-[14px] outline-none transition-all focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              />
            </div>
            <Btn primary disabled={uploading || !uploadFile} onClick={handleUpload} style={{ height: 44 }}>
              {uploading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Uploading…
                </>
              ) : (
                'Upload & Select'
              )}
            </Btn>
          </div>
        </div>
      )}

      {tab === 1 && (
        <div className="mt-0">
          {loading ? (
            <div className="flex items-center gap-2 py-5 text-[13px] text-gray-500">
              <Loader2 size={16} className="animate-spin" />
              Loading datasets…
            </div>
          ) : datasets.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-200 py-5 text-center">
              <p className="text-[13px] text-gray-500">No datasets yet.</p>
              <Btn style={{ marginTop: 12, fontSize: 12 }} onClick={() => setTab(0)}>
                Upload a dataset
              </Btn>
            </div>
          ) : (
            <>
              <div
                className="overflow-hidden rounded-lg border border-gray-200"
                style={{ borderWidth: '0.5px' }}
              >
                <div className="grid grid-cols-12 border-b border-gray-200 bg-gray-50 px-4 py-2 text-[10px] font-medium uppercase tracking-wide text-gray-500">
  <div className="col-span-1" />
  <div className="col-span-5">Name</div>
  <div className="col-span-2">Format</div>
  <div className="col-span-2">Rows</div>
  <div className="col-span-2">Uploaded</div>
</div>

                <div className="divide-y divide-gray-100">
                  {paginatedDatasets.map((d) => {
                    const selected = String(selectedDataset?.id) === String(d.id)
                    return (
                      <button
                        key={d.id}
                        type="button"
                        onClick={() => onSelect(d)}
                        className={`grid w-full grid-cols-12 items-center px-4 py-1.5 text-left transition-colors ${
                          selected ? 'bg-indigo-50' : 'hover:bg-gray-50'
                        }`}
                      >
                        <div className="col-span-1 flex justify-center">
                          <span
                            className={`flex h-4 w-4 items-center justify-center rounded-full border ${
                              selected
                                ? 'border-indigo-600 bg-indigo-600'
                                : 'border-gray-300 bg-white'
                            }`}
                          >
                            {selected && (
                              <span className="h-1.5 w-1.5 rounded-full bg-white" />
                            )}
                          </span>
                        </div>
                        <div className="col-span-5 min-w-0">
                          <div className="truncate text-[14px] font-medium text-gray-900">
                            {d.name}
                          </div>
                          
                        </div>

                        <div className="col-span-2 text-[12px] text-gray-500 uppercase">
  {d.format}
</div>
                        <div className="col-span-2 text-[12px] text-gray-700">
                          {d.row_count}
                        </div>
                        <div className="col-span-2 text-[12px] text-gray-500">
                          {formatRelativeTime(d.created_at)}
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="mt-2 flex items-center justify-between">

  <div className="text-[12px] text-gray-500">
    Showing {rangeStart}–{rangeEnd} of {total} datasets
  </div>

  <div className="flex items-center gap-2">

    {/* PREVIOUS */}

    <button
      type="button"
      disabled={page === 1}
      onClick={() => setPage((p) => p - 1)}
      className={`
        flex h-8 w-8 items-center justify-center rounded-lg border transition-all
        ${
          page === 1
            ? 'cursor-not-allowed border-gray-100 text-gray-300'
            : 'border-gray-200 text-gray-600 hover:bg-gray-50'
        }
      `}
    >
      <ChevronLeft size={14} />
    </button>

    {/* PAGE */}

    <div className="rounded-lg bg-indigo-600 px-3 py-1.5 text-[11px] font-medium text-white">
      {page} / {totalPages}
    </div>

    {/* NEXT */}

    <button
      type="button"
      disabled={page >= totalPages}
      onClick={() => setPage((p) => p + 1)}
      className={`
        flex h-8 w-8 items-center justify-center rounded-lg border transition-all
        ${
          page >= totalPages
            ? 'cursor-not-allowed border-gray-100 text-gray-300'
            : 'border-gray-200 text-gray-600 hover:bg-gray-50'
        }
      `}
    >
      <ChevronRight size={14} />
    </button>

    {/* REFRESH */}

    <button
      type="button"
      onClick={loadDatasets}
      className="
        flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 text-gray-600 transition-all hover:bg-gray-50
      "
    >
      <RefreshCw size={13} />
    </button>
  </div>
</div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
