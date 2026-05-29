import React from 'react'
import { RefreshCw } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import Btn from '../components/Btn'
import PageHeader from '../components/PageHeader'
import { logs } from '../data/mockData'
import { useAgents } from '../context/AgentsContext'

const levelColor = { INFO: '#1D4ED8', WARN: '#B45309', ERROR: '#991B1B' }

export default function Logs() {
  const { agents } = useAgents()
  return (
    <div>
      <PageHeader title="Logs" subtitle="Centralized logs from Cloud Run, GKE, and Vertex AI — via Cloud Logging" />

      <Card>
        <div className="flex items-center gap-2 flex-wrap mb-4">
          <input type="search" placeholder="Search logs..." style={{ flex: 1, minWidth: 180 }} />
          <select style={{ width: 130 }}>
            <option>All agents</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          <select style={{ width: 100 }}>
            <option>All levels</option>
            <option>INFO</option>
            <option>WARN</option>
            <option>ERROR</option>
          </select>
          <select style={{ width: 110 }}>
            <option>Last 1 hour</option>
            <option>Last 24h</option>
            <option>Last 7d</option>
          </select>
          <Btn><RefreshCw size={13} />Refresh</Btn>
        </div>

        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
          {logs.map((log, i) => (
            <div
              key={i}
              className="flex items-start gap-2.5 py-1.5"
              style={{ borderBottom: i < logs.length - 1 ? '0.5px solid #E5E7EB' : 'none' }}
            >
              <span className="text-gray-400 whitespace-nowrap flex-shrink-0">{log.time}</span>
              <span
                className="w-11 text-center flex-shrink-0 font-medium"
                style={{ color: levelColor[log.level] || '#6B7280' }}
              >
                {log.level}
              </span>
              <span className="text-gray-500 flex-1 leading-relaxed">{log.msg}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
