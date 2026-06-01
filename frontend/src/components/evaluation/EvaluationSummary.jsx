import React from 'react'
import { MetricChecklist } from './MetricsStep'
import { frameworkLabel } from '../../lib/evaluationConstants'

export default function EvaluationSummary({ agent, dataset, framework, selectedMetrics }) {
  return (
    <div
      className="bg-gray-50 border border-gray-200 rounded-lg p-4"
      style={{ borderWidth: '0.5px' }}
    >
      <div className="text-[12px] font-medium text-gray-500 uppercase tracking-[0.04em] mb-3">
        Evaluation Summary
      </div>
      <dl className="space-y-2 text-[13px]">
        <div className="flex gap-2">
          <dt className="text-gray-500 w-24 flex-shrink-0">Agent</dt>
          <dd className="text-gray-900 font-medium">{agent?.name || '—'}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-gray-500 w-24 flex-shrink-0">Dataset</dt>
          <dd className="text-gray-900 font-medium">{dataset?.name || '—'}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-gray-500 w-24 flex-shrink-0">Framework</dt>
          <dd className="text-gray-900 font-medium">
            {framework?.name || frameworkLabel(framework?.id) || '—'}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-gray-500 w-24 flex-shrink-0">Metrics</dt>
          <dd className="flex-1">
            <MetricChecklist metrics={selectedMetrics} />
          </dd>
        </div>
      </dl>
    </div>
  )
}
