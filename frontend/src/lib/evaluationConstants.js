export const JOB_STATUS = ['draft', 'queued', 'running', 'completed', 'failed']

export const FRAMEWORKS = [
  { id: 'vertex', name: 'Vertex AI', description: 'Google Vertex AI evaluation metrics' },
  { id: 'ragas', name: 'RAGAS', description: 'RAG assessment framework for LLM apps' },
  { id: 'deepeval', name: 'DeepEval', description: 'LLM evaluation with DeepEval metrics' },
]

export const FRAMEWORK_METRICS = {
  vertex: ['groundedness', 'relevance', 'correctness', 'fluency'],
  ragas: ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall'],
  deepeval: ['hallucination', 'answer_relevancy', 'toxicity'],
}

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

export const DEFAULT_METRICS_STATE = {
  // Deterministic
  exact_match: true,
  contains_expected: true,
  response_nonempty: true,
  response_length: true,
  latency_ms: true,

  // Trajectory
  agent_trajectory_exact_match: true,
  agent_trajectory_in_order_match: true,
  agent_trajectory_any_order_match: true,
  agent_trajectory_precision: false,
  agent_trajectory_recall: true,

  // Final Response Quality
  final_response_quality: true,
  hallucination: false,
  tool_use_quality: true,
  safety: true,
  final_response_match: false,
  final_response_ref_free: true,

  // Multi-Turn Toggle
  include_multi_turn: true,

  // Multi-Turn Metrics
  agent_multi_turn_task_success: true,
  agent_multi_turn_tool_use_quality: false,
  agent_multi_turn_trajectory_quality: true,

  // Custom Metrics
  custom_llm_metric: false,
  custom_code_metric: false,
}

export const METRIC_CATEGORIES = [
  {
    id: 'deterministic',
    category: 'Deterministic Metrics',
    description: 'String-match metrics · no model required',
    metrics: [
      { id: 'exact_match', label: 'Exact Match', enabled: true },
      { id: 'contains_expected', label: 'Contains Expected', enabled: true },
      { id: 'response_nonempty', label: 'Response Non-Empty', enabled: true },
      { id: 'response_length', label: 'Response Length', enabled: true },
      { id: 'latency_ms', label: 'Latency', enabled: true },
    ]
  },
  {
    id: 'trajectory',
    category: 'Trajectory Metrics',
    description: 'Tool-call path evaluation · no model required',
    notice: 'Requires reference_trajectory and predicted_trajectory columns in dataset',
    metrics: [
      { id: 'agent_trajectory_exact_match', label: 'Exact Match', description: 'agent_trajectory_exact_match', enabled: true },
      { id: 'agent_trajectory_in_order_match', label: 'In-order Match', description: 'agent_trajectory_in_order_match', enabled: true },
      { id: 'agent_trajectory_any_order_match', label: 'Any-order Match', description: 'agent_trajectory_any_order_match', enabled: true },
      { id: 'agent_trajectory_precision', label: 'Precision', description: 'agent_trajectory_precision', enabled: false },
      { id: 'agent_trajectory_recall', label: 'Recall', description: 'agent_trajectory_recall', enabled: true },
    ]
  },
  {
    id: 'final_response_quality',
    category: 'Final Response Quality Metrics',
    description: 'Vertex AI managed LLM-as-a-Judge metrics',
    notice: 'Judge model is managed internally by Vertex AI. No configuration required.',
    subsections: [
      {
        id: 'single_turn',
        label: 'Single-turn',
        metrics: [
          { id: 'final_response_quality', label: 'Final Response Quality', description: 'Adaptive rubric', enabled: true },
          { id: 'hallucination', label: 'Hallucination', description: 'Static rubric', enabled: false },
          { id: 'tool_use_quality', label: 'Tool Use Quality', description: 'Static rubric', enabled: true },
          { id: 'safety', label: 'Safety', description: 'Binary · static rubric', enabled: true },
          { id: 'final_response_match', label: 'Final Response Match', description: 'Needs reference output', enabled: false },
          { id: 'final_response_ref_free', label: 'Final Response Ref-Free', description: 'No reference needed', enabled: true },
        ]
      },
      {
        id: 'multi_turn',
        label: 'Multi-turn',
        isMultiTurn: true,
        metrics: [
          { id: 'agent_multi_turn_task_success', label: 'Multi-Turn Task Success', description: 'agent_multi_turn_task_success', enabled: true },
          { id: 'agent_multi_turn_tool_use_quality', label: 'Multi-Turn Tool Use Quality', description: 'agent_multi_turn_tool_use_quality', enabled: false },
          { id: 'agent_multi_turn_trajectory_quality', label: 'Multi-Turn Trajectory Quality', description: 'agent_multi_turn_trajectory_quality', enabled: true },
        ]
      }
    ]
  },
  {
    id: 'custom',
    category: 'Custom Metrics',
    description: 'Define your own evaluation logic',
    isCustom: true,
    metrics: [
      { id: 'custom_llm_metric', label: 'Custom LLM Metric', description: 'Uses LLM to judge responses', enabled: false, type: 'llm' },
      { id: 'custom_code_metric', label: 'Custom Code Metric', description: 'Uses Python evaluation logic', enabled: false, type: 'code' },
    ]
  }
]

/** Flat list of all app metrics (excludes custom LLM/code metrics). */
export function collectApplicationMetricIds() {
  const ids = []
  for (const cat of METRIC_CATEGORIES) {
    if (cat.isCustom) continue
    for (const m of cat.metrics ?? []) {
      ids.push(m.id)
    }
    for (const sub of cat.subsections ?? []) {
      for (const m of sub.metrics ?? []) {
        ids.push(m.id)
      }
    }
  }
  return ids
}

export const APPLICATION_METRICS = collectApplicationMetricIds()

export function normalizeFramework(id) {
  if (!id) return 'vertex'
  const s = String(id).toLowerCase()
  if (s === 'vertex_ai' || s === 'vertex') return 'vertex'
  if (s === 'ragas') return 'ragas'
  if (s === 'deepeval') return 'deepeval'
  return s
}

export function frameworkLabel(id) {
  const fw = FRAMEWORKS.find((f) => f.id === normalizeFramework(id))
  return fw?.name || id || '—'
}

export function metricLabel(id) {
  return METRIC_SUMMARY_LABELS[id] || METRIC_LABELS[id] || id.replace(/_/g, ' ')
}
