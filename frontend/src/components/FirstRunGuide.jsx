import React from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Circle } from 'lucide-react'
import { Card } from './Card'
import Btn from './Btn'

/**
 * What to do first.
 *
 * With no agents onboarded the dashboard is all empty charts, which tells a new
 * user nothing about where to start. This replaces it with the actual path and
 * marks off the steps that are already done.
 */
export default function FirstRunGuide({ agents = [], datasets = 0, runs = 0 }) {
  const nav = useNavigate()

  const steps = [
    {
      done: agents.length > 0,
      title: 'Onboard an agent',
      detail:
        'Deployments lists what is already running in your GCP project. Pick one, test it, and save it.',
      action: 'Go to Deployments',
      to: '/deployments',
    },
    {
      done: datasets > 0,
      title: 'Build a dataset',
      detail:
        "Turn the agent's own production sessions into evaluation cases — no test data to write by hand.",
      action: 'Go to Agents',
      to: '/agents',
    },
    {
      done: runs > 0,
      title: 'Run an evaluation',
      detail:
        'The metric pack for your agent type is pre-selected. Scores come back with the judge’s reasoning.',
      action: 'New evaluation',
      to: '/evaluation',
    },
  ]

  const next = steps.find((s) => !s.done)
  if (!next) return null

  return (
    <Card className="mb-5">
      <div className="p-5">
        <div className="text-[15px] font-medium text-gray-900 mb-1">
          Get your first result
        </div>
        <div className="text-[12px] text-gray-500 mb-4">
          Three steps. Nothing needs to be installed into your agent.
        </div>

        <div className="space-y-3">
          {steps.map((step) => {
            const isNext = step === next
            return (
              <div
                key={step.title}
                className="flex items-start gap-3 rounded-lg p-3"
                style={{
                  border: isNext ? '1px solid #C7D2FE' : '1px solid transparent',
                  background: isNext ? '#EEF2FF' : 'transparent',
                }}
              >
                {step.done ? (
                  <CheckCircle2 size={16} className="text-green-600 mt-0.5" />
                ) : (
                  <Circle size={16} className="text-gray-300 mt-0.5" />
                )}
                <div className="flex-1">
                  <div
                    className="text-[13px] font-medium"
                    style={{ color: step.done ? '#9CA3AF' : '#111827' }}
                  >
                    {step.title}
                  </div>
                  {!step.done && (
                    <div className="text-[12px] text-gray-500">{step.detail}</div>
                  )}
                </div>
                {isNext && (
                  <Btn primary onClick={() => nav(step.to)} style={{ fontSize: 12 }}>
                    {step.action}
                    <ArrowRight size={13} />
                  </Btn>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </Card>
  )
}
