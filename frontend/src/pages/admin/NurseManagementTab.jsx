import { useState, useEffect } from 'react'
import { nursesApi, authApi } from '../../api/client'

const WD_OPTS = ['월', '화', '수', '목', '금', '토', '일']

function NurseForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState(initial || {
    name: '', role: '', grade: '', is_pregnant: false, is_male: false,
    is_4day_week: false, fixed_weekly_off: null, vacation_days: 0,
    prev_month_n: 0, note: ''
  })
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }))

  return (
    <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 space-y-4">
      <div className="grid grid-cols-2 gap-3">
        {[
          ['이름 *', 'name', 'text', '이름'],
          ['역할 (비고1)', 'role', 'text', '중2, 책임만 ...'],
          ['직급 (비고2)', 'grade', 'text', '책임, 서브차지 ...'],
        ].map(([lbl, key, type, ph]) => (
          <div key={key} className={key === 'name' ? 'col-span-2' : ''}>
            <label className="label">{lbl}</label>
            <input
              type={type}
              value={form[key]}
              onChange={e => set(key, e.target.value)}
              placeholder={ph}
              className="input"
            />
          </div>
        ))}

        <div>
          <label className="label">고정 주휴</label>
          <select
            value={form.fixed_weekly_off ?? ''}
            onChange={e => set('fixed_weekly_off', e.target.value === '' ? null : parseInt(e.target.value))}
            className="input"
          >
            <option value="">없음</option>
            {WD_OPTS.map((wd, i) => <option key={i} value={i}>{wd}요일</option>)}
          </select>
        </div>

        <div>
          <label className="label">휴가 잔여</label>
          <input type="number" min={0} value={form.vacation_days}
            onChange={e => set('vacation_days', parseInt(e.target.value) || 0)}
            className="input" />
        </div>

        <div>
          <label className="label">전월 N</label>
          <input type="number" min={0} value={form.prev_month_n}
            onChange={e => set('prev_month_n', parseInt(e.target.value) || 0)}
            className="input" />
        </div>

        <div>
          <label className="label">메모</label>
          <input value={form.note} onChange={e => set('note', e.target.value)} className="input" />
        </div>
      </div>

      <div className="flex flex-wrap gap-4 pt-1">
        {[
          ['is_pregnant', '임산부'],
          ['is_male', '남성'],
          ['is_4day_week', '주4일'],
        ].map(([k, label]) => (
          <label key={k} className="flex items-center gap-2 cursor-pointer select-none">
            <div
              onClick={() => set(k, !form[k])}
              className={`w-9 h-5 rounded-full transition-colors flex items-center px-0.5 cursor-pointer ${form[k] ? 'bg-blue-600' : 'bg-slate-200'}`}>
              <div className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${form[k] ? 'translate-x-4' : ''}`} />
            </div>
            <span className="text-sm font-medium text-slate-700">{label}</span>
          </label>
        ))}
      </div>

      <div className="flex gap-2 pt-1">
        <button onClick={onCancel} className="btn-secondary flex-1 text-sm">취소</button>
        <button
          onClick={() => { if (!form.name.trim()) return; onSave(form) }}
          disabled={!form.name.trim()}
          className="btn-primary flex-1 text-sm"
        >저장</button>
      </div>
    </div>
  )
}

export default function NurseManagementTab() {
  const [nurses, setNurses] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)
  const [msg, setMsg] = useState({ text: '', ok: true })
  const [pinReset, setPinReset] = useState({})

  const load = () => {
    nursesApi.list().then(res => setNurses(res.data)).catch(() => {}).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const showMsg = (text, ok = true) => { setMsg({ text, ok }); setTimeout(() => setMsg({ text: '', ok: true }), 2500) }

  const handleSave = async (form) => {
    try {
      if (editing === 'new') { await nursesApi.create(form); showMsg('추가되었습니다') }
      else { await nursesApi.update(editing.id, form); showMsg('수정되었습니다') }
      setEditing(null); load()
    } catch (e) { showMsg(e.response?.data?.detail || '저장 실패', false) }
  }

  const handleDelete = async (nurse) => {
    if (!window.confirm(`${nurse.name}을(를) 삭제하시겠습니까?`)) return
    try { await nursesApi.remove(nurse.id); showMsg('삭제되었습니다'); load() }
    catch (e) { showMsg(e.response?.data?.detail || '삭제 실패', false) }
  }

  const handlePinReset = async (nurse) => {
    if (!window.confirm(`${nurse.name}의 PIN을 0000으로 초기화할까요?`)) return
    try {
      await authApi.resetPin(nurse.id)
      setPinReset(p => ({ ...p, [nurse.id]: true }))
      setTimeout(() => setPinReset(p => ({ ...p, [nurse.id]: false })), 2500)
    } catch { showMsg('PIN 초기화 실패', false) }
  }

  const handleExcelImport = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      const res = await nursesApi.importExcel(file)
      showMsg(`${res.data.length}명 가져오기 완료`); load()
    } catch (err) { showMsg(err.response?.data?.detail || '엑셀 가져오기 실패', false) }
    e.target.value = ''
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-slate-400 gap-2 text-sm">
      <div className="w-4 h-4 border-2 border-slate-200 border-t-slate-400 rounded-full animate-spin" />
      불러오는 중...
    </div>
  )

  return (
    <div className="p-2 sm:p-4 space-y-4 max-w-2xl mx-auto">
      {/* 액션 바 */}
      <div className="flex gap-2">
        <button onClick={() => setEditing('new')} className="btn-primary flex-1 text-sm flex items-center justify-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          간호사 추가
        </button>
        <label className="btn-secondary flex-1 text-sm flex items-center justify-center gap-2 cursor-pointer">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          엑셀 가져오기
          <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handleExcelImport} />
        </label>
      </div>

      {/* 메시지 */}
      {msg.text && (
        <div className={`rounded-xl px-4 py-3 text-center text-sm font-semibold border ${
          msg.ok ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-600 border-red-200'
        }`}>
          {msg.ok ? '✓ ' : '✗ '}{msg.text}
        </div>
      )}

      {/* 새 간호사 폼 */}
      {editing === 'new' && (
        <NurseForm onSave={handleSave} onCancel={() => setEditing(null)} />
      )}

      {/* 간호사 목록 */}
      <div className="card overflow-hidden">
        {nurses.length === 0 ? (
          <div className="text-center py-16 text-slate-400">
            <svg className="mx-auto mb-3 text-slate-300" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
            <p className="text-sm">등록된 간호사가 없습니다</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {nurses.map(n => (
              <li key={n.id}>
                {editing?.id === n.id ? (
                  <div className="p-3">
                    <NurseForm initial={n} onSave={handleSave} onCancel={() => setEditing(null)} />
                  </div>
                ) : (
                  <div className="flex items-center px-4 py-3.5">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-900 text-sm">{n.name}</span>
                        {n.grade && (
                          <span className="badge bg-blue-50 text-blue-700">{n.grade}</span>
                        )}
                        {n.role && (
                          <span className="badge bg-slate-100 text-slate-600">{n.role}</span>
                        )}
                        {n.is_4day_week && <span className="badge bg-amber-50 text-amber-700">주4일</span>}
                        {n.is_pregnant && <span className="badge bg-pink-50 text-pink-700">임산부</span>}
                        {n.is_male && <span className="badge bg-sky-50 text-sky-700">남성</span>}
                      </div>
                      {n.vacation_days > 0 && (
                        <p className="text-xs text-slate-400 mt-0.5">휴가 {n.vacation_days}일 잔여</p>
                      )}
                    </div>
                    <div className="flex gap-1 ml-3 flex-shrink-0">
                      <button
                        onClick={() => handlePinReset(n)}
                        className={`text-xs px-2.5 py-1.5 rounded-lg font-medium transition-colors ${
                          pinReset[n.id] ? 'bg-green-50 text-green-600' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                        }`}>
                        {pinReset[n.id] ? '✓ PIN' : 'PIN↺'}
                      </button>
                      <button
                        onClick={() => setEditing(n)}
                        className="text-xs px-2.5 py-1.5 bg-blue-50 text-blue-700 rounded-lg font-medium hover:bg-blue-100 transition-colors">
                        수정
                      </button>
                      <button
                        onClick={() => handleDelete(n)}
                        className="text-xs px-2.5 py-1.5 bg-red-50 text-red-600 rounded-lg font-medium hover:bg-red-100 transition-colors">
                        삭제
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-center text-xs text-slate-400">총 {nurses.length}명</p>
    </div>
  )
}
