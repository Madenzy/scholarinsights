import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchPendingRegistration, resendVerificationCode, verifyEmail } from '../../api/auth'
import { ApiError } from '../../api/client'

export default function VerifyEmail() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['pending-registration'], queryFn: fetchPendingRegistration })

  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!isLoading && !data?.pending) {
    return (
      <>
        <h1>Confirm your email</h1>
        <div className="alert alert--error mb-4">Please start your school registration again.</div>
        <p className="auth-footer">
          <Link to="/register">Back to registration</Link>
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
      const result = await verifyEmail(code)
      queryClient.setQueryData(['me'], { user: result.user })
      navigate('/', { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
        if (err.status === 409) {
          setTimeout(() => navigate('/register'), 1500)
        }
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  async function handleResend() {
    setError(null)
    setMessage(null)
    try {
      const result = await resendVerificationCode()
      setMessage(result.message)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    }
  }

  return (
    <>
      <h1>Confirm your email</h1>
      <p className="sub">
        We sent a 6-digit code to <strong>{data?.pending?.email}</strong>. Enter it below to finish registering your school.
      </p>

      {error && <div className="alert alert--error mb-4">{error}</div>}
      {message && <div className="alert alert--info mb-4">{message}</div>}

      <form onSubmit={handleVerify}>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="code">Verification code</label>
            <input
              id="code"
              type="text"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              required
              autoFocus
              autoComplete="one-time-code"
              placeholder="123456"
              style={{ letterSpacing: '.3em', textAlign: 'center', fontSize: 20, fontWeight: 600 }}
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn--primary btn--lg btn--block" disabled={submitting}>
            {submitting ? 'Confirming…' : 'Confirm email'}
          </button>
        </div>
      </form>

      <form onSubmit={(e) => { e.preventDefault(); handleResend() }} style={{ marginTop: 4 }}>
        <button type="submit" className="btn btn--ghost btn--lg btn--block">Resend code</button>
      </form>

      <p className="auth-footer">
        <Link to="/register">Start over with a different email</Link>
      </p>
    </>
  )
}
