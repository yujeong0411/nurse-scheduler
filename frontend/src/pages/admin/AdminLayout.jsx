import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Joyride, { STATUS, EVENTS, ACTIONS } from 'react-joyride'
import useAuthStore from '../../store/auth'
import { settingsApi, authApi } from '../../api/client'
import SettingsTab from './SettingsTab'
import NurseManagementTab from './NurseManagementTab'
import SubmissionsTab from './SubmissionsTab'
import ScheduleResultTab from './ScheduleResultTab'
import { fmtDate } from '../../utils/constants'

function TourTooltip({ continuous, index, step, size, backProps, closeProps, primaryProps, skipProps, isLastStep }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 20,
      boxShadow: '0 8px 40px rgba(0,0,0,0.18)', width: 300,
      overflow: 'hidden', fontFamily: "'Inter', '맑은 고딕', 'Apple SD Gothic Neo', sans-serif",
    }}>
      <div style={{ height: 4, background: 'linear-gradient(90deg, #2A3A7A, #4B6CB7)' }} />
      <div style={{ padding: '20px 20px 16px' }}>
        <div style={{ display: 'flex', gap: 5, marginBottom: 12 }}>
          {Array.from({ length: size }).map((_, i) => (
            <div key={i} style={{
              height: 3, flex: 1, borderRadius: 2,
              background: i <= index ? '#2A3A7A' : '#E2E8F0', transition: 'background 0.3s',
            }} />
          ))}
        </div>
        {step.title && <p style={{ margin: '0 0 8px', fontSize: 15, fontWeight: 700, color: '#0F172A' }}>{step.title}</p>}
        <p style={{ margin: 0, fontSize: 13.5, color: '#475569', lineHeight: 1.6 }}>{step.content}</p>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px 16px' }}>
        <button {...skipProps} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: '#94A3B8', fontFamily: 'inherit', padding: '6px 4px' }}>
          건너뛰기
        </button>
        <div style={{ display: 'flex', gap: 8 }}>
          {index > 0 && (
            <button {...backProps} style={{ background: '#F1F5F9', border: 'none', borderRadius: 10, cursor: 'pointer', fontSize: 13, fontWeight: 600, color: '#475569', padding: '8px 16px', fontFamily: 'inherit' }}>
              이전
            </button>
          )}
          <button {...(isLastStep ? closeProps : primaryProps)} style={{ background: '#2A3A7A', border: 'none', borderRadius: 10, cursor: 'pointer', fontSize: 13, fontWeight: 700, color: '#fff', padding: '8px 18px', fontFamily: 'inherit' }}>
            {isLastStep ? '완료' : '다음 →'}
          </button>
        </div>
      </div>
    </div>
  )
}

