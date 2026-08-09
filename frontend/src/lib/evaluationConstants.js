export const JOB_STATUS = ['draft', 'queued', 'running', 'completed', 'failed']

// Only frameworks with real execution behind them. RAGAS was selectable while
// being uninstalled with zero code, which was the same lie as the metric map.
export const FRAMEWORKS = [
  {
    id: 'deepeval',
    name: 'DeepEval',
    description: 'LLM-judged metrics via Gemini on Vertex AI, scored per trace and per sub-agent',
  },
  {
    id: 'deterministic',
    name: 'Deterministic only',
    description: 'String comparison and trace-health checks. No judge calls, no cost.',
  },
]

export const STEPS = [
  { id: 1, label: 'Select Agent' },
  { id: 2, label: 'Select Dataset' },
  { id: 3, label: 'Select Framework' },
  { id: 4, label: 'Select Metrics' },
]

/** Map stored framework values (e.g. vertex_ai) to UI framework ids. */
// Display names for the metrics the backend registry actually serves. The
// previous table labelled fifteen metrics that no longer exist (trajectory
// aliases, final_response_*, multi-turn, custom_llm_metric) and none of the
// current ones. metricLabel falls back to the humanised id for anything new.
export const METRIC_SUMMARY_LABELS = {
  exact_match: 'Exact Match',
  contains_expected: 'Contains Expected',
  response_nonempty: 'Response Non-Empty',
  argument_match: 'Tool Argument Match',
  trajectory_in_order_match: 'Trajectory In-order Match',
  trajectory_any_order_match: 'Trajectory Any-order Match',
  trajectory_precision: 'Trajectory Precision',
  trajectory_recall: 'Trajectory Recall',
  trace_tool_success_rate: 'Tool Success Rate',
  trace_no_redundant_calls: 'No Redundant Tool Calls',
  trace_no_loop: 'No Tool Loop',
  trace_step_efficiency: 'Step Efficiency',
  trace_answered: 'Answered',
  answer_relevancy: 'Answer Relevancy',
  faithfulness: 'Faithfulness',
  contextual_precision: 'Contextual Precision',
  contextual_recall: 'Contextual Recall',
  hallucination: 'Hallucination (inverted)',
  toxicity: 'Non-toxic (inverted)',
  bias: 'Unbiased (inverted)',
  tool_correctness: 'Tool Correctness',
  task_completion: 'Task Completion',
  correctness: 'Correctness',
}

// The metric list is served by the backend registry. This is only the
// fallback used before that fetch resolves; the registry is the source of truth.
export const FALLBACK_METRIC_IDS = [
  'response_nonempty',
  'answer_relevancy',
  'faithfulness',
  'trace_answered',
  'trace_tool_success_rate',
]

export function normalizeFramework(id) {
  if (!id) return 'deepeval'
  const s = String(id).toLowerCase()
  // Legacy runs stored vertex/vertex_ai/ragas before those paths existed.
  if (s === 'vertex_ai' || s === 'vertex' || s === 'ragas') return 'deepeval'
  return s
}

export function frameworkLabel(id) {
  const fw = FRAMEWORKS.find((f) => f.id === normalizeFramework(id))
  return fw?.name || id || '—'
}

export function metricLabel(id) {
  return METRIC_SUMMARY_LABELS[id] || id.replace(/_/g, ' ')
}
