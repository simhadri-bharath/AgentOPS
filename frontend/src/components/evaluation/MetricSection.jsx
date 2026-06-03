import React, { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

export default function MetricSection({
  title,
  icon: Icon,
  description,
  activeCountText,
  children,
  defaultOpen = true,
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div
      className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition-all duration-200"
      style={{ borderWidth: '0.5px' }}
    >
      {/* Header bar */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between bg-gray-50 px-3.5 py-2.5 transition-colors hover:bg-gray-100/70 focus:outline-none"
      >
        <div className="flex items-center gap-2 text-[13px] font-semibold text-gray-900">
          {Icon && <Icon size={15} className="text-gray-500 flex-shrink-0" />}
          <span>{title}</span>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-gray-500">
          {activeCountText && (
            <span className="bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
              {activeCountText}
            </span>
          )}
          {isOpen ? <ChevronUp size={13} className="text-gray-400" /> : <ChevronDown size={13} className="text-gray-400" />}
        </div>
      </button>

      {/* Sub-header / Description */}
      {description && (
        <div className="border-b border-gray-100 bg-gray-50/20 px-3.5 py-1 text-[11px] text-gray-500 select-none">
          {description}
        </div>
      )}

      {/* Collapsible Content */}
      {isOpen && (
        <div className="animate-in fade-in slide-in-from-top-1 duration-200 border-t border-gray-100">
          {children}
        </div>
      )}
    </div>
  )
}
