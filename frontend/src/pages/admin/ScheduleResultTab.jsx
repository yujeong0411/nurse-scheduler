import { useState, useEffect, useRef } from 'react'
import { scheduleApi, requestsApi, settingsApi, rulesApi } from '../../api/client'
import { sc, fmtDate, getWd, getDate, mmdd, WD, NUM_DAYS, WORK_SET, SHIFT_GROUPS } from '../../utils/constants'
import NameFilter from '../../components/NameFilter'

const OFF_SET = new Set(['주', 'OFF', 'POFF', '법휴', '수면', '생휴', '휴가', '특휴', '공가', '경가', '보수', '필수', '번표', '병가'])

const SHIFT_LEVEL = { 'D':1, 'D9':1, 'D1':1, '중1':2, '중2':2, 'E':3, 'N':4 }

function inferFailureReasons(day, requestedCode, assignedShift, nurseId, scheduleData, nurses) {
  const reasons = []
  const get = (nid, d) => scheduleData[nid]?.[d] ?? scheduleData[nid]?.[String(d)]

  const prevShift  = get(nurseId, day - 1)
  const prev2Shift = get(nurseId, day - 2)
  const reqLv  = SHIFT_LEVEL[requestedCode]
  const prevLv = SHIFT_LEVEL[prevShift]

  // ── 역순 금지 ──
  if (reqLv && prevLv && prevLv > reqLv) {
    reasons.push(`${day - 1}일이 ${prevShift} 근무라 ${requestedCode}는 역순 배정 금지 규칙에 걸립니다.`)
  }

  // ── N 후 D계열 최소 2일 휴무 (H3a) ──
  if (prevShift === 'N' && reqLv != null && reqLv <= 2) {
    reasons.push(`${day - 1}일 N 근무 후에는 D/중간계열 전에 최소 2일 휴무가 필요합니다.`)
  }
  if (prev2Shift === 'N' && prevShift && OFF_SET.has(prevShift) && reqLv != null && reqLv <= 2) {
    reasons.push(`${day - 2}일 N → ${day - 1}일 휴무 패턴 후 D/중간계열은 배정 불가입니다 (N 후 2일 휴무 규칙).`)
  }

  // ── 연속 근무 한도 ──
  let consec = 0
  for (let d = day - 1; d >= Math.max(1, day - 5); d--) {
    if (WORK_SET.has(get(nurseId, d))) consec++
    else break
  }
  if (consec >= 4) {
    reasons.push(`${day - consec}일부터 ${consec}일 연속 근무 중으로, 최대 연속 근무(5일) 한도에 가깝습니다.`)
  }

  // ── 신청 근무가 OFF인데 근무 배정된 경우: 해당 날 인력 부족 ──
  if (OFF_SET.has(requestedCode) && assignedShift && WORK_SET.has(assignedShift)) {
    const others = nurses.filter(n => n.id !== nurseId && get(n.id, day) === assignedShift).map(n => n.name)
    const total = others.length + 1
    const nameStr = others.slice(0, 3).join(', ') + (others.length > 3 ? ` 외 ${others.length - 3}명` : '')
    reasons.push(
      `해당 날 ${assignedShift} 최소 인원(${total}명) 충족을 위해 배정됐습니다.` +
      (others.length > 0 ? ` (같은 날 ${assignedShift}: ${nameStr})` : '')
    )
  }

  // ── 신청 근무가 있었는데 다른 근무가 배정된 경우: 정원 초과 ──
  if (WORK_SET.has(requestedCode) && assignedShift !== requestedCode) {
    const onRequested = nurses.filter(n => get(n.id, day) === requestedCode).map(n => n.name)
    if (onRequested.length > 0) {
      const nameStr = onRequested.slice(0, 3).join(', ') + (onRequested.length > 3 ? ` 외 ${onRequested.length - 3}명` : '')
      reasons.push(
        `해당 날 ${requestedCode}는 ${onRequested.length}명이 이미 배정되어 정원이 찼습니다. (${nameStr})`
      )
    }
  }

  return reasons
}

