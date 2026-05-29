import React, { useState } from 'react'

export default function MetricToggle({
  label,
  defaultOn = true,
  isLast = false,
  checked,
  onChange,
}) {
  const [internalOn, setInternalOn] = useState(defaultOn)
  const on = checked !== undefined ? checked : internalOn
  const toggle = () => {
    const next = !on
    if (onChange) onChange(next)
    else setInternalOn(next)
  }
  return (
    <div
      className="flex items-center justify-between py-2 text-[12px]"
      style={{ borderBottom: isLast ? 'none' : '0.5px solid #E5E7EB' }}
    >
      <span className="text-gray-900">{label}</span>
      <div className={`toggle-sw ${on ? '' : 'off'}`} onClick={toggle} role="switch" aria-checked={on} />
    </div>
  )
}
