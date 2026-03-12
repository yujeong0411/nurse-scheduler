import { useState, useEffect, useRef } from 'react'
import { scheduleApi, settingsApi } from '../../api/client'
import { sc, fmtDate, getWd, getDate, mmdd, WD, NUM_DAYS, WORK_SET } from '../../utils/constants'

// 편집 모달
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
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-3xl shadow-2xl p-5 w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-gray-900">{nurse.name}</h3>
            <p className="text-sm text-gray-500">{dateObj.getMonth()+1}월 {dateObj.getDate()}일 ({WD[wd]})</p>
          </div>
          <button onClick={onClose} className="w-8 h-8 bg-gray-100 rounded-full text-gray-500 font-bold">×</button>
        </div>

        <div className="grid grid-cols-4 gap-2 mb-4">
          {SHIFT_OPTIONS.map(s => {
            const st = sc(s)
            const isSel = s === shift
            return (
              <button key={s || '_empty'} onClick={() => setShift(s)}
                className="rounded-xl font-bold py-2.5 text-sm transition-all"
                style={{
                  background: isSel ? (s ? st.fg : '#374151') : (s ? st.bg : '#F9FAFB'),
                  color: isSel ? 'white' : (s ? st.fg : '#9CA3AF'),
                  border: `2px solid ${isSel ? (s ? st.fg : '#374151') : (s ? st.border : '#E5E7EB')}`,
                }}>
                {s || '없음'}
              </button>
            )
          })}
        </div>

        {violations.length > 0 && (
          <div className="mb-3 rounded-xl p-3" style={{ background: '#FEF2F2', border: '1.5px solid #FECACA' }}>
            <p className="text-sm font-bold text-red-700 mb-1">⚠️ 규칙 위반</p>
            {violations.map((v, i) => <p key={i} className="text-xs text-red-600">• {v}</p>)}
            <div className="flex gap-2 mt-3">
              <button onClick={() => setViolations([])}
                className="flex-1 text-sm py-2 bg-white rounded-xl font-medium border border-gray-200">취소</button>
              <button onClick={() => handleSave(true)}
                className="flex-1 text-sm py-2 bg-red-500 text-white rounded-xl font-bold">무시하고 저장</button>
            </div>
          </div>
        )}

        {err && <p className="text-xs text-red-600 text-center mb-3">{err}</p>}

        {violations.length === 0 && (
          <button onClick={() => handleSave(false)} disabled={saving}
            className="w-full py-3 bg-blue-600 text-white rounded-xl font-bold disabled:opacity-50">
            {saving ? '저장 중...' : '저장'}
          </button>
        )}
      </div>
    </div>
  )
}

