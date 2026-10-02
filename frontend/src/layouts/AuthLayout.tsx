import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import { useCurrentUser } from '../hooks/useCurrentUser'

export default function AuthLayout() {
  const { user, isLoading } = useCurrentUser()
  const { pathname } = useLocation()

  if (!isLoading && user) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="auth-shell">
      <nav className="auth-nav">
        <Link to="/" className="auth-nav__brand">
          <span className="mark">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
              <path d="M6 12v5c3 3 9 3 12 0v-5" />
            </svg>
          </span>
          <span className="name">InsightScholar</span>
        </Link>
        <div className="auth-nav__links">
          <Link to="/" className="link-muted">Home</Link>
          {pathname !== '/login' && <Link to="/login" className="btn btn--ghost btn--sm">Sign In</Link>}
          {pathname !== '/register' && <Link to="/register" className="btn btn--primary btn--sm">Register School</Link>}
        </div>
      </nav>

      <div className="auth-page">
        <div className="auth-card">
          <Outlet />
        </div>
      </div>

      <footer className="auth-page-footer">
        <nav className="auth-page-footer__links">
          <a href="/legal/about">About</a>
          <a href="/legal/privacy">Privacy</a>
          <a href="/legal/terms">Terms</a>
          <a href="/legal/cookies">Cookies</a>
          <a href="/legal/security">Security</a>
        </nav>
      </footer>
    </div>
  )
}
