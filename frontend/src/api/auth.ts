import { api } from './client'
import type { CurrentUser } from '../types'

export type MfaMethod = 'totp' | 'email'

export type LoginResult =
  | { user: CurrentUser; mfa_required?: undefined }
  | { mfa_required: true; method: MfaMethod; user?: undefined }

export function fetchMe() {
  return api.get<{ user: CurrentUser | null }>('/api/auth/me')
}

export function login(username: string, password: string, remember: boolean) {
  return api.post<LoginResult>('/api/auth/login', { username, password, remember })
}

export function verifyMfa(code: string) {
  return api.post<{ user: CurrentUser }>('/api/auth/login/mfa-verify', { code })
}

export function resendMfaCode() {
  return api.post<{ message: string }>('/api/auth/login/mfa-resend')
}

export function logout() {
  return api.post<{ ok: true }>('/api/auth/logout')
}

export function fetchHasSchools() {
  return api.get<{ has_schools: boolean }>('/api/auth/has-schools')
}

export function forgotPassword(email: string) {
  return api.post<{ message: string }>('/api/auth/forgot-password', { email })
}

export function checkResetToken(token: string) {
  return api.get<{ valid: boolean; error?: string }>(`/api/auth/reset-password/${token}`)
}

export function resetPassword(token: string, password: string, confirm: string) {
  return api.post<{ message: string }>(`/api/auth/reset-password/${token}`, { password, confirm })
}

export function schoolRegister(formData: FormData) {
  return api.post<{ message: string; email: string }>('/api/auth/school-register', formData)
}

export function fetchPendingRegistration() {
  return api.get<{ pending: { email: string } | null }>('/api/auth/pending-registration')
}

export function resendVerificationCode() {
  return api.post<{ message: string }>('/api/auth/verify-email/resend')
}

export function verifyEmail(code: string) {
  return api.post<{ user: CurrentUser }>('/api/auth/verify-email', { code })
}
