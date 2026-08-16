import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  Brain, Building2, LayoutDashboard, Bot, FlaskConical, Server, Database,
  History, Activity, Terminal, ShieldAlert, Rocket, Settings
} from 'lucide-react'
import { useAgents } from '../context/AgentsContext'

const NavSection = ({ label }) => (
  <div className="px-3 py-2 pt-3 text-[10px] font-medium text-gray-400 uppercase tracking-[0.06em]">
    {label}
  </div>
)

function NavItem({ to, icon: Icon, label, badge }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-2.5 px-3.5 py-1.5 mx-2 rounded-md cursor-pointer text-[13px] transition-colors duration-100 ` +
        (isActive
          ? 'bg-indigo-50 text-indigo-700 font-medium'
          : 'text-gray-600 hover:bg-gray-100')
      }
    >
      <Icon size={16} className="flex-shrink-0" />
      <span className="flex-1">{label}</span>
      {badge && (
        <span className="ml-auto bg-indigo-50 text-indigo-700 text-[10px] px-1.5 py-px rounded-full font-medium">
          {badge}
        </span>
      )}
    </NavLink>
  )
}

export default function Sidebar() {
  const { agents, health } = useAgents()
  const project = health?.details?.gcp_project || 'no project set'
  return (
    <div
      className="w-[220px] flex-shrink-0 flex flex-col"
      style={{
        background: 'var(--color-background-primary)',
        borderRight: '0.5px solid #E5E7EB',
        height: '100vh',
      }}
    >
      {/* Logo */}
      <div className="flex items-center  gap-2.5 px-4 py-3 " style={{ borderBottom: '0.5px solid #E5E7EB' }}>
        <div className="w-7 h-7 bg-indigo-600 rounded-md flex items-center justify-center flex-shrink-0">
          <Brain size={15} color="#fff" />
        </div>
        <div>
          <div className="text-[14px] font-medium bold text-gray-900">AgentOps</div>
          
        </div>
      </div>

      {/* Active GCP project (single-project today; no switcher to imply otherwise) */}
      <div
        className="mx-2 my-2 px-2.5 py-1 border rounded-md flex items-center gap-2"
        style={{ borderColor: '#E5E7EB', background: 'var(--color-background-secondary)', borderWidth: '0.5px' }}
        title={project}
      >
        <Building2 size={14} className="text-gray-400" />
        <span className="text-[12px] text-gray-600 flex-1 truncate">{project}</span>
      </div>

      {/* Nav */}
      <div className="flex-1 overflow-y-auto">
        <NavSection label="Platform" />
        <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" />
        <NavItem to="/deployments" icon={Server} label="Deployments" />
        <NavItem to="/agents" icon={Bot} label="Agents" badge={agents.length} />

        {/* "New evaluation" and "New scan" are actions, not destinations, so
            they are buttons on the pages that list what they produce. Jobs and
            History both listed evaluation runs from the same endpoint. */}
        <NavSection label="Evaluation" />
        <NavItem to="/datasets" icon={Database} label="Datasets" />
        <NavItem to="/jobs" icon={FlaskConical} label="Evaluations" />
        <NavItem to="/history" icon={History} label="Compare runs" />

        <NavSection label="Security" />
        <NavItem to="/red-team" icon={ShieldAlert} label="Red team" />

        <NavSection label="Observability" />
        <NavItem to="/traces" icon={Activity} label="Traces" />
        <NavItem to="/logs" icon={Terminal} label="Logs" />

        <NavSection label="Setup" />
        <NavItem to="/onboarding" icon={Rocket} label="Getting started" />
        <NavItem to="/settings" icon={Settings} label="Settings" />
      </div>

    </div>
  )
}
