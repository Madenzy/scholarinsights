import { api } from './client'
import type { DashboardData } from '../types'

export function fetchDashboard() {
  return api.get<DashboardData>('/api/dashboard/')
}
