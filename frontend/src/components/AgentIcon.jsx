import React from 'react'
import { Bot } from 'lucide-react'

const colorMap = {
  purple: { bg: '#EEF2FF', color: '#4338CA' },
  teal:   { bg: '#CCFBF1', color: '#0F766E' },
  amber:  { bg: '#FEF3C7', color: '#B45309' },
  blue:   { bg: '#DBEAFE', color: '#1D4ED8' },
}

export default function AgentIcon({ color = 'purple', size = 28, iconSize = 14 }) {
  const { bg, color: c } = colorMap[color] || colorMap.purple
  return (
    <div
      className="flex items-center justify-center rounded-md flex-shrink-0"
      style={{ width: size, height: size, background: bg, color: c }}
    >
      <Bot size={iconSize} />
    </div>
  )
}
