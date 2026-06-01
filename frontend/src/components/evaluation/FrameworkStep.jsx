import React from 'react'
import { FRAMEWORKS } from '../../lib/evaluationConstants'

export default function FrameworkStep({
  selectedFramework,
  onSelect,
}) {
  return (
    <div className="grid grid-cols-2 gap-3">

      {FRAMEWORKS.map((fw) => {
        const selected =
          selectedFramework?.id === fw.id

        return (
          <button
            key={fw.id}
            type="button"
            onClick={() => onSelect(fw)}
            className={`
              rounded-xl
              border
              px-4
              py-3
              text-left
              transition-all
              ${
                selected
                  ? 'border-indigo-500 bg-indigo-50 ring-1 ring-indigo-500'
                  : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50'
              }
            `}
            style={{ borderWidth: '0.5px' }}
          >

            {/* FRAMEWORK NAME */}

            <div className="text-[13px] font-semibold text-gray-900">
              {fw.name}
            </div>

            {/* DESCRIPTION */}

            <div className="mt-1 line-clamp-2 text-[11px] leading-5 text-gray-500">
              {fw.description}
            </div>
          </button>
        )
      })}
    </div>
  )
}