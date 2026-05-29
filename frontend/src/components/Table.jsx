import React from 'react'

export function Table({ children, className = '' }) {
  return (
    <table className={`w-full border-collapse ${className}`}>
      {children}
    </table>
  )
}

export function THead({ children }) {
  return (
    <thead>
      <tr>
        {children}
      </tr>
    </thead>
  )
}

export function Th({ children }) {
  return (
    <th
      className="text-left text-[11px] font-medium text-gray-400 px-3 py-2 uppercase tracking-[0.04em]"
      style={{ borderBottom: '0.5px solid #E5E7EB' }}
    >
      {children}
    </th>
  )
}

export function Td({ children, className = '', style = {} }) {
  return (
    <td
      className={`px-3 py-2.5 text-[12px] text-gray-900 align-middle ${className}`}
      style={{ borderBottom: '0.5px solid #E5E7EB', ...style }}
    >
      {children}
    </td>
  )
}

export function TRow({ children, onClick, highlight = false }) {
  return (
    <tr
      onClick={onClick}
      className={`${onClick ? 'cursor-pointer hover:bg-gray-50' : ''} ${highlight ? 'bg-red-50' : ''}`}
      style={highlight ? { background: '#FEF2F2' } : {}}
    >
      {children}
    </tr>
  )
}
