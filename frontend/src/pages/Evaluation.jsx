import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Briefcase, Check, ChevronRight, Loader2 } from 'lucide-react'
import Btn from '../components/Btn'
import PageHeader from '../components/PageHeader'
import AgentStep from '../components/evaluation/AgentStep'
import DatasetStep from '../components/evaluation/DatasetStep'
import FrameworkStep from '../components/evaluation/FrameworkStep'
import MetricsStep from '../components/evaluation/MetricsStep'
import { useAgents } from '../context/AgentsContext'
import * as evaluationsApi from '../api/evaluations'
import { FRAMEWORK_METRICS, DEFAULT_METRICS_STATE } from '../lib/evaluationConstants'

const STEPS = [
  { id: 1, title: 'Select Agent' },
  { id: 2, title: 'Select Dataset' },
  { id: 3, title: 'Select Framework' },
  { id: 4, title: 'Select Metrics' },
]

const STEP_META = {
  1: {
    title: 'Choose agent to evaluate',
    subtitle: 'Select one deployed agent from your registry.',
  },
  2: {
    title: 'Choose evaluation dataset',
    subtitle: 'Upload a CSV/JSON file or pick an existing dataset.',
  },
  3: {
    title: 'Choose evaluation framework',
    subtitle: 'Pick the scoring framework for this job.',
  },
  4: {
    title: 'Choose metrics',
    subtitle: 'Toggle metrics and review the summary before creating the job.',
  },
}

