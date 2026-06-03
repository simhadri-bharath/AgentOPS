import React from 'react'
import { Info, ShieldCheck } from 'lucide-react'

export default function InfoBanner({ message, type = 'info' }) {
  if (type === 'shield') {
    return (
      <div className="flex items-center gap-2 px-3.5 py-2 bg-blue-50 border-b border-blue-100 text-[12px] text-blue-700 font-medium animate-in fade-in duration-200">
        <ShieldCheck size={14} className="flex-shrink-0 text-blue-600 animate-pulse" />
        <span>{message}</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 px-3.5 py-2 bg-indigo-50 border-b border-indigo-100 text-[12px] text-indigo-700 font-medium animate-in fade-in duration-200">
      <Info size={14} className="flex-shrink-0 text-indigo-600" />
      <span>{message}</span>
    </div>
  )
}
