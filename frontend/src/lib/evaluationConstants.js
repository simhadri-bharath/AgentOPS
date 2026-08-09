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

export const METRIC_LABELS = {
  groundedness: 'Groundedness',
  relevance: 'Relevance',
  correctness: 'Correctness',
  fluency: 'Fluency',
  faithfulness: 'Faithfulness',
  answer_relevancy: 'Answer relevancy',
  context_precision: 'Context precision',
  context_recall: 'Context recall',
  hallucination: 'Hallucination',
  toxicity: 'Toxicity',
}

export const STEPS = [
  { id: 1, label: 'Select Agent' },
  { id: 2, label: 'Select Dataset' },
  { id: 3, label: 'Select Framework' },
  { id: 4, label: 'Select Metrics' },
]

/** Map stored framework values (e.g. vertex_ai) to UI framework ids. */
export const METRIC_SUMMARY_LABELS = {
  exact_match: 'Exact Match',
  contains_expected: 'Contains Expected',
  response_nonempty: 'Response Non-Empty',
  response_length: 'Response Length',
  latency_ms: 'Latency',
  agent_trajectory_exact_match: 'Trajectory Exact Match',
  agent_trajectory_in_order_match: 'Trajectory In-order Match',
  agent_trajectory_any_order_match: 'Trajectory Any-order Match',
  agent_trajectory_precision: 'Trajectory Precision',
  agent_trajectory_recall: 'Trajectory Recall',
  final_response_quality: 'Final Response Quality',
  hallucination: 'Hallucination',
  tool_use_quality: 'Tool Use Quality',
  safety: 'Safety',
  final_response_match: 'Final Response Match',
  final_response_ref_free: 'Final Response Ref-Free',
  agent_multi_turn_task_success: 'Multi-Turn Task Success',
  agent_multi_turn_tool_use_quality: 'Multi-Turn Tool Use Quality',
  agent_multi_turn_trajectory_quality: 'Multi-Turn Trajectory Quality',
  custom_llm_metric: 'Custom LLM Metric',
  custom_code_metric: 'Custom Code Metric',
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
  return METRIC_SUMMARY_LABELS[id] || METRIC_LABELS[id] || id.replace(/_/g, ' ')
}
