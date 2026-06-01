import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Plus } from 'lucide-react'
import { Card, CardHeader } from '../components/Card'
import Badge from '../components/Badge'
import Btn from '../components/Btn'
import EmptyState from '../components/EmptyState'
import PageHeader from '../components/PageHeader'
import { Table, THead, Th, Td, TRow } from '../components/Table'
import * as evaluationsApi from '../api/evaluations'
import { formatRelativeTime } from '../lib/agentMapper'
import { frameworkLabel } from '../lib/evaluationConstants'
import { runStatusLabel, runStatusVariant } from '../lib/evaluationMapper'

export default function JobsPage() {
  const nav = useNavigate()
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await evaluationsApi.fetchJobs({ limit: 100 })
      setJobs(data.items || [])
    } catch (err) {
      setError(err.message || 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const statusBadge = (job) => (
    <Badge variant={runStatusVariant(job.status, job.aggregate_scores)}>
      {runStatusLabel(job.status)}
    </Badge>
  )

  return (
    <div>
      <PageHeader title="Evaluation Jobs" subtitle="Draft and completed evaluation jobs">
        <Btn primary onClick={() => nav('/evaluation')}>
          <Plus size={13} />
          New Evaluation
        </Btn>
      </PageHeader>

      {error && (
        <div className="mb-4 px-3 py-2 rounded-md text-[12px] bg-red-50 text-red-800">
          {error}
        </div>
      )}

      <Card>
        <CardHeader title="All jobs">
          <Btn style={{ fontSize: 11 }} onClick={load}>
            Refresh
          </Btn>
        </CardHeader>

        {loading ? (
          <div className="flex items-center gap-2 text-[12px] text-gray-500 p-4">
            <Loader2 size={14} className="animate-spin" />
            Loading jobs…
          </div>
        ) : jobs.length === 0 ? (
          <EmptyState message="No evaluation jobs yet. Create one from New Evaluation." />
        ) : (
          <Table>
            <THead>
              <Th>Job Name</Th>
              <Th>Status</Th>
              <Th>Framework</Th>
              <Th>Created</Th>
            </THead>
            <tbody>
              {jobs.map((job) => (
                <TRow key={job.id} onClick={() => nav(`/jobs/${job.id}`)}>
                  <Td className="font-medium">{job.name}</Td>
                  <Td>{statusBadge(job)}</Td>
                  <Td>{frameworkLabel(job.framework)}</Td>
                  <Td style={{ color: '#6B7280' }}>{formatRelativeTime(job.created_at)}</Td>
                </TRow>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  )
}
