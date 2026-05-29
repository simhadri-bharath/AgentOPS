import React from 'react'

export default function KVRow({ label, value, isLast = false }) {
  return (
    <div
      className="flex justify-between items-center py-1.5 text-[12px]"
      style={{ borderBottom: isLast ? 'none' : '0.5px solid #E5E7EB' }}
    >
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-900 font-medium" style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{value}</span>
    </div>
  )
}
