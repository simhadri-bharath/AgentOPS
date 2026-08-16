import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Loader2,
  Shield,
  Zap,
  Settings2,
  Check,
  AlertTriangle,
} from 'lucide-react'
import { Card, CardHeader } from '../../components/Card'
import Btn from '../../components/Btn'
import PageHeader from '../../components/PageHeader'
import { useAgents } from '../../context/AgentsContext'
import * as redteamApi from '../../api/redteam'

const JUDGE_MODELS = [
  'gemini-2.5-flash',
  'gemini-2.5-pro',
  'gemini-2.0-flash',
  'gemini-2.0-flash-lite',
  'gemini-1.5-pro',
  'gemini-1.5-flash',
]

export function caseKey(tc) {
  return tc.external_id || String(tc.id)
}

// ─── Stepper Component ────────────────────────────────────────────────
function Stepper({ steps, current }) {
  return (
    <div className="flex items-center justify-center gap-0 mb-6">
      {steps.map((s, i) => {
        const done = i < current
        const active = i === current
        return (
          <React.Fragment key={i}>
            {i > 0 && (
              <div
                className="h-[2px] flex-1 max-w-[60px]"
                style={{ background: done ? '#6366F1' : '#E5E7EB' }}
              />
            )}
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold"
                style={{
                  background: done ? '#6366F1' : active ? '#6366F1' : '#E5E7EB',
                  color: done || active ? '#fff' : '#9CA3AF',
                }}
              >
                {done ? <Check size={12} /> : i + 1}
              </div>
              <span
                className="text-[11px] font-medium uppercase tracking-wide"
                style={{ color: active ? '#6366F1' : done ? '#374151' : '#9CA3AF' }}
              >
                {s}
              </span>
            </div>
          </React.Fragment>
        )
      })}
    </div>
  )
}

