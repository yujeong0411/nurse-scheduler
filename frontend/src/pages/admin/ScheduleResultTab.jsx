import { useState, useEffect, useRef } from 'react'
import { scheduleApi, requestsApi, settingsApi } from '../../api/client'
import { sc, fmtDate, getWd, getDate, mmdd, WD, NUM_DAYS, WORK_SET, SHIFT_GROUPS } from '../../utils/constants'

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

function CellEditModal({ nurse, day, startDate, currentShift, onSave, onClose }) {
  const [shift, setShift] = useState(currentShift || '')
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)
  const [violations, setViolations] = useState([])

  const SHIFT_OPTIONS = [
    '', 'D', 'D9', 'D1', '중1', '중2', 'E', 'N',
    '주', 'OFF', 'POFF', '법휴', '수면', '생휴', '휴가',
    '병가', '특휴', '공가', '경가', '보수', '필수', '번표'
  ]
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
      <div className="bg-white rounded-2xl shadow-2xl p-5 w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-slate-900">{nurse.name}</h3>
            <p className="text-xs text-slate-500 mt-0.5">{dateObj.getMonth()+1}월 {dateObj.getDate()}일 ({WD[wd]})</p>
          </div>
          <button onClick={onClose} className="w-8 h-8 bg-slate-100 rounded-full text-slate-500 font-bold text-lg">×</button>
        </div>

        <div className="space-y-2 mb-4">
          {SHIFT_GROUPS.map(grp => (
            <div key={grp.label}>
              <p className="text-xs font-semibold mb-1" style={{ color: grp.color }}>{grp.label}</p>
              <div className="flex flex-wrap gap-1">
                {grp.shifts.map(s => {
                  const st = sc(s)
                  const isSel = s === shift
                  return (
                    <button key={s} onClick={() => setShift(s)}
                      className="rounded-lg font-bold py-1 px-2 text-xs transition-all"
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
          <button onClick={() => setShift('')}
            className={`w-full py-1.5 rounded-lg text-xs font-semibold transition-colors mt-1 ${shift === '' ? 'bg-slate-200 text-slate-700' : 'bg-slate-50 text-slate-400 hover:bg-slate-100'}`}>
            없음 (삭제)
          </button>
        </div>

        {violations.length > 0 && (
          <div className="mb-3 rounded-xl p-3 bg-red-50 border border-red-200">
            <p className="text-sm font-bold text-red-700 mb-1">⚠️ 규칙 위반</p>
            {violations.map((v, i) => <p key={i} className="text-xs text-red-600">• {v}</p>)}
            <div className="flex gap-2 mt-3">
              <button onClick={() => setViolations([])}
                className="flex-1 text-sm py-2 bg-white rounded-xl font-semibold border border-slate-200">취소</button>
              <button onClick={() => handleSave(true)}
                className="flex-1 text-sm py-2 bg-red-500 text-white rounded-xl font-bold">무시하고 저장</button>
            </div>
          </div>
        )}

        {err && <p className="text-xs text-red-600 text-center mb-3">{err}</p>}

        {violations.length === 0 && (
          <button onClick={() => handleSave(false)} disabled={saving}
            className="w-full py-3 bg-blue-600 text-white rounded-xl font-bold text-sm disabled:opacity-50 hover:bg-blue-700 transition-colors">
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
  const [reqMap, setReqMap] = useState({}) // { nurseId: { day: { codes, is_or } } }
  const [evalData, setEvalData] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [editCell, setEditCell] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [msg, setMsg] = useState(null) // { text, ok }
  const pollRef = useRef(null)

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
        // 기존 근무표 + 신청 + 최신 job 병렬 로드
        const [schedRes, reqRes, jobRes] = await Promise.allSettled([
          scheduleApi.getByPeriod(pid),
          requestsApi.getAll(pid),
          scheduleApi.latestJobByPeriod(pid),
        ])
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

  const handleEvaluate = async () => {
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
      a.download = `근무표_${settings?.start_date || ''}.xlsx`
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

  return (
    <div className="flex flex-col flex-1 overflow-hidden">

      {/* 상단 바 */}
      <div className="bg-white border-b border-slate-100 px-4 py-3 flex items-center gap-4 flex-shrink-0">
        <div className="flex-1 min-w-0">
          {startDate
            ? <p className="font-bold text-slate-800 text-sm">{fmtDate(startDate)} ~ {endStr}</p>
            : <p className="text-slate-400 text-sm">시작일을 먼저 설정해주세요.</p>
          }
          {scheduleData && <p className="text-xs text-slate-400 mt-0.5">{nurses.length}명 · 셀 클릭으로 편집</p>}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {scheduleData && (
            <>
              <button onClick={handleEvaluate}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition-colors">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/>
                  <line x1="6" y1="20" x2="6" y2="14"/>
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
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50">
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
      {evalData && (
        <div className="bg-white border-b border-slate-100 px-4 py-3 flex items-center gap-4 flex-shrink-0">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center font-black text-lg bg-blue-50 text-blue-700 flex-shrink-0">
            {evalData.grade}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-bold text-slate-800 text-sm">{evalData.score}점</p>
            <p className="text-xs text-slate-400">규칙위반 {evalData.violation_details?.length ?? 0}건</p>
          </div>
          {evalData.violation_details?.length > 0 && (
            <div className="text-xs text-red-500 max-w-xs hidden sm:block truncate">
              {evalData.violation_details[0]}
              {evalData.violation_details.length > 1 && ` 외 ${evalData.violation_details.length - 1}건`}
            </div>
          )}
        </div>
      )}

      {/* 근무표 그리드 */}
      {scheduleData && nurses.length > 0 ? (
        <div className="flex-1 overflow-auto">
          <table className="text-xs border-collapse w-full" style={{ minWidth: 'max-content' }}>
            <thead className="sticky top-0 z-10">
              <tr>
                <th className="sticky left-0 z-20 bg-slate-100 text-slate-600 px-3 py-2 text-left font-semibold border-b border-r border-slate-200 whitespace-nowrap" style={{ minWidth: 88 }}>
                  이름
                </th>
                {days.map(d => {
                  const wd = getWd(startDate, d)
                  const isSat = wd === 5, isSun = wd === 6
                  const dateObj = getDate(startDate, d)
                  return (
                    <th key={d} className="py-1.5 font-medium text-center border-b border-slate-200" style={{
                      minWidth: 42,
                      background: isSun ? '#fee2e2' : isSat ? '#eff6ff' : '#f8fafc',
                      color: isSun ? '#dc2626' : isSat ? '#2563eb' : '#64748b',
                    }}>
                      <div style={{ fontSize: 10 }}>{mmdd(dateObj)}</div>
                      <div style={{ fontSize: 10 }}>{WD[wd]}</div>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {nurses.map((nurse, ni) => {
                const nurseShifts = scheduleData[nurse.id] || {}
                return (
                  <tr key={nurse.id} className="group hover:bg-blue-50/40 transition-colors">
                    <td className="sticky left-0 z-10 px-3 py-1.5 font-medium whitespace-nowrap border-r border-b border-slate-100 bg-white group-hover:bg-blue-50/40 transition-colors text-slate-800">
                      {nurse.name}
                    </td>
                    {days.map(d => {
                      const s = nurseShifts[d] || nurseShifts[String(d)] || ''
                      const st = s ? sc(s) : null
                      const wd = getWd(startDate, d)
                      const isSat = wd === 5, isSun = wd === 6
                      const req = reqMap[nurse.id]?.[d]
                      const matched = req && isReqMatch(s, req.codes, req.is_or)
                      const cellBg = matched ? '#fef9c3' : isSun ? '#fef2f2' : isSat ? '#eff6ff' : undefined
                      return (
                        <td key={d}
                          onClick={() => scheduleId && setEditCell({ nurseId: nurse.id, nurseObj: nurse, day: d })}
                          className="text-center p-0.5 border-b border-r border-slate-100 cursor-pointer transition-colors"
                          style={{ background: cellBg }}>
                          {s ? (
                            <span className="inline-flex items-center justify-center rounded font-semibold"
                              style={{ background: st.bg, color: st.fg, border: `1px solid ${st.border}`, fontSize: 11, minWidth: 34, height: 22 }}>
                              {s}
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
      ) : !generating && (
        <div className="flex flex-col items-center justify-center flex-1 text-slate-400 gap-3">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <p className="text-sm">생성 버튼을 눌러 근무표를 만들어주세요.</p>
        </div>
      )}

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
