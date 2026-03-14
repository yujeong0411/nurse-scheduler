import { useState, useEffect, useRef, useCallback } from 'react'
import { requestsApi, nursesApi, rulesApi } from '../../api/client'
import { sc, fmtDate, getWd, getDate, mmdd, WD, NUM_DAYS, SHIFT_GROUPS, DEFAULT_RULES } from '../../utils/constants'
import { validate } from '../../utils/validate'

const WD_KR = ['월', '화', '수', '목', '금', '토', '일']

function NurseInfoBadges({ nurse }) {
  if (!nurse) return null
  const tags = []
  if (nurse.grade) tags.push({ label: nurse.grade, color: '#1d4ed8', bg: '#eff6ff' })
  if (nurse.role) tags.push({ label: nurse.role, color: '#6d28d9', bg: '#f5f3ff' })
  if (nurse.is_male) tags.push({ label: '남', color: '#0369a1', bg: '#e0f2fe' })
  if (nurse.is_4day_week) tags.push({ label: '주4일', color: '#047857', bg: '#ecfdf5' })
  if (nurse.is_pregnant) tags.push({ label: '임산부', color: '#be185d', bg: '#fdf2f8' })
  if (nurse.fixed_weekly_off != null && nurse.fixed_weekly_off !== '')
    tags.push({ label: `${WD_KR[nurse.fixed_weekly_off]}요일 주휴`, color: '#92400e', bg: '#fffbeb' })
  if (!tags.length) return null
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {tags.map((t, i) => (
        <span key={i} className="px-1.5 py-0.5 rounded text-xs font-medium"
          style={{ color: t.color, background: t.bg }}>{t.label}</span>
      ))}
    </div>
  )
}

