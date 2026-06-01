import React from 'react'

export function Card({ children, className = '', style = {} }) {
  return (
    <div
      className={`bg-white border border-gray-200 rounded-lg p-4 ${className}`}
      style={{ borderWidth: '0.5px', ...style }}
    >
      {children}
    </div>
  )
}

export function CardHeader({ title, children }) {
  return (
    <div className="flex items-center justify-between mb-2">
      <span className="text-[13px] font-medium text-gray-900">{title}</span>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  )
}
