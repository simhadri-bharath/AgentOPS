import React from 'react'
import { CheckCircle2 } from 'lucide-react'
import { frameworkLabel, METRIC_SUMMARY_LABELS } from '../../lib/evaluationConstants'

export default function SummaryPanel({
  agent,
  dataset,
  framework,
  selectedMetrics = [],
}) {
  return (
    <div
      className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"
      style={{ borderWidth: '0.5px' }}
    >
      <div className="text-[12px] font-semibold text-gray-400 uppercase tracking-[0.04em] mb-4 border-b border-gray-100 pb-2 select-none">
        Evaluation Summary
      </div>
      <dl className="space-y-3.5 text-[13px]">
        <div className="flex gap-2">
          <dt className="text-gray-500 w-20 flex-shrink-0 font-normal select-none">Agent</dt>
          <dd className="text-gray-900 font-medium truncate">{agent?.name || '—'}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-gray-500 w-20 flex-shrink-0 font-normal select-none">Dataset</dt>
          <dd className="text-gray-900 font-medium truncate">{dataset?.name || '—'}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-gray-500 w-20 flex-shrink-0 font-normal select-none">Framework</dt>
          <dd className="text-gray-900 font-medium truncate">
            {framework?.name || frameworkLabel(framework?.id) || '—'}
          </dd>
        </div>
        <div className="flex flex-col gap-2 pt-3 border-t border-gray-100">
          <dt className="text-gray-500 font-normal select-none">Metrics</dt>
          <dd className="flex-1">
            {selectedMetrics.length === 0 ? (
              <span className="text-gray-400 text-[12px] italic select-none">
                No metrics selected
              </span>
            ) : (
              <ul className="space-y-1.5 max-h-[220px] overflow-y-auto pr-1">
                {selectedMetrics.map((m) => (
                  <li
                    key={m}
                    className="flex items-center gap-2 text-[12px] text-gray-700 font-medium animate-in fade-in slide-in-from-left-1 duration-150"
                  >
                    <CheckCircle2
                      size={13}
                      className="flex-shrink-0 text-green-500 fill-green-50"
                    />
                    <span className="truncate">{METRIC_SUMMARY_LABELS[m] || m}</span>
                  </li>
                ))}
              </ul>
            )}
          </dd>
        </div>
      </dl>
    </div>
  )
}
