import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { requestsApi, settingsApi, rulesApi, nursesApi, holidaysApi } from '../api/client'
import useAuthStore from '../store/auth'
import { validate } from '../utils/validate'
import {
  NUM_DAYS, WD, DEFAULT_RULES,
  sc, fmtDate, getWd, getDate, mmdd, dlPassed
} from '../utils/constants'
import ShiftSheet from '../components/ShiftSheet'
import PinModal from '../components/PinModal'

export default function NursePage() {
  const navigate = useNavigate()
  const { nurseId, nurseName, clearAuth } = useAuthStore()

  const [settings, setSettings] = useState(null)
  const [rules, setRules] = useState(DEFAULT_RULES)
  const [periodId, setPeriodId] = useState(null)
  const [nurse, setNurse] = useState(null)
  const [shifts, setShifts] = useState({})
  const [notes, setNotes] = useState({})
  const [picker, setPicker] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [showPin, setShowPin] = useState(false)
  const [toast, setToast] = useState(null)
  const [holidayNames, setHolidayNames] = useState({}) // period day → 공휴일 이름

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    (async () => {
      try {
        const [sRes, rRes, meRes] = await Promise.all([
          settingsApi.get(), rulesApi.get(), nursesApi.me()
        ])
        const s = sRes.data
        setSettings(s)
        setRules(rRes.data)
        setNurse(meRes.data)
        if (s.period_id) {
          setPeriodId(s.period_id)
          const reqRes = await requestsApi.getMine(s.period_id)
          const map = {}, noteMap = {}
          ;(reqRes.data || []).forEach(it => {
            map[it.day] = it.code
            if (it.note) noteMap[it.day] = it.note
          })
          setShifts(map)
          setNotes(noteMap)
        }

        // 공휴일 이름 매핑 (기간이 두 달에 걸칠 수 있으므로 두 달 모두 조회)
        if (s.start_date) {
          const start = new Date(s.start_date)
          const holMap = {}
          const seen = new Set()
          for (let di = 0; di < NUM_DAYS; di++) {
            const d = new Date(start.getTime() + di * 86400000)
            const ym = `${d.getFullYear()}-${d.getMonth()}`
            if (!seen.has(ym)) {
              seen.add(ym)
              try {
                const res = await holidaysApi.get(d.getFullYear(), d.getMonth() + 1)
                ;(res.data || []).forEach(h => {
                  const hd = new Date(d.getFullYear(), d.getMonth(), h.day)
                  const idx = Math.round((hd - start) / 86400000) + 1
                  if (idx >= 1 && idx <= NUM_DAYS) holMap[idx] = h.name
                })
              } catch { /* 공휴일 조회 실패 무시 */ }
            }
          }
          setHolidayNames(holMap)
        }
      } catch (e) {
        if (e.response?.status === 401) { clearAuth(); navigate('/') }
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const setShift = useCallback((day, s, note = '') => {
    setShifts(prev => {
      const next = { ...prev }
      if (s) next[day] = s; else delete next[day]
      return next
    })
    setNotes(prev => {
      const next = { ...prev }
      if (s && note) next[day] = note; else delete next[day]
      return next
    })
    setSaved(false)
  }, [])

  const handleSubmit = async () => {
    if (!periodId) { showToast('관리자가 시작일을 설정해야 합니다.', false); return }
    if (dlPassed(settings?.deadline)) { showToast('신청 마감이 지났습니다.', false); return }
    setSaving(true)
    try {
      const items = Object.entries(shifts).map(([day, code]) => ({
        day: parseInt(day), code, is_or: false, note: notes[+day] || ''
      }))
      await requestsApi.upsert(periodId, nurseId, items)
      setSaved(true)
      showToast('신청이 저장되었습니다.', true)
    } catch {
      showToast('저장 실패. 다시 시도해주세요.', false)
    } finally {
      setSaving(false)
    }
  }

  const handleLogout = () => { clearAuth(); navigate('/') }

  const startDate = settings?.start_date || null
  const deadline = settings?.deadline || null
  const deptName = settings?.department_name || ''
  const passed = dlPassed(deadline)
  const endStr = startDate ? fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000)) : ''

  // 일요일 시작 달력 (Sun=0, Mon=1, ..., Sat=6)
  const startWd = startDate ? new Date(startDate).getDay() : 0
  const cells = []
  for (let i = 0; i < startWd; i++) cells.push(null)
  for (let d = 1; d <= NUM_DAYS; d++) cells.push(d)
  while (cells.length % 7 !== 0) cells.push(null)

  const reqCount = Object.keys(shifts).length

  const nurseForValidate = nurse ? { ...nurse, is_4day: nurse.is_4day_week } : null

  // 공휴일 API 결과를 규칙에 병합 → 법휴 유효성 검사에 자동 반영
  const effectiveRules = {
    ...rules,
    public_holidays: [
      ...(rules.public_holidays || []),
      ...Object.keys(holidayNames).map(Number)
        .filter(d => !(rules.public_holidays || []).includes(d))
    ]
  }

  const allV = (startDate && nurseForValidate) ? Object.entries(shifts).reduce((acc, [day, code]) => {
    const ps = { ...shifts }; delete ps[+day]
    const label = mmdd(getDate(startDate, +day))
    validate(ps, +day, code, nurseForValidate, effectiveRules, startDate)
      .forEach(v => acc.push(`${label}: ${v}`))
    return acc
  }, []) : []

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="flex items-center gap-3 text-slate-400 text-sm">
        <div className="w-5 h-5 border-2 border-slate-200 border-t-slate-400 rounded-full animate-spin" />
        불러오는 중...
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">

      {/* 헤더 */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="flex items-center justify-between px-4 h-14">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </div>
            <div>
              <p className="font-bold text-slate-900 text-sm leading-none">{nurseName}</p>
              {deptName && <p className="text-slate-400 text-xs mt-0.5">{deptName}</p>}
            </div>
          </div>

          {startDate && (
            <p className="text-xs text-slate-500 font-medium hidden sm:block">
              {fmtDate(startDate)} ~ {endStr}
            </p>
          )}

          <div className="flex items-center gap-2">
            <button onClick={() => setShowPin(true)}
              className="flex items-center gap-1.5 text-slate-500 hover:text-slate-800 text-xs font-medium px-2.5 py-1.5 rounded-lg hover:bg-slate-100 transition-colors">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
              PIN
            </button>
            <button onClick={handleLogout}
              className="flex items-center gap-1.5 text-slate-500 hover:text-slate-800 text-xs font-medium px-2.5 py-1.5 rounded-lg hover:bg-slate-100 transition-colors">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
              로그아웃
            </button>
          </div>
        </div>

        {/* 기간 (모바일) */}
        {startDate && (
          <div className="px-4 pb-2 sm:hidden">
            <p className="text-xs text-slate-400">{fmtDate(startDate)} ~ {endStr}</p>
          </div>
        )}
      </header>

      {/* 내 정보 카드 — 마감 배너 위 */}
      {nurse && (
        <div className="bg-white border-b border-slate-100 px-4 py-3">
          <div className="flex flex-wrap gap-1.5">
            {nurse.grade && (
              <span className="px-2.5 py-1 rounded-full text-xs font-bold"
                style={{ background: '#EFF6FF', color: '#1D4ED8' }}>{nurse.grade}</span>
            )}
            {nurse.role && (
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold"
                style={{ background: '#F0F9FF', color: '#0369A1' }}>{nurse.role}</span>
            )}
            {nurse.is_male && (
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold"
                style={{ background: '#F0F9FF', color: '#0284C7' }}>남성</span>
            )}
            {nurse.is_pregnant && (
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold"
                style={{ background: '#FDF4FF', color: '#A21CAF' }}>임산부</span>
            )}
            {nurse.is_4day_week && (
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold"
                style={{ background: '#F0FDF4', color: '#15803D' }}>주4일제</span>
            )}
            {nurse.fixed_weekly_off != null && nurse.fixed_weekly_off !== '' && (
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold"
                style={{ background: '#FFFBEB', color: '#92400E' }}>주휴 {WD[parseInt(nurse.fixed_weekly_off)]}요일</span>
            )}
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold"
              style={{ background: '#F0FDF4', color: '#166534' }}>연차 {nurse.vacation_days ?? 0}일</span>
            {nurse.pending_sleep && (
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold"
                style={{ background: '#F8F9FF', color: '#3730A3' }}>수면이월</span>
            )}
          </div>
        </div>
      )}

      {/* 마감 배너 */}
      {deadline && (
        <div className={`flex items-center justify-center gap-2 py-2 text-xs font-semibold ${passed ? 'bg-red-50 text-red-600 border-b border-red-100' : 'bg-amber-50 text-amber-700 border-b border-amber-100'}`}>
          {passed ? (
            <>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
              </svg>
              신청이 마감되었습니다
            </>
          ) : (
            <>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
              마감: {deadline.replace('T', ' ')}
            </>
          )}
        </div>
      )}

      {!startDate ? (
        <div className="flex flex-col items-center justify-center flex-1 text-slate-400 gap-3">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/>
            <line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
          </svg>
          <p className="text-sm">관리자가 근무 기간을 설정해야 합니다.</p>
        </div>
      ) : (
        <div className="flex-1 pb-28 space-y-3 p-4">

          {/* 위반 알림 */}
          {allV.length > 0 && (
            <div className="bg-red-50 border border-red-100 rounded-2xl p-3">
              <p className="font-semibold text-red-700 text-sm mb-1.5">규칙 위반 {allV.length}건</p>
              {allV.slice(0, 3).map((v, i) => (
                <p key={i} className="text-red-500 text-xs mt-0.5">• {v}</p>
              ))}
              {allV.length > 3 && <p className="text-red-400 text-xs mt-0.5">외 {allV.length - 3}건...</p>}
            </div>
          )}
          {allV.length === 0 && reqCount > 0 && (
            <div className="bg-emerald-50 border border-emerald-100 rounded-2xl px-3 py-2.5 flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <p className="text-emerald-700 text-sm font-semibold">규칙 위반 없음</p>
            </div>
          )}

          {/* 달력 */}
          <div className="bg-white rounded-2xl overflow-hidden border border-slate-100 shadow-sm">
            {/* 요일 헤더 (일요일 시작) */}
            <div className="grid grid-cols-7 pt-3 pb-2">
              {['일','월','화','수','목','금','토'].map((label, i) => (
                <div key={i} className="text-center text-xs font-black"
                  style={{ color: i === 0 ? '#F87171' : i === 6 ? '#60A5FA' : '#94A3B8', letterSpacing: '0.05em' }}>
                  {label}
                </div>
              ))}
            </div>
            {/* 날짜 셀 */}
            <div className="grid grid-cols-7 gap-px bg-slate-100 border-t border-slate-100">
              {cells.map((day, i) => {
                if (!day) return <div key={i} className="bg-slate-50" style={{ minHeight: 84 }} />
                const wd = getWd(startDate, day) // Mon=0..Sun=6
                const isSat = wd === 5, isSun = wd === 6
                const isHol = (effectiveRules.public_holidays || []).includes(day)
                const s = shifts[day] || ''
                const st = sc(s)
                const ps = { ...shifts }; delete ps[day]
                const vs = s && nurseForValidate ? validate(ps, day, s, nurseForValidate, effectiveRules, startDate) : []
                const dateObj = getDate(startDate, day)
                const fixedWd = (nurseForValidate?.fixed_weekly_off != null && nurseForValidate?.fixed_weekly_off !== '')
                  ? parseInt(nurseForValidate.fixed_weekly_off) : -1
                const isFixedOff = (!isNaN(fixedWd) && fixedWd >= 0 && wd === fixedWd)
                const isRed = isSun || isHol
                const dateColor = isSat ? '#3B82F6' : isRed ? '#EF4444' : '#475569'
                const cellBg = isRed ? '#FFF5F5' : isSat ? '#F5F8FF' : '#FFFFFF'
                const holName = holidayNames[day]

                // 고정 주휴 — 회색 처리, 건들지 못한다는 느낌
                if (isFixedOff) {
                  return (
                    <div key={i} className="flex flex-col pt-2 px-1 pb-1.5 cursor-not-allowed select-none"
                      style={{ minHeight: 84, background: '#F8FAFC' }}>
                      <span className="text-xs font-semibold text-center w-full" style={{ color: '#94A3B8' }}>{mmdd(dateObj)}</span>
                      <span className="flex-1 flex items-center justify-center w-full font-bold text-sm" style={{ color: '#94A3B8' }}>주</span>
                    </div>
                  )
                }

                return (
                  <button key={i}
                    onClick={() => { if (!passed) setPicker({ day }) }}
                    disabled={passed}
                    className="flex flex-col pt-2 px-1 pb-1.5 transition-all active:scale-95 relative"
                    style={{ minHeight: 84, background: cellBg }}>
                    {/* 날짜 */}
                    <span className="text-xs font-bold leading-none text-center w-full" style={{ color: dateColor }}>{mmdd(dateObj)}</span>
                    {/* 공휴일 이름 */}
                    {holName && (
                      <span className="mt-0.5 text-center font-semibold leading-tight w-full"
                        style={{ fontSize: 7.5, color: '#F87171', lineHeight: 1.1 }}>
                        {holName}
                      </span>
                    )}
                    {/* 근무 뱃지 or + 버튼 */}
                    {s ? (
                      <span className="mt-1.5 flex-1 w-full flex items-center justify-center rounded-xl font-black"
                        style={{ fontSize: s.endsWith('제외') ? 11 : 14, background: st.bg, color: st.fg, border: `1.5px solid ${st.border}`, minHeight: 36 }}>
                        {s}
                      </span>
                    ) : (
                      <span className="mt-1.5 flex-1 w-full flex items-center justify-center rounded-xl font-bold"
                        style={{ background: isRed ? '#FEE2E2' : isSat ? '#DBEAFE' : '#F1F5F9', color: isRed ? '#FCA5A5' : isSat ? '#93C5FD' : '#CBD5E1', fontSize: 18, minHeight: 36 }}>+</span>
                    )}
                    {/* 위반 경고 */}
                    {vs.length > 0 && (
                      <span className="absolute top-1 right-1 bg-red-500 text-white rounded-full flex items-center justify-center font-black"
                        style={{ width: 14, height: 14, fontSize: 8 }}>!</span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>


        </div>
      )}

      {/* 제출 버튼 */}
      {startDate && !passed && (
        <div className="fixed bottom-0 left-0 right-0 px-4 pb-6 pt-3 bg-white/95 backdrop-blur-sm border-t border-slate-100">
          <button onClick={handleSubmit} disabled={saving}
            className={`w-full rounded-2xl font-bold text-white py-4 text-base transition-all active:scale-[0.98] disabled:opacity-60 ${saved ? 'bg-emerald-500' : 'bg-blue-600 hover:bg-blue-700'}`}
            style={{ boxShadow: saved ? '0 4px 16px rgba(16,185,129,0.3)' : '0 4px 16px rgba(37,99,235,0.3)' }}>
            {saving ? (
              <span className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                저장 중...
              </span>
            ) : saved ? (
              <span className="flex items-center justify-center gap-2">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                신청 완료 (재저장 가능)
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
                신청 제출하기
              </span>
            )}
          </button>
        </div>
      )}

      {picker && (
        <ShiftSheet
          day={picker.day}
          shifts={shifts}
          nurse={nurseForValidate}
          rules={effectiveRules}
          startDate={startDate}
          notes={notes}
          onSelect={(s, note) => { setShift(picker.day, s, note); setPicker(null) }}
          onClose={() => setPicker(null)}
        />
      )}

      {showPin && <PinModal onClose={() => setShowPin(false)} />}

      {/* 토스트 */}
      {toast && (
        <div className="fixed top-4 left-4 right-4 z-50 flex justify-center pointer-events-none">
          <div className={`flex items-center gap-2 rounded-2xl px-4 py-3 shadow-lg text-sm font-semibold border ${toast.ok ? 'bg-white text-emerald-700 border-emerald-100' : 'bg-white text-red-600 border-red-100'}`}>
            {toast.ok ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            )}
            {toast.msg}
          </div>
        </div>
      )}
    </div>
  )
}
