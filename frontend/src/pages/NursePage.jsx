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
  const { token, nurseId, nurseName, clearAuth } = useAuthStore()

  const [settings, setSettings] = useState(null)
  const [rules, setRules] = useState(DEFAULT_RULES)
  const [periodId, setPeriodId] = useState(null)
  const [nurse, setNurse] = useState(null)
  const [shifts, setShifts] = useState({})
  const [picker, setPicker] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [showPin, setShowPin] = useState(false)
  const [toast, setToast] = useState('')

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(''), 3000) }

  // 설정·규칙·신청·프로필 데이터 로드
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
          const map = {}
          ;(reqRes.data || []).forEach(it => { map[it.day] = it.code })
          setShifts(map)
        }
      } catch (e) {
        if (e.response?.status === 401) { clearAuth(); navigate('/') }
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const setShift = useCallback((day, s) => {
    setShifts(prev => {
      const next = { ...prev }
      if (s) next[day] = s; else delete next[day]
      return next
    })
    setSaved(false)
  }, [])

  const handleSubmit = async () => {
    if (!periodId) { showToast('❌ 관리자가 시작일을 설정해야 합니다.'); return }
    if (dlPassed(settings?.deadline)) { showToast('❌ 신청 마감이 지났습니다.'); return }
    setSaving(true)
    try {
      const items = Object.entries(shifts).map(([day, code]) => ({
        day: parseInt(day), code, is_or: false
      }))
      await requestsApi.upsert(periodId, nurseId, items)
      setSaved(true)
      showToast('✅ 신청이 저장되었습니다.')
    } catch (e) {
      showToast('❌ 저장 실패. 다시 시도해주세요.')
    } finally {
      setSaving(false)
    }
  }

  const handleLogout = () => { clearAuth(); navigate('/') }

  const startDate = settings?.start_date || null
  const deadline = settings?.deadline || null
  const passed = dlPassed(deadline)
  const endStr = startDate ? fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000)) : ''

  // 달력 셀 구성
  const startWd = startDate ? getWd(startDate, 1) : 0
  const cells = []
  for (let i = 0; i < startWd; i++) cells.push(null)
  for (let d = 1; d <= NUM_DAYS; d++) cells.push(d)
  while (cells.length % 7 !== 0) cells.push(null)

  // 통계
  let nCnt = 0, wCnt = 0, oCnt = 0
  Object.entries(shifts).forEach(([, v]) => {
    if (v) {
      if (WORK_SET.has(v)) wCnt++; else oCnt++
      if (v === 'N') nCnt++
    }
  })
  const reqCount = Object.keys(shifts).length

  // validate()가 기대하는 필드명으로 변환 (is_4day_week → is_4day)
  const nurseForValidate = nurse ? {
    ...nurse,
    is_4day: nurse.is_4day_week,
  } : null
  const allV = (startDate && nurseForValidate) ? Object.entries(shifts).reduce((acc, [day, code]) => {
    validate(shifts, +day, code, nurseForValidate, rules, startDate)
      .forEach(v => acc.push(`${day}일: ${v}`))
    return acc
  }, []) : []

  return (
    <div className="min-h-screen" style={{ background: '#F1F5F9' }}>
      {/* 헤더 */}
      <div className="sticky top-0 z-10 shadow-md" style={{ background: 'linear-gradient(135deg,#1e3a8a,#2563eb)' }}>
        <div className="flex items-center gap-3 px-4 pt-5 pb-2">
          <button onClick={handleLogout}
            className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center text-white text-lg font-bold flex-shrink-0">
            ←
          </button>
          <div className="flex-1">
            <h1 className="font-bold text-white leading-tight" style={{ fontSize: '22px' }}>{nurseName}</h1>
            {startDate && <p className="text-blue-200 text-sm mt-0.5">{fmtDate(startDate)} ~ {endStr}</p>}
          </div>
          <button onClick={() => setShowPin(true)}
            className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ fontSize: '18px' }} title="PIN 변경">🔐
          </button>
        </div>
      </div>

      {/* 마감 배너 */}
      {deadline && (
        <div className={`text-center py-3 font-bold ${passed ? 'bg-red-600 text-white' : 'bg-yellow-400 text-yellow-900'}`}
          style={{ fontSize: '14px' }}>
          {passed ? '⛔ 신청이 마감되었습니다' : `⏰ 마감: ${fmtDate(deadline)}`}
        </div>
      )}

      {!startDate && !loading ? (
        <div className="flex flex-col items-center justify-center py-24 text-gray-400 text-center">
          <span className="text-5xl mb-3">⚙️</span>
          <p className="text-sm">관리자가 시작일을 설정해야 합니다.</p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-24 text-gray-400">
          <span className="text-2xl mr-2">⏳</span>불러오는 중...
        </div>
      ) : (
        <div style={{ paddingBottom: '100px' }}>
          {/* 통계 바 */}
          <div className="grid grid-cols-4 gap-2 p-4">
            {[
              ['신청', reqCount, '#1D4ED8'],
              ['근무', wCnt, '#0369A1'],
              ['야간', nCnt, '#DC2626'],
              ['휴무', oCnt, '#B45309'],
            ].map(([label, val, color]) => (
              <div key={label} className="rounded-2xl text-center py-3 px-1"
                style={{ background: color, boxShadow: '0 2px 8px rgba(0,0,0,0.12)' }}>
                <div className="text-white font-black" style={{ fontSize: '26px', lineHeight: 1 }}>{val}</div>
                <div className="text-white/80 font-semibold mt-1" style={{ fontSize: '11px' }}>{label}</div>
              </div>
            ))}
          </div>

          {/* 위반 목록 */}
          {allV.length > 0 && (
            <div className="mx-4 mb-3 rounded-2xl p-4" style={{ background: '#FEF2F2', border: '1.5px solid #FECACA' }}>
              <p className="font-bold text-red-700 mb-2" style={{ fontSize: '14px' }}>⚠️ 규칙 위반 {allV.length}건</p>
              {allV.slice(0, 3).map((v, i) => <p key={i} className="text-red-600 mt-1" style={{ fontSize: '13px' }}>• {v}</p>)}
              {allV.length > 3 && <p className="text-red-400 mt-1" style={{ fontSize: '12px' }}>외 {allV.length - 3}건...</p>}
            </div>
          )}
          {allV.length === 0 && reqCount > 0 && (
            <div className="mx-4 mb-3 rounded-2xl px-4 py-3" style={{ background: '#F0FDF4', border: '1.5px solid #BBF7D0' }}>
              <p className="font-semibold text-green-700" style={{ fontSize: '14px' }}>✓ 규칙 위반 없음</p>
            </div>
          )}

          {/* 달력 */}
          <div className="mx-4 bg-white rounded-2xl overflow-hidden" style={{ boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
            {/* 요일 헤더 */}
            <div className="grid grid-cols-7" style={{ background: '#1e3a8a' }}>
              {WD.map((wd, i) => (
                <div key={i} className="text-center font-bold py-2.5" style={{
                  fontSize: '13px',
                  color: i === 5 ? '#93C5FD' : i === 6 ? '#FCA5A5' : 'rgba(255,255,255,0.9)'
                }}>{wd}</div>
              ))}
            </div>
            {/* 날짜 셀 */}
            <div className="grid grid-cols-7" style={{ gap: '1px', background: '#E5E7EB' }}>
              {cells.map((day, i) => {
                if (!day) return <div key={i} className="bg-white" style={{ minHeight: '72px' }} />
                const wd = getWd(startDate, day)
                const isSat = wd === 5, isSun = wd === 6
                const isHol = (rules.public_holidays || []).includes(day)
                const s = shifts[day] || ''
                const st = sc(s)
                const vs = s && nurseForValidate ? validate(shifts, day, s, nurseForValidate, rules, startDate) : []
                const dateObj = getDate(startDate, day)
                const fixedWd = (nurseForValidate?.fixed_weekly_off != null && nurseForValidate?.fixed_weekly_off !== '')
                  ? parseInt(nurseForValidate.fixed_weekly_off) : -1
                const isFixedOff = (!isNaN(fixedWd) && fixedWd >= 0 && wd === fixedWd)
                const dateColor = isSat ? '#3B82F6' : (isSun || isHol) ? '#EF4444' : '#374151'

                if (isFixedOff) {
                  return (
                    <div key={i} className="flex flex-col items-center relative"
                      style={{ minHeight: '72px', background: '#E5E7EB', cursor: 'not-allowed', paddingTop: '6px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 600, color: '#9CA3AF' }}>{mmdd(dateObj)}</span>
                      <span className="mt-1 rounded-lg font-bold w-4/5 text-center"
                        style={{ background: '#9CA3AF', color: 'white', fontSize: '11px', padding: '3px 2px' }}>주</span>
                      <span className="absolute bottom-1" style={{ fontSize: '9px' }}>🔒</span>
                    </div>
                  )
                }

                return (
                  <button key={i}
                    onClick={() => { if (!passed) setPicker({ day }) }}
                    disabled={passed}
                    className="flex flex-col items-center relative active:opacity-60 transition-opacity"
                    style={{ minHeight: '72px', background: (isHol || isSat || isSun) ? '#EFF6FF' : '#FFFFFF', paddingTop: '6px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: dateColor }}>{mmdd(dateObj)}</span>
                    {s ? (
                      <span className="mt-1 rounded-lg font-bold w-4/5 text-center"
                        style={{ background: st.fg, color: 'white', fontSize: '12px', padding: '3px 2px', letterSpacing: '-0.3px' }}>
                        {s}
                      </span>
                    ) : (
                      <span className="mt-1.5 flex items-center justify-center rounded-full"
                        style={{ width: '24px', height: '24px', border: '2px dashed #D1D5DB', color: '#D1D5DB', fontSize: '14px' }}>
                        +
                      </span>
                    )}
                    {vs.length > 0 && (
                      <span className="absolute top-1 right-1 bg-red-500 rounded-full flex items-center justify-center text-white font-black"
                        style={{ width: '16px', height: '16px', fontSize: '9px' }}>!</span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* 신청 내역 리스트 */}
          {reqCount > 0 && (
            <div className="mx-4 mt-3 bg-white rounded-2xl p-4" style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <p className="font-bold text-gray-600 mb-3" style={{ fontSize: '14px' }}>신청 내역</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(shifts).sort(([a], [b]) => +a - +b).map(([day, code]) => {
                  const st2 = sc(code)
                  const dObj = getDate(startDate, +day)
                  return (
                    <span key={day} className="rounded-xl font-semibold border"
                      style={{ background: st2.bg, color: st2.fg, borderColor: st2.border, fontSize: '13px', padding: '5px 10px' }}>
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
        <div className="fixed bottom-0 left-0 right-0 px-4 pb-6 pt-3"
          style={{ background: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(8px)', borderTop: '1px solid #E5E7EB' }}>
          <button onClick={handleSubmit} disabled={saving}
            className="w-full rounded-2xl font-bold transition-all active:scale-95"
            style={{
              padding: '18px', fontSize: '17px',
              background: saved ? '#16A34A' : '#2563EB',
              color: 'white',
              boxShadow: saved ? '0 4px 14px rgba(22,163,74,0.4)' : '0 4px 14px rgba(37,99,235,0.4)',
              opacity: saving ? 0.7 : 1
            }}>
            {saving ? '저장 중...' : saved ? '✅ 신청 완료 (재저장 가능)' : '📨 신청 제출하기'}
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
          onSelect={(s) => { setShift(picker.day, s); setPicker(null) }}
          onClose={() => setPicker(null)}
        />
      )}

      {showPin && <PinModal onClose={() => setShowPin(false)} />}

      {toast && (
        <div className="fixed top-4 left-4 right-4 z-50 flex justify-center" style={{ pointerEvents: 'none' }}>
          <div className="rounded-2xl px-5 py-3 shadow-lg font-semibold text-sm"
            style={{
              background: toast.startsWith('❌') ? '#FEF2F2' : '#F0FDF4',
              color: toast.startsWith('❌') ? '#DC2626' : '#16A34A',
              border: `1.5px solid ${toast.startsWith('❌') ? '#FECACA' : '#BBF7D0'}`,
              pointerEvents: 'auto'
            }}>{toast}</div>
        </div>
      )}
    </div>
  )
}
