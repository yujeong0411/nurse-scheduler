import { create } from 'zustand'
import { authApi } from '../api/client'

const useAuthStore = create((set) => ({
  role: localStorage.getItem('role') || null,       // 'admin' | 'nurse'
  nurseId: localStorage.getItem('nurseId') || null,
  nurseName: localStorage.getItem('nurseName') || null,

  setAuth: (role, name = null, nurseId = null) => {
    localStorage.setItem('role', role)
    if (name) localStorage.setItem('nurseName', name)
    if (nurseId) localStorage.setItem('nurseId', nurseId)
    set({ role, nurseName: name, nurseId })
  },

  clearAuth: async () => {
    try { await authApi.logout() } catch { /* 쿠키 만료 등 무시 */ }
    localStorage.removeItem('role')
    localStorage.removeItem('nurseName')
    localStorage.removeItem('nurseId')
    set({ role: null, nurseName: null, nurseId: null })
  },
}))

export default useAuthStore
