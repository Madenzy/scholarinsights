import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { forgotPassword } from '../../api/auth'
import { ApiError } from '../../api/client'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const result = await forgotPassword(email)
      setMessage(result.message)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <h1>Forgot password</h1>
      <p className="sub">Enter your account email and we'll send you a link to reset your password.</p>

      {error && <div className="alert alert--error mb-4">{error}</div>}
      {message && <div className="alert alert--info mb-4">{message}</div>}

      {!message && (
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                required
                autoFocus
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <button type="submit" className="btn btn--primary btn--lg btn--block" disabled={submitting}>
              {submitting ? 'Sending…' : 'Send reset link'}
            </button>
          </div>
        </form>
      )}

      <p className="auth-footer">
        <Link to="/login">Back to sign in</Link>
      </p>
    </>
  )
}
