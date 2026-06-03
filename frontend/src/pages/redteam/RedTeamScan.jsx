import React, { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ChevronRight, ChevronLeft, Loader2, Shield, Settings, Server, Wrench, CheckCircle, Info } from 'lucide-react'
import { Card, CardHeader } from '../../components/Card'
import Btn from '../../components/Btn'
import PageHeader from '../../components/PageHeader'
import { useAgents } from '../../context/AgentsContext'
import * as redteamApi from '../../api/redteam'

export default function RedTeamScan() {
  const nav = useNavigate()
  const { agents } = useAgents()
  
  // Wizard steps: 1 to 6
  const [step, setStep] = useState(1)
  const [agentId, setAgentId] = useState('')
  const [scanMode, setScanMode] = useState('custom') // 'custom' | 'deepeval'
  const [judgeModel, setJudgeModel] = useState('gemini-2.5-pro')
  const [useLlmJudge, setUseLlmJudge] = useState(true)

  // Hydrated metadata states
  const [targetPurpose, setTargetPurpose] = useState('')
  const [targetSystemPrompt, setTargetSystemPrompt] = useState('')

  // Selected vulnerabilities
  const [customCategories, setCustomCategories] = useState(
    redteamApi.REDTEAM_CATEGORIES.map((c) => c.id)
  )
  const [deepevalCategories, setDeepevalCategories] = useState([])

  // Selected attack enhancements and weights
  const [enhancements, setEnhancements] = useState({
    BASE64: { enabled: true, weight: 0.25 },
    MULTILINGUAL: { enabled: true, weight: 0.25 },
    GRAY_BOX_ATTACK: { enabled: true, weight: 0.25 },
    JAILBREAK_CRESCENDO: { enabled: true, weight: 0.25 },
  })

  // Queries
  const { data: agentMeta, isLoading: metaLoading } = useQuery({
    queryKey: ['redteam', 'agent-metadata', agentId],
    queryFn: () => redteamApi.fetchAgentMetadata(agentId),
    enabled: !!agentId,
  })

  const { data: deevevalVulsData, isLoading: deevalVulsLoading } = useQuery({
    queryKey: ['redteam', 'vulnerabilities'],
    queryFn: redteamApi.fetchVulnerabilities,
    enabled: scanMode === 'deepeval',
  })

  const { data: customTestCasesData, isLoading: customCasesLoading } = useQuery({
    queryKey: ['redteam', 'test-cases', 'scan'],
    queryFn: () => redteamApi.fetchTestCases({ source: 'all', limit: 500 }),
    enabled: scanMode === 'custom',
  })

  // Autofill metadata on selection
  useEffect(() => {
    if (agentMeta) {
      setTargetPurpose(agentMeta.target_purpose || '')
      setTargetSystemPrompt(agentMeta.system_prompt || '')
    }
  }, [agentMeta])

  // Autofill deepeval categories once taxonomy finishes loading
  useEffect(() => {
    if (deevevalVulsData?.vulnerabilities) {
      setDeepevalCategories(deevevalVulsData.vulnerabilities.map((v) => v.id))
    }
  }, [deevevalVulsData])

  const selectedAgentObj = useMemo(() => {
    return agents.find((a) => a.id === agentId)
  }, [agents, agentId])

  const handleEnhancementToggle = (key) => {
    setEnhancements((prev) => ({
      ...prev,
      [key]: { ...prev[key], enabled: !prev[key].enabled },
    }))
  }

  const handleWeightChange = (key, val) => {
    setEnhancements((prev) => ({
      ...prev,
      [key]: { ...prev[key], weight: parseFloat(val) },
    }))
  }

  const mutation = useMutation({
    mutationFn: redteamApi.startRedTeamRun,
    onSuccess: (data) => {
      nav(`/red-team/runs/${data.run_id}`)
    },
  })

  const handleLaunch = () => {
    const payload = {
      agent_id: agentId,
      judge_model: judgeModel,
      scan_mode: scanMode,
    }

    if (scanMode === 'deepeval') {
      payload.categories = deepevalCategories
      payload.target_purpose = targetPurpose
      payload.target_system_prompt = targetSystemPrompt
      
      const activeEnhancements = {}
      Object.entries(enhancements).forEach(([key, val]) => {
        if (val.enabled) {
          activeEnhancements[key] = val.weight
        }
      })
      payload.attack_enhancements = activeEnhancements
    } else {
      payload.categories = customCategories
      payload.use_llm_judge = useLlmJudge
      payload.include_custom_cases = true
    }

    mutation.mutate(payload)
  }

  const renderStepIndicator = () => {
    const steps = [
      { num: 1, label: 'Agent' },
      { num: 2, label: 'Scan Mode' },
      { num: 3, label: 'Metadata' },
      { num: 4, label: 'Vulnerabilities' },
      { num: 5, label: 'Enhancements' },
      { num: 6, label: 'Launch' },
    ]

    return (
      <div className="flex items-center justify-between mb-6 px-1 text-[11px] font-medium text-gray-500 uppercase tracking-wider">
        {steps.map((s, idx) => {
          const isCurrent = step === s.num
          const isCompleted = step > s.num
          if (s.num === 5 && scanMode === 'custom') return null // Skip enhancements for custom mode
          return (
            <React.Fragment key={s.num}>
              {idx > 0 && !(s.num === 5 && scanMode === 'custom') && (
                <div className={`h-[1px] flex-1 mx-2 bg-gray-200 ${isCompleted ? 'bg-indigo-600' : ''}`} />
              )}
              <div className="flex items-center gap-1.5">
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] border transition-colors ${
                    isCurrent
                      ? 'border-indigo-600 bg-indigo-600 text-white shadow-sm'
                      : isCompleted
                      ? 'border-indigo-600 bg-indigo-50 text-indigo-600'
                      : 'border-gray-200 bg-white text-gray-400'
                  }`}
                >
                  {isCompleted ? '✓' : s.num}
                </div>
                <span className={isCurrent ? 'text-indigo-600 font-semibold' : 'text-gray-500'}>
                  {s.label}
                </span>
              </div>
            </React.Fragment>
          )
        })}
      </div>
    )
  }

  const nextDisabled = () => {
    if (step === 1) return !agentId
    if (step === 3 && metaLoading) return true
    if (step === 4) {
      if (scanMode === 'custom') return customCategories.length === 0
      return deepevalCategories.length === 0
    }
    return false
  }

  const handleNext = () => {
    if (step === 4 && scanMode === 'custom') {
      setStep(6) // Skip enhancements for custom mode
    } else {
      setStep((s) => s + 1)
    }
  }

  const handlePrev = () => {
    if (step === 6 && scanMode === 'custom') {
      setStep(4) // Skip enhancements for custom mode
    } else {
      setStep((s) => s - 1)
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <PageHeader
        title="Dynamic AI Security Scanning"
        subtitle="Configure and execute real-time adversarial simulations against your agents"
      />

      {mutation.error && (
        <div className="mb-4 px-3 py-2 rounded-md text-[12px] bg-red-50 text-red-800 flex items-center gap-2 border border-red-200">
          <Info size={14} className="text-red-600 flex-shrink-0" />
          <span>{mutation.error.message}</span>
        </div>
      )}

      {renderStepIndicator()}

      <Card className="shadow-lg overflow-hidden border border-gray-150">
        {/* Step 1: Select Agent */}
        {step === 1 && (
          <div className="p-5 space-y-4">
            <CardHeader title="Step 1: Select Target Agent" />
            <p className="text-[12px] text-gray-500">
              Select one of the discovered Reasoning Engines deployed on Google Vertex AI.
            </p>
            <div className="pt-2">
              <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                Target Agent
              </label>
              <select
                className="w-full rounded-md border border-gray-300 p-2 text-[12px] focus:outline-none focus:ring-1 focus:ring-indigo-600 bg-white"
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
              >
                <option value="">Select agent…</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.display_name || a.name} ({a.region})
                  </option>
                ))}
              </select>
            </div>
            {selectedAgentObj && (
              <div className="mt-3 p-3 bg-gray-50 border rounded-md text-[12px] text-gray-600 space-y-1">
                <div><strong>Deployment:</strong> {selectedAgentObj.deployment_type}</div>
                <div><strong>Endpoint:</strong> <code className="text-[10px] bg-gray-100 px-1 py-0.5 rounded">{selectedAgentObj.endpoint_url}</code></div>
                <div><strong>Model:</strong> {selectedAgentObj.model_name || 'gemini-2.5-pro'}</div>
              </div>
            )}
          </div>
        )}

        {/* Step 2: Select Scan Mode */}
        {step === 2 && (
          <div className="p-5 space-y-4">
            <CardHeader title="Step 2: Select Scanning Methodology" />
            <p className="text-[12px] text-gray-500">
              Choose between static heuristic scans and dynamic DeepEval-native scans.
            </p>
            <div className="grid grid-cols-2 gap-4 pt-2">
              <div
                onClick={() => setScanMode('custom')}
                className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                  scanMode === 'custom'
                    ? 'border-indigo-600 bg-indigo-50/50 shadow-sm'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="font-semibold text-[13px] text-gray-900 mb-1">Custom Mode (Heuristic)</div>
                <div className="text-[11px] text-gray-500 leading-relaxed">
                  Executes predefined attack packages from the platform library. Fastest, run-safe, and uses rule-based classifications.
                </div>
              </div>
              <div
                onClick={() => setScanMode('deepeval')}
                className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                  scanMode === 'deepeval'
                    ? 'border-indigo-600 bg-indigo-50/50 shadow-sm'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="font-semibold text-[13px] text-gray-900 mb-1 flex items-center gap-1.5">
                  DeepEval Mode (Dynamic)
                  <span className="bg-indigo-600 text-white text-[9px] px-1 py-0.2 rounded font-bold uppercase">Native</span>
                </div>
                <div className="text-[11px] text-gray-500 leading-relaxed">
                  Generates context-aware, dynamic attacks customized to the agent's prompt and purpose. Performs deep semantic safety evaluations.
                </div>
              </div>
            </div>

            <div className="pt-3 border-t">
              <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
                Judge & Simulator Model
              </label>
              <select
                className="w-full rounded-md border border-gray-300 p-2 text-[12px] focus:outline-none focus:ring-1 focus:ring-indigo-600 bg-white"
                value={judgeModel}
                onChange={(e) => setJudgeModel(e.target.value)}
              >
                <option value="gemini-2.5-pro">gemini-2.5-pro (Recommended)</option>
                <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                <option value="gemini-2.5-flash-lite">gemini-2.5-flash-lite</option>
              </select>
            </div>
          </div>
        )}

        {/* Step 3: Agent Metadata Preview */}
        {step === 3 && (
          <div className="p-5 space-y-4">
            <CardHeader title="Step 3: Agent Specifications Preview" />
            <p className="text-[12px] text-gray-500">
              The platform automatically connects to Vertex AI to extract deployment metadata, tools description, and construct the agent context.
            </p>
            {metaLoading ? (
              <div className="flex flex-col items-center justify-center py-8 text-gray-500 text-[12px] gap-2">
                <Loader2 size={24} className="animate-spin text-indigo-600" />
                <span>Hydrating agent specifications…</span>
              </div>
            ) : (
              <div className="space-y-3 pt-2">
                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
                    Auto-Loaded Agent Description
                  </label>
                  <div className="p-2.5 bg-gray-50 rounded border text-[12px] text-gray-700 font-mono">
                    {agentMeta?.description || 'No description provided by the Reasoning Engine.'}
                  </div>
                </div>

                {scanMode === 'deepeval' && (
                  <>
                    <div>
                      <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
                        Generated Target Purpose
                      </label>
                      <textarea
                        rows={2}
                        className="w-full rounded-md border border-gray-300 p-2 text-[12px] focus:outline-none focus:ring-1 focus:ring-indigo-600 bg-white"
                        value={targetPurpose}
                        onChange={(e) => setTargetPurpose(e.target.value)}
                        placeholder="Define agent purpose for attack generation..."
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
                        Inferred Target System Prompt
                      </label>
                      <textarea
                        rows={3}
                        className="w-full rounded-md border border-gray-300 p-2 text-[12px] focus:outline-none focus:ring-1 focus:ring-indigo-600 bg-white font-mono"
                        value={targetSystemPrompt}
                        onChange={(e) => setTargetSystemPrompt(e.target.value)}
                        placeholder="Inferred system prompt for evaluations..."
                      />
                    </div>
                  </>
                )}

                {agentMeta?.tool_metadata && agentMeta.tool_metadata.length > 0 && (
                  <div>
                    <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5 flex items-center gap-1">
                      <Settings size={12} className="text-gray-400" /> Tool Metadata ({agentMeta.tool_metadata.length})
                    </label>
                    <div className="border rounded-md overflow-hidden max-h-40 overflow-y-auto">
                      {agentMeta.tool_metadata.map((t, idx) => (
                        <div key={idx} className="p-2 border-b last:border-b-0 text-[11px] bg-white flex flex-col gap-0.5">
                          <span className="font-semibold text-gray-800 font-mono flex items-center gap-1">
                            🔧 {t.name}
                          </span>
                          <span className="text-gray-500">{t.description || 'No tool description.'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 4: Select Vulnerabilities */}
        {step === 4 && (
          <div className="p-5 space-y-4">
            <CardHeader title="Step 4: Select Vulnerabilities Taxonomy" />
            <p className="text-[12px] text-gray-500">
              Select the specific safety and vulnerability areas you want to run simulations on.
            </p>

            {scanMode === 'custom' ? (
              <div className="space-y-2 pt-2">
                {redteamApi.REDTEAM_CATEGORIES.map((c) => {
                  const enabled = customCategories.includes(c.id)
                  return (
                    <label
                      key={c.id}
                      className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all hover:bg-gray-50 ${
                        enabled ? 'border-indigo-600 bg-indigo-50/20' : 'border-gray-200'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={enabled}
                        className="mt-1"
                        onChange={() =>
                          setCustomCategories((prev) =>
                            prev.includes(c.id) ? prev.filter((x) => x !== c.id) : [...prev, c.id]
                          )
                        }
                      />
                      <div>
                        <div className="font-semibold text-[12px] text-gray-900">{c.label}</div>
                        <div className="text-[11px] text-gray-500 mt-0.5">{c.desc}</div>
                      </div>
                    </label>
                  )
                })}
              </div>
            ) : deevalVulsLoading ? (
              <div className="flex flex-col items-center justify-center py-8 text-gray-500 text-[12px] gap-2">
                <Loader2 size={24} className="animate-spin text-indigo-600" />
                <span>Loading DeepEval Vulnerabilities Taxonomy…</span>
              </div>
            ) : (
              <div className="space-y-2 pt-2 max-h-96 overflow-y-auto pr-1">
                {deevevalVulsData?.vulnerabilities.map((v) => {
                  const enabled = deepevalCategories.includes(v.id)
                  return (
                    <label
                      key={v.id}
                      className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all hover:bg-gray-50 ${
                        enabled ? 'border-indigo-600 bg-indigo-50/20' : 'border-gray-200'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={enabled}
                        className="mt-1"
                        onChange={() =>
                          setDeepevalCategories((prev) =>
                            prev.includes(v.id) ? prev.filter((x) => x !== v.id) : [...prev, v.id]
                          )
                        }
                      />
                      <div>
                        <div className="font-semibold text-[12px] text-gray-900">{v.name}</div>
                        <div className="text-[11px] text-gray-500 mt-0.5">{v.description}</div>
                      </div>
                    </label>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Step 5: Attack Enhancements (DeepEval Only) */}
        {step === 5 && (
          <div className="p-5 space-y-4">
            <CardHeader title="Step 5: Configure Attack Enhancements" />
            <p className="text-[12px] text-gray-500">
              Apply adversarial injection strategies to jailbreak safety filters, with configurable weights.
            </p>

            <div className="space-y-3 pt-2">
              {Object.entries(enhancements).map(([key, val]) => (
                <div key={key} className="p-3 border rounded-lg flex items-center justify-between gap-4 bg-white">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={val.enabled}
                      onChange={() => handleEnhancementToggle(key)}
                    />
                    <div>
                      <div className="font-semibold text-[12px] text-gray-900">
                        {key.replace('_', ' ')}
                      </div>
                    </div>
                  </label>
                  {val.enabled && (
                    <div className="flex items-center gap-2 w-48">
                      <span className="text-[10px] text-gray-500 uppercase">Weight:</span>
                      <input
                        type="range"
                        min="0.0"
                        max="1.0"
                        step="0.05"
                        value={val.weight}
                        className="w-24 h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                        onChange={(e) => handleWeightChange(key, e.target.value)}
                      />
                      <span className="text-[11px] font-mono text-gray-700 w-8 text-right">
                        {val.weight.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Step 6: Review & Launch */}
        {step === 6 && (
          <div className="p-5 space-y-4">
            <CardHeader title="Step 6: Review & Launch Adversarial Simulation" />
            <p className="text-[12px] text-gray-500">
              Review your Red Teaming configuration. Launching the scan executes attacks asynchronously.
            </p>

            <div className="border rounded-md divide-y text-[12px] bg-gray-50">
              <div className="p-3 flex justify-between">
                <span className="text-gray-500">Target Agent:</span>
                <span className="font-semibold text-gray-800">{selectedAgentObj?.display_name || selectedAgentObj?.name}</span>
              </div>
              <div className="p-3 flex justify-between">
                <span className="text-gray-500">Execution Mode:</span>
                <span className="font-semibold text-gray-800 uppercase">{scanMode}</span>
              </div>
              <div className="p-3 flex justify-between">
                <span className="text-gray-500">Judge Model:</span>
                <span className="font-semibold text-gray-800">{judgeModel}</span>
              </div>
              <div className="p-3 flex flex-col gap-1">
                <span className="text-gray-500">Vulnerabilities Categories:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {scanMode === 'custom'
                    ? customCategories.map((c) => (
                        <span key={c} className="text-[10px] px-2 py-0.5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-md">
                          {c}
                        </span>
                      ))
                    : deepevalCategories.map((c) => (
                        <span key={c} className="text-[10px] px-2 py-0.5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-md">
                          {c}
                        </span>
                      ))}
                </div>
              </div>
              {scanMode === 'deepeval' && (
                <div className="p-3 flex flex-col gap-1">
                  <span className="text-gray-500">Applied Enhancements:</span>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {Object.entries(enhancements).map(([key, val]) => {
                      if (!val.enabled) return null
                      return (
                        <span key={key} className="text-[10px] px-2 py-0.5 bg-gray-150 border text-gray-700 rounded-md">
                          {key.replace('_', ' ')} (w: {val.weight.toFixed(2)})
                        </span>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>

            <Btn
              primary
              style={{ width: '100%', justifyContents: 'center', padding: '12px' }}
              disabled={mutation.isPending}
              onClick={handleLaunch}
            >
              {mutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Shield size={14} />
              )}
              Initialize Adversarial Simulation
            </Btn>
          </div>
        )}

        {/* Wizard Footer Navigation */}
        <div className="flex justify-between items-center p-4 bg-gray-50 border-t">
          {step > 1 ? (
            <Btn secondary onClick={handlePrev} disabled={mutation.isPending}>
              <ChevronLeft size={14} /> Back
            </Btn>
          ) : (
            <div />
          )}

          {step < 6 ? (
            <Btn
              primary
              onClick={handleNext}
              disabled={nextDisabled()}
            >
              Next <ChevronRight size={14} />
            </Btn>
          ) : (
            <div />
          )}
        </div>
      </Card>
    </div>
  )
}
