import React from 'react'

export default function Btn({ children, primary = false, onClick, className = '', style = {}, type = 'button' }) {
  const base = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] cursor-pointer transition-colors duration-100 font-medium border'
  const variant = primary
    ? 'bg-indigo-600 text-white border-indigo-600 hover:bg-indigo-700'
    : 'bg-white text-gray-800 border-gray-300 hover:bg-gray-50'
  return (
    <button type={type} onClick={onClick} className={`${base} ${variant} ${className}`} style={style}>
      {children}
    </button>
  )
}
