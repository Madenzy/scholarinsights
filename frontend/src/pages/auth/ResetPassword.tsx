import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { checkResetToken, resetPassword } from '../../api/auth'
import { ApiError } from '../../api/client'
import { PasswordInput } from '../../components/PasswordField'

export default function ResetPassword() {
  const { token = '' } = useParams<{ token: string }>()
  const { data: check, isLoading: checking } = useQuery({
    queryKey: ['reset-token', token],
    queryFn: () => checkResetToken(token),
  })

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (check && !check.valid) {
      setError(check.error ?? 'This password reset link is invalid.')
    }
  }, [check])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await resetPassword(token, password, confirm)
      setDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <h1>Reset password</h1>
      <p className="sub">Choose a new password for your account.</p>

      {error && <div className="alert alert--error mb-4">{error}</div>}
      {done && <div className="alert alert--success mb-4">Your password has been reset. Please sign in.</div>}

      {!checking && check?.valid && !done && (
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="password">New password</label>
              <PasswordInput
                id="password"
                value={password}
                onChange={setPassword}
                autoComplete="new-password"
                placeholder="Min. 12 characters"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="confirm">Confirm new password</label>
              <PasswordInput
                id="confirm"
                value={confirm}
                onChange={setConfirm}
                autoComplete="new-password"
                placeholder="Repeat the password"
                required
              />
            </div>
            <button type="submit" className="btn btn--primary btn--lg btn--block" disabled={submitting}>
              {submitting ? 'Resetting…' : 'Reset password'}
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