export default function ScheduleResultTab() {
  const [settings, setSettings] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [scheduleId, setScheduleId] = useState(null)
  const [scheduleData, setScheduleData] = useState(null)
  const [nurses, setNurses] = useState([])
  const [evalData, setEvalData] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [editCell, setEditCell] = useState(null) // {nurseId, nurseObj, day}
  const [msg, setMsg] = useState('')
  const pollRef = useRef(null)

  const showMsg = (m) => { setMsg(m); setTimeout(() => setMsg(''), 3000) }

  useEffect(() => {
    settingsApi.get().then(res => setSettings(res.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  // 폴링 시작
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
        } else if (res.data.status === 'failed') {
          clearInterval(pollRef.current)
          showMsg('❌ 근무표 생성 실패: ' + (res.data.error_msg || ''))
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
    } catch (e) {
      showMsg('❌ 결과 로드 실패')
      setGenerating(false)
    }
  }

  const handleGenerate = async () => {
    if (!settings?.period_id) { showMsg('❌ 시작일을 먼저 설정해주세요.'); return }
    if (!window.confirm('근무표를 생성하시겠습니까? 기존 근무표가 있으면 덮어씌워집니다.')) return
    setGenerating(true)
    setJobStatus('pending')
    setScheduleData(null)
    setEvalData(null)
    try {
      const res = await scheduleApi.generate(settings.period_id)
      setJobId(res.data.job_id)
      setJobStatus('pending')
    } catch (e) {
      showMsg('❌ 생성 요청 실패: ' + (e.response?.data?.detail || ''))
      setGenerating(false)
    }
  }

  const handleCellEdit = async (day, newShift, force = false) => {
    const res = await scheduleApi.updateCell(scheduleId, {
      nurse_id: editCell.nurseId, day, new_shift: newShift, force
    })
    if (res.data.saved) {
      // 로컬 업데이트
      setScheduleData(prev => ({
        ...prev,
        [editCell.nurseId]: { ...(prev[editCell.nurseId] || {}), [day]: newShift }
      }))
    }
    return res.data
  }

  const handleEvaluate = async () => {
    if (!scheduleId) return
    try {
      const res = await scheduleApi.evaluate(scheduleId)
      setEvalData(res.data)
    } catch (e) {
      showMsg('❌ 평가 실패')
    }
  }

  const handleExport = async () => {
    if (!scheduleId) return
    try {
      const res = await scheduleApi.exportXlsx(scheduleId)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `근무표_${settings?.start_date || ''}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      showMsg('❌ 내보내기 실패')
    }
  }

  if (loading) return <div className="flex justify-center py-16 text-gray-400">불러오는 중...</div>

  const startDate = settings?.start_date || null

  // 달력 셀
  const startWd = startDate ? getWd(startDate, 1) : 0

  return (
    <div className="p-4 space-y-4 max-w-4xl mx-auto">
      {/* 액션 바 */}
      <div className="bg-white rounded-2xl shadow-sm p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-bold text-gray-900">근무표 생성</h3>
            {startDate && <p className="text-sm text-gray-500">{fmtDate(startDate)} ~ {fmtDate(new Date(new Date(startDate).getTime()+27*86400000))}</p>}
          </div>
          <button onClick={handleGenerate} disabled={generating || !startDate}
            className="px-5 py-2.5 bg-blue-600 text-white rounded-xl font-bold text-sm disabled:opacity-50">
            {generating ? '생성 중...' : '🔄 생성'}
          </button>
        </div>

        {/* 솔버 진행 상태 */}
        {generating && (
          <div className="bg-blue-50 rounded-xl p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg animate-spin">⏳</span>
              <span className="text-sm font-semibold text-blue-800">
                {jobStatus === 'pending' ? '작업 대기 중...' : jobStatus === 'running' ? 'OR-Tools 최적화 중...' : '완료'}
              </span>
            </div>
            <div className="bg-blue-100 rounded-full h-2 overflow-hidden">
              <div className="bg-blue-500 h-2 rounded-full animate-pulse" style={{ width: jobStatus === 'running' ? '60%' : '20%' }} />
            </div>
            <p className="text-xs text-blue-600 mt-2">최대 180초 소요될 수 있습니다.</p>
          </div>
        )}

        {msg && (
          <div className={`rounded-xl px-3 py-2 text-sm font-semibold mt-2 ${msg.startsWith('✓') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
            {msg}
          </div>
        )}
      </div>

      {/* 결과 */}
      {scheduleData && nurses.length > 0 && (
        <>
          {/* 평가·내보내기 */}
          <div className="flex gap-2">
            <button onClick={handleEvaluate}
              className="flex-1 py-3 bg-white border-2 border-blue-600 text-blue-700 rounded-xl font-bold text-sm">
              📊 평가
            </button>
            <button onClick={handleExport}
              className="flex-1 py-3 bg-green-600 text-white rounded-xl font-bold text-sm">
              📥 엑셀
            </button>
          </div>

          {/* 평가 결과 */}
          {evalData && (
            <div className="bg-white rounded-2xl shadow-sm p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center font-black text-2xl"
                  style={{ background: '#EFF6FF', color: '#1D4ED8' }}>{evalData.grade}</div>
                <div>
                  <p className="font-bold text-gray-900 text-lg">{evalData.score}점</p>
                  <p className="text-sm text-gray-500">규칙위반 {evalData.violation_count ?? 0}건</p>
                </div>
              </div>
              {evalData.violation_details?.slice(0, 5).map((v, i) => (
                <p key={i} className="text-xs text-red-600">• {typeof v === 'string' ? v : JSON.stringify(v)}</p>
              ))}
              {(evalData.violation_details?.length ?? 0) > 5 && (
                <p className="text-xs text-gray-400">외 {evalData.violation_details.length - 5}건...</p>
              )}
            </div>
          )}

          {/* 근무표 그리드 — 가로 스크롤 */}
          <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
              <p className="text-sm font-bold text-gray-700">근무표 (셀 클릭 = 편집)</p>
              <p className="text-xs text-gray-400">{nurses.length}명</p>
            </div>
            <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
              <table style={{ borderCollapse: 'collapse', minWidth: '100%' }}>
                <thead>
                  <tr style={{ background: '#1e3a8a' }}>
                    <th style={{ padding: '8px 12px', textAlign: 'left', color: 'white', fontSize: '13px', fontWeight: 700, position: 'sticky', left: 0, background: '#1e3a8a', minWidth: '80px', zIndex: 2 }}>이름</th>
                    {Array.from({ length: NUM_DAYS }, (_, i) => i + 1).map(d => {
                      const wd = getWd(startDate, d)
                      const isSat = wd === 5, isSun = wd === 6
                      const dateObj = getDate(startDate, d)
                      return (
                        <th key={d} style={{
                          padding: '4px 2px', textAlign: 'center', fontSize: '11px', fontWeight: 600, minWidth: '34px',
                          color: isSat ? '#93C5FD' : isSun ? '#FCA5A5' : 'rgba(255,255,255,0.9)'
                        }}>
                          <div>{dateObj.getDate()}</div>
                          <div style={{ fontSize: '9px', opacity: 0.8 }}>{WD[wd]}</div>
                        </th>
                      )
                    })}
                  </tr>
                </thead>
                <tbody>
                  {nurses.map((nurse, ni) => {
                    const nurseShifts = scheduleData[nurse.id] || {}
                    return (
                      <tr key={nurse.id} style={{ background: ni % 2 === 0 ? 'white' : '#F9FAFB' }}>
                        <td style={{
                          padding: '6px 12px', fontSize: '13px', fontWeight: 700, color: '#111827',
                          position: 'sticky', left: 0, background: ni % 2 === 0 ? 'white' : '#F9FAFB',
                          borderRight: '1px solid #E5E7EB', zIndex: 1, whiteSpace: 'nowrap'
                        }}>
                          {nurse.name}
                        </td>
                        {Array.from({ length: NUM_DAYS }, (_, i) => i + 1).map(d => {
                          const s = nurseShifts[d] || nurseShifts[String(d)] || ''
                          const st = sc(s)
                          const wd = getWd(startDate, d)
                          const isSat = wd === 5, isSun = wd === 6
                          return (
                            <td key={d}
                              onClick={() => scheduleId && setEditCell({ nurseId: nurse.id, nurseObj: nurse, day: d })}
                              style={{
                                padding: '3px 2px', textAlign: 'center', cursor: 'pointer',
                                background: s ? st.bg : (isSat || isSun) ? '#F0F9FF' : 'transparent',
                                borderBottom: '1px solid #F3F4F6', borderRight: '1px solid #F3F4F6',
                              }}>
                              {s && (
                                <span style={{
                                  display: 'inline-block', fontSize: '11px', fontWeight: 700,
                                  color: st.fg, padding: '1px 3px', borderRadius: '4px',
                                  background: st.bg, border: `1px solid ${st.border}`,
                                  whiteSpace: 'nowrap',
                                }}>{s}</span>
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
        </>
      )}

      {editCell && (
        <CellEditModal
          nurse={editCell.nurseObj}
          day={editCell.day}
          startDate={startDate}
          currentShift={scheduleData?.[editCell.nurseId]?.[editCell.day] ||
            scheduleData?.[editCell.nurseId]?.[String(editCell.day)] || ''}
          onSave={handleCellEdit}
          onClose={() => setEditCell(null)}
        />
      )}
    </div>
  )
}
