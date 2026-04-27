import { useState, useEffect, useRef, useCallback } from 'react'
import { requestsApi, nursesApi, rulesApi } from '../../api/client'
import { sc, fmtDate, getWd, getDate, mmdd, WD, NUM_DAYS, SHIFT_GROUPS, WORK_SET, DEFAULT_RULES } from '../../utils/constants'
import { validate } from '../../utils/validate'
import NameFilter from '../../components/NameFilter'

const WD_KR = ['월', '화', '수', '목', '금', '토', '일']

function buildRequestMap(items) {
  const map = {}
  items.forEach(item => {
    if (!map[item.nurse_id]) map[item.nurse_id] = {}
    const day = item.day
    if (!map[item.nurse_id][day]) {
      map[item.nurse_id][day] = { codes: [], is_or: false, note: item.note || '', condition: item.condition || 'B' }
    }
    map[item.nurse_id][day].codes.push(item.code)
    if (item.is_or) map[item.nurse_id][day].is_or = true
    if (item.note) map[item.nurse_id][day].note = item.note
    if (item.condition === 'A') map[item.nurse_id][day].condition = 'A'
  })
  return map
}

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
  const [importing, setImporting] = useState(false)
  const [importMsg, setImportMsg] = useState(null)
  const [activePick, setActivePick] = useState(null)
  const [pickerSelected, setPickerSelected] = useState([])  // 피커 내 임시 선택
  const [pickerCondition, setPickerCondition] = useState('B')  // 피커 내 A/B 조건
  const [blockPopup, setBlockPopup] = useState(null)  // { code, violations[] }
  const [saving, setSaving] = useState(null)
  const [selectedNames, setSelectedNames] = useState(null)
  const [highlightedId, setHighlightedId] = useState(null)
  const [dateFilter, setDateFilter] = useState(null)   // null | { day, codes: Set }
  const [datePicker, setDatePicker] = useState(null)   // null | { day, x, y }
  const [scores, setScores] = useState({})              // nurse_id → score
  const [scoreSortAsc, setScoreSortAsc] = useState(false) // 점수 낮은 순 정렬
  const pickerRef = useRef(null)
  const datePickerRef = useRef(null)
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
      requestsApi.getAllScores(period.period_id).catch(() => ({ data: [] })),
    ]).then(([sRes, aRes, nRes, rRes, scRes]) => {
      setStatus(sRes.data)
      const map = buildRequestMap(aRes.data)
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
      const sMap = {}
      ;(scRes.data || []).forEach(r => { sMap[r.nurse_id] = r.score })
      setScores(sMap)
    }).catch(() => {}).finally(() => setLoading(false))

  }, [period?.period_id])

  const handleRefreshStatus = () => {
    if (!periodIdRef.current) return
    requestsApi.getStatus(periodIdRef.current)
      .then(res => setStatus(res.data))
      .catch(() => {})
  }

  useEffect(() => {
    if (!activePick) return
    const handler = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) setActivePick(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [activePick])

  useEffect(() => {
    if (!datePicker) return
    const handler = (e) => {
      if (datePickerRef.current && !datePickerRef.current.contains(e.target)) setDatePicker(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [datePicker])

  const handleDateHeaderClick = (e, d) => {
    if (datePicker?.day === d) { setDatePicker(null); return }
    const rect = e.currentTarget.getBoundingClientRect()
    setDatePicker({ day: d, x: rect.left, y: rect.bottom })
  }

  const handleImport = async (e) => {
    const file = e.target.files[0]
    if (!file || !period?.period_id) return
    setImporting(true)
    setImportMsg(null)
    try {
      const res = await requestsApi.importXlsx(period.period_id, file)
      setImportMsg({ ok: true, text: res.data.message })
      setTimeout(() => setImportMsg(null), 3000)
      // 데이터 새로고침
      const [sRes, aRes] = await Promise.all([
        requestsApi.getStatus(period.period_id),
        requestsApi.getAll(period.period_id),
      ])
      setStatus(sRes.data)
      const map = buildRequestMap(aRes.data)
      allRequestsRef.current = map
      setAllRequests(map)
    } catch (err) {
      setImportMsg({ ok: false, text: err.response?.data?.detail || '가져오기 실패' })
      setTimeout(() => setImportMsg(null), 4000)
    } finally {
      setImporting(false)
      e.target.value = ''
    }
  }

  const handleRecalcScores = async () => {
    if (!period?.period_id) return
    if (!window.confirm('현재 신청 데이터 기준으로 전체 점수를 재계산합니다.')) return
    try {
      await requestsApi.recalcScores(period.period_id)
      const scRes = await requestsApi.getAllScores(period.period_id)
      const map = {}
      scRes.data.forEach(s => { map[s.nurse_id] = s.score })
      setScores(map)
    } catch (e) {
      alert('점수 재계산 실패: ' + (e.response?.data?.detail || e.message))
    }
  }

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
    setHighlightedId(nurseId)
    if (activePick?.nurseId === nurseId && activePick?.day === day) { setActivePick(null); return }
    const rect = e.currentTarget.getBoundingClientRect()
    const existingCodes = allRequestsRef.current[nurseId]?.[day]?.codes || []
    const existingCondition = allRequestsRef.current[nurseId]?.[day]?.condition || 'B'
    setPickerSelected(existingCodes)
    setPickerCondition(existingCondition)
    setBlockPopup(null)
    setActivePick({ nurseId, day, x: rect.left, y: rect.bottom })
  }

  const handlePickCodes = useCallback(async (codes, condition = 'B') => {
    if (!activePick) return
    const { nurseId, day } = activePick
    setActivePick(null)

    // ref로 최신 상태 읽기 (stale closure 방지)
    const nurseData = { ...(allRequestsRef.current[nurseId] || {}) }
    if (codes.length > 0) nurseData[day] = { codes, is_or: codes.length > 1, note: nurseData[day]?.note || '', condition }
    else delete nurseData[day]

    // UI 즉시 반영
    const next = { ...allRequestsRef.current, [nurseId]: nurseData }
    allRequestsRef.current = next
    setAllRequests(next)

    setSaving(nurseId)
    try {
      const _SKIP = new Set(['병가', '필수'])
      const items = Object.entries(nurseData).flatMap(([d, v]) => {
        const isOr = v.codes.length > 1
        const cond = v.condition || 'B'
        return v.codes.map(c => ({ day: parseInt(d), code: c, is_or: isOr, note: v.note || '', condition: _SKIP.has(c) ? 'B' : cond }))
      })
      await requestsApi.upsert(periodIdRef.current, nurseId, items)
    } catch {
      requestsApi.getAll(periodIdRef.current).then(res => {
        const map = buildRequestMap(res.data)
        allRequestsRef.current = map
        setAllRequests(map)
      }).catch(() => {})
      alert('저장에 실패했습니다.')
    } finally { setSaving(null) }
  }, [activePick])

  const startDate = period?.start_date || null
  const submitted = status.filter(s => s.submitted_at)
  const endStr = startDate ? fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000)) : ''
  const days = Array.from({ length: NUM_DAYS }, (_, i) => i + 1)
  const pct = status.length > 0 ? Math.round(submitted.length / status.length * 100) : 0
  const allNames = status.map(s => s.name)
  const filteredStatus = selectedNames !== null
    ? status.filter(s => selectedNames.has(s.name))
    : status
  const dateFiltered = dateFilter
    ? filteredStatus.filter(s => {
        const codes = allRequests[s.nurse_id]?.[dateFilter.day]?.codes || []
        return codes.some(c => dateFilter.codes.has(c))
      })
    : filteredStatus
  const displayStatus = scoreSortAsc
    ? [...dateFiltered].sort((a, b) => (scores[a.nurse_id] ?? 100) - (scores[b.nurse_id] ?? 100))
    : dateFiltered

  const pickerCodes = datePicker ? (() => {
    const s = new Set()
    status.forEach(st => {
      const codes = allRequestsRef.current[st.nurse_id]?.[datePicker.day]?.codes || []
      codes.forEach(c => s.add(c))
    })
    return [...s].sort()
  })() : []

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* 상단 바 */}
      <div id="admin-submissions-toolbar" className="bg-white border-b border-slate-100 px-4 py-3 flex items-center gap-4 flex-shrink-0">
        <div className="flex-1 min-w-0">
          {startDate && <p className="font-bold text-slate-800 text-sm">{fmtDate(startDate)} ~ {endStr}</p>}
          <div className="flex items-center gap-2 mt-1">
            <div className="flex-1 bg-slate-100 rounded-full h-1.5 max-w-32">
              <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-xs text-slate-500">{submitted.length}/{status.length}명 제출</span>
            <button onClick={handleRefreshStatus} title="제출 현황 새로고침"
              className="flex items-center justify-center w-5 h-5 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
              </svg>
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={handleRecalcScores}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex-shrink-0 border bg-amber-50 text-amber-700 border-amber-300 hover:bg-amber-100">
            점수 재계산
          </button>
          <button
            onClick={() => setScoreSortAsc(v => !v)}
            title="점수 낮은 순 정렬"
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex-shrink-0 border ${scoreSortAsc ? 'bg-violet-100 text-violet-700 border-violet-300' : 'bg-slate-100 text-slate-600 border-slate-300 hover:bg-slate-200'}`}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"/><polyline points="5 12 12 19 19 12"/>
            </svg>
            점수순
          </button>
          <label className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer flex-shrink-0 ${importing ? 'opacity-50 pointer-events-none' : ''} bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300`}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            {importing ? '가져오는 중...' : '엑셀 불러오기'}
            <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handleImport} />
          </label>
          <button onClick={handleExport} disabled={exporting}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50 flex-shrink-0">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            {exporting ? '내보내는 중...' : '엑셀 저장'}
          </button>
        </div>
      </div>

      {/* 그리드 */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-400 gap-2 text-sm">
          <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-400 rounded-full animate-spin" />
          불러오는 중...
        </div>
      ) : !startDate ? (
        <div className="text-center py-16 text-slate-400 text-sm">시작일을 먼저 설정해주세요.</div>
      ) : (
      <div id="admin-submissions-grid" className="flex-1 min-h-0" style={{ overflowY: 'auto', overflowX: 'scroll' }}>
        <table className="text-xs border-collapse w-full" style={{ minWidth: 'max-content' }}>
          <thead>
            <tr>
              <th className="sticky top-0 left-0 z-30 px-3 py-2 text-left font-semibold whitespace-nowrap"
                style={{ minWidth: 88, background: '#f1f5f9', color: '#334155', boxShadow: '0 1px 4px rgba(0,0,0,0.09), 2px 0 6px rgba(0,0,0,0.06)' }}>
                <NameFilter allNames={allNames} selectedNames={selectedNames} onChange={setSelectedNames} />
              </th>
              {days.map(d => {
                const wd = getWd(startDate, d)
                const isSat = wd === 5, isSun = wd === 6
                const dateObj = getDate(startDate, d)
                const isPickerOpen = datePicker?.day === d
                const isFiltered = dateFilter?.day === d
                return (
                  <th key={d}
                    onClick={(e) => handleDateHeaderClick(e, d)}
                    className="sticky top-0 z-10 py-1.5 font-medium text-center border-r border-slate-200 cursor-pointer transition-colors"
                    style={{
                      minWidth: 42,
                      background: isPickerOpen ? '#e0e7ff' : isFiltered ? '#dbeafe' : isSun ? '#fff0f0' : isSat ? '#f0f4ff' : '#f1f5f9',
                      color: isSun ? '#dc2626' : isSat ? '#2563eb' : '#475569',
                      boxShadow: '0 1px 4px rgba(0,0,0,0.09)',
                    }}>
                    <div style={{ fontSize: 11 }}>{mmdd(dateObj)}</div>
                    <div style={{ fontSize: 11 }}>{WD[wd]}</div>
                    {isFiltered && <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#3b82f6', margin: '1px auto 0' }} />}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {displayStatus.map((st, ni) => {
              const shifts = allRequests[st.nurse_id] || {}
              const isSubmitted = !!st.submitted_at
              const isSavingThis = saving === st.nurse_id
              return (
                <tr key={st.nurse_id} className={`group transition-colors ${highlightedId === st.nurse_id ? 'bg-blue-100' : 'hover:bg-blue-100'}`}>
                  <td className={`sticky left-0 z-10 px-3 py-1.5 font-medium whitespace-nowrap border-b border-slate-200 transition-colors cursor-pointer ${highlightedId === st.nurse_id ? 'bg-blue-50' : 'bg-white group-hover:bg-blue-50'}`}
                    style={{ boxShadow: '2px 0 6px rgba(0,0,0,0.06)' }}
                    onClick={() => { setActivePick(null); setHighlightedId(id => id === st.nurse_id ? null : st.nurse_id) }}
                    onMouseDown={e => e.stopPropagation()}>
                    <div className="flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isSavingThis ? 'bg-amber-400 animate-pulse' : isSubmitted ? 'bg-emerald-400' : 'bg-slate-200'}`} />
                      <span className="text-slate-800">{st.name}</span>
                      {(() => { const sc = scores[st.nurse_id] ?? 100; return (
                        <span className="px-1 py-0.5 rounded text-[10px] font-bold leading-none"
                          style={{ background: sc <= 70 ? '#FEE2E2' : sc < 100 ? '#EDE9FE' : '#F1F5F9', color: sc <= 70 ? '#B91C1C' : sc < 100 ? '#6D28D9' : '#94A3B8' }}>
                          {sc}점
                        </span>
                      ) })()}
                    </div>
                  </td>
                  {days.map(d => {
                    const entry = shifts[d] || null
                    const codes = entry?.codes || []
                    const code = codes.join('/')      // 표시용 ("N" 또는 "N/휴가")
                    const note = entry?.note || ''
                    const wd = getWd(startDate, d)
                    const isSat = wd === 5, isSun = wd === 6
                    const c = codes.length > 0 ? sc(codes[0]) : null   // 첫 코드 색상 사용
                    const isActive = activePick?.nurseId === st.nurse_id && activePick?.day === d
                    const isFixedOff = fixedOffMap[st.nurse_id] === wd
                    const baseBg = isSun ? '#fef2f2' : isSat ? '#eff6ff' : isFixedOff ? '#f5f5f4' : undefined
                    return (
                      <td key={d}
                        onClick={isFixedOff ? undefined : (e) => handleCellClick(e, st.nurse_id, d)}
                        className={`text-center border-b border-r border-slate-200 transition-colors ${isFixedOff ? 'cursor-default' : 'cursor-pointer'}`}
                        style={{
                          background: isActive ? '#dbeafe' : code && !isFixedOff ? '#fef9c3' : baseBg,
                          boxShadow: isActive ? 'inset 0 0 0 2px #3b82f6' : undefined,
                          padding: '2px 1px',
                        }}
                        onMouseEnter={e => { if (!isFixedOff && !isActive) e.currentTarget.style.background = code ? '#fef3c7' : isSun ? '#fee2e2' : isSat ? '#dbeafe' : '#f1f5f9' }}
                        onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = isActive ? '#dbeafe' : code && !isFixedOff ? '#fef9c3' : baseBg }}>
                        <div className="flex flex-col items-center justify-center" style={{ minHeight: 22 }}>
                          {isFixedOff ? (
                            <span className="font-semibold" style={{ color: '#854D0E', fontSize: 11 }}>주</span>
                          ) : code ? (
                            <span className="relative font-semibold" style={{ color: codes[0] === 'N' ? '#B91C1C' : '#374151', fontSize: code.length > 3 ? 9 : 11, lineHeight: 1 }} title={note || undefined}>
                              {code}
                              {entry?.condition === 'A' && (
                                <span className="absolute -top-1.5 -left-1.5 text-white rounded-full flex items-center justify-center font-black"
                                  style={{ background: '#4338CA', width: 11, height: 11, fontSize: 7 }}>A</span>
                              )}
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
      )}

      {/* 날짜 필터 피커 */}
      {datePicker && (() => {
        const popW = 140
        const popH = 52 + pickerCodes.length * 28 + (dateFilter?.day === datePicker.day ? 36 : 0)
        const top = datePicker.y + 4 + popH > window.innerHeight ? datePicker.y - popH - 4 : datePicker.y + 4
        const left = Math.max(4, Math.min(datePicker.x, window.innerWidth - popW - 4))
        const isThisDayFiltered = dateFilter?.day === datePicker.day

        const toggleCode = (code) => {
          const base = isThisDayFiltered ? new Set(dateFilter.codes) : new Set(pickerCodes)
          if (base.has(code)) {
            base.delete(code)
            if (base.size === 0 || base.size === pickerCodes.length) { setDateFilter(null); return }
          } else {
            base.add(code)
            if (base.size === pickerCodes.length) { setDateFilter(null); return }
          }
          setDateFilter({ day: datePicker.day, codes: base })
        }

        return (
          <div ref={datePickerRef}
            className="fixed z-50 bg-white rounded-xl shadow-xl border border-slate-200"
            style={{ top, left, width: popW }}>
            <div className="px-3 py-2 border-b border-slate-100 text-xs font-semibold text-slate-500">
              {mmdd(getDate(startDate, datePicker.day))} 필터
            </div>
            {pickerCodes.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-3">데이터 없음</p>
            ) : (
              <div className="py-1">
                <label className="flex items-center gap-2 px-3 py-1 hover:bg-slate-50 cursor-pointer border-b border-slate-100 mb-1">
                  <input type="checkbox"
                    checked={!isThisDayFiltered}
                    ref={el => { if (el) el.indeterminate = isThisDayFiltered && dateFilter.codes.size > 0 && dateFilter.codes.size < pickerCodes.length }}
                    onChange={() => isThisDayFiltered ? setDateFilter(null) : setDateFilter({ day: datePicker.day, codes: new Set() })}
                    style={{ width: 13, height: 13, accentColor: '#3b82f6', cursor: 'pointer' }} />
                  <span className="text-xs font-semibold text-slate-600">(전체)</span>
                </label>
                {pickerCodes.map(code => {
                  const checked = !isThisDayFiltered || dateFilter.codes.has(code)
                  return (
                    <label key={code} className="flex items-center gap-2 px-3 py-1 hover:bg-slate-50 cursor-pointer">
                      <input type="checkbox" checked={checked} onChange={() => toggleCode(code)}
                        style={{ width: 13, height: 13, accentColor: '#3b82f6', cursor: 'pointer' }} />
                      <span className="text-xs font-semibold"
                        style={{ color: code === 'N' ? '#B91C1C' : '#374151' }}>
                        {code}
                      </span>
                    </label>
                  )
                })}
              </div>
            )}
            {isThisDayFiltered && (
              <div className="px-2 py-1.5 border-t border-slate-100">
                <button onClick={() => setDateFilter(null)}
                  className="w-full text-xs text-blue-600 hover:text-blue-800 font-semibold py-0.5 text-center">
                  초기화
                </button>
              </div>
            )}
          </div>
        )
      })()}

      {/* 코드 피커 */}
      {activePick && (() => {
        const { nurseId, day } = activePick
        const nurse = nursesMap[nurseId] || null
        const sd = period?.start_date || null
        const isHol = (rules.public_holidays || []).includes(day)
        const shiftsForNurse = Object.fromEntries(
          Object.entries(allRequestsRef.current[nurseId] || {}).map(([d, v]) => [+d, (v.codes || [])[0] || ''])
        )
        const shiftsWithout = { ...shiftsForNurse }; delete shiftsWithout[day]
        const note = allRequestsRef.current[nurseId]?.[day]?.note
        const popW = Math.min(260, window.innerWidth - 8)
        const popH = (blockPopup ? 340 : 260) + (note ? 40 : 0)
        const top = activePick.y + 2 + popH > window.innerHeight ? activePick.y - popH - 2 : activePick.y + 2
        const left = Math.max(4, Math.min(activePick.x, window.innerWidth - popW - 4))
        return (
        <div ref={pickerRef}
          className="fixed z-50 bg-white rounded-xl shadow-xl border border-slate-200"
          style={{ width: popW, top, left }}>
          <div className="p-2 space-y-1.5">
            {/* 현재 선택 미리보기 */}
            <div className="flex items-center gap-1 flex-wrap min-h-[22px]">
              {pickerSelected.length > 0 ? pickerSelected.map(s => {
                const c = sc(s)
                return (
                  <span key={s} className="px-1.5 py-0.5 rounded font-bold text-[10px]"
                    style={{ background: c.fg, color: 'white' }}>{s}</span>
                )
              }) : <span className="text-[10px] text-slate-300">선택 없음</span>}
            </div>

            {note && (
              <div className="flex items-start gap-1 px-1.5 py-1.5 rounded-lg bg-amber-50 border border-amber-200">
                <span className="text-[10px] text-amber-800 leading-snug">{note}</span>
              </div>
            )}

            {SHIFT_GROUPS.map(grp => (
              <div key={grp.label}>
                <p className="text-[10px] font-semibold mb-1 px-0.5" style={{ color: grp.color }}>{grp.label}</p>
                <div className="flex flex-wrap gap-1">
                  {grp.shifts.map(code => {
                    const c = sc(code)
                    const vs = nurse ? validate(shiftsWithout, day, code, nurse, rules, sd) : []
                    const isHolBlocked = isHol && !WORK_SET.has(code) && code !== '법휴'
                    const isSel = pickerSelected.includes(code)
                    return (
                      <button key={code}
                        onClick={() => {
                          setBlockPopup(null)
                          if (isHolBlocked) { setBlockPopup({ code, violations: ['공휴일에는 법휴만 허용됩니다 (근무 신청은 가능)'] }); return }
                          if (vs.length > 0 && !isSel) { setBlockPopup({ code, violations: vs }); return }
                          setPickerSelected(prev =>
                            prev.includes(code) ? prev.filter(x => x !== code) : [...prev, code]
                          )
                        }}
                        className="relative rounded-md font-bold py-0.5 px-2 text-xs transition-all"
                        style={{
                          background: isSel ? c.fg : c.bg,
                          color: isSel ? 'white' : c.fg,
                          border: `1.5px solid ${(isHolBlocked || (vs.length > 0 && !isSel)) ? '#FCA5A5' : isSel ? c.fg : c.border}`,
                          opacity: (isHolBlocked || (vs.length > 0 && !isSel)) ? 0.4 : 1,
                        }}>
                        {code}
                        {(isHolBlocked || (vs.length > 0 && !isSel)) && (
                          <span className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full flex items-center justify-center font-black"
                            style={{ width: 13, height: 13, fontSize: 8 }}>!</span>
                        )}
                        {isSel && (
                          <span className="absolute -top-1 -right-1 text-white rounded-full flex items-center justify-center font-black"
                            style={{ background: '#2A3A7A', width: 13, height: 13, fontSize: 8 }}>✓</span>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}

            {blockPopup && (
              <div className="rounded-lg p-2 bg-red-50 border border-red-200">
                <p className="text-[10px] font-bold text-red-700 mb-1">🚫 {blockPopup.code} — 선택 불가</p>
                {blockPopup.violations.map((v, i) => (
                  <p key={i} className="text-[10px] text-red-600 leading-snug">• {v}</p>
                ))}
                <button onClick={() => setBlockPopup(null)}
                  className="mt-2 w-full py-1 text-[10px] bg-white rounded font-semibold border border-slate-200 hover:bg-slate-50 transition-colors">
                  확인
                </button>
              </div>
            )}

            {/* A/B 조건 토글 */}
            {pickerSelected.length > 0 && (() => {
              const _SKIP = new Set(['병가', '필수'])
              const hasPriority = pickerSelected.some(c => !_SKIP.has(c))
              if (!hasPriority) return null
              const { nurseId } = activePick
              const aUsed = Object.entries(allRequestsRef.current[nurseId] || {})
                .filter(([d, v]) => v.condition === 'A' && parseInt(d) !== activePick.day).length
              const aLeft = 3 - aUsed
              return (
                <div className="border-t border-slate-100 pt-1.5">
                  <p className="text-[9px] text-slate-400 mb-1">우선순위 조건</p>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setPickerCondition('A')}
                      disabled={pickerCondition !== 'A' && aLeft <= 0}
                      className="flex-1 py-1 text-[10px] font-bold rounded transition-all"
                      style={{
                        background: pickerCondition === 'A' ? '#4338CA' : '#EEF2FF',
                        color: pickerCondition === 'A' ? 'white' : aLeft <= 0 ? '#A5B4FC' : '#4338CA',
                        opacity: pickerCondition !== 'A' && aLeft <= 0 ? 0.5 : 1,
                      }}>
                      A{pickerCondition !== 'A' && aLeft <= 0 ? '(소진)' : ''}
                    </button>
                    <button
                      onClick={() => setPickerCondition('B')}
                      className="flex-1 py-1 text-[10px] font-bold rounded transition-all"
                      style={{
                        background: pickerCondition === 'B' ? '#64748B' : '#F1F5F9',
                        color: pickerCondition === 'B' ? 'white' : '#64748B',
                      }}>
                      B
                    </button>
                  </div>
                </div>
              )
            })()}

            <div className="border-t border-slate-100 pt-1 flex gap-1">
              <button onClick={() => handlePickCodes([])}
                className="py-1 px-2 text-[10px] font-semibold text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors flex-shrink-0">
                지우기
              </button>
              <button
                onClick={() => handlePickCodes(pickerSelected, pickerCondition)}
                className="flex-1 py-1 text-[10px] font-bold text-white rounded transition-colors"
                style={{ background: pickerSelected.length > 0 ? '#2A3A7A' : '#94A3B8' }}>
                {pickerSelected.length === 0 ? '선택 없음' : `${pickerSelected.join('/')} 저장`}
              </button>
            </div>
          </div>
        </div>
        )
      })()}

      {/* 엑셀 가져오기 토스트 */}
      {importMsg && (
        <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-[60] px-4 py-3 rounded-xl shadow-lg text-sm font-semibold flex items-center gap-2 ${
          importMsg.ok ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white'
        }`}>
          {importMsg.ok ? '✓' : '✗'} {importMsg.text}
        </div>
      )}

    </div>
  )
}
