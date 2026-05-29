import React from 'react'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import PageHeader from '../components/PageHeader'
import TraceRow from '../components/TraceRow'
import { traces, traceDetail } from '../data/mockData'
import { useAgents } from '../context/AgentsContext'

const statusBadge = (s) => {
  if (s === 'OK') return <Badge variant="green">OK</Badge>
  return <Badge variant="red">Error</Badge>
}

export default function Traces() {
  const { agents } = useAgents()
  return (
    <div>
      <PageHeader title="Traces" subtitle="Execution traces across all agents — powered by OpenTelemetry" />

      <div className="grid grid-cols-2 gap-4 items-start">
        <Card>
          <CardHeader title="Trace list">
            <input type="search" placeholder="Filter..." style={{ width: 140 }} />
            <select style={{ width: 120 }}>
              <option>All agents</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </CardHeader>
          <Table>
            <THead>
              <Th>Trace ID</Th><Th>Agent</Th><Th>Latency</Th><Th>Status</Th>
            </THead>
            <tbody>
              {traces.map((t, i) => (
                <TRow key={t.id} onClick={() => {}} style={i === 0 ? { background: 'var(--color-background-secondary)' } : {}}>
                  <Td style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>{t.id}</Td>
                  <Td>{t.agent}</Td>
                  <Td>{t.latency}</Td>
                  <Td>{statusBadge(t.status)}</Td>
                </TRow>
              ))}
            </tbody>
          </Table>
        </Card>

        <Card>
          <CardHeader title="Trace · tr-a4f92b">
            <Badge variant="blue">1.24s total</Badge>
          </CardHeader>
          {traceDetail.map((t, i) => (
            <TraceRow
              key={i}
              dot={t.color}
              label={t.label}
              meta={t.meta}
              body={t.body}
              time={t.time}
              isLast={i === traceDetail.length - 1}
            />
          ))}
        </Card>
      </div>
    </div>
  )
}
