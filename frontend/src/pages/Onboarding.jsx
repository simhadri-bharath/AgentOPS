import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, Loader2, Search } from 'lucide-react'
import Badge from '../components/Badge'
import Btn from '../components/Btn'
import PageHeader from '../components/PageHeader'
import { useAgents } from '../context/AgentsContext'

function OnboardStep({ num, title, desc, done, active, action }) {
  return (
    <div
      className="flex items-start gap-3.5 p-4 rounded-lg mb-3"
      style={{
        border: done ? '0.5px solid #86EFAC' : active ? '0.5px solid #4F46E5' : '0.5px solid #E5E7EB',
        background: done ? '#F0FDF4' : active ? '#EEF2FF' : 'white',
      }}
    >
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-medium flex-shrink-0"
        style={{
          background: done ? '#22C55E' : active ? '#4F46E5' : '#EEF2FF',
          color: done || active ? '#fff' : '#4338CA',
        }}
      >
        {done ? <Check size={14} /> : num}
      </div>
      <div className="flex-1">
        <div className="text-[13px] font-medium text-gray-900">{title}</div>
        <div className="text-[12px] text-gray-500 mt-0.5">{desc}</div>
      </div>
      {action}
    </div>
  )
}

export default function Onboarding() {
  const nav = useNavigate()
  const { health, agents, syncing, syncDiscovery, testDiscovery, discoveryTest } = useAgents()
  const [testMessage, setTestMessage] = useState(null)

  const gcpOk = health?.gcp_auth === 'ok'
  const dbOk = health?.database === 'ok'
  const hasAgents = agents.length > 0

  const handleTest = async () => {
    try {
      const result = await testDiscovery()
      setTestMessage(result.message)
    } catch (err) {
      setTestMessage(err.message)
    }
  }

  const handleDiscover = async () => {
    try {
      const summary = await syncDiscovery()
      setTestMessage(
        `Synced ${summary.discovered} engine(s): ${summary.created} created, ${summary.updated} updated.`
      )
    } catch (err) {
      setTestMessage(err.message)
    }
  }

  return (
    <div>
      <PageHeader
        title="Getting started"
        subtitle="Connect your GCP project and discover your agents in 4 steps"
      />

      <div style={{ maxWidth: 560 }}>
        <OnboardStep
          num={1}
          title="Connect GCP project"
          desc="Authenticate via Application Default Credentials (gcloud auth application-default login)"
          done={gcpOk}
          action={
            gcpOk ? (
              <Badge variant="green">Done</Badge>
            ) : (
              <Btn style={{ fontSize: 11 }} onClick={handleTest}>Test connection</Btn>
            )
          }
        />
        <OnboardStep
          num={2}
          title="Database & API health"
          desc="PostgreSQL connected and backend running"
          done={dbOk}
          action={
            dbOk ? <Badge variant="green">Done</Badge> : <Badge variant="amber">Check /health</Badge>
          }
        />
        <OnboardStep
          num={3}
          title="Discover agents"
          desc="Sync Vertex AI Reasoning Engines into the agent registry"
          done={hasAgents}
          active={!hasAgents}
          action={
            <Btn primary style={{ fontSize: 11 }} onClick={handleDiscover} disabled={syncing}>
              {syncing ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
              {syncing ? 'Discovering…' : 'Discover now'}
            </Btn>
          }
        />
        <OnboardStep
          num={4}
          title="Browse discovered agents"
          desc="View agent details, endpoints, and deployment metadata"
          done={hasAgents}
          action={
            <Btn onClick={() => nav('/agents')} style={{ fontSize: 11 }} disabled={!hasAgents}>
              View agents →
            </Btn>
          }
        />

        {(testMessage || discoveryTest?.message) && (
          <div className="mt-2 px-3 py-2 rounded-lg text-[12px] bg-indigo-50 text-indigo-900 border border-indigo-100">
            {testMessage || discoveryTest.message}
          </div>
        )}
      </div>
    </div>
  )
}
