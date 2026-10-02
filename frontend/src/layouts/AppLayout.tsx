import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import { useCurrentUser } from '../hooks/useCurrentUser'

// Portal (student/parent) and Superadmin haven't moved to React yet.
// Their Flask-rendered pages still work fine, so send those roles there
// with a real page load instead of dead-ending inside the SPA.
function legacyAreaFor(user: { is_portal_user: boolean; is_super_admin: boolean }) {
  if (user.is_super_admin) return '/superadmin/'
  if (user.is_portal_user) return '/portal/'
  return null
}

function LegacyRedirect({ to }: { to: string }) {
  useEffect(() => {
    window.location.replace(to)
  }, [to])
  return <div className="content">Redirecting…</div>
}

export default function AppLayout() {
  const { user, isLoading } = useCurrentUser()
  const [navOpen, setNavOpen] = useState(false)

  if (isLoading) {
    return <div className="content">Loading…</div>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  const legacyArea = legacyAreaFor(user)
  if (legacyArea) {
    return <LegacyRedirect to={legacyArea} />
  }

  return (
    <div className="app">
      <Sidebar user={user} open={navOpen} onNavigate={() => setNavOpen(false)} />
      <div className={`sidebar__backdrop${navOpen ? ' open' : ''}`} onClick={() => setNavOpen(false)} />
      <div className="main">
        <button type="button" className="mobile-nav-toggle" aria-label="Open menu" onClick={() => setNavOpen(true)}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <Outlet context={{ user }} />
      </div>
    </div>
  )
}
