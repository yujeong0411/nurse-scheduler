import { useState, useEffect, useRef } from 'react'
import { scheduleApi, requestsApi, settingsApi, rulesApi } from '../../api/client'
import { sc, fmtDate, getWd, getDate, mmdd, WD, NUM_DAYS, WORK_SET, SHIFT_GROUPS } from '../../utils/constants'
import NameFilter from '../../components/NameFilter'

const OFF_SET = new Set(['주', 'OFF', 'POFF', '법휴', '수면', '생휴', '휴가', '특휴', '공가', '경가', '보수', '필수', '번표', '병가'])

function isReqMatch(shift, reqCodes, isOr) {
  if (!shift || !reqCodes?.length) return false
  if (reqCodes.some(c => c.includes('제외'))) return false
  for (const c of reqCodes) {
    if (c === shift) return true
    if (OFF_SET.has(c) && OFF_SET.has(shift)) return true
  }
  return false
}

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
    <div className="flex flex-wrap gap-1 mt-1.5">
      {tags.map((t, i) => (
        <span key={i} className="px-1.5 py-0.5 rounded text-xs font-medium"
          style={{ color: t.color, background: t.bg }}>{t.label}</span>
      ))}
    </div>
  )
}

function CellEditModal({ nurse, day, startDate, currentShift, onSave, onClose }) {
  const [shift, setShift] = useState(currentShift || '')
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)
  const [violations, setViolations] = useState([])

  const dateObj = getDate(startDate, day)
  const wd = getWd(startDate, day)

  const handleSave = async (force = false) => {
    setSaving(true); setErr('')
    try {
      const res = await onSave(day, shift, force)
      if (res.violations?.length && !force) {
        setViolations(res.violations)
        setSaving(false)
        return
      }
      onClose()
    } catch (e) {
      setErr(e.response?.data?.detail || '저장 실패')
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl p-5 w-full max-w-sm" onClick={e => e.stopPropagation()}>

        {/* 헤더: 이름 + 날짜 + 닫기 */}
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-bold text-slate-900 text-base">{nurse.name}</h3>
            <p className="text-xs text-slate-400 mt-0.5">{dateObj.getMonth()+1}월 {dateObj.getDate()}일 ({WD[wd]})</p>
            <NurseInfoBadges nurse={nurse} />
          </div>
          <button onClick={onClose}
            className="w-7 h-7 flex items-center justify-center bg-slate-100 hover:bg-slate-200 rounded-full text-slate-400 text-base transition-colors flex-shrink-0 ml-2">
            ×
          </button>
        </div>

        <div className="h-px bg-slate-100 mb-3" />

        {/* 근무 선택 */}
        <div className="space-y-2.5 mb-4">
          {SHIFT_GROUPS.map(grp => (
            <div key={grp.label}>
              <p className="text-xs font-semibold mb-1.5" style={{ color: grp.color }}>{grp.label}</p>
              <div className="flex flex-wrap gap-1">
                {grp.shifts.map(s => {
                  const st = sc(s)
                  const isSel = s === shift
                  return (
                    <button key={s} onClick={() => setShift(s)}
                      className="rounded-lg font-bold py-1 px-2.5 text-xs transition-all"
                      style={{
                        background: isSel ? st.fg : st.bg,
                        color: isSel ? 'white' : st.fg,
                        border: `1.5px solid ${isSel ? st.fg : st.border}`,
                      }}>
                      {s}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
          <div className="pt-1 border-t border-slate-100">
            <button onClick={() => setShift('')}
              className={`w-full py-1.5 rounded-lg text-xs font-semibold transition-colors ${shift === '' ? 'bg-slate-200 text-slate-700' : 'text-slate-400 hover:text-red-500 hover:bg-red-50'}`}>
              없음 (삭제)
            </button>
          </div>
        </div>

        {/* 위반 경고 */}
        {violations.length > 0 && (
          <div className="mb-3 rounded-xl p-3 bg-red-50 border border-red-200">
            <p className="text-xs font-bold text-red-700 mb-1">⚠️ 규칙 위반</p>
            {violations.map((v, i) => <p key={i} className="text-xs text-red-600">• {v}</p>)}
            <div className="flex gap-2 mt-3">
              <button onClick={() => setViolations([])}
                className="flex-1 text-xs py-2 bg-white rounded-lg font-semibold border border-slate-200 hover:bg-slate-50 transition-colors">취소</button>
              <button onClick={() => handleSave(true)}
                className="flex-1 text-xs py-2 bg-red-500 text-white rounded-lg font-bold hover:bg-red-600 transition-colors">무시하고 저장</button>
            </div>
          </div>
        )}

        {err && <p className="text-xs text-red-600 text-center mb-3">{err}</p>}

        {violations.length === 0 && (
          <button onClick={() => handleSave(false)} disabled={saving}
            className="w-full py-2.5 bg-blue-600 text-white rounded-xl font-bold text-sm disabled:opacity-50 hover:bg-blue-700 transition-colors">
            {saving ? '저장 중...' : '저장'}
          </button>
        )}
      </div>
    </div>
  )
}

export default function ScheduleResultTab({ period }) {
  const [settings, setSettings] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [scheduleId, setScheduleId] = useState(null)
  const [scheduleData, setScheduleData] = useState(null)
  const [nurses, setNurses] = useState([])
  const [reqMap, setReqMap] = useState({})
  const [evalData, setEvalData] = useState(null)
  const [showStats, setShowStats] = useState(false)
  const [sleepNMonthly, setSleepNMonthly] = useState(7)
  const [generating, setGenerating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [editCell, setEditCell] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [msg, setMsg] = useState(null)
  const [selectedNames, setSelectedNames] = useState(null)
  const [dateFilter, setDateFilter] = useState(null)   // null | { day, codes: Set }
  const [datePicker, setDatePicker] = useState(null)   // null | { day, x, y }
  const pollRef = useRef(null)
  const datePickerRef = useRef(null)

  const showMsg = (text, ok = true) => {
    setMsg({ text, ok })
    if (ok) setTimeout(() => setMsg(null), 3000)  // 성공만 자동 닫힘, 오류는 수동 닫기
  }

  useEffect(() => {
    const periodId = period?.period_id
    const loadAll = async () => {
      setLoading(true)
      try {
        const cfg = period || (await settingsApi.get()).data
        setSettings(cfg)
        const pid = cfg.period_id
        if (!pid) return
        // 기존 근무표 + 신청 + 최신 job + rules 병렬 로드
        const [schedRes, reqRes, jobRes, rulesRes] = await Promise.allSettled([
          scheduleApi.getByPeriod(pid),
          requestsApi.getAll(pid),
          scheduleApi.latestJobByPeriod(pid),
          rulesApi.get(),
        ])
        if (rulesRes.status === 'fulfilled') {
          setSleepNMonthly(rulesRes.value.data.sleep_n_monthly ?? 7)
        }
        if (schedRes.status === 'fulfilled') {
          const d = schedRes.value.data
          setScheduleId(d.id)
          setScheduleData(d.schedule_data)
          setNurses(d.nurses)
        }
        if (reqRes.status === 'fulfilled') {
          const map = {}
          for (const r of reqRes.value.data) {
            const nid = r.nurse_id
            const day = r.day
            if (!map[nid]) map[nid] = {}
            if (!map[nid][day]) map[nid][day] = { codes: [], is_or: r.is_or }
            map[nid][day].codes.push(r.code)
          }
          setReqMap(map)
        }
        // 진행 중인 job이 있으면 재폴링 재개
        if (jobRes.status === 'fulfilled') {
          const job = jobRes.value.data
          if (job.status === 'pending' || job.status === 'running') {
            setJobId(job.job_id)
            setJobStatus(job.status)
            setGenerating(true)
          }
        }
      } catch {}
      finally { setLoading(false) }
    }
    loadAll()
  }, [period?.period_id])

  useEffect(() => {
    if (!jobId || jobStatus === 'done' || jobStatus === 'failed') return
    pollRef.current = setInterval(async () => {
      try {
        const res = await scheduleApi.jobStatus(jobId)
        setJobStatus(res.data.status)
        if (res.data.status === 'done' && res.data.schedule_id) {
          clearInterval(pollRef.current)
          setScheduleId(res.data.schedule_id)
          loadSchedule(res.data.schedule_id)
          if (settings?.period_id) loadRequests(settings.period_id)
        } else if (res.data.status === 'failed') {
          clearInterval(pollRef.current)
          showMsg('근무표 생성 실패: ' + (res.data.error_msg || ''), false)
          setGenerating(false)
        }
      } catch {}
    }, 3000)
    return () => clearInterval(pollRef.current)
  }, [jobId, jobStatus])

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

  const loadSchedule = async (sid) => {
    try {
      const res = await scheduleApi.get(sid)
      setScheduleData(res.data.schedule_data)
      setNurses(res.data.nurses)
      setGenerating(false)
    } catch { showMsg('결과 로드 실패', false); setGenerating(false) }
  }

  const loadRequests = async (pid) => {
    try {
      const res = await requestsApi.getAll(pid)
      const map = {}
      for (const r of res.data) {
        const nid = r.nurse_id; const day = r.day
        if (!map[nid]) map[nid] = {}
        if (!map[nid][day]) map[nid][day] = { codes: [], is_or: r.is_or }
        map[nid][day].codes.push(r.code)
      }
      setReqMap(map)
    } catch {}
  }

  const handleGenerate = async () => {
    if (!settings?.period_id) { showMsg('시작일을 먼저 설정해주세요.', false); return }
    if (!window.confirm('근무표를 생성하시겠습니까? 기존 근무표가 있으면 덮어씌워집니다.')) return
    setGenerating(true); setJobStatus('pending'); setScheduleData(null); setEvalData(null)
    try {
      const res = await scheduleApi.generate(settings.period_id)
      setJobId(res.data.job_id)
    } catch (e) {
      showMsg('생성 요청 실패: ' + (e.response?.data?.detail || ''), false)
      setGenerating(false)
    }
  }

  const handleCellEdit = async (day, newShift, force = false) => {
    const res = await scheduleApi.updateCell(scheduleId, { nurse_id: editCell.nurseId, day, new_shift: newShift, force })
    if (res.data.saved) {
      setScheduleData(prev => ({ ...prev, [editCell.nurseId]: { ...(prev[editCell.nurseId] || {}), [day]: newShift } }))
    }
    return res.data
  }

  const handleToggleEvaluate = async () => {
    if (evalData) { setEvalData(null); return }
    if (!scheduleId) return
    try { const res = await scheduleApi.evaluate(scheduleId); setEvalData(res.data) }
    catch { showMsg('평가 실패', false) }
  }

  const handleExport = async () => {
    if (!scheduleId) return
    setExporting(true)
    try {
      const res = await scheduleApi.exportXlsx(scheduleId)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a'); a.href = url
      const sd = settings?.start_date || ''
      const fmt = s => { const d = new Date(s); return `${String(d.getFullYear()).slice(2)}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}` }
      const ed = sd ? new Date(new Date(sd).getTime() + 27*86400000).toISOString().slice(0,10) : ''
      a.download = sd ? `근무표_${fmt(sd)}~${fmt(ed)}.xlsx` : '근무표.xlsx'
      a.click(); URL.revokeObjectURL(url)
    } catch { showMsg('내보내기 실패', false) }
    finally { setExporting(false) }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-slate-400 gap-2 text-sm">
      <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-400 rounded-full animate-spin" />
      불러오는 중...
    </div>
  )

  const startDate = settings?.start_date || null
  const endStr = startDate ? fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000)) : ''
  const days = Array.from({ length: NUM_DAYS }, (_, i) => i + 1)
  const allNames = nurses.map(n => n.name)
  const filteredNurses = selectedNames !== null
    ? nurses.filter(n => selectedNames.has(n.name))
    : nurses
  const displayNurses = dateFilter
    ? filteredNurses.filter(n => {
        const s = scheduleData?.[n.id]?.[dateFilter.day] || scheduleData?.[n.id]?.[String(dateFilter.day)] || ''
        return dateFilter.codes.has(s)
      })
    : filteredNurses

  // 날짜 피커에 표시할 근무 종류 목록 (해당 날짜에 실제 배정된 값만)
  const pickerCodes = datePicker && scheduleData ? (() => {
    const s = new Set()
    nurses.forEach(n => {
      const v = scheduleData[n.id]?.[datePicker.day] || scheduleData[n.id]?.[String(datePicker.day)] || ''
      if (v) s.add(v)
    })
    return [...s].sort()
  })() : []

  return (
    <div className="flex flex-col flex-1 min-h-0">

      {/* 상단 바 */}
      <div className="bg-white border-b border-slate-100 px-4 py-3 flex-shrink-0 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
        {/* 기간 텍스트 */}
        <div className="flex-1 min-w-0">
          {startDate
            ? <p className="font-bold text-slate-800 text-sm truncate">{fmtDate(startDate)} ~ {endStr}</p>
            : <p className="text-slate-400 text-sm">시작일을 먼저 설정해주세요.</p>
          }
          {scheduleData && <p className="text-xs text-slate-400 mt-0.5">{nurses.length}명 · 셀 클릭으로 편집</p>}
        </div>
        {/* 버튼 묶음 */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {scheduleData && (
            <>
              <button onClick={() => setShowStats(v => !v)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${showStats ? 'bg-indigo-600 text-white hover:bg-indigo-700' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'}`}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
                </svg>
                통계
              </button>
              <button onClick={handleToggleEvaluate}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${evalData ? 'bg-amber-500 text-white hover:bg-amber-600' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'}`}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
                평가
              </button>
              <button onClick={handleExport} disabled={exporting}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                {exporting ? '내보내는 중...' : '엑셀'}
              </button>
            </>
          )}
          <button onClick={handleGenerate} disabled={generating || !startDate}
            className="flex items-center gap-1.5 px-3 py-1.5 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50" style={{ background: '#2A3A7A' }}>
            {generating ? (
              <div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            ) : (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.36"/>
              </svg>
            )}
            {generating ? '생성 중...' : '생성'}
          </button>
        </div>
      </div>

      {/* 솔버 진행 */}
      {generating && (
        <div className="bg-blue-50 border-b border-blue-100 px-4 py-2.5 flex items-center gap-3 flex-shrink-0">
          <div className="w-3.5 h-3.5 border-2 border-blue-300 border-t-blue-600 rounded-full animate-spin flex-shrink-0" />
          <div className="flex-1">
            <p className="text-xs font-semibold text-blue-800">
              {jobStatus === 'pending' ? '작업 대기 중...' : 'OR-Tools 최적화 중...'}
            </p>
            <div className="mt-1 bg-blue-100 rounded-full h-1 overflow-hidden">
              <div className="bg-blue-500 h-1 rounded-full animate-pulse" style={{ width: jobStatus === 'running' ? '65%' : '20%' }} />
            </div>
          </div>
          <span className="text-xs text-blue-500 flex-shrink-0">최대 180초</span>
        </div>
      )}

      {/* 메시지 */}
      {msg && (
        <div className={`px-4 py-2.5 flex items-start gap-3 flex-shrink-0 ${msg.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700 border-b border-red-200'}`}>
          <p className="text-xs font-semibold flex-1 whitespace-pre-wrap">{msg.text}</p>
          {!msg.ok && (
            <button onClick={() => setMsg(null)}
              className="flex-shrink-0 text-red-400 hover:text-red-600 font-bold text-base leading-none mt-0.5">×</button>
          )}
        </div>
      )}

      {/* 평가 결과 */}
      {evalData && (() => {
        const rf = evalData.request_fulfilled || {}
        const rate = rf.rate ?? 0
        const fulfilled = rf.fulfilled ?? 0
        const total = rf.total ?? 0
        const violCount = evalData.violation_details?.length ?? 0
        const patternCount = Object.values(evalData.bad_patterns || {}).reduce((s, v) => s + (Array.isArray(v) ? v.length : 0), 0)
        const rateColor = rate >= 90 ? '#15803D' : rate >= 75 ? '#D97706' : '#DC2626'
        const StatItem = ({ value, label, sub, color }) => (
          <div className="flex flex-col items-center justify-center text-center" style={{ minWidth: 56 }}>
            <span className="font-black leading-none" style={{ fontSize: 18, color: color || '#1e293b' }}>{value}</span>
            <span className="text-xs font-semibold text-slate-600 mt-0.5">{label}</span>
            {sub && <span className="text-xs text-slate-400 leading-none mt-0.5">{sub}</span>}
          </div>
        )
        return (
          <div className="bg-white border-b border-slate-100 px-4 py-2 flex items-stretch gap-0 flex-shrink-0">
            <StatItem value={`${rate.toFixed(1)}%`} label="요청반영률" sub={`${fulfilled}/${total}건`} color={rateColor} />
            <div className="w-px bg-slate-100 mx-3 self-stretch flex-shrink-0" />
            <StatItem value={`${violCount}건`} label="규칙위반" color={violCount > 0 ? '#DC2626' : '#374151'} />
            {patternCount > 0 && <>
              <div className="w-px bg-slate-100 mx-3 self-stretch flex-shrink-0" />
              <StatItem value={`${patternCount}건`} label="나쁜패턴" color="#D97706" />
            </>}
            {violCount > 0 && (
              <div className="flex-1 min-w-0 hidden sm:flex items-center ml-3 pl-3 border-l border-slate-100">
                <p className="text-xs text-red-500 truncate">
                  {evalData.violation_details[0]}
                  {violCount > 1 && <span className="text-slate-400"> 외 {violCount - 1}건</span>}
                </p>
              </div>
            )}
          </div>
        )
      })()}

      {/* 근무표 그리드 */}
      {scheduleData && nurses.length > 0 ? (
        <div className="flex-1 min-h-0" style={{ overflowY: 'auto', overflowX: 'scroll' }}>
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
                      onClick={(e) => scheduleData && handleDateHeaderClick(e, d)}
                      className="sticky top-0 z-10 py-1.5 font-medium text-center border-r border-slate-200 transition-colors"
                      style={{
                        minWidth: 42,
                        cursor: scheduleData ? 'pointer' : 'default',
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
                {showStats && ['총근무', 'D', 'E', 'N', '중2', 'OFF', '휴가'].map((h, hi) => (
                  <th key={h} className="sticky top-0 z-10 py-1.5 font-semibold text-center border-r border-slate-100 text-indigo-600"
                    style={{ minWidth: 44, borderLeft: hi === 0 ? '2px solid #c7d2fe' : undefined, borderRight: undefined, boxShadow: '0 1px 4px rgba(0,0,0,0.09)', fontSize: 10, background: '#eef2ff' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayNurses.map((nurse, ni) => {
                const nurseShifts = scheduleData[nurse.id] || {}

                // 통계 계산
                let dCnt = 0, eCnt = 0, nCnt = 0, 중2Cnt = 0, offCnt = 0, vacCnt = 0
                days.forEach(d => {
                  const s = nurseShifts[d] || nurseShifts[String(d)] || ''
                  if (s === 'D' || s === 'D9' || s === 'D1') dCnt++
                  else if (s === 'E') eCnt++
                  else if (s === 'N') nCnt++
                  else if (s === '중2' || s === '중1') 중2Cnt++
                  else if (s === 'OFF') offCnt++
                  else if (s === '휴가') vacCnt++
                })
                const totalWork = dCnt + eCnt + nCnt + 중2Cnt

                return (
                  <tr key={nurse.id} className="group hover:bg-blue-100 transition-colors">
                    <td className="sticky left-0 z-10 px-3 py-1.5 font-medium whitespace-nowrap border-b border-slate-200 bg-white group-hover:bg-blue-50 transition-colors text-slate-800"
                      style={{ boxShadow: '2px 0 6px rgba(0,0,0,0.06)' }}>
                      {nurse.name}
                    </td>
                    {days.map(d => {
                      const s = nurseShifts[d] || nurseShifts[String(d)] || ''
                      const wd = getWd(startDate, d)
                      const isSat = wd === 5, isSun = wd === 6
                      const req = reqMap[nurse.id]?.[d]
                      const hasReq = req?.codes?.some(c => !c.includes('제외'))
                      const matched = hasReq && isReqMatch(s, req.codes, req.is_or)
                      const unmatched = hasReq && !matched
                      const reqLabel = unmatched ? req.codes.filter(c => !c.includes('제외')).join('/') : null
                      const isWeeklyOff = s === '주'
                      const textColor = s === 'N' ? '#B91C1C' : s === '주' ? '#854D0E' : '#374151'
                      return (
                        <td key={d}
                          onClick={() => !isWeeklyOff && scheduleId && setEditCell({ nurseId: nurse.id, nurseObj: nurse, day: d })}
                          className={`text-center border-b border-r border-slate-200 transition-colors ${isWeeklyOff ? 'cursor-default' : 'cursor-pointer'}`}
                          style={{
                            background: hasReq ? '#fef9c3' : isSun ? '#fef2f2' : isSat ? '#eff6ff' : undefined,
                            boxShadow: unmatched ? 'inset 0 0 0 2px #ef4444' : undefined,
                            padding: '2px 1px',
                          }}>
                          <div className="flex flex-col items-center justify-center" style={{ minHeight: 22 }}>
                            {s ? (
                              <span className="font-semibold" style={{ color: textColor, fontSize: 11 }}>{s}</span>
                            ) : null}
                            {reqLabel && (
                              <span style={{ fontSize: 8, color: '#ef4444', lineHeight: 1.2 }}>{reqLabel}</span>
                            )}
                          </div>
                        </td>
                      )
                    })}
                    {showStats && [totalWork, dCnt, eCnt, nCnt, 중2Cnt, offCnt, vacCnt].map((val, idx) => (
                      <td key={idx} className="text-center border-b border-r border-slate-200 font-medium"
                        style={{
                          background: '#eef2ff',
                          borderLeft: idx === 0 ? '2px solid #c7d2fe' : undefined,
                          padding: '2px 4px',
                          fontSize: 11,
                          color: idx === 3 && val > 0 ? '#B91C1C' : '#374151',  // N: 빨간
                        }}>
                        {val || ''}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
            {showStats && (
              <tfoot>
                {['D', 'E', 'N', '중2'].map((shift, si) => (
                  <tr key={shift}>
                    <td className="sticky left-0 z-10 px-3 py-1 font-semibold text-indigo-600 border-b border-slate-200 whitespace-nowrap"
                      style={{
                        fontSize: 11,
                        background: '#eef2ff',
                        boxShadow: '2px 0 6px rgba(0,0,0,0.06)',
                        borderTop: si === 0 ? '2px solid #c7d2fe' : undefined,
                      }}>
                      {shift} 인원
                    </td>
                    {days.map(d => {
                      const cnt = nurses.filter(n => {
                        const s = (scheduleData[n.id] || scheduleData[String(n.id)] || {})[d]
                            || (scheduleData[n.id] || scheduleData[String(n.id)] || {})[String(d)] || ''
                        return shift === 'D' ? (s === 'D' || s === 'D9' || s === 'D1')
                             : shift === '중2' ? (s === '중2' || s === '중1')
                             : s === shift
                      }).length
                      const wd = getWd(startDate, d)
                      const isSat = wd === 5, isSun = wd === 6
                      return (
                        <td key={d} className="text-center border-b border-r border-slate-200 font-semibold"
                          style={{
                            fontSize: 11, padding: '2px 1px',
                            borderTop: si === 0 ? '2px solid #c7d2fe' : undefined,
                            background: isSun ? '#fce7f3' : isSat ? '#e0e7ff' : '#eef2ff',
                            color: cnt === 0 ? '#ef4444' : '#4338ca',
                          }}>
                          {cnt}
                        </td>
                      )
                    })}
                    {[0,1,2,3,4,5,6].map(i => (
                      <td key={i} className="border-b border-r border-slate-200"
                        style={{
                          background: '#eef2ff',
                          borderLeft: i === 0 ? '2px solid #c7d2fe' : undefined,
                          borderTop: si === 0 ? '2px solid #c7d2fe' : undefined,
                        }} />
                    ))}
                  </tr>
                ))}
              </tfoot>
            )}
          </table>
        </div>
      ) : !generating && (
        <div className="flex flex-col items-center justify-center flex-1 text-slate-400 gap-3">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <p className="text-sm">생성 버튼을 눌러 근무표를 만들어주세요.</p>
        </div>
      )}

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
                        style={{ color: code === 'N' ? '#B91C1C' : code === '주' ? '#854D0E' : '#374151' }}>
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

      {editCell && (
        <CellEditModal
          nurse={editCell.nurseObj}
          day={editCell.day}
          startDate={startDate}
          currentShift={scheduleData?.[editCell.nurseId]?.[editCell.day] || scheduleData?.[editCell.nurseId]?.[String(editCell.day)] || ''}
          onSave={handleCellEdit}
          onClose={() => setEditCell(null)}
        />
      )}
    </div>
  )
}