// ─── Main Wizard Component ────────────────────────────────────────────
export default function RedTeamScan() {
  const nav = useNavigate()
  const { selectableAgents } = useAgents()

  // Wizard state
  const [step, setStep] = useState(0)
  // A standards preset replaces choosing from 37 vulnerabilities and 28
  // attacks by hand. DeepTeam maps the standard to both itself.
  const [framework, setFramework] = useState('')
  const [agentId, setAgentId] = useState('')
  const [scanMode, setScanMode] = useState('') // 'custom' | 'dynamic'
  const [judgeModel, setJudgeModel] = useState('gemini-2.5-pro')

  // Dynamic mode state
  const [targetPurpose, setTargetPurpose] = useState('')
  const [targetSystemPrompt, setTargetSystemPrompt] = useState('')
  const [selectedVulns, setSelectedVulns] = useState(new Set())
  const [vulnSubTypes, setVulnSubTypes] = useState({}) // { vulnId: [...selectedTypes] }
  const [selectedAttacks, setSelectedAttacks] = useState(new Set())
  const [expandedVulnCats, setExpandedVulnCats] = useState({})

  // Custom mode state
  const [categories, setCategories] = useState(redteamApi.REDTEAM_CATEGORIES.map((c) => c.id))
  const [expandedCats, setExpandedCats] = useState({})
  const [selectedCaseIds, setSelectedCaseIds] = useState(() => new Set())
  const [useLlmJudge, setUseLlmJudge] = useState(true)

  // Queries
  const { data: agentMeta, isLoading: metaLoading } = useQuery({
    queryKey: ['redteam', 'agent-metadata', agentId],
    queryFn: () => redteamApi.fetchAgentMetadata(agentId),
    enabled: !!agentId && scanMode === 'dynamic',
  })

  const { data: vulnsData, isLoading: vulnsLoading } = useQuery({
    queryKey: ['redteam', 'deepteam-vulns'],
    queryFn: redteamApi.fetchDeepTeamVulnerabilities,
    enabled: scanMode === 'dynamic',
  })

  const { data: frameworksData } = useQuery({
    queryKey: ['redteam', 'deepteam-frameworks'],
    queryFn: redteamApi.fetchDeepTeamFrameworks,
  })

  const { data: attacksData, isLoading: attacksLoading } = useQuery({
    queryKey: ['redteam', 'deepteam-attacks'],
    queryFn: redteamApi.fetchDeepTeamAttacks,
    enabled: scanMode === 'dynamic',
  })

  const { data: testCasesData, isLoading: casesLoading } = useQuery({
    queryKey: ['redteam', 'test-cases', 'scan'],
    queryFn: () => redteamApi.fetchTestCases({ source: 'all', limit: 500 }),
    enabled: scanMode === 'custom',
  })

  const allCases = testCasesData?.items || []

  // Auto-fill metadata when loaded
  useEffect(() => {
    if (agentMeta) {
      setTargetPurpose(agentMeta.target_purpose || '')
      setTargetSystemPrompt(agentMeta.system_prompt || '')
    }
  }, [agentMeta])

  // Auto-select all vulnerabilities when catalog loads
  useEffect(() => {
    if (vulnsData?.vulnerabilities && selectedVulns.size === 0) {
      setSelectedVulns(new Set(vulnsData.vulnerabilities.map((v) => v.id)))
    }
  }, [vulnsData])

  // Auto-select all attacks when catalog loads
  useEffect(() => {
    if (attacksData?.attacks && selectedAttacks.size === 0) {
      setSelectedAttacks(new Set(attacksData.attacks.map((a) => a.id)))
    }
  }, [attacksData])

  // Custom mode helpers
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
      const bucket = (casesByCategory[categoryId] || []).filter(() =>
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

  // Mutation
  const mutation = useMutation({
    mutationFn: redteamApi.startRedTeamRun,
    onSuccess: (data) => {
      nav(`/red-team/runs/${data.run_id}`)
    },
  })

  const launchCustom = () => {
    const ids = allCases
      .filter((tc) => categories.includes(tc.category) && selectedCaseIds.has(caseKey(tc)))
      .map(caseKey)
    mutation.mutate({
      agent_id: agentId,
      scan_mode: 'custom',
      categories,
      judge_model: judgeModel,
      use_llm_judge: useLlmJudge,
      selected_case_ids: ids,
    })
  }

  const launchDynamic = () => {
    const vulns = (vulnsData?.vulnerabilities || [])
      .filter((v) => selectedVulns.has(v.id))
      .map((v) => ({
        name: v.id,
        types: vulnSubTypes[v.id] || [],
      }))
    const attacks = (attacksData?.attacks || [])
      .filter((a) => selectedAttacks.has(a.id))
      .map((a) => ({
        name: a.id,
        weight: 1,
      }))
    mutation.mutate({
      agent_id: agentId,
      scan_mode: 'dynamic',
      judge_model: judgeModel,
      target_purpose: targetPurpose,
      target_system_prompt: targetSystemPrompt,
      framework: framework || null,
      vulnerabilities: framework ? [] : vulns,
      attacks: framework ? [] : attacks,
    })
  }

  const selectedAgent = selectableAgents.find((a) => a.id === agentId)

  // ─── Step definitions ───────────────────────────────────────────────
  const dynamicSteps = framework
    ? ['Agent', 'Scan Mode', 'Metadata', 'Launch']
    : ['Agent', 'Scan Mode', 'Metadata', 'Vulnerabilities', 'Enhancements', 'Launch']
  const customSteps = ['Agent', 'Scan Mode', 'Configure', 'Launch']
  const activeSteps = scanMode === 'dynamic' ? dynamicSteps : scanMode === 'custom' ? customSteps : ['Agent', 'Scan Mode']

  return (
    <div>
      <PageHeader
        title="Dynamic AI Security Scanning"
        subtitle="Configure and execute real-time adversarial simulations against your agents"
      />

      {mutation.error && (
        <div className="mb-4 px-3 py-2 rounded-md text-[12px] bg-red-50 text-red-800">
          {mutation.error.message}
        </div>
      )}

      <Card>
        <div className="p-5">
          <Stepper steps={activeSteps} current={step} />

          {/* ────── Step 0: Agent Selection ────── */}
          {step === 0 && (
            <div className="max-w-xl mx-auto">
              <h3 className="text-[15px] font-semibold text-indigo-600 mb-1">
                Step 1: Select Target Agent
              </h3>
              <p className="text-[12px] text-gray-500 mb-4">
                Select one of the discovered Reasoning Engines deployed on Google Vertex AI.
              </p>
              <label className="block text-[11px] font-medium text-gray-500 uppercase mb-1">
                Target Agent
              </label>
              <select
                style={{ width: '100%' }}
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
              >
                <option value="">Select agent…</option>
                {selectableAgents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.display_name || a.name} ({a.metadata?.region || a.region || 'us-central1'})
                  </option>
                ))}
              </select>
              <div className="flex justify-end mt-6">
                <Btn primary disabled={!agentId} onClick={() => setStep(1)}>
                  Next <ChevronRight size={14} />
                </Btn>
              </div>
            </div>
          )}

          {/* ────── Step 1: Scan Mode Selection ────── */}
          {step === 1 && (
            <div className="max-w-xl mx-auto">
              <h3 className="text-[15px] font-semibold text-indigo-600 mb-1">
                Step 2: Select Scanning Methodology
              </h3>
              <p className="text-[12px] text-gray-500 mb-4">
                Attacks can be generated for this specific agent, or replayed from a
                fixed library. Generated attacks are what most people mean by red teaming.
              </p>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {/* Custom Mode Card */}
                <div
                  onClick={() => setScanMode('custom')}
                  className="cursor-pointer rounded-lg p-4 transition-all"
                  style={{
                    border: scanMode === 'custom' ? '2px solid #6366F1' : '1px solid #E5E7EB',
                    background: scanMode === 'custom' ? '#EEF2FF' : '#FFFFFF',
                  }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Settings2 size={16} className="text-gray-700" />
                    <span className="text-[13px] font-semibold text-gray-900">
                      Fixed attack library
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-500">
                    Replays the same 40 stored prompts every time. Fast, cheap and
                    repeatable — good for regression, but it does not adapt to this
                    agent.
                  </p>
                </div>
                {/* Dynamic Mode Card */}
                <div
                  onClick={() => setScanMode('dynamic')}
                  className="cursor-pointer rounded-lg p-4 transition-all"
                  style={{
                    border: scanMode === 'dynamic' ? '2px solid #6366F1' : '1px solid #E5E7EB',
                    background: scanMode === 'dynamic' ? '#EEF2FF' : '#FFFFFF',
                  }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Zap size={16} className="text-indigo-600" />
                    <span className="text-[13px] font-semibold text-gray-900">
                      Generated attacks
                    </span>
                    <span
                      className="text-[9px] font-bold px-1.5 py-0.5 rounded"
                      style={{ background: '#6366F1', color: '#fff' }}
                    >
                      RECOMMENDED
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-500">
                    DeepTeam writes fresh attacks aimed at this agent&apos;s stated purpose,
                    for the vulnerabilities you pick, and judges each response. Slower
                    and costs more per scan.
                  </p>
                </div>
              </div>

              <label className="block text-[11px] font-medium text-gray-500 uppercase mb-1">
                Judge & Simulator Model
              </label>
              <select
                style={{ width: '100%' }}
                value={judgeModel}
                onChange={(e) => setJudgeModel(e.target.value)}
              >
                {JUDGE_MODELS.map((m) => (
                  <option key={m} value={m}>
                    {m} {m === 'gemini-2.5-pro' ? '(Recommended)' : ''}
                  </option>
                ))}
              </select>

              <div className="flex justify-between mt-6">
                <Btn onClick={() => setStep(0)}>
                  <ChevronLeft size={14} /> Back
                </Btn>
                <Btn primary disabled={!scanMode} onClick={() => setStep(2)}>
                  Next <ChevronRight size={14} />
                </Btn>
              </div>
            </div>
          )}

          {/* ────── Step 2 (Dynamic): Metadata Preview ────── */}
          {step === 2 && scanMode === 'dynamic' && (
            <div className="max-w-xl mx-auto">
              <h3 className="text-[15px] font-semibold text-indigo-600 mb-1">
                Step 3: Agent Specifications Preview
              </h3>
              <p className="text-[12px] text-gray-500 mb-4">
                The platform automatically connects to Vertex AI to extract deployment metadata, tools
                description, and construct the agent context.
              </p>

              {metaLoading ? (
                <div className="flex items-center gap-2 py-8 justify-center text-gray-500 text-[12px]">
                  <Loader2 size={16} className="animate-spin" /> Fetching metadata from GCP…
                </div>
              ) : (
                <div className="space-y-3">
                  <div>
                    <label className="block text-[11px] font-medium text-gray-500 uppercase mb-1">
                      Auto-loaded Agent Description
                    </label>
                    <input
                      type="text"
                      className="w-full text-[12px] px-3 py-2 rounded-md"
                      style={{ border: '1px solid #D1D5DB', background: '#F9FAFB' }}
                      value={agentMeta?.description || ''}
                      readOnly
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-gray-500 uppercase mb-1">
                      Generated Target Purpose
                    </label>
                    <textarea
                      className="w-full text-[12px] px-3 py-2 rounded-md"
                      style={{ border: '1px solid #D1D5DB', minHeight: '60px' }}
                      value={targetPurpose}
                      onChange={(e) => setTargetPurpose(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-gray-500 uppercase mb-1">
                      Inferred Target System Prompt
                    </label>
                    <textarea
                      className="w-full text-[12px] px-3 py-2 rounded-md"
                      style={{ border: '1px solid #D1D5DB', minHeight: '60px' }}
                      value={targetSystemPrompt}
                      onChange={(e) => setTargetSystemPrompt(e.target.value)}
                    />
                  </div>
                  {agentMeta?.a2a_card && (
                    <div className="mt-3">
                      <details className="text-[12px] bg-gray-50 border border-gray-200 rounded-md p-2">
                        <summary className="font-semibold text-gray-700 cursor-pointer select-none">
                          View Fetched A2A Card Details
                        </summary>
                        <pre className="mt-2 text-[10px] text-gray-600 overflow-x-auto bg-white p-2 rounded border border-gray-100 max-h-48 font-mono">
                          {JSON.stringify(agentMeta.a2a_card, null, 2)}
                        </pre>
                      </details>
                    </div>
                  )}
                </div>
              )}

              <div className="flex justify-between mt-6">
                <Btn onClick={() => setStep(1)}>
                  <ChevronLeft size={14} /> Back
                </Btn>
                <Btn primary onClick={() => setStep(3)}>
                  Next <ChevronRight size={14} />
                </Btn>
              </div>
            </div>
          )}

          {/* ────── Step 2 (Custom): Custom Scan Config ────── */}
          {step === 2 && scanMode === 'custom' && (
            <div className="max-w-2xl mx-auto">
              <h3 className="text-[15px] font-semibold text-indigo-600 mb-1">
                Step 3: Configure Custom Scan
              </h3>
              <p className="text-[12px] text-gray-500 mb-4">
                Select attack categories, specific prompts, and judge model.
              </p>

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
                        >
                          {enabled && expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
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
                          <button type="button" className="text-[10px] text-indigo-600" onClick={() => syncSelectionForCategory(c.id, true)}>Select all</button>
                          <button type="button" className="text-[10px] text-gray-500" onClick={() => syncSelectionForCategory(c.id, false)}>Clear</button>
                        </div>
                        {bucket.map((tc) => {
                          const key = caseKey(tc)
                          return (
                            <label key={key} className="flex items-start gap-2 py-1.5 cursor-pointer hover:bg-gray-50 rounded px-1">
                              <input type="checkbox" checked={selectedCaseIds.has(key)} onChange={(e) => togglePrompt(key, e)} className="mt-0.5" />
                              <span className="flex-1 min-w-0">
                                <span className="text-[10px] text-gray-400 font-mono">{key}</span>
                                <span className="block text-[11px] text-gray-800 truncate" title={tc.prompt}>{tc.prompt}</span>
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

              <label className="flex items-center gap-2 text-[12px] cursor-pointer mt-3">
                <input type="checkbox" checked={useLlmJudge} onChange={(e) => setUseLlmJudge(e.target.checked)} />
                Use LLM judge fallback when rules are uncertain
              </label>

              <div className="flex justify-between mt-6">
                <Btn onClick={() => setStep(1)}>
                  <ChevronLeft size={14} /> Back
                </Btn>
                <Btn primary onClick={() => setStep(3)}>
                  Next <ChevronRight size={14} />
                </Btn>
              </div>
            </div>
          )}

          {/* ────── Step 3 (Dynamic): Vulnerability Selection ────── */}
          {step === 3 && scanMode === 'dynamic' && (
            <div className="max-w-2xl mx-auto">
              <h3 className="text-[15px] font-semibold text-indigo-600 mb-1">
                Step 4: Select Vulnerabilities
              </h3>
              <div className="mb-4 p-3 rounded-lg border" style={{ borderColor: '#C7D2FE', background: '#EEF2FF' }}>
                <label className="block text-[12px] font-medium text-gray-800 mb-1">
                  Scan against a standard (recommended)
                </label>
                <select
                  className="w-full mb-1"
                  value={framework}
                  onChange={(e) => setFramework(e.target.value)}
                >
                  <option value="">Choose vulnerabilities manually</option>
                  {(frameworksData?.frameworks || []).map((f) => (
                    <option key={f.name} value={f.name}>
                      {f.label}
                    </option>
                  ))}
                </select>
                <div className="text-[11px] text-gray-500">
                  {framework
                    ? 'DeepTeam derives the vulnerabilities and attacks for this standard. The manual lists below are skipped.'
                    : `${(vulnsData?.vulnerabilities || []).length} vulnerabilities and ${(attacksData?.attacks || []).length} attacks available. Picking a standard is usually faster.`}
                </div>
              </div>

              <p className="text-[12px] text-gray-500 mb-4">
                Choose which vulnerability categories DeepTeam should test against your agent.
              </p>

              {vulnsLoading ? (
                <div className="flex items-center gap-2 py-8 justify-center text-gray-500 text-[12px]">
                  <Loader2 size={16} className="animate-spin" /> Loading vulnerability catalog…
                </div>
              ) : (
                <div className="space-y-2">
                  {Object.entries(vulnsData?.grouped || {}).map(([catName, vulns]) => {
                    const catExpanded = expandedVulnCats[catName]
                    const allSelected = vulns.every((v) => selectedVulns.has(v.id))
                    const someSelected = vulns.some((v) => selectedVulns.has(v.id))
                    return (
                      <div key={catName} className="rounded-md text-[12px]" style={{ border: '1px solid #E5E7EB' }}>
                        <div
                          className="flex items-center justify-between px-3 py-2.5 cursor-pointer"
                          onClick={() => setExpandedVulnCats((p) => ({ ...p, [catName]: !p[catName] }))}
                        >
                          <div className="flex items-center gap-2">
                            {catExpanded ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
                            <span className="font-semibold text-gray-800">{catName}</span>
                            <span className="text-[10px] text-gray-400">
                              {vulns.filter((v) => selectedVulns.has(v.id)).length}/{vulns.length}
                            </span>
                          </div>
                          <input
                            type="checkbox"
                            checked={allSelected}
                            ref={(el) => { if (el) el.indeterminate = someSelected && !allSelected }}
                            onChange={() => {
                              setSelectedVulns((prev) => {
                                const next = new Set(prev)
                                if (allSelected) vulns.forEach((v) => next.delete(v.id))
                                else vulns.forEach((v) => next.add(v.id))
                                return next
                              })
                            }}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>
                        {catExpanded && (
                          <div className="border-t px-3 py-2 space-y-0" style={{ borderColor: '#E5E7EB' }}>
                            {vulns.map((v) => {
                              const isSelected = selectedVulns.has(v.id)
                              const hasSubTypes = v.sub_types && v.sub_types.length > 0
                              const activeSubTypes = vulnSubTypes[v.id] || []
                              return (
                                <div key={v.id}>
                                  <label className="flex items-start gap-2 py-1.5 cursor-pointer hover:bg-gray-50 rounded px-1">
                                    <input
                                      type="checkbox"
                                      className="mt-0.5"
                                      checked={isSelected}
                                      onChange={() => {
                                        setSelectedVulns((prev) => {
                                          const next = new Set(prev)
                                          if (next.has(v.id)) next.delete(v.id)
                                          else next.add(v.id)
                                          return next
                                        })
                                        // Clear sub-type selection when deselecting
                                        if (isSelected) {
                                          setVulnSubTypes((prev) => {
                                            const next = { ...prev }
                                            delete next[v.id]
                                            return next
                                          })
                                        }
                                      }}
                                    />
                                    <div className="flex-1">
                                      <span className="font-medium text-gray-900">{v.label}</span>
                                      <span className="block text-[11px] text-gray-500">{v.description}</span>
                                    </div>
                                  </label>
                                  {/* Sub-type pill toggles */}
                                  {isSelected && hasSubTypes && (
                                    <div className="ml-7 mb-2 mt-0.5">
                                      <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">
                                        Sub-types ({activeSubTypes.length > 0 ? `${activeSubTypes.length} selected` : 'none — all tested'})
                                      </span>
                                      <div className="flex flex-wrap gap-1.5 mt-1">
                                        {v.sub_types.map((st) => {
                                          const isActive = activeSubTypes.includes(st)
                                          return (
                                            <button
                                              key={st}
                                              type="button"
                                              onClick={(e) => {
                                                e.stopPropagation()
                                                setVulnSubTypes((prev) => {
                                                  const current = prev[v.id] || []
                                                  const updated = isActive
                                                    ? current.filter((s) => s !== st)
                                                    : [...current, st]
                                                  return { ...prev, [v.id]: updated }
                                                })
                                              }}
                                              className="transition-all duration-150"
                                              style={{
                                                display: 'inline-flex',
                                                alignItems: 'center',
                                                padding: '3px 10px',
                                                borderRadius: '999px',
                                                fontSize: '11px',
                                                fontWeight: 500,
                                                cursor: 'pointer',
                                                border: isActive ? '1.5px solid #6366F1' : '1px solid #D1D5DB',
                                                background: isActive ? '#6366F1' : '#FFFFFF',
                                                color: isActive ? '#FFFFFF' : '#4B5563',
                                              }}
                                            >
                                              {st}
                                            </button>
                                          )
                                        })}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}

              <p className="text-[11px] text-gray-500 mt-2">
                {selectedVulns.size} vulnerabilit{selectedVulns.size === 1 ? 'y' : 'ies'} selected
              </p>

              <div className="flex justify-between mt-6">
                <Btn onClick={() => setStep(2)}>
                  <ChevronLeft size={14} /> Back
                </Btn>
                <Btn primary disabled={selectedVulns.size === 0} onClick={() => setStep(4)}>
                  Next <ChevronRight size={14} />
                </Btn>
              </div>
            </div>
          )}

          {/* ────── Step 3 (Custom): Launch ────── */}
          {step === 3 && scanMode === 'custom' && (
            <div className="max-w-xl mx-auto">
              <h3 className="text-[15px] font-semibold text-indigo-600 mb-1">
                Step 4: Review & Launch
              </h3>
              <p className="text-[12px] text-gray-500 mb-4">
                Review your custom scan configuration and launch.
              </p>

              <div className="rounded-lg p-4 mb-4" style={{ background: '#F9FAFB', border: '1px solid #E5E7EB' }}>
                <div className="grid grid-cols-2 gap-3 text-[12px]">
                  <div>
                    <span className="text-gray-500">Agent:</span>
                    <span className="ml-2 font-medium">{selectedAgent?.display_name || selectedAgent?.name}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Mode:</span>
                    <span className="ml-2 font-medium">Custom (Heuristic)</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Categories:</span>
                    <span className="ml-2 font-medium">{categories.length}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Test prompts:</span>
                    <span className="ml-2 font-medium">{selectedTotal}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Judge model:</span>
                    <span className="ml-2 font-medium">{judgeModel}</span>
                  </div>
                </div>
              </div>

              <div className="flex justify-between mt-6">
                <Btn onClick={() => setStep(2)}>
                  <ChevronLeft size={14} /> Back
                </Btn>
                <Btn
                  primary
                  style={{ padding: '10px 24px' }}
                  disabled={mutation.isPending || selectedTotal === 0}
                  onClick={launchCustom}
                >
                  {mutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Shield size={13} />}
                  Launch Custom Scan ({selectedTotal} tests)
                </Btn>
              </div>
            </div>
          )}

          {/* ────── Step 4 (Dynamic): Attack Enhancements ────── */}
          {step === 4 && scanMode === 'dynamic' && (
            <div className="max-w-2xl mx-auto">
              <h3 className="text-[15px] font-semibold text-indigo-600 mb-1">
                Step 5: Select Attack Enhancements
              </h3>
              <p className="text-[12px] text-gray-500 mb-4">
                Choose adversarial attack strategies that DeepTeam will use to probe your agent.
              </p>

              {attacksLoading ? (
                <div className="flex items-center gap-2 py-8 justify-center text-gray-500 text-[12px]">
                  <Loader2 size={16} className="animate-spin" /> Loading attack strategies…
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Single-Turn */}
                  <div>
                    <h4 className="text-[12px] font-semibold text-gray-700 mb-2 uppercase tracking-wide">
                      Single-Turn Attacks
                    </h4>
                    <div className="space-y-1">
                      {(attacksData?.single_turn || []).map((a) => (
                        <label
                          key={a.id}
                          className="flex items-start gap-2 py-2 px-3 cursor-pointer hover:bg-gray-50 rounded-md text-[12px]"
                          style={{ border: '1px solid #E5E7EB' }}
                        >
                          <input
                            type="checkbox"
                            className="mt-0.5"
                            checked={selectedAttacks.has(a.id)}
                            onChange={() => {
                              setSelectedAttacks((prev) => {
                                const next = new Set(prev)
                                if (next.has(a.id)) next.delete(a.id)
                                else next.add(a.id)
                                return next
                              })
                            }}
                          />
                          <div className="flex-1">
                            <span className="font-medium text-gray-900">{a.label}</span>
                            <span className="block text-[11px] text-gray-500">{a.description}</span>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Multi-Turn */}
                  <div>
                    <h4 className="text-[12px] font-semibold text-gray-700 mb-2 uppercase tracking-wide">
                      Multi-Turn Attacks
                    </h4>
                    <div className="space-y-1">
                      {(attacksData?.multi_turn || []).map((a) => (
                        <label
                          key={a.id}
                          className="flex items-start gap-2 py-2 px-3 cursor-pointer hover:bg-gray-50 rounded-md text-[12px]"
                          style={{ border: '1px solid #E5E7EB' }}
                        >
                          <input
                            type="checkbox"
                            className="mt-0.5"
                            checked={selectedAttacks.has(a.id)}
                            onChange={() => {
                              setSelectedAttacks((prev) => {
                                const next = new Set(prev)
                                if (next.has(a.id)) next.delete(a.id)
                                else next.add(a.id)
                                return next
                              })
                            }}
                          />
                          <div className="flex-1">
                            <span className="font-medium text-gray-900">{a.label}</span>
                            <span className="block text-[11px] text-gray-500">{a.description}</span>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              <p className="text-[11px] text-gray-500 mt-2">
                {selectedAttacks.size} attack{selectedAttacks.size === 1 ? '' : 's'} selected
              </p>

              <div className="flex justify-between mt-6">
                <Btn onClick={() => setStep(3)}>
                  <ChevronLeft size={14} /> Back
                </Btn>
                <Btn primary disabled={selectedAttacks.size === 0} onClick={() => setStep(5)}>
                  Next <ChevronRight size={14} />
                </Btn>
              </div>
            </div>
          )}

          {/* ────── Step 5 (Dynamic): Review & Launch ────── */}
          {step === 5 && scanMode === 'dynamic' && (
            <div className="max-w-xl mx-auto">
              <h3 className="text-[15px] font-semibold text-indigo-600 mb-1">
                Step 6: Review & Launch
              </h3>
              <p className="text-[12px] text-gray-500 mb-4">
                Review your dynamic scan configuration and launch the DeepTeam adversarial simulation.
              </p>

              <div className="rounded-lg p-4 mb-4 space-y-2" style={{ background: '#F9FAFB', border: '1px solid #E5E7EB' }}>
                <div className="grid grid-cols-2 gap-3 text-[12px]">
                  <div>
                    <span className="text-gray-500">Agent:</span>
                    <span className="ml-2 font-medium">{selectedAgent?.display_name || selectedAgent?.name}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Mode:</span>
                    <span className="ml-2 font-medium">Dynamic (DeepTeam)</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Vulnerabilities:</span>
                    <span className="ml-2 font-medium">{selectedVulns.size}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Attacks:</span>
                    <span className="ml-2 font-medium">{selectedAttacks.size}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Judge model:</span>
                    <span className="ml-2 font-medium">{judgeModel}</span>
                  </div>
                </div>

                <div className="pt-2 border-t text-[12px]" style={{ borderColor: '#E5E7EB' }}>
                  <div className="text-gray-500 mb-1">Target Purpose:</div>
                  <div className="text-gray-800 text-[11px]">{targetPurpose || '—'}</div>
                </div>

                <div className="pt-2 border-t text-[12px]" style={{ borderColor: '#E5E7EB' }}>
                  <div className="text-gray-500 mb-1">Selected Vulnerabilities:</div>
                  <div className="flex flex-wrap gap-1">
                    {[...selectedVulns].map((id) => {
                      const v = (vulnsData?.vulnerabilities || []).find((x) => x.id === id)
                      return (
                        <span key={id} className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
                          {v?.label || id}
                        </span>
                      )
                    })}
                  </div>
                </div>

                <div className="pt-2 border-t text-[12px]" style={{ borderColor: '#E5E7EB' }}>
                  <div className="text-gray-500 mb-1">Selected Attacks:</div>
                  <div className="flex flex-wrap gap-1">
                    {[...selectedAttacks].map((id) => {
                      const a = (attacksData?.attacks || []).find((x) => x.id === id)
                      return (
                        <span key={id} className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">
                          {a?.label || id}
                        </span>
                      )
                    })}
                  </div>
                </div>
              </div>

              <div
                className="flex items-center gap-2 px-3 py-2.5 rounded-md text-[12px] mb-4"
                style={{ background: '#FEF3C7', border: '0.5px solid #FCD34D', color: '#92400E' }}
              >
                <AlertTriangle size={14} className="flex-shrink-0" />
                This scan will send adversarial prompts to your live agent endpoint. Results may take several minutes.
              </div>

              <div className="flex justify-between mt-4">
                <Btn onClick={() => setStep(4)}>
                  <ChevronLeft size={14} /> Back
                </Btn>
                <Btn
                  primary
                  style={{ padding: '10px 24px' }}
                  disabled={mutation.isPending || selectedVulns.size === 0 || selectedAttacks.size === 0}
                  onClick={launchDynamic}
                >
                  {mutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
                  Launch Dynamic Scan
                </Btn>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
