import React from 'react'
import { Check } from 'lucide-react'
import { STEPS } from '../../lib/evaluationConstants'

export default function Stepper({ currentStep }) {
  return (
    <nav className="flex flex-col gap-1">
      {STEPS.map((step) => {
        const done = currentStep > step.id
        const active = currentStep === step.id
        return (
          <div
            key={step.id}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] transition-colors ${
              active
                ? 'bg-indigo-50 text-indigo-700 font-medium'
                : done
                  ? 'text-gray-700'
                  : 'text-gray-400'
            }`}
          >
            <span
              className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] flex-shrink-0 ${
                active
                  ? 'bg-indigo-600 text-white'
                  : done
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-400'
              }`}
            >
              {done ? <Check size={12} /> : step.id}
            </span>
            <span>{step.label}</span>
          </div>
        )
      })}
    </nav>
  )
}