const TOUR_STEPS = [
  {
    target: 'body', placement: 'center', disableBeacon: true,
    title: '관리자 가이드',
    content: '근무표 생성을 위한 4단계 워크플로우를 안내합니다. 설정 → 간호사 → 신청현황 → 근무표 순서로 진행하세요.',
  },
  // ── 설정 탭 ──
  {
    target: '#admin-period-btn', placement: 'bottom', disableBeacon: true,
    title: '기간 선택',
    content: '편집할 근무 기간을 선택합니다. 눈 버튼으로 간호사에게 신청 기간을 공개하거나 숨길 수 있어요.',
  },
  {
    target: '#admin-settings-period', placement: 'bottom', disableBeacon: true,
    title: '① 일정 설정',
    content: '근무표 시작일과 신청 마감일을 설정합니다. 마감일이 지나면 간호사 신청이 자동으로 잠깁니다. 설정 후 반드시 "일정 저장"을 눌러야 적용됩니다.',
  },
  {
    target: '#admin-settings-rules', placement: 'bottom', disableBeacon: true,
    title: '① 근무 규칙',
    content: '일별 최소 인원, 연속 근무 제한, 야간 횟수 등 솔버 제약 조건을 설정합니다.',
  },
  {
    target: '#admin-settings-holidays', placement: 'top', disableBeacon: true,
    title: '① 법정 공휴일',
    content: '"자동 감지" 버튼으로 해당 기간의 법정 공휴일을 자동으로 불러옵니다. 확인 후 "규칙 저장"을 눌러야 최종 저장됩니다.',
  },
  // ── 간호사 탭 ──
  {
    target: '#admin-nurses-add-btn', placement: 'bottom', disableBeacon: true,
    title: '② 간호사 추가',
    content: '이름·직급·역할·고정주휴·휴가잔여를 입력해 간호사를 등록합니다.',
  },
  {
    target: '#admin-nurses-excel', placement: 'bottom', disableBeacon: true,
    title: '② 규칙 엑셀 불러오기',
    content: '미리 작성된 엑셀 규칙 파일에서 간호사 목록을 한 번에 가져올 수 있습니다.',
  },
  {
    target: '#admin-nurses-prev', placement: 'bottom', disableBeacon: true,
    title: '② 이전 근무 반영',
    content: '새 달 근무표 생성 전 반드시 실행하세요. 전월 N 횟수·수면이월·생휴·휴가잔여를 자동 업데이트합니다. DB 자동 반영 또는 지난 달 엑셀 파일로 반영할 수 있어요.',
  },
  // ── 신청현황 탭 ──
  {
    target: '#admin-submissions-toolbar', placement: 'bottom', disableBeacon: true,
    title: '③ 신청현황',
    content: '간호사들의 근무 신청을 한눈에 확인합니다. 셀 클릭으로 직접 수정하거나, 날짜 헤더 클릭으로 필터링, 엑셀로 내보내기·불러오기가 가능합니다.',
  },
  // ── 근무표 탭 ──
  {
    target: '#admin-schedule-generate', placement: 'bottom', disableBeacon: true,
    title: '④ 근무표 생성',
    content: 'OR-Tools가 모든 규칙과 신청을 반영해 최적 근무표를 자동 생성합니다(최대 300초). 생성 후 셀 클릭으로 수동 편집하고, 엑셀 버튼으로 저장하세요.',
  },
]

