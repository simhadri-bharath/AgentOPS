import React from 'react'

const variantClasses = {
  green: 'bg-green-100 text-green-700',
  amber: 'bg-yellow-100 text-yellow-800',
  red: 'bg-red-100 text-red-800',
  blue: 'bg-blue-100 text-blue-800',
  purple: 'bg-indigo-50 text-indigo-700',
  gray: 'bg-gray-100 text-gray-600',
}

export default function Badge({ variant = 'gray', children, className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${variantClasses[variant] || variantClasses.gray} ${className}`}
    >
      {children}
    </span>
  )
}
