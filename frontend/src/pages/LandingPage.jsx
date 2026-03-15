import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { settingsApi } from '../api/client'
import { fmtDate, dlPassed } from '../utils/constants'

export default function LandingPage() {
  const navigate = useNavigate()
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    settingsApi.get({ timeout: 5000 })
      .then(res => setSettings(res.data))
      .catch(() => { })
      .finally(() => setLoading(false))
  }, [])

  const startDate = settings?.start_date
  const deadline = settings?.deadline
  const passed = dlPassed(deadline)
  const endStr = startDate ? fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000)) : ''

  return (
    <div className="min-h-screen flex flex-col" style={{
      background: 'linear-gradient(145deg, #0F172A 0%, #1E3A8A 50%, #1D4ED8 100%)'
    }}>
      {/* 상단 여백 */}
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-16">

        {/* 로고 영역 */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-black text-white tracking-tight mb-2">Nurse Scheduler</h1>
          {/* 설명 pill */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium mb-3"
            style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)', color: '#93C5FD' }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/>
              <line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
            </svg>
            근무 신청 및 자동 근무표 생성 시스템
          </div>
          {settings?.department_name && (
            <p className="text-blue-300 text-sm font-semibold">{settings.department_name}</p>
          )}
        </div>

        {/* 기간 카드 */}
        {!loading && startDate && (
          <div className="w-full max-w-sm mb-8 rounded-2xl p-4"
            style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)' }}>
            <p className="text-blue-300 text-sm font-semibold uppercase tracking-widest mb-2 text-center">근무 일정</p>
            <p className="text-white font-bold text-lg text-center mb-3">
              {fmtDate(startDate)} ~ {endStr}
            </p>
            {deadline && (
              <div className={`flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold ${passed
                  ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                  : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}>
                {passed ? (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
                  </svg>
                ) : (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/>
                  </svg>
                )}
                <span>{passed ? '신청 마감됨' : `마감 ${fmtDate(deadline)}`}</span>
              </div>
            )}
          </div>
        )}

        {loading && (
          <div className="mb-8 flex items-center gap-2 text-blue-300 text-sm">
            <div className="w-4 h-4 border-2 border-blue-300/30 border-t-blue-300 rounded-full animate-spin" />
            서버 연결 중...
          </div>
        )}

        {/* CTA 버튼 */}
        <div className="w-full max-w-sm space-y-3">
          <button
            onClick={() => navigate('/nurse/login')}
            className="w-full bg-white text-blue-700 font-bold text-lg rounded-2xl py-5 flex items-center justify-center gap-3 active:scale-95 transition-all shadow-2xl hover:bg-blue-50 hover:scale-[1.02]"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
            근무 신청하기
          </button>

          <button
            onClick={() => navigate('/admin/login')}
            className="w-full text-white font-semibold text-lg rounded-2xl py-4 flex items-center justify-center gap-2 active:scale-95 transition-all hover:scale-[1.02] hover:brightness-125"
            style={{ background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)' }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
            </svg>
            관리자
          </button>
        </div>
      </div>

      {/* Footer */}
      <footer className="px-5 pb-8 pt-4"
        style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="max-w-sm mx-auto text-center">
          <p className="text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>
            <span className="inline-block">© 2026 Nurse Scheduler · </span>
            <span className="inline-block">Contact:{' '}
              <a href="mailto:choiyujeong0411@gmail.com" className="hover:underline">
                choiyujeong0411@gmail.com
              </a>
            </span>
          </p>
        </div>
      </footer>
    </div>
  )
}
