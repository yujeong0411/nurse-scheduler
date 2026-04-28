import { Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import NurseAuthPage from './pages/NurseAuthPage'
import NursePage from './pages/NursePage'
import AdminAuthPage from './pages/admin/AdminAuthPage'
import AdminLayout from './pages/admin/AdminLayout'
import useAuthStore from './store/auth'

function RequireAdmin({ children }) {
  const { role } = useAuthStore()
  if (role !== 'admin') return <Navigate to="/admin/login" replace />
  return children
}

function RequireNurse({ children }) {
  const { role } = useAuthStore()
  if (role !== 'nurse') return <Navigate to="/nurse/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/nurse/login" element={<NurseAuthPage />} />
      <Route path="/nurse" element={<RequireNurse><NursePage /></RequireNurse>} />
      <Route path="/admin/login" element={<AdminAuthPage />} />
      <Route path="/admin/*" element={<RequireAdmin><AdminLayout /></RequireAdmin>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
