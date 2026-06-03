import { Navigate } from 'react-router-dom'

/** @deprecated Use /red-team dashboard */
export default function RedTeaming() {
  return <Navigate to="/red-team" replace />
}
