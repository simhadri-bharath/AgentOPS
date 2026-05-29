import React from 'react'
import { Inbox } from 'lucide-react'

export default function EmptyState({ message = 'No data available' }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-gray-400 text-center gap-2.5">
      <Inbox size={32} />
      <p className="text-[13px]">{message}</p>
    </div>
  )
}
