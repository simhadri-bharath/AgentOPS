import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Card } from '../components/Card'
import Btn from '../components/Btn'

/**
 * Any unmatched URL used to render an empty white page with no navigation and
 * nothing to say what happened -- indistinguishable from a crash.
 */
export default function NotFound() {
  const { pathname } = useLocation()
  return (
    <Card>
      <div className="p-8 text-center">
        <div className="text-[18px] font-medium text-gray-900 mb-1">Page not found</div>
        <div className="text-[13px] text-gray-500 mb-5">
          Nothing is routed at{' '}
          <span style={{ fontFamily: 'var(--font-mono)' }}>{pathname}</span>.
        </div>
        <div className="flex justify-center gap-2">
          <Link to="/dashboard">
            <Btn primary>Back to dashboard</Btn>
          </Link>
          <Link to="/jobs">
            <Btn>Evaluations</Btn>
          </Link>
        </div>
      </div>
    </Card>
  )
}
