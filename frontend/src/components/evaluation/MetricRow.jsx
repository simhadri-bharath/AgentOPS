import React from 'react'
import MetricToggle from '../MetricToggle'

export default function MetricRow({ label, description, checked, onChange }) {
  return (
    <div className="flex items-center justify-between px-3.5 py-2.5 hover:bg-gray-50/40 transition-colors duration-150 border-b border-gray-100 last:border-b-0">
      <div className="flex flex-col gap-0.5 min-w-0 pr-4">
        <span className="text-[13px] font-medium text-gray-900 truncate select-none">
          {label}
        </span>
        {description && (
          <span className="text-[11px] text-gray-500 font-normal truncate select-none">
            {description}
          </span>
        )}
      </div>
      <div className="flex-shrink-0">
        <MetricToggle
          checked={checked}
          onChange={onChange}
          label=""
          isLast
        />
      </div>
    </div>
  )
}
