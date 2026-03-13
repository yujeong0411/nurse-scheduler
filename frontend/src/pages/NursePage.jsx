import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { requestsApi, settingsApi, rulesApi, nursesApi } from '../api/client'
import useAuthStore from '../store/auth'
import { validate } from '../utils/validate'
import {
  NUM_DAYS, WD, WORK_SET, DEFAULT_RULES,
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

  const startWd = startDate ? getWd(startDate, 1) : 0
  const cells = []
  for (let i = 0; i < startWd; i++) cells.push(null)
  for (let d = 1; d <= NUM_DAYS; d++) cells.push(d)
  while (cells.length % 7 !== 0) cells.push(null)

  let nCnt = 0, wCnt = 0, oCnt = 0
  Object.values(shifts).forEach(v => {
    if (v) {
      if (WORK_SET.has(v)) wCnt++; else oCnt++
      if (v === 'N') nCnt++
    }
  })
  const reqCount = Object.keys(shifts).length

  const nurseForValidate = nurse ? { ...nurse, is_4day: nurse.is_4day_week } : null
  const allV = (startDate && nurseForValidate) ? Object.entries(shifts).reduce((acc, [day, code]) => {
    const ps = { ...shifts }; delete ps[+day]
    const label = mmdd(getDate(startDate, +day))
    validate(ps, +day, code, nurseForValidate, rules, startDate)
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

          {/* 통계 카드 */}
          <div className="grid grid-cols-4 gap-2">
            {[
              { label: '신청', val: reqCount, color: '#2563EB', bg: '#EFF6FF' },
              { label: '근무', val: wCnt, color: '#0369A1', bg: '#F0F9FF' },
              { label: '야간', val: nCnt, color: '#DC2626', bg: '#FEF2F2' },
              { label: '휴무', val: oCnt, color: '#B45309', bg: '#FFFBEB' },
            ].map(({ label, val, color, bg }) => (
              <div key={label} className="rounded-2xl text-center py-3 px-1 border"
                style={{ background: bg, borderColor: color + '22' }}>
                <div className="font-black text-2xl leading-none" style={{ color }}>{val}</div>
                <div className="text-xs font-semibold mt-1" style={{ color: color + 'aa' }}>{label}</div>
              </div>
            ))}
          </div>

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
            {/* 요일 헤더 */}
            <div className="grid grid-cols-7 border-b border-slate-100">
              {WD.map((wd, i) => (
                <div key={i} className="text-center py-2 text-xs font-semibold"
                  style={{ color: i === 6 ? '#EF4444' : i === 5 ? '#3B82F6' : '#94A3B8' }}>
                  {wd}
                </div>
              ))}
            </div>
            {/* 날짜 셀 */}
            <div className="grid grid-cols-7" style={{ gap: '1px', background: '#F1F5F9' }}>
              {cells.map((day, i) => {
                if (!day) return <div key={i} className="bg-white" style={{ minHeight: 68 }} />
                const wd = getWd(startDate, day)
                const isSat = wd === 5, isSun = wd === 6
                const isHol = (rules.public_holidays || []).includes(day)
                const s = shifts[day] || ''
                const st = sc(s)
                const ps = { ...shifts }; delete ps[day]
                const vs = s && nurseForValidate ? validate(ps, day, s, nurseForValidate, rules, startDate) : []
                const dateObj = getDate(startDate, day)
                const fixedWd = (nurseForValidate?.fixed_weekly_off != null && nurseForValidate?.fixed_weekly_off !== '')
                  ? parseInt(nurseForValidate.fixed_weekly_off) : -1
                const isFixedOff = (!isNaN(fixedWd) && fixedWd >= 0 && wd === fixedWd)
                const dateColor = isSat ? '#3B82F6' : (isSun || isHol) ? '#EF4444' : '#475569'
                const cellBg = isFixedOff ? '#F1F5F9' : (isSun || isSat || isHol) ? '#F8FAFF' : '#FFFFFF'

                if (isFixedOff) {
                  return (
                    <div key={i} className="flex flex-col items-center pt-1.5 cursor-not-allowed"
                      style={{ minHeight: 68, background: cellBg }}>
                      <span className="text-xs font-semibold" style={{ color: '#94A3B8' }}>{mmdd(dateObj)}</span>
                      <span className="mt-1 rounded-lg font-bold text-center px-1 py-0.5 text-xs w-4/5"
                        style={{ background: '#CBD5E1', color: 'white' }}>주</span>
                      <span className="text-xs mt-0.5" style={{ color: '#CBD5E1' }}>🔒</span>
                    </div>
                  )
                }

                return (
                  <button key={i}
                    onClick={() => { if (!passed) setPicker({ day }) }}
                    disabled={passed}
                    className="flex flex-col items-center pt-1.5 transition-colors active:bg-blue-50 relative"
                    style={{ minHeight: 68, background: cellBg }}>
                    <span className="text-xs font-bold" style={{ color: dateColor }}>{mmdd(dateObj)}</span>
                    {s ? (
                      <span className="mt-1 rounded-lg font-bold text-center px-1 py-0.5 text-xs w-4/5 leading-tight"
                        style={{ background: st.bg, color: st.fg, border: `1.5px solid ${st.border}` }}>
                        {s}
                      </span>
                    ) : (
                      <span className="mt-1.5 flex items-center justify-center rounded-full text-slate-300"
                        style={{ width: 24, height: 24, border: '2px dashed #CBD5E1', fontSize: 16 }}>+</span>
                    )}
                    {vs.length > 0 && (
                      <span className="absolute top-1 right-1 bg-red-500 text-white rounded-full flex items-center justify-center font-black"
                        style={{ width: 15, height: 15, fontSize: 9 }}>!</span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* 신청 내역 */}
          {reqCount > 0 && (
            <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">신청 내역</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(shifts).sort(([a], [b]) => +a - +b).map(([day, code]) => {
                  const st2 = sc(code)
                  const dObj = getDate(startDate, +day)
                  return (
                    <span key={day} className="rounded-lg font-semibold text-xs px-2.5 py-1 border"
                      style={{ background: st2.bg, color: st2.fg, borderColor: st2.border }}>
                      {mmdd(dObj)} {code}
                    </span>
                  )
                })}
              </div>
            </div>
          )}
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
          rules={rules}
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
