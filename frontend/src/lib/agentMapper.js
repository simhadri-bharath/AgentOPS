const PLATFORM_MAP = {
  vertex_ai: { label: 'Vertex AI', color: 'purple' },
  cloud_run: { label: 'Cloud Run', color: 'blue' },
  gke: { label: 'GKE', color: 'amber' },
}

const ICON_COLORS = ['purple', 'blue', 'teal', 'amber', 'indigo']

export function formatRelativeTime(iso) {
  if (!iso) return '—'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return '—'
  const diffMs = Date.now() - then
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function statusToUi(status) {
  const s = (status || '').toLowerCase()
  if (s === 'healthy') return 'Healthy'
  if (s === 'inactive') return 'Inactive'
  if (s === 'degraded') return 'Degraded'
  if (s === 'unknown') return 'Unknown'
  return status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown'
}

function deploymentInfo(deploymentType) {
  return (
    PLATFORM_MAP[deploymentType] || {
      label: deploymentType || 'Unknown',
      color: 'gray',
    }
  )
}

/** Map backend AgentRead JSON to the UI shape used across pages. */
export function mapApiAgent(agent, index = 0) {
  const platform = deploymentInfo(agent.deployment_type)
  const meta = agent.metadata || {}
  const labels = meta.labels || {}
  const toolKeys = Object.keys(labels).filter((k) => !['model', 'model_name'].includes(k))

  return {
    id: String(agent.id),
    name: agent.display_name || agent.name,
    slug: agent.name,
    region: agent.region || '—',
    platform: platform.label,
    platformColor: platform.color,
    model: agent.model_name || '—',
    status: statusToUi(agent.status),
    lastActive: formatRelativeTime(agent.last_seen_at),
    lastEvalScore: null,
    lastEvalStatus: null,
    iconColor: platform.color || ICON_COLORS[index % ICON_COLORS.length],
    endpoint: agent.endpoint_url || '—',
    framework: meta.framework || 'Google ADK',
    project: agent.gcp_project || '—',
    tools: toolKeys.length ? toolKeys.join(', ') : '—',
    source: agent.source,
    discoveredAt: agent.discovered_at,
    lastSeenAt: agent.last_seen_at,
    metadata: meta,
    stats: {
      latencyP50: '—',
      latencyP95: '—',
      tokenUsage: '—',
      tokenDelta: '—',
      errorRate: '—',
      errorCount: '—',
      lastEvalRun: '—',
    },
    toolUsage: [],
    _raw: agent,
  }
}

export function countByDeploymentType(agents) {
  const counts = { vertex_ai: 0, cloud_run: 0, gke: 0, other: 0 }
  for (const a of agents) {
    const key = a._raw?.deployment_type || ''
    if (key in counts) counts[key] += 1
    else counts.other += 1
  }
  return counts
}
