import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../../api/client'
import useAuthStore from '../../store/auth'

export default function AdminAuthPage() {
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async () => {
    if (!password) { setErr('비밀번호를 입력해주세요.'); return }
    setLoading(true)
    try {
      const res = await authApi.adminLogin(password)
      setAuth(res.data.token, 'admin')
      navigate('/admin')
    } catch (e) {
      setErr(e.response?.data?.detail || '비밀번호가 틀렸습니다.')
      setPassword('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{
      background: 'linear-gradient(145deg, #0F172A 0%, #1E3A8A 50%, #1D4ED8 100%)'
    }}>
      {/* 뒤로가기 */}
      <div className="p-5">
        <button onClick={() => navigate('/')}
          className="flex items-center gap-2 text-blue-300 hover:text-white transition-colors text-sm font-medium">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          돌아가기
        </button>
      </div>

      <div className="flex-1 flex flex-col justify-center px-5 pb-12">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-5"
            style={{ background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.2)' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="8" r="4"/>
              <path d="M20 21a8 8 0 1 0-16 0"/>
              <polyline points="16 11 18 13 22 9"/>
            </svg>
          </div>
          <h2 className="text-3xl font-black text-white mb-1">관리자 로그인</h2>
          <p className="text-blue-300 text-sm">관리자 비밀번호를 입력하세요</p>
        </div>

        {/* 로그인 카드 */}
        <div className="bg-white rounded-3xl shadow-2xl p-6 max-w-sm mx-auto w-full space-y-4">
          <div>
            <label className="label">비밀번호</label>
            <input
              type="password"
              value={password}
              onChange={e => { setPassword(e.target.value); setErr('') }}
              onKeyDown={e => { if (e.key === 'Enter') handleLogin() }}
              placeholder="비밀번호 입력"
              className="input text-base"
              autoFocus
            />
          </div>

          {err && (
            <div className="rounded-xl px-4 py-3 bg-red-50 border border-red-200 text-red-600 text-sm font-medium text-center">
              {err}
            </div>
          )}

          <button
            onClick={handleLogin}
            disabled={loading || !password}
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
    </div>
  )
}
