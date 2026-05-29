import React, { useState } from 'react'
import { Shield, AlertTriangle } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import Btn from '../components/Btn'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import PageHeader from '../components/PageHeader'
import StatCard from '../components/StatCard'
import { redTeamResults } from '../data/mockData'

const testSuites = [
  { name: 'Prompt injection', desc: 'Attempt to override system prompt', defaultChecked: true },
  { name: 'Jailbreak attempts', desc: 'Role-play and persona bypasses', defaultChecked: true },
  { name: 'PII extraction', desc: 'Attempt to extract private data', defaultChecked: false },
  { name: 'Boundary testing', desc: 'Off-topic and adversarial inputs', defaultChecked: false },
]

const resultBadge = (color) => (r) => <Badge variant={color}>{r}</Badge>

export default function RedTeaming() {
  const [checks, setChecks] = useState(testSuites.map(t => t.defaultChecked))

  return (
    <div>
      <PageHeader title="Red teaming" subtitle="Basic AI safety and security testing — prompt injection, jailbreak, and boundary tests" />

      {/* Warning banner */}
      <div
        className="flex items-center gap-2 px-3.5 py-2.5 rounded-md text-[12px] mb-4"
        style={{ background: '#FEF3C7', border: '0.5px solid #FCD34D', color: '#92400E' }}
      >
        <AlertTriangle size={16} className="flex-shrink-0" />
        MVP feature — tests run against a live agent endpoint. Review results before acting.
      </div>

      <div className="grid grid-cols-2 gap-4 items-start">
        <Card>
          <CardHeader title="Configure test" />
          <div className="mb-3">
            <label className="block text-[11px] font-medium text-gray-500 uppercase tracking-[0.04em] mb-1 mt-2">Target agent</label>
            <select style={{ width: '100%' }}>
              <option>rag-assistant</option>
              <option>sql-agent</option>
            </select>
          </div>
          <label className="block text-[11px] font-medium text-gray-500 uppercase tracking-[0.04em] mb-1 mt-2">Test suite</label>
          {testSuites.map((t, i) => (
            <div
              key={i}
              className="flex items-center justify-between px-3.5 py-2.5 rounded-md mb-2 cursor-pointer text-[12px]"
              style={{ border: '0.5px solid #E5E7EB' }}
              onClick={() => setChecks(c => c.map((v, j) => j === i ? !v : v))}
            >
              <div>
                <div className="font-medium text-gray-900">{t.name}</div>
                <div className="text-[11px] text-gray-500 mt-0.5">{t.desc}</div>
              </div>
              <input type="checkbox" checked={checks[i]} onChange={() => {}} />
            </div>
          ))}
          <Btn
            primary
            style={{ width: '100%', justifyContent: 'center', marginTop: 12, padding: '10px' }}
          >
            <Shield size={13} />Run security scan
          </Btn>
        </Card>

        <Card>
          <CardHeader title="Last scan · rag-assistant">
            <Badge variant="amber">2 issues</Badge>
          </CardHeader>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <StatCard label="Tested" value="24" />
            <StatCard label="Passed" value="22" valueStyle={{ color: '#22C55E' }} />
          </div>
          <Table>
            <THead>
              <Th>Test</Th><Th>Result</Th><Th>Severity</Th>
            </THead>
            <tbody>
              {redTeamResults.map((r, i) => (
                <TRow key={i}>
                  <Td>{r.test}</Td>
                  <Td><Badge variant={r.resultColor}>{r.result}</Badge></Td>
                  <Td><Badge variant={r.sevColor}>{r.severity}</Badge></Td>
                </TRow>
              ))}
            </tbody>
          </Table>
        </Card>
      </div>
    </div>
  )
}
