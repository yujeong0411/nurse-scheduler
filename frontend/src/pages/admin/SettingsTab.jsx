import { useState, useEffect } from 'react'
import { settingsApi, rulesApi, holidaysApi } from '../../api/client'
import { dlPassed, fmtDate } from '../../utils/constants'

function Section({ title, icon, children }) {
  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
        {icon}
        <span className="text-sm lg:text-base font-semibold text-slate-700">{title}</span>
      </div>
      <ul className="divide-y divide-slate-100">{children}</ul>
    </div>
  )
}

function NumRow({ label, desc, value, onChange, unit, min = 0 }) {
  return (
    <li className="flex items-center justify-between px-4 py-3">
      <div>
        <p className="text-sm lg:text-base font-medium text-slate-800">{label}</p>
        {desc && <p className="text-xs lg:text-sm text-slate-400 mt-0.5">{desc}</p>}
      </div>
      <div className="flex items-center gap-2">
        <button onClick={() => onChange(Math.max(min, (value || 0) - 1))}
          className="w-8 h-8 lg:w-9 lg:h-9 bg-slate-100 hover:bg-slate-200 rounded-full text-slate-600 font-bold text-lg flex items-center justify-center transition-colors">−</button>
        <span className="w-8 text-center font-bold text-slate-900 lg:text-base">{value ?? 0}</span>
        <button onClick={() => onChange((value || 0) + 1)}
          className="w-8 h-8 lg:w-9 lg:h-9 rounded-full text-white font-bold text-lg flex items-center justify-center transition-colors" style={{ background: '#2A3A7A' }}>+</button>
        <span className="text-xs lg:text-sm text-slate-400 w-5">{unit}</span>
      </div>
    </li>
  )
}

