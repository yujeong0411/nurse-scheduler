import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 300000,  // 솔버 최대 180초 + 여유 (개별 요청에서 override 가능)
})

// 요청 인터셉터: JWT 토큰 자동 첨부
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 응답 인터셉터: 401 시 로그인으로 이동
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !err.config?.url?.includes('/login')) {
      localStorage.removeItem('token')
      localStorage.removeItem('role')
      window.location.href = '/'
    }
    return Promise.reject(err)
  }
)

// ── 인증 ─────────────────────────────────────────
export const authApi = {
  adminLogin:     (password) => api.post('/auth/admin/login', { password }),
  nurseLogin:     (nurse_id, pin) => api.post('/auth/nurse/login', { nurse_id, pin }),
  changePin:      (old_pin, new_pin) => api.put('/auth/nurse/pin', { old_pin, new_pin }),
  changeAdminPw:  (old_pw, new_pw) => api.put('/auth/admin/password', { old_pw, new_pw }),
  resetPin:       (nurse_id) => api.put(`/auth/admin/pin-reset/${nurse_id}`),
}

// ── 간호사 ───────────────────────────────────────
export const nursesApi = {
  names:        () => api.get('/nurses/names'),
  me:           () => api.get('/nurses/me'),
  list:         () => api.get('/nurses'),
  create:       (data) => api.post('/nurses', data),
  update:       (id, data) => api.put(`/nurses/${id}`, data),
  remove:       (id) => api.delete(`/nurses/${id}`),
  importExcel:  (file) => {
    const fd = new FormData(); fd.append('file', file)
    return api.post('/nurses/import-excel', fd)
  },
  applyPrevSchedule: (scheduleId = null) =>
    api.post('/nurses/apply-prev-schedule', null, {
      params: scheduleId ? { schedule_id: scheduleId } : {}
    }),
  importPrevExcel: (file) => {
    const fd = new FormData(); fd.append('file', file)
    return api.post('/nurses/import-prev-excel', fd)
  },
}

// ── 설정·규칙 ─────────────────────────────────────
export const settingsApi = {
  get:            (config) => api.get('/settings', config),
  update:         (data) => api.put('/settings', data),
  listPeriods:    () => api.get('/settings/periods'),
  getPeriod:      (id) => api.get(`/settings/${id}`),
  activatePeriod: (id) => api.put(`/settings/${id}/activate`),
  deletePeriod:   (id) => api.delete(`/settings/${id}`),
}

export const rulesApi = {
  get:    () => api.get('/rules'),
  update: (data) => api.put('/rules', data),
}

export const holidaysApi = {
  get: (year, month) => api.get('/holidays', { params: { year, month } }),
}

// ── 근무신청 ──────────────────────────────────────
export const requestsApi = {
  getAll:         (period_id) => api.get(`/requests/${period_id}`),
  getMine:        (period_id) => api.get(`/requests/${period_id}/me`),
  getStatus:      (period_id) => api.get(`/requests/${period_id}/status`),
  upsert:         (period_id, nurse_id, items) =>
    api.put(`/requests/${period_id}/${nurse_id}`, { items }),
  getScore:       (period_id, nurse_id) =>
    api.get(`/requests/${period_id}/score/${nurse_id}`),
  getAllScores:    (period_id) =>
    api.get(`/requests/${period_id}/scores`),
  resetScores:    (period_id) =>
    api.post(`/requests/${period_id}/reset-scores`),
  recalcScores:   (period_id) =>
    api.post(`/requests/${period_id}/recalc-scores`),
  getAssignmentLog: (period_id, day, code) =>
    api.get(`/requests/${period_id}/assignment-log/${day}/${encodeURIComponent(code)}`),
  exportXlsx:     (period_id) =>
    api.get(`/requests/${period_id}/export`, { responseType: 'blob' }),
  importXlsx:     (period_id, file) => {
    const fd = new FormData(); fd.append('file', file)
    return api.post(`/requests/${period_id}/import`, fd)
  },
}

// ── 근무표 ────────────────────────────────────────
export const scheduleApi = {
  checkConflicts: (period_id) => api.get(`/schedule/check-conflicts/${period_id}`),
  generate:      (period_id, timeout_seconds = 300) =>
    api.post('/schedule/generate', { period_id, timeout_seconds }),
  jobStatus:          (job_id) => api.get(`/schedule/job/${job_id}`),
  latestJobByPeriod:  (period_id) => api.get(`/schedule/job/period/${period_id}`),
  getByPeriod:   (period_id) => api.get(`/schedule/period/${period_id}`),
  get:           (schedule_id) => api.get(`/schedule/${schedule_id}`),
  updateCell: (schedule_id, data) => api.patch(`/schedule/${schedule_id}/cell`, data),
  evaluate:   (schedule_id) => api.get(`/schedule/${schedule_id}/evaluate`),
  exportXlsx: (schedule_id) =>
    api.get(`/schedule/${schedule_id}/export`, { responseType: 'blob' }),
}

export default api
