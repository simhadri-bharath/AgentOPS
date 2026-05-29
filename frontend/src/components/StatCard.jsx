import React from 'react'

export default function StatCard({ label, value, meta, valueStyle = {} }) {
  return (
    <div className="bg-gray-50 rounded-md p-3.5" style={{ background: 'var(--color-background-secondary)' }}>
      <div className="text-[11px] font-medium text-gray-400 uppercase tracking-[0.04em] mb-1.5">{label}</div>
      <div className="text-[22px] font-medium text-gray-900" style={valueStyle}>{value}</div>
      {meta && <div className="text-[11px] text-gray-500 mt-1">{meta}</div>}
    </div>
  )
}
