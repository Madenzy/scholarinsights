import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuthActions } from '../../hooks/useCurrentUser'
import { fetchHasSchools } from '../../api/auth'
import { ApiError } from '../../api/client'
import { PasswordInput } from '../../components/PasswordField'

export default function Login() {
  const navigate = useNavigate()
  const { login } = useAuthActions()
  const { data: hasSchoolsData } = useQuery({ queryKey: ['has-schools'], queryFn: fetchHasSchools })
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const result = await login(username, password, remember)
      if (result.mfa_required) {
        navigate('/verify-mfa', { state: { method: result.method }, replace: true })
      } else {
        navigate('/', { replace: true })
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <h1>Sign in</h1>
      <p className="sub">Students, parents, teachers and admins all use this page.</p>

      {error && <div className="alert alert--error mb-4">{error}</div>}

      <form onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              required
              autoFocus
              autoComplete="username"
              placeholder="Your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          <div className="field">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label htmlFor="password">Password</label>
              <Link to="/forgot-password" style={{ fontSize: '12.5px', color: 'var(--primary)' }}>Forgot password?</Link>
            </div>
            <PasswordInput
              id="password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              placeholder="••••••••"
              required
            />
          </div>

          <div className="checkbox-row">
            <input
              type="checkbox"
              id="remember"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            <label htmlFor="remember">Keep me signed in</label>
          </div>

          <button type="submit" className="btn btn--primary btn--lg btn--block" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </div>
      </form>

      {hasSchoolsData && !hasSchoolsData.has_schools ? (
        <div className="auth-divider">
          <p>No schools registered yet.</p>
          <Link to="/register" className="btn btn--ghost btn--block">Register your school</Link>
        </div>
      ) : (
        <p className="auth-footer">
          Is your school not on InsightScholar?{' '}
          <Link to="/register">Register now</Link>
        </p>
      )}
    </>
  )
}
