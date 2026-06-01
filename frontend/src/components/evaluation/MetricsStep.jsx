import React from 'react'
import { Check } from 'lucide-react'

import MetricToggle from '../MetricToggle'
import EvaluationSummary from './EvaluationSummary'

import {
  FRAMEWORK_METRICS,
  metricLabel,
} from '../../lib/evaluationConstants'

export default function MetricsStep({
  selectedFramework,
  metricsOn,
  onToggleMetric,
  selectedAgent,
  selectedDataset,
}) {
  const metrics =
    FRAMEWORK_METRICS[selectedFramework?.id] || []

  return (
    <div className="grid grid-cols-2 gap-4 items-start">

      {/* METRICS */}

      <div
        className="
          rounded-xl
          border
          border-gray-200
          bg-white
          px-4
          py-3
        "
        style={{ borderWidth: '0.5px' }}
      >

        <div className="mb-3">

          <div className="text-[14px] font-semibold text-gray-900">
            Metrics
          </div>

          <div className="mt-0.5 text-[12px] text-gray-500">
            Select evaluation metrics
          </div>
        </div>

        {metrics.length === 0 ? (
          <p className="text-[12px] text-gray-500">
            Select a framework first.
          </p>
        ) : (
          <div className="space-y-1">

            {metrics.map((id, i) => (
              <MetricToggle
                key={id}
                label={metricLabel(id)}
                checked={metricsOn[id]}
                onChange={(on) =>
                  onToggleMetric(id, on)
                }
                isLast={i === metrics.length - 1}
                compact
              />
            ))}
          </div>
        )}
      </div>

      {/* SUMMARY */}

      <div className="sticky top-4">

        <EvaluationSummary
          agent={selectedAgent}
          dataset={selectedDataset}
          framework={selectedFramework}
          selectedMetrics={metrics.filter(
            (m) => metricsOn[m]
          )}
        />
      </div>
    </div>
  )
}

export function MetricChecklist({ metrics }) {
  if (!metrics?.length) {
    return (
      <span className="text-gray-400">
        None selected
      </span>
    )
  }

  return (
    <ul className="space-y-1">

      {metrics.map((m) => (
        <li
          key={m}
          className="
            flex
            items-center
            gap-2
            text-[12px]
            text-gray-700
          "
        >
          <Check
            size={11}
            className="flex-shrink-0 text-green-600"
          />

          {metricLabel(m)}
        </li>
      ))}
    </ul>
  )
}