export default function Evaluation() {
  const nav = useNavigate()
  const [searchParams] = useSearchParams()
  const { agents, loading: agentsLoading } = useAgents()

  const [step, setStep] = useState(1)
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [selectedDataset, setSelectedDataset] = useState(null)
  const [selectedFramework, setSelectedFramework] = useState(null)
  const [metricsOn, setMetricsOn] = useState(DEFAULT_METRICS_STATE)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    const agentId = searchParams.get('agentId')
    if (agentId && agents.length) {
      const match = agents.find((a) => a.id === agentId)
      if (match) setSelectedAgent(match)
    }
  }, [searchParams, agents])

  const selectedMetrics = useMemo(() => {
    return Object.entries(metricsOn)
      .filter(([id, on]) => {
        if (!on) return false
        if (id === 'include_multi_turn') return false
        // Filter out multi-turn metrics if the control toggle is disabled
        if (
          id === 'agent_multi_turn_task_success' ||
          id === 'agent_multi_turn_tool_use_quality' ||
          id === 'agent_multi_turn_trajectory_quality'
        ) {
          return !!metricsOn['include_multi_turn']
        }
        return true
      })
      .map(([id]) => id)
  }, [metricsOn])

  const meta = STEP_META[step]

  const canGoNext = () => {
    if (step === 1) return !!selectedAgent
    if (step === 2) return !!selectedDataset
    if (step === 3) return !!selectedFramework
    if (step === 4) return selectedMetrics.length > 0
    return false
  }

  const handleNext = () => {
    if (step < 4 && canGoNext()) setStep(step + 1)
  }

  const handleBack = () => {
    if (step > 1) setStep(step - 1)
  }

  const handleStepClick = (targetStep) => {
    if (targetStep < step) setStep(targetStep)
  }

  const toggleMetric = (id, on) => {
    setMetricsOn((prev) => ({ ...prev, [id]: on }))
  }

  const handleCreateJob = async () => {
    setError(null)
    if (!selectedAgent || !selectedDataset || !selectedFramework) {
      setError('Complete all steps before creating a job.')
      return
    }
    if (selectedMetrics.length === 0) {
      setError('Select at least one metric.')
      return
    }

    setCreating(true)
    try {
      const job = await evaluationsApi.createEvaluationJob({
        agent_id: selectedAgent.id,
        dataset_id: selectedDataset.id,
        framework: selectedFramework.id,
        metrics: selectedMetrics,
      })
      nav(`/jobs/${job.id}`)
    } catch (err) {
      setError(err.message || 'Failed to create evaluation job')
    } finally {
      setCreating(false)
    }
  }

  const renderStep = () => {
    switch (step) {
      case 1:
        return (
          <AgentStep
            agents={agents}
            loading={agentsLoading}
            selectedAgent={selectedAgent}
            onSelect={setSelectedAgent}
          />
        )
      case 2:
        return (
          <DatasetStep
            selectedDataset={selectedDataset}
            onSelect={setSelectedDataset}
          />
        )
      case 3:
        return (
          <FrameworkStep
            selectedFramework={selectedFramework}
            onSelect={setSelectedFramework}
          />
        )
      case 4:
        return (
          <MetricsStep
            selectedFramework={selectedFramework}
            metricsOn={metricsOn}
            onToggleMetric={toggleMetric}
            selectedAgent={selectedAgent}
            selectedDataset={selectedDataset}
          />
        )
      default:
        return null
    }
  }

  return (
    <div>
      <PageHeader
        title="New Evaluation"
        subtitle="Configure an evaluation job — save as draft and run when ready"
      >
        <Btn onClick={() => nav('/jobs')}>
          <Briefcase size={13} />
          Jobs
        </Btn>
      </PageHeader>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
          {error}
        </div>
      )}

      <div
        className="overflow-hidden rounded-xl border border-gray-200 bg-white"
        style={{ borderWidth: '0.5px' }}
      >
        {/* Top stepper */}
        <div className="grid grid-cols-4 border-b border-gray-200">
          {STEPS.map((s) => {
            const active = step === s.id
            const completed = step > s.id
            const clickable = completed

            return (
              <button
                key={s.id}
                type="button"
                onClick={() => clickable && handleStepClick(s.id)}
                disabled={!clickable}
                className={`relative flex flex-col items-center justify-center gap-2 py-3 transition-colors ${
                  active
                    ? 'bg-indigo-50'
                    : completed
                      ? 'bg-white hover:bg-gray-50 cursor-pointer'
                      : 'bg-white cursor-default'
                }`}
              >
                <div
                  className={`flex h-6 w-6 items-center justify-center rounded-full text-[12px] font-semibold ${
                    active
                      ? 'bg-indigo-600 text-white'
                      : completed
                        ? 'bg-green-500 text-white'
                        : 'border border-gray-300 bg-white text-gray-400'
                  }`}
                >
                  {completed ? <Check size={10} /> : s.id}
                </div>
                <span
                  className={`text-[13px] font-medium ${
                    active
                      ? 'text-indigo-700'
                      : completed
                        ? 'text-green-700'
                        : 'text-gray-400'
                  }`}
                >
                  {s.title}
                </span>
                {active && (
                  <div className="absolute bottom-0 left-0 h-0.5 w-full bg-indigo-600" />
                )}
              </button>
            )
          })}
        </div>

        {/* Step content */}
        <div className="p-3 ">
          <div className="mb-2 border-b border-gray-100 pb-1">
            <h2 className="text-[15px] font-medium text-gray-900">{meta.title}</h2>
            <p className="mt-1 text-[12px] text-gray-500">{meta.subtitle}</p>
          </div>

          {renderStep()}
        </div>

        {/* Footer navigation */}
        <div className="flex items-center justify-between border-t border-gray-200 bg-gray-50 px-6 py-3">
          <Btn disabled={step === 1} onClick={handleBack}>
            Back
          </Btn>

          <div className="flex items-center gap-2 text-[12px] text-gray-500">
            Step {step} of {STEPS.length}
          </div>

          {step < 4 ? (
            <Btn primary disabled={!canGoNext()} onClick={handleNext}>
              Next
              <ChevronRight size={14} />
            </Btn>
          ) : (
            <Btn primary disabled={creating || !canGoNext()} onClick={handleCreateJob}>
              {creating ? (
                <>
                  <Loader2 size={13} className="animate-spin" />
                  Creating…
                </>
              ) : (
                'Create Evaluation Job'
              )}
            </Btn>
          )}
        </div>
      </div>
    </div>
  )
}
