import type { ReactElement } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useOutletContext } from 'react-router-dom'
import { fetchDashboard } from '../../api/dashboard'
import type { CurrentUser } from '../../types'

export default function Dashboard() {
  const { user } = useOutletContext<{ user: CurrentUser }>()
  const { data, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: fetchDashboard })

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p className="sub">Welcome back, {user.display_name}</p>
        </div>
        <Link to="/reports/generate" className="btn btn--primary">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Report
        </Link>
      </div>

      <div className="content">
        <div className="stats-grid">
          <StatCard icon="students" label="Students" value={data?.stats.students} loading={isLoading} />
          <StatCard icon="reports" label="Reports" value={data?.stats.reports} loading={isLoading} />
          <StatCard icon="classes" label="Classes" value={data?.stats.classes} loading={isLoading} />
          <StatCard icon="subjects" label="Subjects" value={data?.stats.subjects} loading={isLoading} />
        </div>

        <div className="card mb-4">
          <div className="card-header">
            <h2>Recent Reports</h2>
            <Link to="/reports" className="btn btn--ghost btn--sm">View all</Link>
          </div>
          {isLoading ? (
            <div className="empty-state"><p>Loading…</p></div>
          ) : data && data.recent_reports.length > 0 ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Student</th><th>Term</th><th>Status</th><th>Average</th><th>Grade</th></tr>
                </thead>
                <tbody>
                  {data.recent_reports.map((r) => (
                    <tr key={r.id}>
                      <td><Link to={`/reports/${r.id}`} className="link-primary">{r.student_name}</Link></td>
                      <td>{r.term_name}</td>
                      <td>
                        <span className={`badge ${r.status === 'published' ? 'badge--green' : 'badge--yellow'}`}>
                          {r.status === 'published' ? 'Published' : 'Draft'}
                        </span>
                      </td>
                      <td>{r.average_score !== null ? `${r.average_score}%` : '-'}</td>
                      <td>{r.overall_grade}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
              </svg>
              <p>No reports yet. <Link to="/reports/generate">Generate the first one.</Link></p>
            </div>
          )}
        </div>

        <div className="gap-row">
          <Link to="/students/add" className="btn btn--ghost">+ Add Student</Link>
          <Link to="/classes" className="btn btn--ghost">Manage Classes</Link>
          <Link to="/terms" className="btn btn--ghost">Academic Terms</Link>
        </div>
      </div>
    </>
  )
}

const ICONS: Record<string, ReactElement> = {
  students: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
    </svg>
  ),
  reports: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
    </svg>
  ),
  classes: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  ),
  subjects: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  ),
}

function StatCard({ icon, label, value, loading }: { icon: string; label: string; value?: number; loading: boolean }) {
  return (
    <div className="stat-card">
      <span className="stat-card__icon stat-card__icon--indigo">{ICONS[icon]}</span>
      <div>
        <div className="stat-card__value">{loading ? '-' : value}</div>
        <div className="stat-card__label">{label}</div>
      </div>
    </div>
  )
}
