import React from 'react'

export default function MiniBar({ pct, color = '#4F46E5' }) {
  return (
    <div className="h-1.5 rounded-full overflow-hidden mt-1.5" style={{ background: 'var(--color-background-secondary)' }}>
      <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
    </div>
  )
}
