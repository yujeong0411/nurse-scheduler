import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/auth'
import { settingsApi, authApi } from '../../api/client'
import SettingsTab from './SettingsTab'
import NurseManagementTab from './NurseManagementTab'
import SubmissionsTab from './SubmissionsTab'
import ScheduleResultTab from './ScheduleResultTab'
import { fmtDate } from '../../utils/constants'

const TABS = [
  {
    id: 'settings', label: '설정',
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/>
      </svg>
    )
  },
  {
    id: 'nurses', label: '간호사',
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
        <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </svg>
    )
  },
  {
    id: 'submissions', label: '신청현황',
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
    )
  },
  {
    id: 'schedule', label: '근무표',
    icon: (active) => (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.2 : 1.8} strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
      </svg>
    )
  },
]

export default function AdminLayout() {
  const navigate = useNavigate()
  const { clearAuth } = useAuthStore()
  const [activeTab, setActiveTab] = useState('settings')
  const [periods, setPeriods] = useState([])
  const [selPeriodId, setSelPeriodId] = useState(() => localStorage.getItem('admin_period_id') || null)
  const [showPeriodPicker, setShowPeriodPicker] = useState(false)
  const [deptName, setDeptName] = useState('')
  const [showPwModal, setShowPwModal] = useState(false)
  const [pwForm, setPwForm] = useState({ old_pw: '', new_pw: '', confirm: '' })
  const [pwMsg, setPwMsg] = useState(null)
  const [pwLoading, setPwLoading] = useState(false)
  const pickerRef = useRef(null)

  const loadPeriods = (selectStartDate = null) => {
    settingsApi.listPeriods()
      .then(res => {
        // 만료되지 않은 기간만 표시 (end_date >= 오늘)
        const today = new Date(); today.setHours(0, 0, 0, 0)
        const list = res.data.filter(p => {
          const end = new Date(new Date(p.start_date).getTime() + 27 * 86400000)
          return end >= today
        })
        setPeriods(list)
        if (list.length > 0) {
          if (selectStartDate) {
            // 새로 저장된 기간을 자동 선택
            const found = list.find(p => p.start_date === selectStartDate)
            if (found) {
              setSelPeriodId(found.id)
              localStorage.setItem('admin_period_id', found.id)
              return
            }
          }
          // localStorage에 저장된 id가 목록에 없으면 최신으로 초기화
          const saved = list.find(p => p.id === localStorage.getItem('admin_period_id'))
          if (!saved) {
            setSelPeriodId(list[0].id)
            localStorage.setItem('admin_period_id', list[0].id)
          }
        }
      })
      .catch(() => {})
  }

  useEffect(() => {
    loadPeriods()
    settingsApi.get().then(res => setDeptName(res.data.department_name || '')).catch(() => {})
  }, [])

  // 드롭다운 바깥 클릭 닫기
  useEffect(() => {
    if (!showPeriodPicker) return
    const handler = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) {
        setShowPeriodPicker(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showPeriodPicker])

  const selPeriod = periods.find(p => p.id === selPeriodId) || periods[0] || null

  const handleSelectPeriod = (p) => {
    setSelPeriodId(p.id)
    localStorage.setItem('admin_period_id', p.id)
    setShowPeriodPicker(false)
  }

  const handleActivatePeriod = async (e, p) => {
    e.stopPropagation()
    try {
      await settingsApi.activatePeriod(p.id)
      loadPeriods()
    } catch {
      alert('활성화 실패')
    }
  }

  const handleDeletePeriod = async (e, p) => {
    e.stopPropagation()
    if (!window.confirm(`${fmtDate(p.start_date)} 기간을 삭제하시겠습니까?\n신청 데이터와 근무표도 함께 삭제됩니다.`)) return
    try {
      await settingsApi.deletePeriod(p.id)
      loadPeriods()
    } catch {
      alert('삭제 실패')
    }
  }

  const handleLogout = () => { clearAuth(); navigate('/') }

  const handlePwChange = async () => {
    if (pwForm.new_pw !== pwForm.confirm) { setPwMsg({ ok: false, text: '새 비밀번호가 일치하지 않습니다.' }); return }
    if (pwForm.new_pw.length < 4) { setPwMsg({ ok: false, text: '비밀번호는 4자 이상이어야 합니다.' }); return }
    setPwLoading(true); setPwMsg(null)
    try {
      await authApi.changeAdminPw(pwForm.old_pw, pwForm.new_pw)
      setPwMsg({ ok: true, text: '비밀번호가 변경되었습니다.' })
      setTimeout(() => { setShowPwModal(false); setPwForm({ old_pw: '', new_pw: '', confirm: '' }); setPwMsg(null) }, 1500)
    } catch (e) {
      setPwMsg({ ok: false, text: e.response?.data?.detail || '변경 실패' })
    } finally { setPwLoading(false) }
  }

  const endDate = selPeriod?.start_date
    ? new Date(new Date(selPeriod.start_date).getTime() + 27 * 86400000)
    : null

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      {/* 헤더 */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="flex items-center justify-between px-4 h-14">
          <div>
            <h1 className="font-bold text-slate-900 text-sm leading-none">관리자</h1>
            {deptName && <p className="text-slate-400 text-xs mt-0.5">{deptName}</p>}
          </div>

          {/* 기간 선택기 */}
          <div ref={pickerRef} className="relative flex-1 flex justify-center px-4">
            {selPeriod && (
              <button
                onClick={() => setShowPeriodPicker(v => !v)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-slate-50 border border-slate-200 transition-colors"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/>
                  <line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
                </svg>
                <span className="text-xs font-semibold text-slate-700">
                  {fmtDate(selPeriod.start_date)}
                  {endDate && <span className="text-slate-400 font-normal"> ~ {fmtDate(endDate)}</span>}
                </span>
                {selPeriod.is_active && (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" title="간호사에게 표시중" />
                )}
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </button>
            )}
            {showPeriodPicker && periods.length > 0 && (
              <div className="absolute top-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg z-50 min-w-64 overflow-hidden">
                <p className="px-3 pt-2.5 pb-1 text-xs font-semibold text-slate-400">기간 선택 · 간호사에게 표시할 기간을 활성화하세요</p>
                {periods.map(p => {
                  const ed = new Date(new Date(p.start_date).getTime() + 27 * 86400000)
                  const isSelected = p.id === selPeriodId
                  const isActive = p.is_active
                  return (
                    <div key={p.id} className={`flex items-center group transition-colors ${isSelected ? 'bg-blue-50' : 'hover:bg-slate-50'}`}>
                      <button onClick={() => handleSelectPeriod(p)}
                        className={`flex-1 text-left px-3 py-2 text-sm flex items-center gap-2 ${isSelected ? 'text-blue-700 font-semibold' : 'text-slate-700'}`}>
                        <span>{fmtDate(p.start_date)} ~ {fmtDate(ed)}</span>
                        {isActive && (
                          /* 눈 아이콘: 간호사에게 표시중 */
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" title="간호사에게 표시중" className="flex-shrink-0">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                          </svg>
                        )}
                      </button>
                      {/* 활성화 버튼 (eye-off) */}
                      {!isActive && (
                        <button
                          onClick={(e) => handleActivatePeriod(e, p)}
                          className="w-7 h-7 flex items-center justify-center rounded-full text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 active:bg-emerald-100 transition-all flex-shrink-0"
                          title="간호사에게 이 기간 표시">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                            <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                            <line x1="1" y1="1" x2="23" y2="23"/>
                          </svg>
                        </button>
                      )}
                      {/* 삭제 버튼 */}
                      <button
                        onClick={(e) => handleDeletePeriod(e, p)}
                        className="mr-2 w-7 h-7 flex items-center justify-center rounded-full text-slate-400 hover:text-red-500 hover:bg-red-50 active:bg-red-100 transition-all flex-shrink-0"
                        title="삭제">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowPwModal(true)}
              className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
              title="비밀번호 변경">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 text-slate-500 hover:text-slate-800 text-xs font-medium px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
              로그아웃
            </button>
          </div>
        </div>

        {/* 탭 */}
        <nav className="flex border-t border-slate-100">
          {TABS.map(tab => {
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="flex-1 flex flex-col items-center gap-1 py-2.5 transition-colors relative"
                style={{ color: active ? '#2563EB' : '#94A3B8' }}
              >
                {tab.icon(active)}
                <span className="text-xs font-semibold">{tab.label}</span>
                {active && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-blue-600 rounded-full" />
                )}
              </button>
            )
          })}
        </nav>
      </header>

      {/* 비밀번호 변경 모달 */}
      {showPwModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
          onClick={() => { setShowPwModal(false); setPwForm({ old_pw: '', new_pw: '', confirm: '' }); setPwMsg(null) }}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h2 className="font-bold text-slate-900 text-base mb-4">관리자 비밀번호 변경</h2>
            <div className="space-y-3">
              {[
                { key: 'old_pw', label: '현재 비밀번호' },
                { key: 'new_pw', label: '새 비밀번호' },
                { key: 'confirm', label: '새 비밀번호 확인' },
              ].map(({ key, label }) => (
                <div key={key}>
                  <label className="block text-xs font-semibold text-slate-500 mb-1">{label}</label>
                  <input
                    type="password"
                    value={pwForm[key]}
                    onChange={e => setPwForm(p => ({ ...p, [key]: e.target.value }))}
                    onKeyDown={e => e.key === 'Enter' && handlePwChange()}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              ))}
            </div>
            {pwMsg && (
              <p className={`mt-3 text-xs font-semibold ${pwMsg.ok ? 'text-emerald-600' : 'text-red-500'}`}>{pwMsg.text}</p>
            )}
            <div className="flex gap-2 mt-4">
              <button onClick={() => { setShowPwModal(false); setPwForm({ old_pw: '', new_pw: '', confirm: '' }); setPwMsg(null) }}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors">
                취소
              </button>
              <button onClick={handlePwChange} disabled={pwLoading}
                className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 transition-colors disabled:opacity-50">
                {pwLoading ? '변경 중...' : '변경'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 탭 콘텐츠 */}
      <main className="flex-1 flex flex-col">
        {activeTab === 'settings'    && <SettingsTab period={selPeriod} onPeriodSaved={loadPeriods} onSelectPeriod={handleSelectPeriod} />}
        {activeTab === 'nurses'      && <NurseManagementTab />}
        {activeTab === 'submissions' && <SubmissionsTab period={selPeriod ? { ...selPeriod, period_id: selPeriod.id } : null} />}
        {activeTab === 'schedule'    && <ScheduleResultTab period={selPeriod ? { ...selPeriod, period_id: selPeriod.id } : null} />}
      </main>
    </div>
  )
}