const TAB_FOR_STEP = [
  null,
  'settings', 'settings', 'settings', 'settings',
  'nurses', 'nurses', 'nurses',
  'submissions',
  'schedule',
]

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
  const [tourRun, setTourRun] = useState(false)
  const [tourStep, setTourStep] = useState(0)
  const pickerRef = useRef(null)

  const loadPeriods = (selectStartDate = null) => {
    settingsApi.listPeriods()
      .then(res => {
        const list = res.data
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
    if (!localStorage.getItem('admin_tour_done')) {
      setTimeout(() => setTourRun(true), 600)
    }
  }, [])

  const handleTourCallback = ({ type, index, action, status }) => {
    if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
      setTourRun(false)
      localStorage.setItem('admin_tour_done', '1')
      return
    }
    if (type === EVENTS.STEP_AFTER) {
      const next = index + (action === ACTIONS.PREV ? -1 : 1)
      const nextTab = TAB_FOR_STEP[next]
      const currTab = TAB_FOR_STEP[index]
      if (nextTab) setActiveTab(nextTab)
      if (nextTab) setActiveTab(nextTab)
      if (nextTab && nextTab !== currTab) {
        setTimeout(() => setTourStep(next), 200)
      } else {
        setTourStep(next)
      }
    }
  }

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
    if (!window.confirm(
      `⚠️ 영구 삭제 경고\n\n` +
      `이 기간의 근무 신청·근무표·기간 정보가\n` +
      `DB에서 완전히 삭제되며 복구 불가능합니다.\n\n` +
      `계속하시겠습니까?`
    )) return
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
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: '#F2F4F8' }}>
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
                id="admin-period-btn"
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
                    <div key={p.id} className={`flex items-center min-w-0 ${isSelected ? 'bg-blue-50' : 'hover:bg-slate-50'} transition-colors`}>
                      {/* 날짜 텍스트 버튼 */}
                      <button onClick={() => handleSelectPeriod(p)}
                        className={`flex-1 min-w-0 text-left px-3 py-2.5 text-sm truncate ${isSelected ? 'text-blue-700 font-semibold' : 'text-slate-700'}`}>
                        {fmtDate(p.start_date)} ~ {fmtDate(ed)}
                      </button>
                      {/* 눈 버튼 — 항상 오른쪽에 고정 */}
                      <button
                        onClick={(e) => { if (!isActive) handleActivatePeriod(e, p) }}
                        className={`flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full transition-all ${isActive ? 'text-emerald-500 cursor-default' : 'text-slate-300 hover:text-emerald-500 hover:bg-emerald-50 active:bg-emerald-100'}`}
                        title={isActive ? '간호사에게 표시 중' : '간호사에게 표시'}>
                        {isActive ? (
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                          </svg>
                        ) : (
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                            <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                            <line x1="1" y1="1" x2="23" y2="23"/>
                          </svg>
                        )}
                      </button>
                      {/* 삭제 버튼 */}
                      <button
                        onClick={(e) => handleDeletePeriod(e, p)}
                        className="flex-shrink-0 mr-1.5 w-8 h-8 flex items-center justify-center rounded-full text-slate-300 hover:text-red-500 hover:bg-red-50 active:bg-red-100 transition-all"
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
              onClick={() => { setTourStep(0); setActiveTab('settings'); setTourRun(true) }}
              className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
              title="사용 가이드">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            </button>
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
                id={`admin-tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className="flex-1 flex flex-col items-center gap-1 py-2.5 transition-colors relative"
                style={{ color: active ? '#2A3A7A' : '#94A3B8' }}
              >
                {tab.icon(active)}
                <span className="text-xs font-semibold">{tab.label}</span>
                {active && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-8 h-0.5 rounded-full" style={{ background: '#2A3A7A' }} />
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
            <h2 className="font-bold text-slate-900 text-base mb-1">관리자 비밀번호 변경</h2>
            <p className="text-xs text-slate-400 mb-4">영문·숫자·특수문자 사용 가능 · 최대 11자</p>
            <div className="space-y-3">
              {[
                { key: 'old_pw', label: '현재 비밀번호', placeholder: '현재 비밀번호 입력' },
                { key: 'new_pw', label: '새 비밀번호', placeholder: '새 비밀번호 입력' },
                { key: 'confirm', label: '새 비밀번호 확인', placeholder: '새 비밀번호 다시 입력' },
              ].map(({ key, label, placeholder }) => (
                <div key={key}>
                  <label className="block text-xs font-semibold text-slate-500 mb-1">{label}</label>
                  <input
                    type="password"
                    maxLength={11}
                    value={pwForm[key]}
                    onChange={e => setPwForm(p => ({ ...p, [key]: e.target.value }))}
                    onKeyDown={e => e.key === 'Enter' && handlePwChange()}
                    placeholder={placeholder}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:border-transparent" style={{ '--tw-ring-color': '#2A3A7A' }}
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
                className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white transition-colors disabled:opacity-50" style={{ background: '#2A3A7A' }}>
                {pwLoading ? '변경 중...' : '변경'}
              </button>
            </div>
          </div>
        </div>
      )}

      <Joyride
        steps={TOUR_STEPS}
        run={tourRun}
        stepIndex={tourStep}
        continuous
        scrollToFirstStep
        spotlightClicks={false}
        disableOverlayClose
        tooltipComponent={TourTooltip}
        styles={{ options: { zIndex: 1100, spotlightShadow: '0 0 0 9999px rgba(0,0,0,0.55)' } }}
        callback={handleTourCallback}
      />

      {/* 탭 콘텐츠 */}
      <main className="flex-1 flex flex-col min-h-0">
        {activeTab === 'settings'    && <SettingsTab period={selPeriod} onPeriodSaved={loadPeriods} onSelectPeriod={handleSelectPeriod} />}
        {activeTab === 'nurses'      && <NurseManagementTab period={selPeriod} />}
        {activeTab === 'submissions' && <SubmissionsTab period={selPeriod ? { ...selPeriod, period_id: selPeriod.id } : null} />}
        {activeTab === 'schedule'    && <ScheduleResultTab period={selPeriod ? { ...selPeriod, period_id: selPeriod.id } : null} />}
      </main>
    </div>
  )
}
