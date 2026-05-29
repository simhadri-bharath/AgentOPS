import React from 'react'

export default function PageHeader({ title, subtitle, children }) {
  return (
    <div className="flex items-start justify-between mb-5">
      <div>
        <div className="text-[20px] font-medium text-gray-900 mb-1">{title}</div>
        {subtitle && <div className="text-[13px] text-gray-500">{subtitle}</div>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  )
}
