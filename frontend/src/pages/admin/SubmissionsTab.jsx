import { useState, useEffect, useRef, useCallback } from 'react'
import { requestsApi, settingsApi } from '../../api/client'
import { sc, fmtDate, getWd, getDate, mmdd, WD, NUM_DAYS, SHIFT_GROUPS } from '../../utils/constants'

const PICKER_GROUPS = SHIFT_GROUPS  // [근무, 휴무, 기타]

export default function SubmissionsTab() {
  const [settings, setSettings] = useState(null)
  const [status, setStatus] = useState([])
  const [allRequests, setAllRequests] = useState({})  // nurseId → {day: code}
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [activePick, setActivePick] = useState(null)  // {nurseId, day, x, y}
  const [saving, setSaving] = useState(null)  // nurseId currently saving
  const pickerRef = useRef(null)
  const periodIdRef = useRef(null)

  useEffect(() => {
    settingsApi.get().then(res => {
      setSettings(res.data)
      periodIdRef.current = res.data.period_id
      if (res.data.period_id) {
        return Promise.all([
          requestsApi.getStatus(res.data.period_id),
          requestsApi.getAll(res.data.period_id),
        ]).then(([sRes, aRes]) => {
          setStatus(sRes.data)
          const map = {}
          aRes.data.forEach(item => {
            if (!map[item.nurse_id]) map[item.nurse_id] = {}
            map[item.nurse_id][item.day] = item.code
          })
          setAllRequests(map)
        })
      }
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  // 피커 바깥 클릭 닫기
  useEffect(() => {
    if (!activePick) return
    const handler = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) {
        setActivePick(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [activePick])

  const handleExport = async () => {
    if (!settings?.period_id) return
    setExporting(true)
    try {
      const res = await requestsApi.exportXlsx(settings.period_id)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `신청현황_${settings.start_date || ''}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch { alert('내보내기 실패') }
    finally { setExporting(false) }
  }

  const handleCellClick = (e, nurseId, day) => {
    e.stopPropagation()
    if (activePick?.nurseId === nurseId && activePick?.day === day) {
      setActivePick(null)
      return
    }
    const rect = e.currentTarget.getBoundingClientRect()
    setActivePick({ nurseId, day, x: rect.left, y: rect.bottom })
  }

  const handlePickCode = useCallback(async (code) => {
    if (!activePick) return
    const { nurseId, day } = activePick
    setActivePick(null)

    // 낙관적 업데이트
    setAllRequests(prev => {
      const next = { ...prev, [nurseId]: { ...(prev[nurseId] || {}) } }
      if (code) next[nurseId][day] = code
      else delete next[nurseId][day]
      return next
    })

    // 서버 저장
    setSaving(nurseId)
    try {
      const shifts = { ...(allRequests[nurseId] || {}) }
      if (code) shifts[day] = code
      else delete shifts[day]
      const items = Object.entries(shifts).map(([d, c]) => ({ day: parseInt(d), code: c, is_or: false }))
      await requestsApi.upsert(periodIdRef.current, nurseId, items)
    } catch {
      // 실패 시 원복
      setAllRequests(prev => ({ ...prev }))
    } finally {
      setSaving(null)
    }
  }, [activePick, allRequests])

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-slate-400 gap-2 text-sm">
      <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-400 rounded-full animate-spin" />
      불러오는 중...
    </div>
  )

  const startDate = settings?.start_date || null
  if (!startDate) return (
    <div className="text-center py-16 text-slate-400 text-sm">시작일을 먼저 설정해주세요.</div>
  )

  const submitted = status.filter(s => s.submitted_at)
  const endStr = fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000))
  const days = Array.from({ length: NUM_DAYS }, (_, i) => i + 1)

  return (
    <div className="p-2 sm:p-4 space-y-3">
      {/* 헤더 */}
      <div className="card p-3 sm:p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="font-bold text-slate-900 text-sm">{fmtDate(startDate)} ~ {endStr}</p>
            <p className="text-xs text-slate-500 mt-0.5">제출 {submitted.length}/{status.length}명</p>
          </div>
          <button onClick={handleExport} disabled={exporting} className="btn-primary text-sm px-4 py-2">
            {exporting ? '내보내는 중...' : '엑셀 저장'}
          </button>
        </div>
        <div className="bg-slate-100 rounded-full h-1.5">
          <div className="bg-blue-600 h-1.5 rounded-full transition-all"
            style={{ width: `${status.length > 0 ? submitted.length / status.length * 100 : 0}%` }} />
        </div>
      </div>

      {/* 그리드 */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto" style={{ WebkitOverflowScrolling: 'touch' }}>
          <table className="text-xs border-collapse" style={{ minWidth: 'max-content' }}>
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-slate-700 text-white px-3 py-2 text-left font-semibold whitespace-nowrap" style={{ minWidth: 88 }}>
                  이름
                </th>
                {days.map(d => {
                  const wd = getWd(startDate, d)
                  const isSat = wd === 5, isSun = wd === 6
                  const dateObj = getDate(startDate, d)
                  return (
                    <th key={d} className="py-2 font-semibold text-center" style={{
                      minWidth: 44,
                      background: isSun ? '#7f1d1d' : isSat ? '#1e3a8a' : '#334155',
                      color: isSun ? '#fca5a5' : isSat ? '#93c5fd' : 'rgba(255,255,255,0.9)',
                    }}>
                      <div style={{ fontSize: 11 }}>{mmdd(dateObj)}</div>
                      <div style={{ fontSize: 10, opacity: 0.8 }}>{WD[wd]}</div>
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
                  <tr key={st.nurse_id} className={ni % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                    <td className="sticky left-0 z-10 px-3 py-2 font-semibold whitespace-nowrap border-r border-slate-200"
                      style={{ background: ni % 2 === 0 ? 'white' : '#f8fafc' }}>
                      <div className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isSavingThis ? 'bg-blue-400 animate-pulse' : isSubmitted ? 'bg-green-400' : 'bg-slate-300'}`} />
                        <span className="text-slate-800">{st.name}</span>
                      </div>
                    </td>
                    {days.map(d => {
                      const code = shifts[d] || ''
                      const wd = getWd(startDate, d)
                      const isSat = wd === 5, isSun = wd === 6
                      const c = code ? sc(code) : null
                      const isActive = activePick?.nurseId === st.nurse_id && activePick?.day === d
                      return (
                        <td key={d}
                          onClick={(e) => handleCellClick(e, st.nurse_id, d)}
                          className="text-center p-1 border border-slate-100 cursor-pointer hover:bg-blue-50 transition-colors"
                          style={{
                            background: isActive ? '#dbeafe' : (isSat || isSun) ? '#f1f5f9' : undefined,
                          }}>
                          {code ? (
                            <span className="inline-block px-1 rounded font-bold"
                              style={{ background: c.bg, color: c.fg, border: `1px solid ${c.border}`, fontSize: 11, minWidth: 34, lineHeight: '22px' }}>
                              {code}
                            </span>
                          ) : (
                            <span className="inline-block" style={{ minWidth: 34, height: 22 }} />
                          )}
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 코드 피커 */}
      {activePick && (
        <div ref={pickerRef}
          className="fixed z-50 bg-white rounded-2xl shadow-2xl border border-slate-200 p-3"
          style={{
            width: Math.min(288, window.innerWidth - 8),
            top: activePick.y + 4 + 260 > window.innerHeight ? activePick.y - 264 : activePick.y + 4,
            left: Math.max(4, Math.min(activePick.x, window.innerWidth - Math.min(288, window.innerWidth - 8) - 4)),
          }}>
          <div className="space-y-2">
            {PICKER_GROUPS.map(grp => (
              <div key={grp.label}>
                <p className="text-xs font-semibold mb-1.5" style={{ color: grp.color }}>{grp.label}</p>
                <div className="flex flex-wrap gap-1">
                  {grp.shifts.map(code => {
                    const c = sc(code)
                    return (
                      <button key={code} onClick={() => handlePickCode(code)}
                        className="px-2 py-0.5 rounded font-bold text-xs transition-opacity hover:opacity-80"
                        style={{ background: c.bg, color: c.fg, border: `1px solid ${c.border}` }}>
                        {code}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
            <div className="pt-1 border-t border-slate-100">
              <button onClick={() => handlePickCode('')}
                className="w-full py-1.5 text-xs font-semibold text-slate-500 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">
                지우기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