// 해당 날 특정 근무의 신청자 목록 반환
function getShiftRequestors(day, code, reqMap, nurses) {
  const nurseMap = Object.fromEntries(nurses.map(n => [n.id, n]))
  return Object.entries(reqMap)
    .filter(([nid, days]) => days[day]?.codes?.includes(code))
    .map(([nid, days]) => ({
      nurseId: nid,
      name: nurseMap[nid]?.name ?? nid,
      condition: days[day].condition ?? 'B',
      score: days[day].score ?? 100,
    }))
}

// 해당 날 특정 근무에 배정된 간호사 수
function getAssignedCount(day, code, scheduleData) {
  if (!scheduleData) return 0
  return Object.values(scheduleData).filter(days => (days[day] ?? days[String(day)]) === code).length
}

function isReqMatch(shift, reqCodes, isOr) {
  if (!shift || !reqCodes?.length) return false
  if (reqCodes.some(c => c.includes('제외'))) return false
  for (const c of reqCodes) {
    if (c === shift) return true
    if (c === 'OFF' && OFF_SET.has(shift)) return true  // 'OFF' 신청만 어떤 휴무든 매칭
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

function CellEditModal({ nurse, day, startDate, currentShift, rect, onSave, onClose }) {
  const [pendingViolations, setPendingViolations] = useState(null) // { shift, violations[] }
  const [saving, setSaving] = useState(false)
  const modalRef = useRef(null)

  useEffect(() => {
    const handleClick = (e) => {
      if (modalRef.current && !modalRef.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  const popW = Math.min(260, window.innerWidth - 8)
  const popH = pendingViolations ? 300 : 210
  const top = rect.bottom + 2 + popH > window.innerHeight ? rect.top - popH - 2 : rect.bottom + 2
  const left = Math.max(4, Math.min(rect.left, window.innerWidth - popW - 4))

  const handleSelect = async (shift, force = false) => {
    if (saving) return
    setSaving(true)
    try {
      const res = await onSave(day, shift, force)
      if (res.violations?.length && !force) {
        setPendingViolations({ shift, violations: res.violations })
      } else {
        onClose()
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div ref={modalRef}
      className="fixed z-50 bg-white rounded-xl shadow-xl border border-slate-200"
      style={{ width: popW, top, left }}>
      <div className="p-2 space-y-1.5">
        {SHIFT_GROUPS.map(grp => {
          const shifts = grp.shifts.filter(s => !s.includes('제외'))
          if (!shifts.length) return null
          return (
          <div key={grp.label}>
            <p className="text-[10px] font-semibold mb-1 px-0.5" style={{ color: grp.color }}>{grp.label}</p>
            <div className="flex flex-wrap gap-1">
              {shifts.map(s => {
                const st = sc(s)
                const isSel = s === currentShift
                return (
                  <button key={s} onClick={() => handleSelect(s)} disabled={saving}
                    className="rounded-md font-bold py-0.5 px-2 text-xs transition-all disabled:opacity-40"
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
          )
        })}

        {pendingViolations && (
          <div className="rounded-lg p-2 bg-red-50 border border-red-200">
            <p className="text-[10px] font-bold text-red-700 mb-1">⚠️ 규칙 위반</p>
            {pendingViolations.violations.map((v, i) => (
              <p key={i} className="text-[10px] text-red-600 leading-snug">• {v}</p>
            ))}
            <div className="flex gap-1.5 mt-2">
              <button onClick={() => setPendingViolations(null)}
                className="flex-1 text-[10px] py-1 bg-white rounded font-semibold border border-slate-200 hover:bg-slate-50 transition-colors">
                취소
              </button>
              <button onClick={() => handleSelect(pendingViolations.shift, true)}
                className="flex-1 text-[10px] py-1 bg-red-500 text-white rounded font-bold hover:bg-red-600 transition-colors">
                무시하고 저장
              </button>
            </div>
          </div>
        )}

        <div className="border-t border-slate-100 pt-1">
          <button onClick={() => handleSelect('')} disabled={saving}
            className="w-full py-1 text-[10px] font-semibold text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors disabled:opacity-40">
            지우기
          </button>
        </div>
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
  const [dailyQuota, setDailyQuota] = useState({ D: 7, E: 8, N: 7 })
  const [generating, setGenerating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [editCell, setEditCell] = useState(null)
  const [logPopup, setLogPopup] = useState(null)   // { day, code, x, y, entries[] }
  const [exporting, setExporting] = useState(false)
  const [msg, setMsg] = useState(null)
  const [selectedNames, setSelectedNames] = useState(null)
  const [highlightedId, setHighlightedId] = useState(null)
  const [dateFilter, setDateFilter] = useState(null)   // null | { day, codes: Set }
  const [datePicker, setDatePicker] = useState(null)   // null | { day, x, y }
  const [conflictWarnings, setConflictWarnings] = useState(null)  // null | warning[] (생성 전 충돌경고)
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
          const r = rulesRes.value.data
          setSleepNMonthly(r.sleep_n_monthly ?? 7)
          setDailyQuota({ D: r.daily_d ?? 7, E: r.daily_e ?? 8, N: r.daily_n ?? 7 })
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
            if (!map[nid][day]) map[nid][day] = { codes: [], is_or: r.is_or, condition: r.condition ?? 'B', score: r.score ?? 100 }
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

  useEffect(() => {
    if (!logPopup) return
    const handler = (e) => { setLogPopup(null) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [logPopup])

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
    // 충돌 사전 체크
    try {
      const chkRes = await scheduleApi.checkConflicts(settings.period_id)
      if (chkRes.data.warnings?.length) {
        setConflictWarnings(chkRes.data.warnings)
        return  // 경고 모달로 분기
      }
    } catch { /* 체크 실패 시 그냥 진행 */ }
    await _doGenerate()
  }

  const _doGenerate = async () => {
    if (!window.confirm('근무표를 생성하시겠습니까? 기존 근무표가 있으면 덮어씌워집니다.')) return
    setConflictWarnings(null)
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
              <button id="admin-schedule-export" onClick={handleExport} disabled={exporting}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                {exporting ? '내보내는 중...' : '엑셀'}
              </button>
            </>
          )}
          <button id="admin-schedule-generate" onClick={handleGenerate} disabled={generating || !startDate}
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

      {/* 로딩 */}
      {loading && (
        <div className="flex items-center justify-center py-20 text-slate-400 gap-2 text-sm">
          <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-400 rounded-full animate-spin" />
          불러오는 중...
        </div>
      )}

      {/* 솔버 진행 */}
      {!loading && generating && (
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
          <span className="text-xs text-blue-500 flex-shrink-0">최대 300초</span>
        </div>
      )}

      {/* 메시지 */}
      {!loading && msg && (
        <div className={`px-4 py-2.5 flex items-start gap-3 flex-shrink-0 ${msg.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700 border-b border-red-200'}`}>
          <p className="text-xs font-semibold flex-1 whitespace-pre-wrap">{msg.text}</p>
          {!msg.ok && (
            <button onClick={() => setMsg(null)}
              className="flex-shrink-0 text-red-400 hover:text-red-600 font-bold text-base leading-none mt-0.5">×</button>
          )}
        </div>
      )}

      {/* 평가 결과 */}
      {!loading && evalData && (() => {
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
      {!loading && scheduleData && nurses.length > 0 ? (
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
                  <tr key={nurse.id} className={`group transition-colors ${highlightedId === nurse.id ? 'bg-blue-100' : 'hover:bg-blue-100'}`}>
                    <td className={`sticky left-0 z-10 px-3 py-1.5 font-medium whitespace-nowrap border-b border-slate-200 transition-colors text-slate-800 cursor-pointer ${highlightedId === nurse.id ? 'bg-blue-50' : 'bg-white group-hover:bg-blue-50'}`}
                      style={{ boxShadow: '2px 0 6px rgba(0,0,0,0.06)' }}
                      onClick={() => { setEditCell(null); setHighlightedId(id => id === nurse.id ? null : nurse.id) }}
                      onMouseDown={e => e.stopPropagation()}>
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
                      const isActive = editCell?.nurseId === nurse.id && editCell?.day === d
                      const textColor = s === 'N' ? '#B91C1C' : s === '주' ? '#854D0E' : '#374151'
                      const baseBg = hasReq ? '#fef9c3' : isSun ? '#fef2f2' : isSat ? '#eff6ff' : '#ffffff'
                      return (
                        <td key={d}
                          onClick={e => {
                            if (isWeeklyOff || !scheduleId) return
                            setHighlightedId(nurse.id)
                            const cellRect = e.currentTarget.getBoundingClientRect()

                            if (unmatched) {
                              // 미배정 셀: 로그 팝업만 표시 (편집은 팝업 내 버튼으로)
                              setEditCell(null)
                              const logCode = req.codes.find(c => !c.includes('제외'))
                              if (logCode && period?.period_id) {
                                setLogPopup({ day: d, code: logCode, assignedShift: s, unmatched: true, nurseId: nurse.id, nurseObj: nurse, x: cellRect.left, y: cellRect.bottom, cellTop: cellRect.top, entries: null })
                                requestsApi.getAssignmentLog(period.period_id, d, logCode)
                                  .then(res => setLogPopup(prev => prev ? { ...prev, entries: res.data } : null))
                                  .catch(() => setLogPopup(prev => prev ? { ...prev, entries: [] } : null))
                              }
                            } else {
                              // 일반 셀: 편집 모달 표시
                              setLogPopup(null)
                              setEditCell({ nurseId: nurse.id, nurseObj: nurse, day: d, rect: cellRect })
                            }
                          }}
                          className={`text-center border-b border-r border-slate-200 transition-colors ${isWeeklyOff ? 'cursor-default' : 'cursor-pointer'}`}
                          style={{
                            background: isActive ? '#dbeafe' : baseBg,
                            boxShadow: isActive ? 'inset 0 0 0 2px #3b82f6' : unmatched ? 'inset 0 0 0 2px #ef4444' : undefined,
                            padding: '2px 1px',
                          }}
                          onMouseEnter={e => { if (!isWeeklyOff && !isActive) e.currentTarget.style.background = hasReq ? '#fef3c7' : isSun ? '#fee2e2' : isSat ? '#dbeafe' : '#f1f5f9' }}
                          onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = baseBg }}>
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
      ) : !loading && !generating && (
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

      {conflictWarnings && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-2xl border border-amber-200 w-full max-w-md mx-4">
            <div className="px-5 pt-5 pb-3">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-amber-500 text-xl">⚠</span>
                <h3 className="font-bold text-slate-800 text-base">A조건 OFF 충돌 가능성</h3>
              </div>
              <p className="text-xs text-slate-500 mb-3">
                아래 날짜에서 A-OFF 신청을 반영하면 최소 인력이 부족할 수 있습니다.
                솔버가 자동으로 조정하지만, 해당 신청이 무시될 수 있습니다.
              </p>
              <div className="space-y-2 max-h-52 overflow-y-auto">
                {conflictWarnings.map((w, i) => (
                  <div key={i} className="rounded-lg bg-amber-50 border border-amber-100 px-3 py-2 text-xs">
                    <div className="font-semibold text-amber-800">{w.date_str}</div>
                    <div className="text-slate-600 mt-0.5">
                      A-OFF 신청: <span className="font-medium">{w.a_off_nurses.join(', ')}</span>
                    </div>
                    <div className="text-slate-500 mt-0.5">
                      가용 {w.available}명 / 최소 필요 {w.required}명
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="px-5 pb-5 pt-2 flex gap-2 justify-end">
              <button
                onClick={() => setConflictWarnings(null)}
                className="px-4 py-2 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >취소</button>
              <button
                onClick={_doGenerate}
                className="px-4 py-2 text-xs font-semibold text-white bg-amber-500 hover:bg-amber-600 rounded-lg transition-colors"
              >이대로 생성</button>
            </div>
          </div>
        </div>
      )}

      {editCell && (
        <CellEditModal
          nurse={editCell.nurseObj}
          day={editCell.day}
          startDate={startDate}
          currentShift={scheduleData?.[editCell.nurseId]?.[editCell.day] || scheduleData?.[editCell.nurseId]?.[String(editCell.day)] || ''}
          rect={editCell.rect}
          onSave={handleCellEdit}
          onClose={() => setEditCell(null)}
        />
      )}

      {logPopup && (() => {
        const popW = 240
        const lpLeft = Math.max(4, Math.min(logPopup.x, window.innerWidth - popW - 4))
        const cellBottom = logPopup.y
        const cellTop = logPopup.cellTop ?? cellBottom - 22
        const spaceBelow = window.innerHeight - cellBottom - 4
        const spaceAbove = cellTop - 4
        const showAbove = spaceBelow < 220 && spaceAbove > spaceBelow
        const maxH = Math.min(320, Math.max(80, showAbove ? spaceAbove : spaceBelow))
        const posStyle = showAbove
          ? { bottom: window.innerHeight - cellTop + 4, maxHeight: maxH }
          : { top: cellBottom + 4, maxHeight: maxH }
        return (
        <div
          className="fixed z-[60] bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden"
          style={{ left: lpLeft, width: popW, ...posStyle }}
          onMouseDown={e => e.stopPropagation()}
          onClick={e => e.stopPropagation()}
        >
          <div className="px-3 py-2 border-b border-slate-100 flex items-center justify-between bg-slate-50">
            <span className="text-xs font-bold text-slate-700">
              {startDate ? `${mmdd(getDate(startDate, logPopup.day))} (${WD[getWd(startDate, logPopup.day)]})` : `${logPopup.day}일`}
              {' '}<span style={{ color: logPopup.code === 'N' ? '#B91C1C' : '#374151' }}>{logPopup.code}</span>
              {' '}<span className="font-normal text-slate-400">{logPopup.unmatched ? '— 미배정 사유' : '— 배정 현황'}</span>
            </span>
            <button onClick={() => setLogPopup(null)} className="text-slate-400 hover:text-slate-600 text-base leading-none">×</button>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: 240 }}>
            {logPopup.entries === null ? (
              <p className="text-xs text-slate-400 text-center py-4">로딩 중...</p>
            ) : logPopup.entries.length === 0 ? (
              // ── 경쟁자 없는 미배정: 사실 기반 분석 ──
              <div className="px-3 py-3 space-y-2">
                {logPopup.assignedShift && (
                  <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-50 border border-slate-200">
                    <span className="text-[10px] text-slate-500">신청</span>
                    <span className="font-bold text-xs" style={{ color: logPopup.code === 'N' ? '#B91C1C' : '#374151' }}>{logPopup.code}</span>
                    <span className="text-slate-300">→</span>
                    <span className="text-[10px] text-slate-500">배정</span>
                    <span className="font-bold text-xs" style={{ color: logPopup.assignedShift === 'N' ? '#B91C1C' : '#374151' }}>{logPopup.assignedShift}</span>
                  </div>
                )}
                {(() => {
                  const hardReasons = inferFailureReasons(
                    logPopup.day, logPopup.code, logPopup.assignedShift,
                    logPopup.nurseId, scheduleData, nurses
                  )
                  const assigned = logPopup.assignedShift
                  const quota = dailyQuota[assigned] ?? null
                  const assignedCount = assigned ? getAssignedCount(logPopup.day, assigned, scheduleData) : 0
                  const requestors = assigned ? getShiftRequestors(logPopup.day, assigned, reqMap, nurses) : []
                  const autoCount = quota != null ? Math.max(0, assignedCount - requestors.length) : null
                  const reqCodeRequestors = getShiftRequestors(logPopup.day, logPopup.code, reqMap, nurses)

                  return (
                    <div className="space-y-2">
                      {hardReasons.length > 0 && (
                        <ul className="space-y-1">
                          {hardReasons.map((r, i) => (
                            <li key={i} className="flex gap-1.5 text-[10px] text-slate-500 leading-relaxed">
                              <span className="text-slate-300 flex-shrink-0 mt-0.5">•</span>
                              <span>{r}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                      {assigned && WORK_SET.has(assigned) && quota != null && (
                        <div className="rounded-lg bg-amber-50 border border-amber-100 px-2.5 py-2 space-y-1">
                          <p className="text-[10px] font-bold text-amber-700">{assigned} 인원 현황 (이 날)</p>
                          <div className="flex items-center gap-1.5 text-[10px] text-slate-600">
                            <span className="text-slate-400">필요</span>
                            <span className="font-bold">{quota}명</span>
                            <span className="text-slate-300">|</span>
                            <span className="text-slate-400">신청</span>
                            <span className="font-bold">{requestors.length}명</span>
                            {autoCount > 0 && <>
                              <span className="text-slate-300">|</span>
                              <span className="text-slate-400">자동배정</span>
                              <span className="font-bold text-amber-600">{autoCount}명</span>
                            </>}
                          </div>
                          {autoCount > 0 && (
                            <p className="text-[10px] text-slate-500 leading-relaxed">
                              {assigned} 인원 {quota}명 중 {autoCount}명은 신청 없이 자동배정됐습니다.
                            </p>
                          )}
                        </div>
                      )}
                      {reqCodeRequestors.length === 1 && (
                        <p className="text-[10px] text-slate-400 leading-relaxed">
                          {logPopup.code} 신청자는 당신 1명이었으나 {assigned ? `${assigned} 인원 충원으로 인해 배정되지 않았습니다.` : '근무 제약으로 배정 불가했습니다.'}
                        </p>
                      )}
                      {!hardReasons.length && !WORK_SET.has(assigned ?? '') && (
                        <p className="text-[10px] text-slate-400 leading-relaxed">
                          근무 제약(연속근무·역순금지·월N한도 등) 충돌로 배정 불가했습니다.
                        </p>
                      )}
                    </div>
                  )
                })()}
              </div>
            ) : (
              // ── 경쟁자 있는 경우: 신청자 순위 + 자동배정 수 ──
              <div>
                {logPopup.entries.map((e) => {
                  const codeLabel = e.requested_codes || e.code || logPopup.code
                  return (
                  <div key={e.nurse_id} className="flex items-center gap-2 px-3 py-1.5 hover:bg-slate-50 border-b border-slate-50 last:border-0">
                    <span
                      className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black text-white"
                      style={{ background: e.is_assigned ? '#22c55e' : '#cbd5e1' }}>
                      {e.rank}
                    </span>
                    <span className="flex-1 text-xs font-semibold text-slate-800 truncate">{e.name}</span>
                    <span className="text-[10px] text-slate-500 flex-shrink-0" title="신청 코드">{codeLabel}</span>
                    <span
                      className="text-[10px] font-bold px-1.5 py-0.5 rounded-md"
                      style={{ background: e.condition === 'A' ? '#EDE9FE' : '#F1F5F9', color: e.condition === 'A' ? '#7C3AED' : '#64748B' }}>
                      {e.condition}
                    </span>
                    <span className="text-[10px] text-slate-400 flex-shrink-0">{e.score}점</span>
                    {e.is_random && <span className="text-[10px]" title="동점 랜덤">🎲</span>}
                    {e.is_assigned && <span className="text-green-500 text-xs font-bold flex-shrink-0">✓</span>}
                  </div>
                  )
                })}
                {(() => {
                  const quota = dailyQuota[logPopup.code] ?? null
                  const assignedCount = getAssignedCount(logPopup.day, logPopup.code, scheduleData)
                  const autoCount = quota != null ? Math.max(0, assignedCount - logPopup.entries.length) : null
                  return autoCount > 0 ? (
                    <p className="px-3 py-1.5 text-[10px] text-slate-400 border-t border-slate-100">
                      위 신청자 외 {autoCount}명은 신청 없이 자동배정됨
                    </p>
                  ) : null
                })()}
              </div>
            )}
          </div>
          {logPopup.unmatched && logPopup.nurseId && (
            <div className="px-3 py-2 border-t border-slate-100">
              <button
                onClick={() => {
                  const nurse = logPopup.nurseObj
                  const day = logPopup.day
                  setLogPopup(null)
                  setEditCell({ nurseId: logPopup.nurseId, nurseObj: nurse, day, rect: { left: logPopup.x, bottom: logPopup.y, top: logPopup.cellTop ?? logPopup.y - 40 } })
                }}
                className="w-full py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors">
                셀 직접 편집
              </button>
            </div>
          )}
        </div>
        )
      })()}
    </div>
  )
}
