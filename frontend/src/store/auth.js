import { create } from 'zustand'

const useAuthStore = create((set) => ({
  token: localStorage.getItem('token') || null,
  role: localStorage.getItem('role') || null,    // 'admin' | 'nurse'
  nurseId: localStorage.getItem('nurseId') || null,
  nurseName: localStorage.getItem('nurseName') || null,

  setAuth: (token, role, name = null, nurseId = null) => {
    localStorage.setItem('token', token)
    localStorage.setItem('role', role)
    if (name) localStorage.setItem('nurseName', name)
    if (nurseId) localStorage.setItem('nurseId', nurseId)
    set({ token, role, nurseName: name, nurseId })
  },

  clearAuth: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('nurseName')
    localStorage.removeItem('nurseId')
    set({ token: null, role: null, nurseName: null, nurseId: null })
  },
}))

export default useAuthStore
