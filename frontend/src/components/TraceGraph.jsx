import React, { useMemo, useCallback } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
} from 'reactflow'
import dagre from 'dagre'
import 'reactflow/dist/style.css'

/* ─── helpers ──────────────────────────────────────────────────────────────── */
function formatDuration(ms) {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60000)
  const s = ((ms % 60000) / 1000).toFixed(0)
  return `${m}m ${s}s`
}

const OP_COLORS = {
  invoke_agent: { bg: '#EEF2FF', border: '#4F46E5', text: '#3730A3' },
  call_llm: { bg: '#FFFBEB', border: '#F59E0B', text: '#92400E' },
  generate_content: { bg: '#F0FDF4', border: '#22C55E', text: '#166534' },
  execute_tool: { bg: '#F0FDFA', border: '#14B8A6', text: '#115E59' },
  send_data: { bg: '#EFF6FF', border: '#3B82F6', text: '#1E40AF' },
  receive_data: { bg: '#FAF5FF', border: '#8B5CF6', text: '#5B21B6' },
  invocation: { bg: '#F8FAFC', border: '#64748B', text: '#334155' },
}

function getOpStyle(name) {
  if (!name) return OP_COLORS.invocation
  const lower = name.toLowerCase()
  for (const [key, style] of Object.entries(OP_COLORS)) {
    if (lower.includes(key)) return style
  }
  return OP_COLORS.invocation
}

/* ─── Custom Node ──────────────────────────────────────────────────────────── */
function SpanNode({ data }) {
  const style = getOpStyle(data.operation || data.label)
  const isSelected = data.isSelected

  return (
    <div
      style={{
        background: isSelected ? style.border : style.bg,
        border: `1.5px solid ${style.border}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 140,
        maxWidth: 200,
        cursor: 'pointer',
        boxShadow: isSelected
          ? `0 0 0 2px ${style.border}40, 0 4px 12px ${style.border}20`
          : '0 1px 3px rgba(0,0,0,0.08)',
        transition: 'all 0.15s ease',
        position: 'relative',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: style.border,
          width: 6,
          height: 6,
          border: '1px solid #fff',
        }}
      />

      {/* Icon + operation */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <div
          style={{
            width: 18,
            height: 18,
            borderRadius: 4,
            background: style.border,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 10, color: '#fff', fontWeight: 700 }}>
            {data.operation === 'invoke_agent' ? 'A' : data.operation === 'call_llm' ? 'L' : 'S'}
          </span>
        </div>
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: isSelected ? '#fff' : style.text,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={data.label}
        >
          {data.label}
        </span>
      </div>

      {/* Agent name */}
      {data.agentName && (
        <div
          style={{
            fontSize: 9,
            color: isSelected ? 'rgba(255,255,255,0.8)' : '#9CA3AF',
            marginBottom: 3,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={data.agentName}
        >
          {data.agentName}
        </div>
      )}

      {/* Duration + model */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 4 }}>
        <span
          style={{
            fontSize: 9,
            fontFamily: "'JetBrains Mono', monospace",
            color: isSelected ? 'rgba(255,255,255,0.9)' : style.text,
            fontWeight: 500,
          }}
        >
          {formatDuration(data.durationMs)}
        </span>
        {data.modelName && (
          <span
            style={{
              fontSize: 8,
              background: isSelected ? 'rgba(255,255,255,0.2)' : `${style.border}15`,
              color: isSelected ? '#fff' : style.text,
              padding: '1px 5px',
              borderRadius: 3,
              fontWeight: 500,
            }}
          >
            {data.modelName}
          </span>
        )}
      </div>

      {/* Token info */}
      {(data.inputTokens || data.outputTokens) && (
        <div
          style={{
            fontSize: 8,
            color: isSelected ? 'rgba(255,255,255,0.7)' : '#9CA3AF',
            marginTop: 3,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {data.inputTokens && `in: ${data.inputTokens}`}
          {data.inputTokens && data.outputTokens && ' · '}
          {data.outputTokens && `out: ${data.outputTokens}`}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: style.border,
          width: 6,
          height: 6,
          border: '1px solid #fff',
        }}
      />
    </div>
  )
}

const nodeTypes = { spanNode: SpanNode }

/* ─── Layout with Dagre ────────────────────────────────────────────────────── */
const NODE_WIDTH = 170
const NODE_HEIGHT = 80

function getLayoutedElements(nodes, edges) {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({
    rankdir: 'LR',
    nodesep: 40,
    ranksep: 60,
    marginx: 30,
    marginy: 30,
  })

  nodes.forEach((node) => {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  })

  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target)
  })

  dagre.layout(g)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = g.node(node.id)
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

/* ─── Main Component ───────────────────────────────────────────────────────── */
export default function TraceGraph({ spanTree, selectedSpanId, onSpanClick }) {
  // Build nodes and edges from span tree
  const { initialNodes, initialEdges } = useMemo(() => {
    const nodes = []
    const edges = []

    function traverse(treeNodes) {
      for (const node of treeNodes || []) {
        const span = node.span
        nodes.push({
          id: span.span_id,
          type: 'spanNode',
          data: {
            label: span.name,
            operation: span.operation || span.name,
            agentName: span.agent_name,
            durationMs: span.duration_ms,
            modelName: span.model_name,
            inputTokens: span.input_tokens,
            outputTokens: span.output_tokens,
            status: span.status,
            isSelected: span.span_id === selectedSpanId,
          },
          position: { x: 0, y: 0 },
        })

        for (const child of node.children || []) {
          edges.push({
            id: `${span.span_id}-${child.span.span_id}`,
            source: span.span_id,
            target: child.span.span_id,
            type: 'smoothstep',
            animated: false,
            style: {
              stroke: '#94A3B8',
              strokeWidth: 1.5,
            },
            markerEnd: {
              type: 'arrowclosed',
              color: '#94A3B8',
              width: 14,
              height: 14,
            },
          })
        }

        traverse(node.children)
      }
    }

    traverse(spanTree)
    return { initialNodes: nodes, initialEdges: edges }
  }, [spanTree, selectedSpanId])

  // Apply dagre layout
  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => getLayoutedElements(initialNodes, initialEdges),
    [initialNodes, initialEdges]
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges)

  // Update nodes when layout changes
  React.useEffect(() => {
    setNodes(layoutedNodes)
    setEdges(layoutedEdges)
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges])

  const handleNodeClick = useCallback(
    (event, node) => {
      if (onSpanClick) {
        onSpanClick(node.id)
      }
    },
    [onSpanClick]
  )

  if (!spanTree || spanTree.length === 0) {
    return (
      <div style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: 12, color: '#9CA3AF' }}>No spans to display</span>
      </div>
    )
  }

  return (
    <div style={{ height: 500, width: '100%', background: '#FAFBFC' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#E2E8F0" gap={20} size={1} />
        <Controls
          style={{
            background: '#fff',
            borderRadius: 6,
            border: '1px solid #E5E7EB',
            boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
          }}
        />
        <MiniMap
          style={{
            background: '#F8FAFC',
            border: '1px solid #E5E7EB',
            borderRadius: 6,
          }}
          nodeColor={(node) => {
            const style = getOpStyle(node.data?.operation)
            return style.border
          }}
          maskColor="rgba(0,0,0,0.08)"
        />
      </ReactFlow>
    </div>
  )
}
