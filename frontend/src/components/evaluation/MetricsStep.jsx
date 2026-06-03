import React, { useState } from 'react'
import {
  Code2,
  Route,
  Sparkles,
  Sliders,
  Wand2,
  Terminal,
  ChevronDown
} from 'lucide-react'

import MetricToggle from '../MetricToggle'
import MetricSection from './MetricSection'
import MetricRow from './MetricRow'
import SummaryPanel from './SummaryPanel'
import InfoBanner from './InfoBanner'

import {
  METRIC_CATEGORIES,
} from '../../lib/evaluationConstants'

const CATEGORY_ICONS = {
  deterministic: Code2,
  trajectory: Route,
  final_response_quality: Sparkles,
  custom: Sliders,
}

export default function MetricsStep({
  metricsOn,
  onToggleMetric,
  selectedAgent,
  selectedDataset,
  selectedFramework,
}) {
  // Custom Metrics Panel expansion states
  const [customLlmExpanded, setCustomLlmExpanded] = useState(false)
  const [customCodeExpanded, setCustomCodeExpanded] = useState(false)

  // Custom Metrics Forms fields state
  const [llmName, setLlmName] = useState('Custom LLM Metric')
  const [llmPrompt, setLlmPrompt] = useState(
    'Score the response from 1 to 5 based on technical correctness, clarity, and detail.'
  )
  const [codeName, setCodeName] = useState('Custom Code Metric')
  const [codeLogic, setCodeLogic] = useState(
    `def evaluate(response, expected):
  # Custom Python evaluation logic
  return 1.0 if len(response) > 0 else 0.0`
  )

  // Calculate active counts dynamically
  const getActiveCount = (cat) => {
    if (cat.id === 'deterministic' || cat.id === 'trajectory') {
      return cat.metrics.filter((m) => !!metricsOn[m.id]).length
    }
    if (cat.id === 'final_response_quality') {
      const singleTurnCount = cat.subsections[0].metrics.filter((m) => !!metricsOn[m.id]).length
      const multiTurnCount = metricsOn['include_multi_turn']
        ? cat.subsections[1].metrics.filter((m) => !!metricsOn[m.id]).length
        : 0
      return singleTurnCount + multiTurnCount
    }
    if (cat.id === 'custom') {
      return cat.metrics.filter((m) => !!metricsOn[m.id]).length
    }
    return 0
  }

  const getActiveCountText = (cat) => {
    const count = getActiveCount(cat)
    if (cat.id === 'custom') {
      return `${count} added`
    }
    return `${count} active`
  }

  // Get only enabled metrics for summary (filtering out include_multi_turn)
  const enabledMetricsForSummary = Object.entries(metricsOn)
    .filter(([id, on]) => {
      if (!on) return false
      if (id === 'include_multi_turn') return false
      // Filter out multi-turn metrics if include_multi_turn is OFF
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start animate-in fade-in duration-300">
      
      {/* LEFT COLUMN: Metric Groups */}
      <div className="lg:col-span-2 flex flex-col gap-4">
        {METRIC_CATEGORIES.map((cat) => {
          const IconComponent = CATEGORY_ICONS[cat.id]

          return (
            <MetricSection
              key={cat.id}
              title={cat.category}
              icon={IconComponent}
              description={cat.description}
              activeCountText={getActiveCountText(cat)}
            >
              {/* Notice Banner */}
              {cat.notice && (
                <InfoBanner
                  message={cat.notice}
                  type={cat.id === 'final_response_quality' ? 'shield' : 'info'}
                />
              )}

              {/* standard categories (Deterministic, Trajectory) */}
              {cat.metrics && !cat.isCustom && (
                <div className="grid grid-cols-1 md:grid-cols-2">
                  {cat.metrics.map((m, idx) => (
                    <div
                      key={m.id}
                      className={`border-b border-gray-100 md:border-b
                        ${idx % 2 === 0 ? 'md:border-r md:border-gray-100' : ''}`}
                    >
                      <MetricRow
                        label={m.label}
                        description={m.description}
                        checked={!!metricsOn[m.id]}
                        onChange={(on) => onToggleMetric(m.id, on)}
                      />
                    </div>
                  ))}
                </div>
              )}

              {/* Final Response Quality Metrics (subsections + multi-turn toggle) */}
              {cat.subsections && (
                <div className="flex flex-col">
                  {cat.subsections.map((sub) => {
                    const isMultiTurnSection = sub.isMultiTurn

                    if (isMultiTurnSection) {
                      return (
                        <div key={sub.id} className="border-t border-gray-100">
                          {/* Include Multi-turn Metrics Toggle Control */}
                          <div className="flex items-center justify-between px-3.5 py-3 border-b border-gray-100 bg-gray-50/20">
                            <span className="text-[13px] font-semibold text-gray-800 select-none">
                              Include multi-turn metrics
                            </span>
                            <MetricToggle
                              checked={!!metricsOn['include_multi_turn']}
                              onChange={(on) => onToggleMetric('include_multi_turn', on)}
                              label=""
                              isLast
                            />
                          </div>

                          {/* Render Multi-turn metrics if control toggle is ON */}
                          {metricsOn['include_multi_turn'] && (
                            <div className="animate-in fade-in duration-200">
                              <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider bg-gray-50/30 px-3.5 py-1.5 border-b border-gray-100 select-none">
                                {sub.label}
                              </div>
                              <div className="grid grid-cols-1 md:grid-cols-2">
                                {sub.metrics.map((m, idx) => (
                                  <div
                                    key={m.id}
                                    className={`border-b border-gray-100 md:border-b
                                      ${idx % 2 === 0 ? 'md:border-r md:border-gray-100' : ''}`}
                                  >
                                    <MetricRow
                                      label={m.label}
                                      description={m.description}
                                      checked={!!metricsOn[m.id]}
                                      onChange={(on) => onToggleMetric(m.id, on)}
                                    />
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    }

                    // Otherwise, Single-turn section
                    return (
                      <div key={sub.id}>
                        <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider bg-gray-50/30 px-3.5 py-1.5 border-b border-gray-100 select-none">
                          {sub.label}
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 border-collapse">
                          {sub.metrics.map((m, idx) => (
                            <div
                              key={m.id}
                              className={`border-b border-gray-100 md:border-b
                                ${idx % 2 === 0 ? 'md:border-r md:border-gray-100' : ''}`}
                            >
                              <MetricRow
                                label={m.label}
                                description={m.description}
                                checked={!!metricsOn[m.id]}
                                onChange={(on) => onToggleMetric(m.id, on)}
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Custom Metrics (expandable Panels) */}
              {cat.isCustom && (
                <div className="flex flex-col">
                  {cat.metrics.map((m) => {
                    const isLlm = m.type === 'llm'
                    const isExpanded = isLlm ? customLlmExpanded : customCodeExpanded
                    const setExpanded = isLlm ? setCustomLlmExpanded : setCustomCodeExpanded
                    const iconBg = isLlm
                      ? 'bg-indigo-50 text-indigo-600'
                      : 'bg-emerald-50 text-emerald-600'
                    const CustomIcon = isLlm ? Wand2 : Terminal

                    return (
                      <div key={m.id} className="border-b border-gray-100 last:border-b-0">
                        {/* Panel header button */}
                        <button
                          type="button"
                          onClick={() => setExpanded(!isExpanded)}
                          className="flex w-full items-center gap-3 px-3.5 py-3 text-left hover:bg-gray-50/30 transition-colors focus:outline-none border-collapse"
                        >
                          <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${iconBg}`}>
                            <CustomIcon size={16} />
                          </div>
                          <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                            <span className="text-[13px] font-semibold text-gray-900 truncate">
                              {m.label}
                            </span>
                            <span className="text-[11px] text-gray-500 truncate">
                              {m.description}
                            </span>
                          </div>
                          <ChevronDown
                            size={14}
                            className={`text-gray-400 transition-transform duration-200 ${
                              isExpanded ? 'rotate-180' : ''
                            }`}
                          />
                        </button>

                        {/* Expanded Panel details */}
                        {isExpanded && (
                          isLlm ? (
                            <div className="flex flex-col gap-3 p-3 bg-gray-50/60 border-t border-gray-100 animate-in fade-in duration-200">
                              <div className="flex flex-col gap-1">
                                <label className="text-[10px] font-bold text-gray-400 uppercase select-none">
                                  Metric Name
                                </label>
                                <input
                                  type="text"
                                  value={llmName}
                                  onChange={(e) => setLlmName(e.target.value)}
                                  className="w-full text-[12px] px-2.5 py-1.5 border border-gray-200 rounded-md focus:border-indigo-500 focus:outline-none"
                                  placeholder="e.g. My Custom Metric"
                                />
                              </div>
                              <div className="flex flex-col gap-1">
                                <label className="text-[10px] font-bold text-gray-400 uppercase select-none">
                                  Evaluation Rubric / Criteria
                                </label>
                                <textarea
                                  value={llmPrompt}
                                  onChange={(e) => setLlmPrompt(e.target.value)}
                                  rows={3}
                                  className="w-full text-[12px] px-2.5 py-1.5 border border-gray-200 rounded-md focus:border-indigo-500 focus:outline-none font-sans resize-none"
                                  placeholder="Instructions to LLM judge..."
                                />
                              </div>
                              <div className="flex items-center justify-between mt-1 pt-2 border-t border-gray-200/60">
                                <span className="text-[12px] text-gray-600 font-semibold select-none">
                                  Enable Custom LLM Metric
                                </span>
                                <MetricToggle
                                  checked={!!metricsOn[m.id]}
                                  onChange={(on) => onToggleMetric(m.id, on)}
                                  label=""
                                  isLast
                                />
                              </div>
                            </div>
                          ) : (
                            <div className="flex flex-col gap-3 p-3 bg-gray-50/60 border-t border-gray-100 animate-in fade-in duration-200">
                              <div className="flex flex-col gap-1">
                                <label className="text-[10px] font-bold text-gray-400 uppercase select-none">
                                  Metric Name
                                </label>
                                <input
                                  type="text"
                                  value={codeName}
                                  onChange={(e) => setCodeName(e.target.value)}
                                  className="w-full text-[12px] px-2.5 py-1.5 border border-gray-200 rounded-md focus:border-indigo-500 focus:outline-none"
                                  placeholder="e.g. My Custom Code Metric"
                                />
                              </div>
                              <div className="flex flex-col gap-1">
                                <label className="text-[10px] font-bold text-gray-400 uppercase select-none">
                                  Python Code Logic
                                </label>
                                <textarea
                                  value={codeLogic}
                                  onChange={(e) => setCodeLogic(e.target.value)}
                                  rows={4}
                                  className="w-full text-[11px] px-2.5 py-1.5 border border-gray-200 rounded-md focus:border-indigo-500 focus:outline-none font-mono resize-none"
                                  placeholder="def evaluate(response, expected):..."
                                />
                              </div>
                              <div className="flex items-center justify-between mt-1 pt-2 border-t border-gray-200/60">
                                <span className="text-[12px] text-gray-600 font-semibold select-none">
                                  Enable Custom Code Metric
                                </span>
                                <MetricToggle
                                  checked={!!metricsOn[m.id]}
                                  onChange={(on) => onToggleMetric(m.id, on)}
                                  label=""
                                  isLast
                                />
                              </div>
                            </div>
                          )
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </MetricSection>
          )
        })}
      </div>

      {/* RIGHT COLUMN: Sticky Summary */}
      <div className="lg:sticky lg:top-4">
        <SummaryPanel
          agent={selectedAgent}
          dataset={selectedDataset}
          framework={selectedFramework}
          selectedMetrics={enabledMetricsForSummary}
        />
      </div>

    </div>
  )
}