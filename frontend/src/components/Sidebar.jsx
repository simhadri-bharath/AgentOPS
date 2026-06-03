import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  Brain, Building2, ChevronDown, LayoutDashboard, Bot, FlaskConical,
  BarChart2, History, Briefcase, Activity, Terminal, ShieldAlert, Rocket, Settings, Ellipsis
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

const projects = [
  "my-gcp-project",
  "vertex-ai-platform",
  "agentops-prod",
  "rag-evaluation-system",
  "genai-monitoring",
  "ml-evaluation-suite",
  "production-agents"
];

export default function Sidebar() {
  const { agents} = useAgents()
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

      {/* Workspace selector */}

      
      <div
        className="mx-2 my-2 px-2.5 py-1 border rounded-md flex items-center gap-2 cursor-pointer"
        style={{ borderColor: '#E5E7EB', background: 'var(--color-background-secondary)', borderWidth: '0.5px' }}
      >
        <Building2 size={14} className="text-gray-400" />
        <span className="text-[12px] text-gray-600 flex-1">my-gcp-project</span>
        <ChevronDown size={14} className="text-gray-400" />
      </div>

      {/* Nav */}
      <div className="flex-1 overflow-y-auto">
        <NavSection label="Platform" />
        <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" />
        <NavItem to="/agents" icon={Bot} label="Agents" badge={agents.length} />

        <NavSection label="Evaluation" />
        <NavItem to="/evaluation" icon={FlaskConical} label="New Evaluation" />
       
        
        <NavItem to="/history" icon={History} label="History" />

        <NavSection label="Observability" />
        <NavItem to="/traces" icon={Activity} label="Traces" />
        <NavItem to="/logs" icon={Terminal} label="Logs" />

        <NavSection label="Red team" />
        <NavItem to="/red-team" icon={ShieldAlert} label="Scanner" />
        {/* <NavItem to="/red-team/library" icon={ShieldAlert} label="Attack library" /> */}
        {/* <NavItem to="/red-team/scan" icon={ShieldAlert} label="New scan" /> */}

        <NavSection label="Setup" />
        <NavItem to="/onboarding" icon={Rocket} label="Onboarding" />
        <NavItem to="/settings" icon={Settings} label="Settings" />
      </div>

      {/* Footer */}
      <div style={{ borderTop: '0.5px solid #E5E7EB', padding: '10px' }}>
        <div className="flex items-center gap-2 px-1 py-1 cursor-pointer rounded-md hover:bg-gray-50">
          <div className="w-7 h-6 rounded-full bg-indigo-50 flex items-center justify-center text-[11px] font-medium text-indigo-700 flex-shrink-0">
            JY
          </div>
          <div className="flex-1">
            <div className="text-[12px] font-medium text-gray-900">Jyoti</div>
            <div className="text-[11px] text-gray-400">Admin</div>
          </div>
          <Ellipsis size={14} className="text-gray-400" />
        </div>
      </div>
    </div>
  )
}
