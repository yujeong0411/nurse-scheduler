import { useState } from 'react'
import { authApi } from '../api/client'

export default function PinModal({ onClose }) {
  const [oldPin, setOldPin] = useState('')
  const [newPin, setNewPin] = useState('')
  const [confPin, setConfPin] = useState('')
  const [err, setErr] = useState('')
  const [ok, setOk] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (newPin.length < 4) { setErr('4자리 이상 입력해주세요.'); return }
    if (newPin !== confPin) { setErr('PIN이 일치하지 않습니다.'); return }
    setSaving(true)
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

  const inputStyle = {
    width: '100%', border: '2px solid #E5E7EB', borderRadius: '12px',
    padding: '14px 16px', fontSize: '24px', textAlign: 'center',
    letterSpacing: '0.4em', boxSizing: 'border-box', outline: 'none'
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6"
      onClick={() => { if (!saving) onClose() }}>
      <div className="bg-white rounded-3xl shadow-2xl p-6 w-full max-w-xs"
        onClick={e => e.stopPropagation()}>
        <h3 className="font-bold text-lg mb-1 text-center">🔐 PIN 변경</h3>
        <p className="text-xs text-gray-400 text-center mb-4">4~6자리 숫자</p>

        {ok ? (
          <div className="text-center py-6">
            <div className="text-5xl mb-3">✅</div>
            <p className="text-green-600 font-bold text-lg">변경 완료!</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-gray-500 block mb-1">현재 PIN</label>
              <input type="password" inputMode="numeric" maxLength={6}
                value={oldPin} onChange={e => { setOldPin(e.target.value.replace(/\D/g, '')); setErr('') }}
                placeholder="● ● ● ●" style={inputStyle} />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-500 block mb-1">새 PIN</label>
              <input type="password" inputMode="numeric" maxLength={6}
                value={newPin} onChange={e => { setNewPin(e.target.value.replace(/\D/g, '')); setErr('') }}
                placeholder="● ● ● ●" style={inputStyle} />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-500 block mb-1">새 PIN 확인</label>
              <input type="password" inputMode="numeric" maxLength={6}
                value={confPin} onChange={e => { setConfPin(e.target.value.replace(/\D/g, '')); setErr('') }}
                onKeyDown={e => { if (e.key === 'Enter') handleSave() }}
                placeholder="● ● ● ●" style={inputStyle} />
            </div>
            {err && (
              <div className="rounded-xl px-3 py-2 text-center text-sm font-medium"
                style={{ background: '#FEF2F2', border: '1.5px solid #FECACA', color: '#DC2626' }}>{err}</div>
            )}
            <div className="flex gap-2 pt-1">
              <button onClick={onClose}
                className="flex-1 rounded-xl font-semibold"
                style={{ padding: '13px', fontSize: '15px', background: '#F3F4F6', color: '#374151' }}>
                취소
              </button>
              <button onClick={handleSave} disabled={saving}
                className="flex-1 rounded-xl font-bold text-white"
                style={{ padding: '13px', fontSize: '15px', background: '#2563EB', opacity: saving ? 0.6 : 1 }}>
                {saving ? '변경 중...' : '변경'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
