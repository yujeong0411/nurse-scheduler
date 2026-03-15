import { useState, useRef, useEffect } from 'react'

/**
 * 엑셀 필터와 동일한 이름 필터 컴포넌트
 *
 * selectedNames: null = 전체 표시(필터 없음), Set = 해당 이름만 표시(빈 Set = 아무도 없음)
 * onChange(null | Set): 외부 상태 업데이트
 */
export default function NameFilter({ allNames, selectedNames, onChange }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // null = 필터 없음(전체), Set = 명시적 선택
  const isFiltered = selectedNames !== null
  const visibleNames = search.trim()
    ? allNames.filter(n => n.includes(search.trim()))
    : allNames

  const allChecked = !isFiltered  // null 이면 전체 체크
  const someChecked = isFiltered && selectedNames.size > 0 && selectedNames.size < allNames.length

  const toggleAll = () => {
    // 전체 체크 → 전체 해제(빈 Set), 전체 해제 → 전체 선택(null)
    onChange(isFiltered ? null : new Set())
  }

  const toggleName = (name) => {
    if (!isFiltered) {
      // 전체 표시 상태에서 하나 해제 → 그 이름 빼고 나머지만 선택
      onChange(new Set(allNames.filter(n => n !== name)))
    } else {
      const next = new Set(selectedNames)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
        // 전원 선택되면 null(전체)로 복귀
        if (next.size === allNames.length) { onChange(null); return }
      }
      onChange(next)
    }
  }

  const isNameChecked = (name) => selectedNames === null || selectedNames.has(name)

  const activeCount = isFiltered ? selectedNames.size : null

  return (
    <div className="relative" ref={ref}>
      {/* 헤더 버튼 */}
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1 hover:text-blue-600 transition-colors"
      >
        이름
        {isFiltered ? (
          <span className="px-1 py-0.5 rounded text-white font-bold leading-none"
            style={{ fontSize: 9, background: '#3b82f6', minWidth: 16, textAlign: 'center' }}>
            {activeCount}
          </span>
        ) : (
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
            strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4 }}>
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
          </svg>
        )}
      </button>

      {/* 드롭다운 */}
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-white rounded-xl shadow-xl border border-slate-200"
          style={{ minWidth: 160 }}>

          {/* 검색 */}
          <div className="p-2 border-b border-slate-100">
            <input
              autoFocus
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => e.key === 'Escape' && setOpen(false)}
              placeholder="이름 검색"
              className="w-full text-xs px-2 py-1 rounded-lg border border-slate-200 text-slate-700 outline-none focus:border-blue-400"
            />
          </div>

          {/* 전체 선택/해제 */}
          {!search.trim() && (
            <div className="px-2 py-1 border-b border-slate-100">
              <label className="flex items-center gap-2 px-1 py-0.5 rounded hover:bg-slate-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={allChecked}
                  ref={el => { if (el) el.indeterminate = someChecked }}
                  onChange={toggleAll}
                  style={{ width: 13, height: 13, accentColor: '#3b82f6', cursor: 'pointer' }}
                />
                <span className="text-xs font-semibold text-slate-600">(전체)</span>
              </label>
            </div>
          )}

          {/* 이름 목록 */}
          <div className="overflow-y-auto py-1" style={{ maxHeight: 200 }}>
            {visibleNames.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-3">결과 없음</p>
            ) : visibleNames.map(name => (
              <label key={name} className="flex items-center gap-2 px-3 py-1 hover:bg-slate-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isNameChecked(name)}
                  onChange={() => toggleName(name)}
                  style={{ width: 13, height: 13, accentColor: '#3b82f6', cursor: 'pointer' }}
                />
                <span className="text-xs text-slate-700">{name}</span>
              </label>
            ))}
          </div>

          {/* 필터 초기화 */}
          {isFiltered && (
            <div className="px-2 py-1.5 border-t border-slate-100">
              <button
                onClick={() => { onChange(null); setOpen(false) }}
                className="w-full text-xs text-blue-600 hover:text-blue-800 font-semibold py-0.5 text-center"
              >
                필터 초기화
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
