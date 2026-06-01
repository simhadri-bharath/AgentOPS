import React, { useState } from 'react'

export default function TabBar({ tabs, defaultTab = 0, activeTab, onChange }) {
  const [internalActive, setInternalActive] = useState(defaultTab)
  const active = activeTab !== undefined ? activeTab : internalActive
  const handleClick = (i) => {
    if (activeTab === undefined) setInternalActive(i)
    onChange && onChange(i)
  }
  return (
    <div className="flex" style={{ borderBottom: '0.5px solid #E5E7EB', marginBottom: 14 }}>
      {tabs.map((tab, i) => (
        <button
          key={i}
          onClick={() => handleClick(i)}
          className="px-4 py-2 text-[12px] cursor-pointer border-b-2 -mb-px transition-colors"
          style={{
            borderBottomColor: active === i ? '#4F46E5' : 'transparent',
            color: active === i ? '#4F46E5' : '#6B7280',
            fontWeight: active === i ? 500 : 400,
            background: 'none',
            outline: 'none',
          }}
        >
          {tab}
        </button>
      ))}
    </div>
  )
}
