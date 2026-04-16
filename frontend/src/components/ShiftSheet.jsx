import { useState, useRef, useEffect } from 'react'
import { validate } from '../utils/validate'
import { SHIFT_GROUPS, WD, sc, getWd, getDate } from '../utils/constants'

export default function ShiftSheet({ day, shifts, notes = {}, nurse, rules, startDate, onSelect, onClose }) {
  const [confirm, setConfirm] = useState(null)  // { shift, violations }
  const [noteStep, setNoteStep] = useState(null) // 사유 입력 단계
  const [noteText, setNoteText] = useState('')
  const noteRef = useRef(null)

  const wd = getWd(startDate, day)
  const dateObj = getDate(startDate, day)
  const isHol = (rules.public_holidays || []).includes(day)
  const currentCodes = shifts[day] || []   // string[]
  const currentNote = notes[day] || ''

  // 멀티셀렉트 상태 — ShiftSheet 열릴 때 기존 선택으로 초기화
  const [selected, setSelected] = useState(currentCodes)

  useEffect(() => {
    if (noteStep) {
      setNoteText(currentNote)
      setTimeout(() => noteRef.current?.focus(), 100)
    }
  }, [noteStep])

  const handlePick = (s) => {
    setConfirm(null)
    setSelected(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    )
  }

  const handleSave = () => {
    onSelect(selected, noteText.trim())
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end items-center"
      style={{ background: 'rgba(0,0,0,0.5)' }} onClick={onClose}>
      <div className="bg-white rounded-t-3xl shadow-2xl flex flex-col w-full max-w-lg"
        style={{ maxHeight: '85vh' }} onClick={e => e.stopPropagation()}>

        {/* 핸들 */}
        <div className="flex justify-center pt-3 flex-shrink-0">
          <div className="w-12 h-1.5 rounded-full bg-slate-200" />
        </div>

        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 flex-shrink-0">
          <div>
            <h3 className="font-black text-slate-900 text-xl">
              {dateObj.getMonth() + 1}월 {dateObj.getDate()}일
            </h3>
            <p className="text-slate-400 text-sm mt-0.5">
              {WD[wd]}요일{isHol ? ' · 공휴일 🎌' : ''}{selected.length > 0 ? ` · ${selected.join(' / ')}` : ''}
            </p>
          </div>
          <button onClick={onClose}
            className="w-9 h-9 bg-slate-100 rounded-full flex items-center justify-center text-slate-500 text-lg font-bold">×</button>
        </div>

        {/* 사유 입력 단계 */}
        {noteStep ? (
          <div className="px-5 py-4 flex flex-col gap-4 flex-shrink-0">
            <div className="flex items-center gap-2 flex-wrap">
              {selected.map(s => {
                const st = sc(s)
                return (
                  <span key={s} className="px-3 py-1 rounded-xl font-bold text-sm"
                    style={{ background: st.bg, color: st.fg, border: `1.5px solid ${st.border}` }}>
                    {s}
                  </span>
                )
              })}
              <span className="text-slate-500 text-sm">선택됨</span>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                사유 <span className="normal-case text-slate-300 font-normal ml-1">(선택)</span>
              </label>
              <textarea
                ref={noteRef}
                value={noteText}
                onChange={e => setNoteText(e.target.value)}
                placeholder="예: 개인 사정, 병원 방문 등"
                rows={3}
                className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:border-transparent resize-none" style={{ '--tw-ring-color': '#2A3A7A' }}
              />
            </div>
            <div className="flex gap-2">
              <button onClick={() => setNoteStep(null)}
                className="flex-1 py-3 rounded-xl font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors text-sm">
                뒤로
              </button>
              <button onClick={handleSave}
                className="flex-1 py-3 rounded-xl font-bold text-white transition-colors text-sm" style={{ background: '#2A3A7A' }}>
                저장 ({selected.length}개)
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* 위반 — 선택 불가 */}
            {confirm && (
              <div className="mx-4 my-3 rounded-2xl p-4 bg-red-50 border border-red-200 flex-shrink-0">
                <p className="font-bold text-red-700 mb-2 text-sm">🚫 {confirm.shift} — 선택 불가</p>
                {confirm.violations.map((v, i) => (
                  <p key={i} className="text-red-500 text-xs mt-1">• {v}</p>
                ))}
                <button onClick={() => setConfirm(null)}
                  className="mt-3 w-full bg-white rounded-xl font-semibold text-sm py-2.5 border border-slate-200">
                  확인
                </button>
              </div>
            )}

            {/* 근무 목록 */}
            <div className="px-4 py-3 overflow-y-auto flex-1" style={{ WebkitOverflowScrolling: 'touch' }}>
              {selected.length > 0 && (
                <button onClick={() => setSelected([])}
                  className="w-full mb-3 rounded-xl font-semibold text-slate-500 bg-slate-100 py-2.5 text-sm">
                  ✕ 선택 초기화
                </button>
              )}
              {currentNote && (
                <div className="mb-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700">
                  <span className="font-semibold">현재 사유:</span> {currentNote}
                </div>
              )}
              {SHIFT_GROUPS.map((grp, gi) => (
                <div key={grp.label} style={{ marginBottom: gi < SHIFT_GROUPS.length - 1 ? '8px' : 0 }}>
                  {gi > 0 && <div className="h-px bg-slate-100 my-2" />}
                  <div className="flex items-center gap-2 mb-2.5">
                    <span className="rounded-full flex-shrink-0" style={{ width: 10, height: 10, background: grp.color }} />
                    <span className="font-bold text-xs" style={{ color: grp.color }}>{grp.label}</span>
                    <span className="text-xs text-slate-300">{grp.shifts.length}종</span>
                  </div>
                  <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
                    {grp.shifts.map(s => {
                      const ps = { ...shifts }; delete ps[day]
                      const vs = nurse ? validate(ps, day, s, nurse, rules, startDate) : []
                      const isCur = selected.includes(s)
                      const st = sc(s)
                      return (
                        <button key={s} onClick={() => handlePick(s)}
                          className="relative rounded-xl font-bold transition-all active:scale-90 py-2.5 text-xs"
                          style={{
                            background: isCur ? st.fg : st.bg,
                            color: isCur ? 'white' : st.fg,
                            border: `2px solid ${isCur ? st.fg : vs.length > 0 ? '#FCA5A5' : st.border}`,
                            opacity: vs.length > 0 && !isCur ? 0.45 : 1,
                            boxShadow: isCur ? '0 2px 8px rgba(0,0,0,0.2)' : 'none',
                          }}>
                          {s}
                          {vs.length > 0 && !isCur && (
                            <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white rounded-full flex items-center justify-center font-black"
                              style={{ width: 16, height: 16, fontSize: 9 }}>!</span>
                          )}
                          {isCur && (
                            <span className="absolute -top-1.5 -right-1.5 text-white rounded-full flex items-center justify-center font-black"
                              style={{ background: '#2A3A7A', width: 16, height: 16, fontSize: 9 }}>✓</span>
                          )}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
              <div style={{ height: 'env(safe-area-inset-bottom, 16px)', minHeight: 16 }} />
            </div>

            {/* 하단 확정 버튼 */}
            <div className="px-4 pb-4 pt-2 flex gap-2 flex-shrink-0 border-t border-slate-100">
              <button
                onClick={() => { onSelect([], ''); onClose() }}
                className="py-3 px-4 rounded-xl font-semibold text-slate-500 bg-slate-100 hover:bg-slate-200 transition-colors text-sm flex-shrink-0">
                초기화
              </button>
              <button
                onClick={() => {
                  if (selected.length === 0) { onSelect([], ''); onClose(); return }
                  setNoteStep(true)
                }}
                disabled={false}
                className="flex-1 py-3 rounded-xl font-bold text-white transition-colors text-sm"
                style={{ background: selected.length > 0 ? '#2A3A7A' : '#94A3B8' }}>
                {selected.length === 0 ? '선택하세요' : `${selected.join(' / ')} 선택 완료`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
