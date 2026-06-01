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
  return METRIC_LABELS[id] || id.replace(/_/g, ' ')
}
