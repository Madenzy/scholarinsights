import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import AuthLayout from './layouts/AuthLayout'
import Login from './pages/auth/Login'
import ForgotPassword from './pages/auth/ForgotPassword'
import ResetPassword from './pages/auth/ResetPassword'
import SchoolRegister from './pages/auth/SchoolRegister'
import VerifyEmail from './pages/auth/VerifyEmail'
import VerifyMfa from './pages/auth/VerifyMfa'
import Dashboard from './pages/dashboard/Dashboard'
import Placeholder from './pages/Placeholder'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password/:token" element={<ResetPassword />} />
          <Route path="/register" element={<SchoolRegister />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/verify-mfa" element={<VerifyMfa />} />
        </Route>

        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/students" element={<Placeholder title="Students" />} />
          <Route path="/students/add" element={<Placeholder title="Add Student" />} />
          <Route path="/reports" element={<Placeholder title="Reports" />} />
          <Route path="/reports/generate" element={<Placeholder title="Generate Report" />} />
          <Route path="/reports/:id" element={<Placeholder title="Report" />} />
          <Route path="/classes" element={<Placeholder title="Classes" />} />
          <Route path="/subjects" element={<Placeholder title="Subjects" />} />
          <Route path="/terms" element={<Placeholder title="Academic Terms" />} />
          <Route path="/teachers" element={<Placeholder title="Teachers" />} />
          <Route path="/users" element={<Placeholder title="Users" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
