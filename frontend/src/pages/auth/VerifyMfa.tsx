import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { resendMfaCode, verifyMfa, type MfaMethod } from '../../api/auth'
import { ApiError } from '../../api/client'
import { useAuthActions } from '../../hooks/useCurrentUser'

export default function VerifyMfa() {
  const navigate = useNavigate()
  const location = useLocation()
  const { completeMfaLogin } = useAuthActions()
  const method = (location.state as { method?: MfaMethod } | null)?.method

  const [code, setCode] = useState('')
  const [useBackupCode, setUseBackupCode] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!method) {
    return (
      <>
        <h1>Verify it's you</h1>
        <div className="alert alert--error mb-4">Your login session expired. Please log in again.</div>
        <p className="auth-footer">
          <Link to="/login">Back to sign in</Link>
        </p>
      </>
    )
  }

  async function handleVerify(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setMessage(null)
    setSubmitting(true)
    try {
      const result = await verifyMfa(code)
      completeMfaLogin(result.user)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleResend() {
    setError(null)
    setMessage(null)
    try {
      const result = await resendMfaCode()
      setMessage(result.message)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    }
  }

  return (
    <>
      <h1>Verify it's you</h1>
      <p className="sub">
        {useBackupCode
          ? 'Enter one of your backup codes.'
          : method === 'totp'
            ? 'Enter the 6-digit code from your authenticator app.'
            : 'Enter the code we emailed you.'}
      </p>

      {error && <div className="alert alert--error mb-4">{error}</div>}
      {message && <div className="alert alert--info mb-4">{message}</div>}

      <form onSubmit={handleVerify}>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="code">{useBackupCode ? 'Backup code' : 'Code'}</label>
            <input
              id="code"
              type="text"
              inputMode={useBackupCode ? 'text' : 'numeric'}
              maxLength={useBackupCode ? 12 : 6}
              required
              autoFocus
              autoComplete="one-time-code"
              placeholder={useBackupCode ? 'XXXXXXXX-XXXX' : '123456'}
              style={{ letterSpacing: '.2em', textAlign: 'center', fontSize: 20, fontWeight: 600 }}
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn--primary btn--lg btn--block" disabled={submitting}>
            {submitting ? 'Verifying…' : 'Verify'}
          </button>
        </div>
      </form>

      {method === 'email' && !useBackupCode && (
        <form onSubmit={(e) => { e.preventDefault(); handleResend() }} style={{ marginTop: 4 }}>
          <button type="submit" className="btn btn--ghost btn--lg btn--block">Resend code</button>
        </form>
      )}

      <p className="auth-footer">
        <button
          type="button"
          onClick={() => { setUseBackupCode((v) => !v); setCode(''); setError(null) }}
          style={{ background: 'none', border: 'none', padding: 0, color: 'var(--primary)', cursor: 'pointer', font: 'inherit' }}
        >
          {useBackupCode ? 'Use your authenticator or email code instead' : 'Use a backup code instead'}
        </button>
      </p>
      <p className="auth-footer">
        <Link to="/login">Back to sign in</Link>
      </p>
    </>
  )
}
