import { useState } from 'react'
import { validate } from '../utils/validate'
import { SHIFT_GROUPS, WD, sc, getWd, getDate } from '../utils/constants'

export default function ShiftSheet({ day, shifts, nurse, rules, startDate, onSelect, onClose }) {
  const [confirm, setConfirm] = useState(null)

  const wd = getWd(startDate, day)
  const dateObj = getDate(startDate, day)
  const isHol = (rules.public_holidays || []).includes(day)
  const current = shifts[day] || ''

  const handlePick = (s) => {
    if (s === current) { onSelect(''); return }
    const ps = { ...shifts }; delete ps[day]
    const vs = validate(ps, day, s, nurse, rules, startDate)
    if (vs.length > 0) { setConfirm({ shift: s, violations: vs }); return }
    onSelect(s)
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end"
      style={{ background: 'rgba(0,0,0,0.5)' }} onClick={onClose}>
      <div className="bg-white rounded-t-3xl shadow-2xl flex flex-col"
        style={{ maxHeight: '85vh' }} onClick={e => e.stopPropagation()}>
        <div className="flex justify-center pt-3 flex-shrink-0">
          <div className="w-12 h-1.5 rounded-full" style={{ background: '#D1D5DB' }} />
        </div>
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 flex-shrink-0">
          <div>
            <h3 className="font-black text-gray-900" style={{ fontSize: '20px' }}>
              {dateObj.getMonth() + 1}월 {dateObj.getDate()}일
            </h3>
            <p className="text-gray-400 mt-0.5" style={{ fontSize: '14px' }}>
              {WD[wd]}요일{isHol ? ' · 공휴일 🎌' : ''}{current ? ` · 현재: ${current}` : ''}
            </p>
          </div>
          <button onClick={onClose}
            className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center text-gray-500 font-bold"
            style={{ fontSize: '20px' }}>×</button>
        </div>

        {confirm && (
          <div className="mx-4 my-3 rounded-2xl p-4 flex-shrink-0"
            style={{ background: '#FEF2F2', border: '1.5px solid #FECACA' }}>
            <p className="font-bold text-red-700 mb-2" style={{ fontSize: '15px' }}>
              ⚠️ {confirm.shift} — 규칙 위반
            </p>
            {confirm.violations.map((v, i) => (
              <p key={i} className="text-red-500 mt-1" style={{ fontSize: '13px' }}>• {v}</p>
            ))}
            <div className="flex gap-2 mt-4">
              <button onClick={() => setConfirm(null)}
                className="flex-1 bg-white rounded-xl font-semibold"
                style={{ padding: '12px', fontSize: '14px', border: '1.5px solid #E5E7EB' }}>
                취소
              </button>
              <button onClick={() => onSelect(confirm.shift)}
                className="flex-1 bg-red-500 text-white rounded-xl font-bold"
                style={{ padding: '12px', fontSize: '14px' }}>
                무시하고 적용
              </button>
            </div>
          </div>
        )}

        <div className="px-4 py-3" style={{ flex: '1 1 0%', overflowY: 'auto', WebkitOverflowScrolling: 'touch', minHeight: 0 }}>
          {current && (
            <button onClick={() => { onSelect(''); onClose() }}
              className="w-full mb-3 rounded-xl font-semibold text-gray-500"
              style={{ padding: '11px', fontSize: '15px', background: '#F3F4F6', border: 'none' }}>
              ✕ 선택 초기화
            </button>
          )}
          {SHIFT_GROUPS.map((grp, gi) => (
            <div key={grp.label} style={{ marginBottom: gi < SHIFT_GROUPS.length - 1 ? '8px' : '0' }}>
              {gi > 0 && <div style={{ height: '1px', background: '#E5E7EB', margin: '8px 0 12px' }} />}
              <div className="flex items-center gap-2 mb-2.5">
                <span className="rounded-full flex-shrink-0" style={{ width: '10px', height: '10px', background: grp.color }} />
                <span className="font-bold" style={{ fontSize: '13px', color: grp.color }}>{grp.label}</span>
                <span style={{ fontSize: '11px', color: '#9CA3AF' }}>{grp.shifts.length}종</span>
              </div>
              <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
                {grp.shifts.map(s => {
                  const ps = { ...shifts }; delete ps[day]
                  const vs = nurse ? validate(ps, day, s, nurse, rules, startDate) : []
                  const isCur = s === current
                  const st = sc(s)
                  return (
                    <button key={s} onClick={() => handlePick(s)}
                      className="relative rounded-xl font-bold transition-all active:scale-90"
                      style={{
                        padding: '11px 3px',
                        fontSize: '13px',
                        background: isCur ? st.fg : st.bg,
                        color: isCur ? 'white' : st.fg,
                        border: `2px solid ${isCur ? st.fg : vs.length > 0 ? '#FCA5A5' : st.border}`,
                        opacity: vs.length > 0 && !isCur ? 0.45 : 1,
                        boxShadow: isCur ? '0 2px 8px rgba(0,0,0,0.2)' : 'none',
                      }}>
                      {s}
                      {vs.length > 0 && !isCur && (
                        <span className="absolute -top-1.5 -right-1.5 bg-red-500 rounded-full flex items-center justify-center text-white font-black"
                          style={{ width: '16px', height: '16px', fontSize: '9px' }}>!</span>
                      )}
                      {isCur && (
                        <span className="absolute -top-1.5 -right-1.5 bg-blue-600 rounded-full flex items-center justify-center text-white font-black"
                          style={{ width: '16px', height: '16px', fontSize: '9px' }}>✓</span>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
          <div style={{ height: 'env(safe-area-inset-bottom, 16px)', minHeight: '16px' }} />
        </div>
      </div>
    </div>
  )
}
