export interface School {
  id: number
  name: string
  logo_url: string | null
}

export interface CurrentUser {
  id: number
  username: string
  email: string
  full_name: string | null
  display_name: string
  role: 'super_admin' | 'school_admin' | 'teacher' | 'student' | 'parent'
  is_super_admin: boolean
  is_admin: boolean
  is_staff: boolean
  is_portal_user: boolean
  school: School | null
}

export interface DashboardStats {
  students: number
  reports: number
  classes: number
  subjects: number
}

export interface RecentReport {
  id: number
  student_name: string
  term_name: string
  status: 'draft' | 'published'
  average_score: number | null
  overall_grade: string
  created_at: string
}

export interface DashboardData {
  stats: DashboardStats
  recent_reports: RecentReport[]
}