export default function SubmissionsTab({ period }) {
  const [status, setStatus] = useState([])
  const [allRequests, setAllRequests] = useState({})
  const [fixedOffMap, setFixedOffMap] = useState({})   // nurse_id → fixed_weekly_off (int)
  const [nursesMap, setNursesMap] = useState({})        // nurse_id → nurse object
  const [rules, setRules] = useState(DEFAULT_RULES)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [activePick, setActivePick] = useState(null)
  const [blockPopup, setBlockPopup] = useState(null)  // { code, violations[] }
  const [saving, setSaving] = useState(null)
  const pickerRef = useRef(null)
  const periodIdRef = useRef(null)
  const allRequestsRef = useRef({})

  useEffect(() => {
    if (!period?.period_id) { setLoading(false); return }
    periodIdRef.current = period.period_id
    setLoading(true)
    Promise.all([
      requestsApi.getStatus(period.period_id),
      requestsApi.getAll(period.period_id),
      nursesApi.list(),
      rulesApi.get(),
    ]).then(([sRes, aRes, nRes, rRes]) => {
      setStatus(sRes.data)
      const map = {}
      aRes.data.forEach(item => {
        if (!map[item.nurse_id]) map[item.nurse_id] = {}
        map[item.nurse_id][item.day] = { code: item.code, note: item.note || '' }
      })
      setAllRequests(map)
      allRequestsRef.current = map
      const fMap = {}, nMap = {}
      ;(nRes.data || []).forEach(n => {
        nMap[n.id] = n
        if (n.fixed_weekly_off != null && n.fixed_weekly_off !== '') fMap[n.id] = parseInt(n.fixed_weekly_off)
      })
      setFixedOffMap(fMap)
      setNursesMap(nMap)
      if (rRes.data) setRules(rRes.data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [period?.period_id])

  useEffect(() => {
    if (!activePick) return
    const handler = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) setActivePick(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [activePick])

  const handleExport = async () => {
    if (!period?.period_id) return
    setExporting(true)
    try {
      const res = await requestsApi.exportXlsx(period.period_id)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      const _fmtYYMMDD = (d) => {
        const dt = typeof d === 'string' ? new Date(d) : d
        return `${String(dt.getFullYear()).slice(2)}${String(dt.getMonth()+1).padStart(2,'0')}${String(dt.getDate()).padStart(2,'0')}`
      }
      const _endDate = new Date(new Date(period.start_date).getTime() + 27 * 86400000)
      a.download = `근무 신청현황_${_fmtYYMMDD(period.start_date)}-${_fmtYYMMDD(_endDate)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch { alert('내보내기 실패') }
    finally { setExporting(false) }
  }

  const handleCellClick = (e, nurseId, day) => {
    e.stopPropagation()
    if (activePick?.nurseId === nurseId && activePick?.day === day) { setActivePick(null); return }
    const rect = e.currentTarget.getBoundingClientRect()
    setActivePick({ nurseId, day, x: rect.left, y: rect.bottom })
  }

  const handlePickCode = useCallback(async (code) => {
    if (!activePick) return
    const { nurseId, day } = activePick
    setActivePick(null)

    // ref로 최신 상태 읽기 (stale closure 방지)
    const nurseData = { ...(allRequestsRef.current[nurseId] || {}) }
    if (code) nurseData[day] = { code, note: nurseData[day]?.note || '' }
    else delete nurseData[day]

    // UI 즉시 반영
    const next = { ...allRequestsRef.current, [nurseId]: nurseData }
    allRequestsRef.current = next
    setAllRequests(next)

    setSaving(nurseId)
    try {
      const items = Object.entries(nurseData).map(([d, v]) => ({ day: parseInt(d), code: v.code, is_or: false, note: v.note || '' }))
      await requestsApi.upsert(periodIdRef.current, nurseId, items)
    } catch {
      // 실패 시 DB에서 재로드
      requestsApi.getAll(periodIdRef.current).then(res => {
        const map = {}
        res.data.forEach(item => {
          if (!map[item.nurse_id]) map[item.nurse_id] = {}
          map[item.nurse_id][item.day] = { code: item.code, note: item.note || '' }
        })
        allRequestsRef.current = map
        setAllRequests(map)
      }).catch(() => {})
      alert('저장에 실패했습니다.')
    } finally { setSaving(null) }
  }, [activePick])

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-slate-400 gap-2 text-sm">
      <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-400 rounded-full animate-spin" />
      불러오는 중...
    </div>
  )

  if (!period?.start_date) return (
    <div className="text-center py-16 text-slate-400 text-sm">시작일을 먼저 설정해주세요.</div>
  )

  const startDate = period.start_date
  const submitted = status.filter(s => s.submitted_at)
  const endStr = fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000))
  const days = Array.from({ length: NUM_DAYS }, (_, i) => i + 1)
  const pct = status.length > 0 ? Math.round(submitted.length / status.length * 100) : 0

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* 상단 바 */}
      <div className="bg-white border-b border-slate-100 px-4 py-3 flex items-center gap-4 flex-shrink-0">
        <div className="flex-1 min-w-0">
          <p className="font-bold text-slate-800 text-sm">{fmtDate(startDate)} ~ {endStr}</p>
          <div className="flex items-center gap-2 mt-1">
            <div className="flex-1 bg-slate-100 rounded-full h-1.5 max-w-32">
              <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-xs text-slate-500">{submitted.length}/{status.length}명 제출</span>
          </div>
        </div>
        <button onClick={handleExport} disabled={exporting}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50 flex-shrink-0">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          {exporting ? '내보내는 중...' : '엑셀 저장'}
        </button>
      </div>

      {/* 그리드 */}
      <div className="flex-1 min-h-0" style={{ overflowY: 'auto', overflowX: 'scroll' }}>
        <table className="text-xs border-collapse w-full" style={{ minWidth: 'max-content' }}>
          <thead>
            <tr>
              <th className="sticky top-0 left-0 z-30 bg-slate-100 text-slate-600 px-3 py-2 text-left font-semibold border-b border-r border-slate-200 whitespace-nowrap" style={{ minWidth: 88 }}>
                이름
              </th>
              {days.map(d => {
                const wd = getWd(startDate, d)
                const isSat = wd === 5, isSun = wd === 6
                const dateObj = getDate(startDate, d)
                return (
                  <th key={d} className="sticky top-0 z-10 py-1.5 font-medium text-center border-b border-r border-slate-200" style={{
                    minWidth: 42,
                    background: isSun ? '#fee2e2' : isSat ? '#eff6ff' : '#f8fafc',
                    color: isSun ? '#dc2626' : isSat ? '#2563eb' : '#64748b',
                  }}>
                    <div style={{ fontSize: 11 }}>{mmdd(dateObj)}</div>
                    <div style={{ fontSize: 11 }}>{WD[wd]}</div>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {status.map((st, ni) => {
              const shifts = allRequests[st.nurse_id] || {}
              const isSubmitted = !!st.submitted_at
              const isSavingThis = saving === st.nurse_id
              return (
                <tr key={st.nurse_id} className="group hover:bg-blue-100 transition-colors">
                  <td className="sticky left-0 z-10 px-3 py-1.5 font-medium whitespace-nowrap border-r border-b border-slate-200 bg-white group-hover:bg-blue-100 transition-colors">
                    <div className="flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isSavingThis ? 'bg-amber-400 animate-pulse' : isSubmitted ? 'bg-emerald-400' : 'bg-slate-200'}`} />
                      <span className="text-slate-800">{st.name}</span>
                    </div>
                  </td>
                  {days.map(d => {
                    const entry = shifts[d] || null
                    const code = entry?.code || ''
                    const note = entry?.note || ''
                    const wd = getWd(startDate, d)
                    const isSat = wd === 5, isSun = wd === 6
                    const c = code ? sc(code) : null
                    const isActive = activePick?.nurseId === st.nurse_id && activePick?.day === d
                    const isFixedOff = fixedOffMap[st.nurse_id] === wd
                    const baseBg = isSun ? '#fef2f2' : isSat ? '#eff6ff' : isFixedOff ? '#f5f5f4' : undefined
                    return (
                      <td key={d}
                        onClick={isFixedOff ? undefined : (e) => handleCellClick(e, st.nurse_id, d)}
                        className={`text-center border-b border-r border-slate-200 transition-colors ${isFixedOff ? 'cursor-default' : 'cursor-pointer'}`}
                        style={{
                          background: isActive ? '#dbeafe' : code && !isFixedOff ? '#fef9c3' : baseBg,
                          padding: '2px 1px',
                        }}>
                        <div className="flex flex-col items-center justify-center" style={{ minHeight: 22 }}>
                          {isFixedOff ? (
                            <span className="font-semibold" style={{ color: '#854D0E', fontSize: 11 }}>주</span>
                          ) : code ? (
                            <span className="relative font-semibold" style={{ color: code === 'N' ? '#B91C1C' : '#374151', fontSize: 11, lineHeight: 1 }} title={note || undefined}>
                              {code}
                              {note && (
                                <span className="absolute -top-1 -right-1 w-2 h-2 bg-amber-400 rounded-full border border-white" style={{ display: 'inline-block' }} />
                              )}
                            </span>
                          ) : null}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* 코드 피커 */}
      {activePick && (() => {
        const { nurseId, day } = activePick
        const nurse = nursesMap[nurseId] || null
        const sd = period?.start_date || null
        const dateObj = sd ? getDate(sd, day) : null
        const wd = sd ? getWd(sd, day) : null
        const shiftsForNurse = Object.fromEntries(
          Object.entries(allRequestsRef.current[nurseId] || {}).map(([d, v]) => [+d, v.code])
        )
        const shiftsWithout = { ...shiftsForNurse }; delete shiftsWithout[day]
        const currentCode = shiftsForNurse[day] || ''
        const popW = Math.min(292, window.innerWidth - 8)
        const popH = 320
        const top = activePick.y + 4 + popH > window.innerHeight ? activePick.y - popH - 4 : activePick.y + 4
        const left = Math.max(4, Math.min(activePick.x, window.innerWidth - popW - 4))
        return (
        <div ref={pickerRef}
          className="fixed z-50 bg-white rounded-2xl shadow-xl border border-slate-200"
          style={{ width: popW, top, left }}>

          {/* 헤더 */}
          <div className="px-3.5 pt-3 pb-2.5 border-b border-slate-100">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-bold text-slate-800 text-sm">{nurse?.name || ''}</span>
                {dateObj && (
                  <span className="text-xs text-slate-400 ml-2">
                    {dateObj.getMonth()+1}월 {dateObj.getDate()}일 ({WD[wd]})
                  </span>
                )}
              </div>
              <button onClick={() => setActivePick(null)}
                className="w-6 h-6 flex items-center justify-center text-slate-300 hover:text-slate-500 hover:bg-slate-100 rounded-full transition-colors text-base">
                ×
              </button>
            </div>
            <NurseInfoBadges nurse={nurse} />
          </div>

          {/* 근무 선택 */}
          <div className="p-3 space-y-2.5">
            {SHIFT_GROUPS.map(grp => (
              <div key={grp.label}>
                <p className="text-xs font-semibold mb-1.5" style={{ color: grp.color }}>{grp.label}</p>
                <div className="flex flex-wrap gap-1">
                  {grp.shifts.map(code => {
                    const c = sc(code)
                    const vs = nurse ? validate(shiftsWithout, day, code, nurse, rules, sd) : []
                    const isCur = code === currentCode
                    return (
                      <button key={code}
                        onClick={() => vs.length > 0 && !isCur
                          ? setBlockPopup({ code, violations: vs })
                          : handlePickCode(code)}
                        className="relative rounded-lg font-bold py-1 px-2.5 text-xs transition-all"
                        style={{
                          background: isCur ? c.fg : c.bg,
                          color: isCur ? 'white' : c.fg,
                          border: `1.5px solid ${vs.length > 0 && !isCur ? '#FCA5A5' : isCur ? c.fg : c.border}`,
                          opacity: vs.length > 0 && !isCur ? 0.45 : 1,
                        }}>
                        {code}
                        {vs.length > 0 && !isCur && (
                          <span className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full flex items-center justify-center font-black"
                            style={{ width: 13, height: 13, fontSize: 8 }}>!</span>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
            <div className="pt-1 border-t border-slate-100">
              <button onClick={() => handlePickCode('')}
                className="w-full py-1.5 text-xs font-semibold text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">
                지우기
              </button>
            </div>
          </div>
        </div>
        )
      })()}

      {/* 위반 차단 팝업 */}
      {blockPopup && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 px-4"
          onClick={() => setBlockPopup(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-5" onClick={e => e.stopPropagation()}>
            <p className="font-bold text-red-700 text-base mb-3">🚫 {blockPopup.code} — 선택 불가</p>
            {blockPopup.violations.map((v, i) => (
              <p key={i} className="text-red-500 text-sm mt-1">• {v}</p>
            ))}
            <button onClick={() => setBlockPopup(null)}
              className="mt-4 w-full py-2.5 rounded-xl font-semibold text-sm bg-slate-100 hover:bg-slate-200 transition-colors">
              확인
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