function ToggleRow({ label, desc, value, onChange }) {
  return (
    <li className="flex items-center justify-between px-4 py-3">
      <div>
        <p className="text-sm lg:text-base font-medium text-slate-800">{label}</p>
        {desc && <p className="text-xs lg:text-sm text-slate-400 mt-0.5">{desc}</p>}
      </div>
      <button onClick={() => onChange(!value)}
        className={`w-11 h-6 rounded-full transition-colors flex items-center px-0.5 ${value ? '' : 'bg-slate-200'}`}
        style={value ? { background: '#2A3A7A' } : {}}>
        <div className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${value ? 'translate-x-5' : ''}`} />
      </button>
    </li>
  )
}

// 기간 인덱스 배열 → "M/D, M/D" 문자열
function indicesToText(indices, startDate) {
  if (!startDate || !indices?.length) return ''
  return indices.map(idx => {
    const d = new Date(new Date(startDate).getTime() + (idx - 1) * 86400000)
    return `${d.getMonth() + 1}/${d.getDate()}`
  }).join(', ')
}

// "M/D, M/D" 문자열 → 기간 인덱스 배열
function textToIndices(text, startDate) {
  if (!text.trim() || !startDate) return []
  const start = new Date(startDate)
  return text.split(',').flatMap(s => {
    const m = s.trim().match(/^(\d{1,2})\/(\d{1,2})$/)
    if (m) {
      const mo = parseInt(m[1]), dy = parseInt(m[2])
      for (let i = 0; i < 28; i++) {
        const dt = new Date(start.getTime() + i * 86400000)
        if (dt.getMonth() + 1 === mo && dt.getDate() === dy) return [i + 1]
      }
      return []
    }
    return []
  })
}

export default function SettingsTab({ period, onPeriodSaved }) {
  const [sd, setSd] = useState('')
  const [dl, setDl] = useState('')
  const [rules, setRules] = useState(null)
  const [rawHolidays, setRawHolidays] = useState([])
  const [holidayText, setHolidayText] = useState('')
  const [scheduleMsg, setScheduleMsg] = useState({ text: '', ok: true })
  const [rulesMsg, setRulesMsg] = useState({ text: '', ok: true })
  const [loading, setLoading] = useState(true)
  const [savingSettings, setSavingSettings] = useState(false)
  const [savingRules, setSavingRules] = useState(false)
  const [detectingHolidays, setDetectingHolidays] = useState(false)

  useEffect(() => {
    rulesApi.get()
      .then(rRes => {
        setRules(rRes.data)
        setRawHolidays(rRes.data.public_holidays || [])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  // rawHolidays 또는 sd가 바뀔 때 holidayText 재계산
  useEffect(() => {
    setHolidayText(indicesToText(rawHolidays, sd))
  }, [rawHolidays, sd])

  // period prop이 바뀌면 날짜/마감 동기화 (datetime-local은 "YYYY-MM-DDTHH:MM" 형식 필요)
  useEffect(() => {
    setSd(period?.start_date || '')
    const dl = period?.deadline || ''
    setDl(dl ? dl.substring(0, 16) : '')
  }, [period?.id])

  const setVal = (k, v) => setRules(p => ({ ...p, [k]: v }))

  const handleScheduleSave = async () => {
    if (!sd) { setScheduleMsg({ text: '시작일을 선택해주세요', ok: false }); setTimeout(() => setScheduleMsg({ text: '', ok: true }), 3000); return }
    setSavingSettings(true)
    try {
      await settingsApi.update({ start_date: sd, deadline: dl || null })
      setScheduleMsg({ text: '저장되었습니다', ok: true })
      onPeriodSaved?.(sd)
    } catch (e) {
      setScheduleMsg({ text: e.response?.data?.detail || '저장 실패', ok: false })
    } finally {
      setSavingSettings(false)
      setTimeout(() => setScheduleMsg({ text: '', ok: true }), 2500)
    }
  }

  const handleRulesSave = async () => {
    const holidays = textToIndices(holidayText, sd)
    const payload = { ...rules, public_holidays: holidays }
    setSavingRules(true)
    try {
      await rulesApi.update(payload)
      setRules(payload)
      setRawHolidays(holidays)
      setRulesMsg({ text: '저장되었습니다', ok: true })
    } catch (e) {
      setRulesMsg({ text: e.response?.data?.detail || '저장 실패', ok: false })
    } finally {
      setSavingRules(false)
      setTimeout(() => setRulesMsg({ text: '', ok: true }), 2500)
    }
  }

  const handleAutoDetect = async () => {
    if (!sd) { alert('시작일을 먼저 설정해주세요.'); return }
    setDetectingHolidays(true)
    try {
      const start = new Date(sd)

      // 28일 범위에 걸친 연월 목록 수집 (최대 2개월)
      const monthKeys = new Set()
      for (let i = 0; i < 28; i++) {
        const d = new Date(start.getTime() + i * 86400000)
        monthKeys.add(`${d.getFullYear()}-${d.getMonth() + 1}`)
      }

      // 해당 월 공휴일 모두 조회
      const allHolidays = []
      for (const key of monthKeys) {
        const [y, m] = key.split('-').map(Number)
        const res = await holidaysApi.get(y, m)
        res.data.forEach(h => allHolidays.push({ year: y, month: m, day: h.day }))
      }

      // 기간 내 공휴일을 "M/D" 형식으로 수집
      const dateStrings = []
      for (let i = 0; i < 28; i++) {
        const d = new Date(start.getTime() + i * 86400000)
        const hit = allHolidays.some(h =>
          h.year === d.getFullYear() && h.month === d.getMonth() + 1 && h.day === d.getDate()
        )
        if (hit) dateStrings.push(`${d.getMonth() + 1}/${d.getDate()}`)
      }

      if (dateStrings.length === 0) {
        alert('해당 기간에 법정공휴일이 없습니다.')
      } else {
        setHolidayText(dateStrings.join(', '))
      }
    } catch { alert('공휴일 조회 실패') }
    finally { setDetectingHolidays(false) }
  }

  const endDate = sd ? new Date(new Date(sd).getTime() + 27 * 86400000) : null
  const passed = dlPassed(dl)

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-slate-400 gap-2 text-sm">
      <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-400 rounded-full animate-spin" />
      불러오는 중...
    </div>
  )

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
    <div className="p-2 sm:p-4 md:p-6 space-y-4 w-full max-w-5xl mx-auto">

      {/* 일정 카드 */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
            <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
            <line x1="3" y1="10" x2="21" y2="10"/>
          </svg>
          <span className="text-sm font-semibold text-slate-700">일정</span>
        </div>
        <div className="p-4 space-y-4">
          <div>
            <label className="label">근무표 시작일</label>
            <input type="date" value={sd} onChange={e => setSd(e.target.value)} className="input" />
            {sd && endDate && (
              <div className="mt-2 rounded-xl px-3 py-2 text-sm font-medium" style={{ background: '#EAECF4', border: '1px solid #C8CEEA', color: '#2A3A7A' }}>
                {fmtDate(sd)} ~ {fmtDate(endDate)}
                <span className="text-xs ml-1" style={{ color: '#7A8AC0' }}>(28일)</span>
              </div>
            )}
          </div>
          <div>
            <label className="label">신청 마감 일시 <span className="normal-case text-slate-300 font-normal ml-1">(선택)</span></label>
            <input type="datetime-local" value={dl} onChange={e => setDl(e.target.value)} className="input" />
            {dl && (
              <div className={`mt-2 rounded-xl px-3 py-2 text-sm font-semibold border ${passed ? 'bg-red-50 border-red-200 text-red-600' : 'bg-amber-50 border-amber-200 text-amber-700'}`}>
                {passed ? '마감됨' : `${dl.replace('T', ' ')} 까지`}
              </div>
            )}
            {dl && <button onClick={() => setDl('')} className="mt-1.5 text-xs text-slate-400 hover:text-slate-600 underline">마감 제거</button>}
          </div>
        </div>
        {scheduleMsg.text && (
          <div className={`mx-4 mb-3 rounded-xl px-3 py-2 text-xs font-semibold text-center border ${scheduleMsg.ok ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-600'}`}>
            {scheduleMsg.ok ? '✓ ' : '✗ '}{scheduleMsg.text}
          </div>
        )}
        <div className="px-4 pb-4">
          <button onClick={handleScheduleSave} disabled={savingSettings} className="btn-primary w-full text-sm">
            {savingSettings ? '저장 중...' : '일정 저장'}
          </button>
        </div>
      </div>

      {rules && (<>
        {/* 일일 최소 인원 */}
        <Section title="일일 최소 인원" icon={
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        }>
          <NumRow label="D 인원" desc="일별 Day 최소 인원" value={rules.daily_d} onChange={v => setVal('daily_d', v)} unit="명" />
          <NumRow label="중2 인원" desc="평일 중간2 최소 인원" value={rules.daily_m} onChange={v => setVal('daily_m', v)} unit="명" />
          <NumRow label="E 인원" desc="일별 Evening 최소 인원" value={rules.daily_e} onChange={v => setVal('daily_e', v)} unit="명" />
          <NumRow label="N 인원" desc="일별 Night 최소 인원" value={rules.daily_n} onChange={v => setVal('daily_n', v)} unit="명" />
        </Section>

        {/* 연속 근무 / N 제한 */}
        <Section title="연속 근무 / N 제한" icon={
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
        }>
          <ToggleRow label="역순 근무 금지" desc="D → 중2 → E → N 순서만 허용" value={rules.ban_reverse_order} onChange={v => setVal('ban_reverse_order', v)} />
          <NumRow label="최대 연속 근무" value={rules.max_consecutive_work} onChange={v => setVal('max_consecutive_work', v)} unit="일" />
          <NumRow label="최대 연속 N" value={rules.max_consecutive_n} onChange={v => setVal('max_consecutive_n', v)} unit="회" />
          <NumRow label="NN 후 휴무" desc="야간 2연속 후 최소 휴무일" value={rules.off_after_2n} onChange={v => setVal('off_after_2n', v)} unit="일" />
          <NumRow label="월 최대 N" value={rules.max_n_per_month} onChange={v => setVal('max_n_per_month', v)} unit="회" />
          <NumRow label="주당 최소 OFF" value={rules.min_weekly_off} onChange={v => setVal('min_weekly_off', v)} unit="일" />
        </Section>

        {/* 직급 제약 */}
        <Section title="직급 제약" icon={
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>
        }>
          <NumRow label="매 근무 책임 최소" desc="책임간호사 최소 인원" value={rules.min_chief_per_shift} onChange={v => setVal('min_chief_per_shift', v)} unit="명" />
          <NumRow label="책임+서브차지 최소" desc="매 근무 고급 인원 합산 최소" value={rules.min_senior_per_shift} onChange={v => setVal('min_senior_per_shift', v)} unit="명" />
        </Section>

        {/* 특수 조건 */}
        <Section title="특수 조건" icon={
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
        }>
          <NumRow label="임산부 연속 근무 제한" desc="임산부 최대 연속 근무일" value={rules.pregnant_poff_interval} onChange={v => setVal('pregnant_poff_interval', v)} unit="일" />
          <ToggleRow label="생리휴무 적용" desc="남성 제외, 월 1개" value={rules.menstrual_leave} onChange={v => setVal('menstrual_leave', v)} />
        </Section>

        {/* 수면 휴무 조건 */}
        <Section title="수면 휴무 발생 조건" icon={
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        }>
          <NumRow label="당월 N 기준" desc="당월 N 횟수 이상이면 수면 발생" value={rules.sleep_n_monthly} onChange={v => setVal('sleep_n_monthly', v)} unit="회" />
          <NumRow label="2개월 합산 N 기준" desc="전월+당월 N 합산 이상이면 수면 발생" value={rules.sleep_n_bimonthly} onChange={v => setVal('sleep_n_bimonthly', v)} unit="회" />
        </Section>

        {/* 법정공휴일 */}
        <div className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/>
              <line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
            </svg>
            <span className="text-sm font-semibold text-slate-700">법정공휴일</span>
          </div>
          <div className="p-4 space-y-3">
            <p className="text-xs text-slate-400">공휴일 날짜 입력 (쉼표 구분, 예: 4/1, 5/5)</p>
            <div className="flex gap-2">
              <input
                value={holidayText}
                placeholder="예: 4/1, 5/5"
                onChange={e => setHolidayText(e.target.value)}
                className="input flex-1"
              />
              <button
                onClick={handleAutoDetect}
                disabled={detectingHolidays || !sd}
                className="btn-secondary text-sm px-4 whitespace-nowrap disabled:opacity-40">
                {detectingHolidays ? '조회 중...' : '자동 감지'}
              </button>
            </div>
          </div>
        </div>

        {/* 규칙 저장 */}
        {rulesMsg.text && (
          <div className={`rounded-xl px-3 py-2 text-xs font-semibold text-center border ${rulesMsg.ok ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-600'}`}>
            {rulesMsg.ok ? '✓ ' : '✗ '}{rulesMsg.text}
          </div>
        )}
        <button onClick={handleRulesSave} disabled={savingRules} className="btn-primary w-full text-sm">
          {savingRules ? '저장 중...' : '규칙 저장'}
        </button>
      </>)}
    </div>
    </div>
  )
}
