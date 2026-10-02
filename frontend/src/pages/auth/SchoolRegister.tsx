import { useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { schoolRegister } from '../../api/auth'
import { ApiError } from '../../api/client'
import { PasswordInput } from '../../components/PasswordField'

const DEFAULT_THEME_COLOR = '#4f46e5'

export default function SchoolRegister() {
  const navigate = useNavigate()
  const formRef = useRef<HTMLFormElement>(null)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const formData = new FormData(formRef.current!)
      await schoolRegister(formData)
      navigate('/verify-email')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 560, width: '100%' }}>
      <h1>Register your school</h1>
      <p className="sub">Set up your school and create the administrator account.</p>

      {error && <div className="alert alert--error mb-4">{error}</div>}

      <form ref={formRef} onSubmit={handleSubmit} encType="multipart/form-data">
        <div className="form-grid">
          <p style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.1em', color: 'var(--muted)', margin: '8px 0 -8px' }}>
            School Information
          </p>

          <div className="field">
            <label htmlFor="school_name">School Name *</label>
            <input id="school_name" name="school_name" type="text" required placeholder="e.g. Greenwood High School" />
          </div>
          <div className="form-row">
            <div className="field">
              <label htmlFor="school_email">School Email *</label>
              <input id="school_email" name="school_email" type="email" required placeholder="info@school.edu" />
            </div>
            <div className="field">
              <label htmlFor="school_phone">Phone</label>
              <input id="school_phone" name="school_phone" type="tel" placeholder="+1 555 000 0000" />
            </div>
          </div>
          <div className="field">
            <label htmlFor="school_address">Address</label>
            <input id="school_address" name="school_address" type="text" placeholder="123 School Road, City" />
          </div>
          <div className="form-row">
            <div className="field">
              <label htmlFor="logo">School Logo</label>
              <input id="logo" name="logo" type="file" accept=".png,.jpg,.jpeg,.webp,.svg" />
              <span className="hint">PNG, JPG, WEBP or SVG, up to 2MB. Optional: shown in your sidebar and portal.</span>
            </div>
            <div className="field" style={{ maxWidth: 160 }}>
              <label htmlFor="theme_color">Theme Color</label>
              <input
                id="theme_color"
                name="theme_color"
                type="color"
                defaultValue={DEFAULT_THEME_COLOR}
                style={{ height: 42, padding: 4, cursor: 'pointer' }}
              />
            </div>
          </div>

          <p style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.1em', color: 'var(--muted)', margin: '8px 0 -8px' }}>
            Administrator Account
          </p>

          <div className="field">
            <label htmlFor="full_name">Your Full Name</label>
            <input id="full_name" name="full_name" type="text" placeholder="Jane Smith" />
          </div>
          <div className="form-row">
            <div className="field">
              <label htmlFor="username">Username *</label>
              <input id="username" name="username" type="text" required autoComplete="username" placeholder="admin" />
            </div>
            <div className="field">
              <label htmlFor="email">Email *</label>
              <input id="email" name="email" type="email" required placeholder="you@school.edu" />
            </div>
          </div>
          <div className="field">
            <label htmlFor="password">Password *</label>
            <PasswordInput
              id="password"
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              placeholder="Min. 12 characters"
              required
            />
            <span className="hint">At least 12 characters, with an uppercase letter, a lowercase letter, a number, and a special character.</span>
          </div>

          <button type="submit" className="btn btn--primary btn--lg" style={{ width: '100%', justifyContent: 'center', marginTop: 4 }} disabled={submitting}>
            {submitting ? 'Registering…' : 'Register School'}
          </button>
          <p style={{ textAlign: 'center', fontSize: 13, color: 'var(--muted)', margin: 0 }}>
            Already registered? <Link to="/login" style={{ color: 'var(--primary)', fontWeight: 600 }}>Sign in</Link>
          </p>
        </div>
      </form>
    </div>
  )
}
