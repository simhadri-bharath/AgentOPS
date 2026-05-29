import React from 'react'

export default function TraceRow({ dot, label, meta, body, time, isLast = false }) {
  return (
    <div className="flex items-start gap-2.5 py-2.5" style={{ borderBottom: isLast ? 'none' : '0.5px solid #E5E7EB' }}>
      <div className="flex flex-col items-center gap-0">
        <div className="w-2.5 h-2.5 rounded-full flex-shrink-0 mt-0.5" style={{ background: dot }} />
        {!isLast && <div className="w-px flex-1 min-h-5 mt-1" style={{ background: '#E5E7EB' }} />}
      </div>
      <div className="flex-1">
        <div className="text-[12px] font-medium text-gray-900">{label}</div>
        {meta && <div className="text-[11px] text-gray-500 mt-0.5">{meta}</div>}
        {body && (
          <div
            className="text-[11px] text-gray-500 px-2 py-1.5 rounded-md mt-1.5 leading-relaxed"
            style={{ fontFamily: 'var(--font-mono)', background: 'var(--color-background-secondary)' }}
          >
            {body}
          </div>
        )}
      </div>
      <span className="text-[11px] text-gray-400 whitespace-nowrap ml-auto">{time}</span>
    </div>
  )
}
