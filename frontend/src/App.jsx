import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AgentsProvider } from './context/AgentsContext'
import AppLayout from './layouts/AppLayout'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import AgentDetail from './pages/AgentDetail'
import Evaluation from './pages/Evaluation'
import JobsPage from './pages/JobsPage'
import JobDetailsPage from './pages/JobDetailsPage'
import Results from './pages/Results'
import History from './pages/History'
import Traces from './pages/Traces'
import Logs from './pages/Logs'
import RedTeaming from './pages/RedTeaming'
import Settings from './pages/Settings'
import Onboarding from './pages/Onboarding'

export default function App() {
  return (
    <BrowserRouter>
      <AgentsProvider>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="agents" element={<Agents />} />
          <Route path="agents/:id" element={<AgentDetail />} />
          <Route path="evaluation" element={<Evaluation />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="jobs/:jobId" element={<JobDetailsPage />} />
          <Route path="results" element={<Navigate to="/history" replace />} />
          <Route path="results/:evaluationId" element={<Results />} />
          <Route path="history" element={<History />} />
          <Route path="traces" element={<Traces />} />
          <Route path="logs" element={<Logs />} />
          <Route path="red-team" element={<RedTeaming />} />
          <Route path="settings" element={<Settings />} />
          <Route path="onboarding" element={<Onboarding />} />
        </Route>
      </Routes>
      </AgentsProvider>
    </BrowserRouter>
  )
}
