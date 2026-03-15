import { useState } from 'react'
import { authApi } from '../api/client'

export default function PinModal({ onClose }) {
  const [oldPin, setOldPin] = useState('')
  const [newPin, setNewPin] = useState('')
  const [confPin, setConfPin] = useState('')
  const [err, setErr] = useState(null)
  const [ok, setOk] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (newPin.length < 4) { setErr('PIN은 4자리 이상이어야 합니다.'); return }
    if (newPin !== confPin) { setErr('새 PIN이 일치하지 않습니다.'); return }
    setSaving(true); setErr(null)
    try {
      await authApi.changePin(oldPin, newPin)
      setOk(true)
      setTimeout(onClose, 1500)
    } catch (e) {
      setErr(e.response?.data?.detail || '변경 실패. 현재 PIN을 확인해주세요.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={() => { if (!saving) onClose() }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
        <h2 className="font-bold text-slate-900 text-base mb-1">PIN 변경</h2>
        <p className="text-xs text-slate-400 mb-4">숫자만 입력 가능 · 최대 8자리</p>

        {ok ? (
          <div className="text-center py-6">
            <p className="text-emerald-600 font-bold text-lg">✅ 변경 완료!</p>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {[
                { key: 'old', label: '현재 PIN', val: oldPin, set: setOldPin },
                { key: 'new', label: '새 PIN', val: newPin, set: setNewPin },
                { key: 'conf', label: '새 PIN 확인', val: confPin, set: setConfPin },
              ].map(({ key, label, val, set }) => (
                <div key={key}>
                  <label className="block text-xs font-semibold text-slate-500 mb-1">{label}</label>
                  <input
                    type="password"
                    inputMode="numeric"
                    maxLength={8}
                    value={val}
                    onChange={e => { set(e.target.value.replace(/\D/g, '')); setErr(null) }}
                    onKeyDown={e => e.key === 'Enter' && handleSave()}
                    placeholder="숫자 PIN 입력"
                    className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:border-transparent" style={{ '--tw-ring-color': '#2A3A7A' }}
                  />
                </div>
              ))}
            </div>

            {err && (
              <p className="mt-3 text-xs font-semibold text-red-500">{err}</p>
            )}

            <div className="flex gap-2 mt-4">
              <button onClick={onClose}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors">
                취소
              </button>
              <button onClick={handleSave} disabled={saving}
                className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white transition-colors disabled:opacity-50" style={{ background: '#2A3A7A' }}>
                {saving ? '변경 중...' : '변경'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
