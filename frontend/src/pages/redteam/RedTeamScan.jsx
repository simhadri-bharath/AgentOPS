import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Loader2, Shield } from 'lucide-react'
import { Card, CardHeader } from '../../components/Card'
import Btn from '../../components/Btn'
import PageHeader from '../../components/PageHeader'
import { useAgents } from '../../context/AgentsContext'
import * as redteamApi from '../../api/redteam'

const JUDGE_MODELS = ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-pro', 'gemini-1.5-flash']

export function caseKey(tc) {
  return tc.external_id || String(tc.id)
}

export default function RedTeamScan() {
  const nav = useNavigate()
  const { agents } = useAgents()
  const [agentId, setAgentId] = useState('')
  const [categories, setCategories] = useState(
    redteamApi.REDTEAM_CATEGORIES.map((c) => c.id)
  )
  const [expandedCats, setExpandedCats] = useState({})
  const [selectedCaseIds, setSelectedCaseIds] = useState(() => new Set())
  const [judgeModel, setJudgeModel] = useState('gemini-2.5-flash')
  const [useLlmJudge, setUseLlmJudge] = useState(true)

  const { data: testCasesData, isLoading: casesLoading } = useQuery({
    queryKey: ['redteam', 'test-cases', 'scan'],
    queryFn: () => redteamApi.fetchTestCases({ source: 'all', limit: 500 }),
  })

  const allCases = testCasesData?.items || []

  const casesByCategory = useMemo(() => {
    const map = {}
    for (const tc of allCases) {
      if (!map[tc.category]) map[tc.category] = []
      map[tc.category].push(tc)
    }
    return map
  }, [allCases])

  const syncSelectionForCategory = useCallback(
    (categoryId, selectAll) => {
      const bucket = (casesByCategory[categoryId] || []).filter((tc) =>
        categories.includes(categoryId)
      )
      setSelectedCaseIds((prev) => {
        const next = new Set(prev)
        for (const tc of bucket) {
          const key = caseKey(tc)
          if (selectAll) next.add(key)
          else next.delete(key)
        }
        return next
      })
    },
    [casesByCategory, categories]
  )

  useEffect(() => {
    if (!allCases.length) return
    setSelectedCaseIds((prev) => {
      if (prev.size > 0) return prev
      const next = new Set()
      for (const cat of categories) {
        for (const tc of casesByCategory[cat] || []) {
          next.add(caseKey(tc))
        }
      }
      return next
    })
  }, [allCases.length, casesByCategory, categories])

  const toggleCategory = (id) => {
    const enabling = !categories.includes(id)
    setCategories((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    )
    if (enabling) {
      syncSelectionForCategory(id, true)
      setExpandedCats((e) => ({ ...e, [id]: true }))
    } else {
      syncSelectionForCategory(id, false)
      setExpandedCats((e) => ({ ...e, [id]: false }))
    }
  }

  const togglePrompt = (key, e) => {
    e.stopPropagation()
    setSelectedCaseIds((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const selectedCountForCategory = (catId) =>
    (casesByCategory[catId] || []).filter((tc) => selectedCaseIds.has(caseKey(tc))).length

  const selectedTotal = useMemo(() => {
    let n = 0
    for (const cat of categories) {
      n += selectedCountForCategory(cat)
    }
    return n
  }, [categories, selectedCaseIds, casesByCategory])

  const mutation = useMutation({
    mutationFn: redteamApi.startRedTeamRun,
    onSuccess: (data) => {
      nav(`/red-team/runs/${data.run_id}`)
    },
  })

  const launch = () => {
    const ids = allCases
      .filter((tc) => categories.includes(tc.category) && selectedCaseIds.has(caseKey(tc)))
      .map(caseKey)
    mutation.mutate({
      agent_id: agentId,
      categories,
      judge_model: judgeModel,
      use_llm_judge: useLlmJudge,
      selected_case_ids: ids,
    })
  }

  return (
    <div>
      <PageHeader
        title="Configure security scan"
        subtitle="Select agent, categories, specific attack prompts, and judge model"
      />

      {mutation.error && (
        <div className="mb-4 px-3 py-2 rounded-md text-[12px] bg-red-50 text-red-800">
          {mutation.error.message}
        </div>
      )}

      <Card>
        <CardHeader title="Scan configuration" />
        <div className="p-4 space-y-4 max-w-2xl">
          <div>
            <label className="block text-[11px] font-medium text-gray-500 uppercase mb-1">
              Target agent
            </label>
            <select
              style={{ width: '100%' }}
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
            >
              <option value="">Select agent…</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-gray-500 uppercase mb-1">
              Attack categories & prompts
            </label>
            {casesLoading && (
              <p className="text-[12px] text-gray-500 mb-2 flex items-center gap-1">
                <Loader2 size={12} className="animate-spin" /> Loading attack library…
              </p>
            )}
            {redteamApi.REDTEAM_CATEGORIES.map((c) => {
              const enabled = categories.includes(c.id)
              const bucket = casesByCategory[c.id] || []
              const expanded = expandedCats[c.id]
              const selectedInCat = selectedCountForCategory(c.id)

              return (
                <div
                  key={c.id}
                  className="rounded-md mb-2 text-[12px]"
                  style={{ border: '0.5px solid #E5E7EB' }}
                >
                  <div
                    className="flex items-center justify-between px-3 py-2 cursor-pointer"
                    onClick={() => toggleCategory(c.id)}
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <button
                        type="button"
                        className="text-gray-400 p-0.5"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (!enabled) return
                          setExpandedCats((x) => ({ ...x, [c.id]: !x[c.id] }))
                        }}
                        aria-label={expanded ? 'Collapse' : 'Expand'}
                      >
                        {enabled && expanded ? (
                          <ChevronDown size={14} />
                        ) : (
                          <ChevronRight size={14} />
                        )}
                      </button>
                      <div>
                        <div className="font-medium text-gray-900">{c.label}</div>
                        <div className="text-[11px] text-gray-500">{c.desc}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {enabled && bucket.length > 0 && (
                        <span className="text-[10px] text-gray-500">
                          {selectedInCat}/{bucket.length} prompts
                        </span>
                      )}
                      <input type="checkbox" readOnly checked={enabled} />
                    </div>
                  </div>

                  {enabled && expanded && bucket.length > 0 && (
                    <div
                      className="border-t px-3 py-2 space-y-1 max-h-48 overflow-y-auto"
                      style={{ borderColor: '#E5E7EB' }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex gap-2 mb-2">
                        <button
                          type="button"
                          className="text-[10px] text-indigo-600"
                          onClick={() => syncSelectionForCategory(c.id, true)}
                        >
                          Select all
                        </button>
                        <button
                          type="button"
                          className="text-[10px] text-gray-500"
                          onClick={() => syncSelectionForCategory(c.id, false)}
                        >
                          Clear
                        </button>
                      </div>
                      {bucket.map((tc) => {
                        const key = caseKey(tc)
                        return (
                          <label
                            key={key}
                            className="flex items-start gap-2 py-1.5 cursor-pointer hover:bg-gray-50 rounded px-1"
                          >
                            <input
                              type="checkbox"
                              checked={selectedCaseIds.has(key)}
                              onChange={(e) => togglePrompt(key, e)}
                              className="mt-0.5"
                            />
                            <span className="flex-1 min-w-0">
                              <span className="text-[10px] text-gray-400 font-mono">{key}</span>
                              <span className="block text-[11px] text-gray-800 truncate" title={tc.prompt}>
                                {tc.prompt}
                              </span>
                            </span>
                          </label>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
            <p className="text-[11px] text-gray-500 mt-1">
              {selectedTotal} prompt{selectedTotal !== 1 ? 's' : ''} selected across{' '}
              {categories.length} categor{categories.length === 1 ? 'y' : 'ies'}
            </p>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-gray-500 uppercase mb-1">
              Judge model (DeepEval / Gemini)
            </label>
            <select
              style={{ width: '100%' }}
              value={judgeModel}
              onChange={(e) => setJudgeModel(e.target.value)}
            >
              {JUDGE_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-2 text-[12px] cursor-pointer">
            <input
              type="checkbox"
              checked={useLlmJudge}
              onChange={(e) => setUseLlmJudge(e.target.checked)}
            />
            Use LLM judge fallback when rules are uncertain
          </label>

          <Btn
            primary
            style={{ width: '100%', justifyContent: 'center', padding: '10px' }}
            disabled={
              mutation.isPending ||
              !agentId ||
              categories.length === 0 ||
              selectedTotal === 0
            }
            onClick={launch}
          >
            {mutation.isPending ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Shield size={13} />
            )}
            Launch scan ({selectedTotal} tests)
          </Btn>
        </div>
      </Card>
    </div>
  )
}
