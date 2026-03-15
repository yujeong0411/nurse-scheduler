import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { nursesApi, authApi } from '../api/client'
import useAuthStore from '../store/auth'

export default function NurseAuthPage() {
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()

  const [nurses, setNurses] = useState([])
  const [nurseId, setNurseId] = useState('')
  const [nurseName, setNurseName] = useState('')
  const [pin, setPin] = useState('')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPicker, setShowPicker] = useState(false)

  useEffect(() => {
    nursesApi.names().then(res => setNurses(res.data)).catch(() => { })
  }, [])

  const handleSelect = (n) => {
    setNurseId(n.id); setNurseName(n.name)
    setErr(''); setPin(''); setShowPicker(false)
  }

  const handleLogin = async () => {
    if (!nurseId) { setErr('이름을 선택해주세요.'); return }
    setLoading(true)
    try {
      const res = await authApi.nurseLogin(nurseId, pin)
      setAuth(res.data.token, 'nurse', res.data.name, nurseId)
      navigate('/nurse')
    } catch (e) {
      setErr(e.response?.data?.detail || 'PIN이 틀렸습니다.')
      setPin('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{
      background: 'linear-gradient(145deg, #A8C8B4 0%, #8EADD4 45%, #E4C49A 80%, #C4A0BC 100%)'
    }}>
      {/* 뒤로가기 */}
      <div className="p-5">
        <button onClick={() => navigate('/')}
          className="flex items-center gap-2 transition-colors text-sm font-medium" style={{ color: '#2A3A7A' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          돌아가기
        </button>
      </div>

      <div className="flex-1 flex flex-col justify-center px-5 pb-12">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-5"
            style={{ background: 'rgba(255,255,255,0.55)', border: '1px solid rgba(255,255,255,0.8)' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#1A2744" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <h2 className="text-3xl font-black mb-1" style={{ color: '#1A2744', textShadow: '0 2px 12px rgba(255,255,255,0.6)' }}>근무 신청</h2>
          <p className="text-sm" style={{ color: 'rgba(30,50,90,0.65)' }}>초기 PIN은 0000입니다</p>
        </div>

        {/* 로그인 카드 */}
        <div className="bg-white rounded-3xl shadow-2xl p-6 max-w-sm mx-auto w-full space-y-4">
          {/* 이름 선택 */}
          <div>
            <label className="label">이름 선택</label>
            <button
              onClick={() => setShowPicker(true)}
              className="w-full flex items-center justify-between rounded-xl px-4 py-3 text-left transition-all border"
              style={{
                border: `1.5px solid ${nurseId ? '#3B82F6' : '#E2E8F0'}`,
                background: nurseId ? '#EFF6FF' : '#F8FAFC',
              }}
            >
              <span className={`text-base font-${nurseId ? 'semibold' : 'normal'}`}
                style={{ color: nurseId ? '#1D4ED8' : '#94A3B8' }}>
                {nurseName || '이름을 선택하세요'}
              </span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
          </div>

          {/* PIN */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="label" style={{ margin: 0 }}>PIN 번호</label>
              <span className="text-xs text-slate-400">숫자 · 최대 8자리</span>
            </div>
            <input
              type="password"
              inputMode="numeric"
              maxLength={8}
              value={pin}
              onChange={e => { setPin(e.target.value.replace(/[^0-9]/g, '')); setErr('') }}
              onKeyDown={e => { if (e.key === 'Enter') handleLogin() }}
              placeholder="숫자 PIN 입력"
              className="input"
            />
          </div>

          {err && (
            <div className="rounded-xl px-4 py-3 bg-red-50 border border-red-200 text-red-600 text-sm font-medium text-center">
              {err}
            </div>
          )}

          <button
            onClick={handleLogin}
            disabled={loading || !nurseId}
            className="btn-primary w-full py-4 text-base"
          >
            {loading
              ? <span className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                확인 중...
              </span>
              : '로그인'
            }
          </button>
        </div>
      </div>

      {/* 이름 선택 바텀시트 */}
      {showPicker && (
        <div className="fixed inset-0 z-50 flex flex-col justify-end" style={{ background: 'rgba(0,0,0,0.6)' }}
          onClick={() => setShowPicker(false)}>
          <div className="bg-white rounded-t-3xl" style={{ maxHeight: '70vh', display: 'flex', flexDirection: 'column' }}
            onClick={e => e.stopPropagation()}>
            {/* 핸들 */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-10 h-1 bg-slate-300 rounded-full" />
            </div>
            {/* 헤더 */}
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-slate-900">이름 선택</h3>
                <p className="text-xs text-slate-400 mt-0.5">총 {nurses.length}명</p>
              </div>
              <button onClick={() => setShowPicker(false)}
                className="w-8 h-8 flex items-center justify-center rounded-full bg-slate-100 text-slate-500">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            {/* 목록 */}
            <div className="overflow-y-auto flex-1 py-2">
              {nurses.length === 0 && (
                <div className="text-center py-12 text-slate-400 text-sm">
                  등록된 간호사가 없습니다.<br />관리자에게 문의하세요.
                </div>
              )}
              {nurses.map(n => {
                const isSel = n.id === nurseId
                return (
                  <button key={n.id} onClick={() => handleSelect(n)}
                    className="w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-slate-50 transition-colors"
                    style={{ background: isSel ? '#EFF6FF' : undefined }}>
                    <div>
                      <span className={`text-base font-${isSel ? 'bold' : 'medium'}`}
                        style={{ color: isSel ? '#1D4ED8' : '#0F172A' }}>{n.name}</span>
                      {(n.grade || n.role) && (
                        <span className="ml-2 text-xs text-slate-400">
                          {[n.grade, n.role].filter(Boolean).join(' · ')}
                        </span>
                      )}
                    </div>
                    {isSel && (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </button>
                )
              })}
              <div className="h-6" />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
