import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Card, CardHeader } from '../../components/Card'
import Badge from '../../components/Badge'
import Btn from '../../components/Btn'
import PageHeader from '../../components/PageHeader'
import { Table, THead, Th, Td, TRow } from '../../components/Table'
import * as redteamApi from '../../api/redteam'
import { categoryLabel, severityVariant } from '../../lib/redteamMapper'

export default function AttackLibrary() {
  const qc = useQueryClient()
  const [category, setCategory] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    category: 'prompt_injection',
    severity: 'medium',
    prompt: '',
    expected_behavior: '',
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['redteam', 'test-cases', category],
    queryFn: () =>
      redteamApi.fetchTestCases({
        category: category || undefined,
        source: 'all',
        limit: 200,
      }),
  })

  const createMutation = useMutation({
    mutationFn: redteamApi.createTestCase,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['redteam', 'test-cases'] })
      setShowForm(false)
      setForm({ category: 'prompt_injection', severity: 'medium', prompt: '', expected_behavior: '' })
    },
  })

  const items = data?.items || []

  return (
    <div>
      <PageHeader
        title="Attack library"
        subtitle="Built-in and custom adversarial prompts by category and severity"

      >
        <Btn onClick={() => setShowForm(!showForm)}>Add custom prompt</Btn>
      </PageHeader>

      {error && (
        <div className="mb-4 px-3 py-2 rounded-md text-[12px] bg-red-50 text-red-800">
          {error.message}
        </div>
      )}

      {showForm && (
        <Card className="mb-4">
          <CardHeader title="Custom attack prompt" />
          <div className="p-3 space-y-2">
            <select
              value={form.category}
              onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
              style={{ width: '100%' }}
            >
              {redteamApi.REDTEAM_CATEGORIES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
            <select
              value={form.severity}
              onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))}
              style={{ width: 160 }}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
            <textarea
              placeholder="Attack prompt"
              value={form.prompt}
              onChange={(e) => setForm((f) => ({ ...f, prompt: e.target.value }))}
              rows={3}
              style={{ width: '100%' }}
            />
            <textarea
              placeholder="Expected secure behavior"
              value={form.expected_behavior}
              onChange={(e) => setForm((f) => ({ ...f, expected_behavior: e.target.value }))}
              rows={2}
              style={{ width: '100%' }}
            />
            <Btn
              primary
              disabled={createMutation.isPending || !form.prompt || !form.expected_behavior}
              onClick={() => createMutation.mutate(form)}
            >
              Save to library
            </Btn>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Prompts">
          <select
            style={{ width: 180 }}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {redteamApi.REDTEAM_CATEGORIES.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
        </CardHeader>

        {isLoading ? (
          <div className="flex items-center gap-2 p-4 text-[12px] text-gray-500">
            <Loader2 size={14} className="animate-spin" /> Loading…
          </div>
        ) : (
          <Table>
            <THead>
              <Th>ID</Th>
              <Th>Category</Th>
              <Th>Severity</Th>
              <Th>Source</Th>
              <Th>Prompt</Th>
            </THead>
            <tbody>
              {items.map((row, i) => (
                <TRow key={row.id || row.external_id || i}>
                  <Td>{row.external_id || shortId(row.id) || '—'}</Td>
                  <Td>{categoryLabel(row.category)}</Td>
                  <Td>
                    <Badge variant={severityVariant(row.severity)}>{row.severity}</Badge>
                  </Td>
                  <Td>{row.source}</Td>
                  <Td className="max-w-md truncate">{row.prompt}</Td>
                </TRow>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  )
}

function shortId(id) {
  if (!id) return null
  const s = String(id)
  return s.length > 8 ? `${s.slice(0, 8)}…` : s
}
