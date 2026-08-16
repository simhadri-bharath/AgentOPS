import React, { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AgentsProvider } from './context/AgentsContext'
import { loadScoringConfig } from './lib/redteamScoring'
import { TracesProvider } from './context/TracesContext'
import AppLayout from './layouts/AppLayout'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import AgentDetail from './pages/AgentDetail'
import Deployments from './pages/Deployments'
import Datasets from './pages/Datasets'
import Evaluation from './pages/Evaluation'
import JobsPage from './pages/JobsPage'
import JobDetailsPage from './pages/JobDetailsPage'
import Results from './pages/Results'
import EvaluationSampleDetail from './pages/EvaluationSampleDetail'
import History from './pages/History'
import Traces from './pages/Traces'
import Logs from './pages/Logs'
import RedTeamDashboard from './pages/redteam/RedTeamDashboard'
import AttackLibrary from './pages/redteam/AttackLibrary'
import RedTeamScan from './pages/redteam/RedTeamScan'
import RedTeamRunResults from './pages/redteam/RedTeamRunResults'
import VulnerabilityDetail from './pages/redteam/VulnerabilityDetail'
import Settings from './pages/Settings'
import Onboarding from './pages/Onboarding'
import NotFound from './pages/NotFound'

export default function App() {
  // Adopt the backend's severity thresholds once, so findings are coloured by
  // the same numbers that produced the verdict.
  useEffect(() => {
    loadScoringConfig()
  }, [])

  return (
    <BrowserRouter>
      <AgentsProvider>
      <TracesProvider>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="deployments" element={<Deployments />} />
          <Route path="agents" element={<Agents />} />
          <Route path="agents/:id" element={<AgentDetail />} />
          <Route path="datasets" element={<Datasets />} />
          <Route path="evaluation" element={<Evaluation />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="jobs/:jobId" element={<JobDetailsPage />} />
          <Route path="results" element={<Navigate to="/history" replace />} />
          <Route path="results/:evaluationId" element={<Results />} />
          <Route
            path="results/:evaluationId/samples/:resultId"
            element={<EvaluationSampleDetail />}
          />
          <Route path="history" element={<History />} />
          <Route path="traces" element={<Traces />} />
          <Route path="logs" element={<Logs />} />
          <Route path="red-team" element={<RedTeamDashboard />} />
          <Route path="red-team/library" element={<AttackLibrary />} />
          <Route path="red-team/scan" element={<RedTeamScan />} />
          <Route path="red-team/runs/:runId" element={<RedTeamRunResults />} />
          <Route
            path="red-team/runs/:runId/vulnerabilities/:resultId"
            element={<VulnerabilityDetail />}
          />
          <Route path="settings" element={<Settings />} />
          <Route path="onboarding" element={<Onboarding />} />
          {/* Inside the layout, so a wrong URL keeps its navigation. */}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
      </TracesProvider>
      </AgentsProvider>
    </BrowserRouter>
  )
}
