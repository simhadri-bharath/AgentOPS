import React from 'react'
import { AlertTriangle } from 'lucide-react'
import { Card, CardHeader } from './Card'
import Badge from './Badge'

const fmt = (n) => (typeof n === 'number' ? n.toLocaleString() : '—')

const money = (n) =>
  typeof n === 'number' ? `$${n < 0.01 ? n.toFixed(4) : n.toFixed(2)}` : '—'

const ms = (n) => (typeof n === 'number' ? `${(n / 1000).toFixed(1)}s` : '—')

const STATE_VARIANT = {
  SUCCESS: 'green',
  AUTH_ERROR: 'red',
  AGENT_ERROR: 'red',
  RATE_LIMITED: 'amber',
  TIMEOUT: 'amber',
  HARVEST_ERROR: 'amber',
  JUDGE_ERROR: 'purple',
  CANCELLED: 'gray',
}

const Cell = ({ label, value, hint }) => (
  <div>
    <div className="text-[11px] text-gray-400">{label}</div>
    <div className="text-[15px] font-medium text-gray-900">{value}</div>
    {hint && <div className="text-[10px] text-gray-400">{hint}</div>}
  </div>
)

/**
 * What the run cost and how it actually went.
 *
 * The states row matters most: a run can show clean averages while most of its
 * samples never reached the agent, and the average alone would hide that.
 */
export default function RunUsagePanel({ job }) {
  const a = job?.aggregate_scores || {}
  const u = job?.usage || {}
  const cfg = job?.run_config || {}
  const states = a.states || {}
  const failed = Object.entries(states).filter(([k]) => k !== 'SUCCESS')

  if (!Object.keys(a).length && !Object.keys(u).length) return null

  return (
    <Card className="mb-4">
      <CardHeader title="Run profile" />
      <div className="px-3 pb-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
          <Cell
            label="Samples"
            value={`${a.total_invoked ?? '—'} / ${a.total_samples ?? '—'}`}
            hint="invoked / total"
          />
          <Cell
            label="Passed"
            value={
              a.total_passed != null ? `${a.total_passed} / ${a.total_scored}` : '—'
            }
            hint={a.pass_threshold ? `threshold ${a.pass_threshold}` : undefined}
          />
          <Cell
            label="Latency p50 / p95"
            value={`${ms(a.p50_latency_ms)} / ${ms(a.p95_latency_ms)}`}
            hint="per invocation"
          />
          <Cell
            label="Eval cost"
            value={money(u.judge_cost_usd_estimate ?? u.agent_cost_usd_estimate)}
            hint="estimated, not billed"
          />
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
          <Cell
            label="Agent tokens"
            value={`${fmt(u.agent_tokens_in)} / ${fmt(u.agent_tokens_out)}`}
            hint="in / out"
          />
          <Cell label="Tool calls" value={fmt(u.agent_tool_calls)} />
          <Cell label="LLM calls" value={fmt(u.agent_llm_calls)} />
          <Cell
            label="Judge evaluations"
            value={`${fmt(u.judge_metric_evaluations)} + ${fmt(
              u.judge_span_evaluations,
            )}`}
            hint="metric + per sub-agent"
          />
        </div>

        {failed.length > 0 && (
          <div className="mb-3 px-3 py-2 rounded-lg text-[12px] bg-amber-50 text-amber-900 border border-amber-200">
            <div className="flex items-center gap-1.5 font-medium mb-1">
              <AlertTriangle size={13} />
              Not every sample reached the agent
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(states).map(([state, count]) => (
                <Badge key={state} variant={STATE_VARIANT[state] || 'gray'}>
                  {state} × {count}
                </Badge>
              ))}
            </div>
            <div className="mt-1">
              Scores cover only the samples that ran. JUDGE_ERROR is a scoring
              failure, not an agent failure.
            </div>
          </div>
        )}

        {Object.keys(cfg).length > 0 && (
          <div className="text-[11px] text-gray-400">
            {/* Recorded so a score from months ago is still interpretable. */}
            judge {cfg.evaluator_model} · {cfg.invocation_interface} · dataset v
            {cfg.dataset_version} ({cfg.dataset_review_status}) · metrics v
            {cfg.metric_config_version}
            {cfg.framework_versions?.deepeval
              ? ` · deepeval ${cfg.framework_versions.deepeval}`
              : ''}
          </div>
        )}
      </div>
    </Card>
  )
}
