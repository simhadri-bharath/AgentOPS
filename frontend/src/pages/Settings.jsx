import React, { useEffect, useState } from 'react'
import { UserPlus, RefreshCw, Loader2 } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import Btn from '../components/Btn'
import PageHeader from '../components/PageHeader'
import { useAgents } from '../context/AgentsContext'

function SettingRow({ name, desc, children, isLast = false }) {
  return (
    <div
      className="flex items-center justify-between py-3.5"
      style={{ borderBottom: isLast ? 'none' : '0.5px solid #E5E7EB' }}
    >
      <div>
        <div className="text-[13px] font-medium text-gray-900">{name}</div>
        <div className="text-[12px] text-gray-500 mt-0.5">{desc}</div>
      </div>
      {children}
    </div>
  )
}

export default function Settings() {
  const {
    health,
    agents,
    discoveryTest,
    syncing,
    refreshHealth,
    testDiscovery,
    syncDiscovery,
  } = useAgents()
  const [testing, setTesting] = useState(false)

  const projectId =
    discoveryTest?.project_id || agents[0]?.project || health?.details?.project_id || '—'
  const region = discoveryTest?.region || agents[0]?.region || '—'

  useEffect(() => {
    testDiscovery().catch(() => {})
  }, [testDiscovery])

  const handleTest = async () => {
    setTesting(true)
    try {
      await testDiscovery()
      await refreshHealth()
    } finally {
      setTesting(false)
    }
  }

  const handleSync = async () => {
    await syncDiscovery()
    await refreshHealth()
  }

  return (
    <div>
      <PageHeader title="Settings" subtitle="Project configuration and integrations">
        <Btn onClick={handleTest} disabled={testing}>
          {testing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          Test GCP
        </Btn>
        <Btn primary onClick={handleSync} disabled={syncing}>
          {syncing ? 'Syncing…' : 'Sync Agents'}
        </Btn>
      </PageHeader>

      <div className="grid grid-cols-2 gap-4 items-start">
        <div>
          <Card className="mb-4">
            <CardHeader title="GCP connection" />
            <SettingRow name="Project ID" desc={projectId}>
              <Badge variant={health?.gcp_auth === 'ok' ? 'green' : 'amber'}>
                {health?.gcp_auth === 'ok' ? 'Connected' : 'Check ADC'}
              </Badge>
            </SettingRow>
            <SettingRow name="Region" desc={region}>
              <Badge variant="gray">{region}</Badge>
            </SettingRow>
            <SettingRow
              name="Authentication"
              desc="Application Default Credentials (gcloud auth application-default login)"
            >
              <Badge variant={health?.gcp_auth === 'ok' ? 'green' : 'red'}>
                {health?.gcp_auth === 'ok' ? 'Valid' : 'Invalid'}
              </Badge>
            </SettingRow>
            <SettingRow name="Agent discovery (test)" desc={discoveryTest?.message || 'Run Test GCP'} isLast>
              <Badge variant={discoveryTest?.authenticated ? 'green' : 'gray'}>
                {discoveryTest?.authenticated
                  ? `${discoveryTest.engine_count ?? 0} RE / ${discoveryTest.service_count ?? 0} CR`
                  : '—'}
              </Badge>
            </SettingRow>
          </Card>

          <Card>
            <CardHeader title="Backend API" />
            <SettingRow name="Health" desc={`GET /health → ${health?.status || 'unknown'}`}>
              <Badge variant={health?.status === 'healthy' ? 'green' : 'amber'}>
                {health?.status || '—'}
              </Badge>
            </SettingRow>
            <SettingRow name="Database" desc={health?.database || '—'} isLast>
              <Badge variant={health?.database === 'ok' ? 'green' : 'red'}>
                {health?.database === 'ok' ? 'OK' : 'Error'}
              </Badge>
            </SettingRow>
          </Card>
        </div>

        <div>
          <Card className="mb-4">
            <CardHeader title="Discovery API" />
            <SettingRow
              name="Vertex AI sync"
              desc="POST /api/v1/discovery/vertex-ai/sync"
            >
              <Badge variant="purple">
                {agents.filter((a) => a._raw?.deployment_type === 'vertex_ai').length} in DB
              </Badge>
            </SettingRow>
            <SettingRow
              name="Cloud Run sync"
              desc="POST /api/v1/discovery/cloud-run/sync"
            >
              <Badge variant="blue">
                {agents.filter((a) => a._raw?.deployment_type === 'cloud_run').length} in DB
              </Badge>
            </SettingRow>
            <SettingRow
              name="Vertex AI test"
              desc="GET /api/v1/discovery/vertex-ai/test"
            >
              <Badge variant={discoveryTest?.vertex?.authenticated ? 'green' : 'gray'}>
                {discoveryTest?.vertex?.authenticated ? 'OK' : 'Not tested'}
              </Badge>
            </SettingRow>
            <SettingRow
              name="Cloud Run test"
              desc="GET /api/v1/discovery/cloud-run/test"
              isLast
            >
              <Badge variant={discoveryTest?.cloudRun?.authenticated ? 'green' : 'gray'}>
                {discoveryTest?.cloudRun?.authenticated ? 'OK' : 'Not tested'}
              </Badge>
            </SettingRow>
          </Card>

          <Card className="mb-4">
            <CardHeader title="Integrations (coming soon)" />
            <SettingRow name="Cloud Logging" desc="Pull logs via Cloud Logging API">
              <Badge variant="gray">Planned</Badge>
            </SettingRow>
            <SettingRow name="OpenTelemetry" desc="OTLP endpoint for traces">
              <Badge variant="gray">Planned</Badge>
            </SettingRow>
            <SettingRow name="Evaluations" desc="Vertex AI Evaluation API">
              <Badge variant="gray">Planned</Badge>
            </SettingRow>
            <SettingRow name="Slack alerts" desc="Notify on eval failures" isLast>
              <Badge variant="gray">Not set</Badge>
            </SettingRow>
          </Card>

          <Card>
            <CardHeader title="Team" />
            <div className="flex items-center gap-2.5 py-2" style={{ borderBottom: '0.5px solid #E5E7EB' }}>
              <div className="w-7 h-7 rounded-full bg-indigo-50 flex items-center justify-center text-[11px] font-medium text-indigo-700">AK</div>
              <div className="flex-1">
                <div className="text-[12px] font-medium">Arjun Kumar</div>
                <div className="text-[11px] text-gray-500">arjun@company.com</div>
              </div>
              <Badge variant="purple">Admin</Badge>
            </div>
            <Btn style={{ marginTop: 8, fontSize: 11 }}>
              <UserPlus size={12} />Invite member
            </Btn>
          </Card>
        </div>
      </div>
    </div>
  )
}
