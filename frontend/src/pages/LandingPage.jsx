import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { settingsApi } from '../api/client'
import { fmtDate, dlPassed } from '../utils/constants'

export default function LandingPage() {
  const navigate = useNavigate()
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [serverError, setServerError] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => { setLoading(false); setServerError(true) }, 6000)
    settingsApi.get({ timeout: 5000 })
      .then(res => setSettings(res.data))
      .catch(() => setServerError(true))
      .finally(() => { clearTimeout(timer); setLoading(false) })
    return () => clearTimeout(timer)
  }, [])

  const startDate = settings?.start_date
  const deadline = settings?.deadline
  const passed = dlPassed(deadline)
  const endStr = startDate ? fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000)) : ''

  return (
    <div className="min-h-screen flex flex-col" style={{
      background: 'linear-gradient(145deg, #A8C8B4 0%, #8EADD4 45%, #E4C49A 80%, #C4A0BC 100%)'
    }}>
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-16">

        {/* 로고 영역 */}
        <div className="text-center mb-10">
          <img src="/logo.png" alt="logo" className="w-20 h-20 md:w-24 md:h-24 mx-auto mb-4 rounded-2xl shadow-lg" />
          <h1 className="text-4xl md:text-6xl font-black tracking-tight mb-2" style={{
            color: '#1A2744', textShadow: '0 2px 12px rgba(255,255,255,0.6)'
          }}>Nurse Scheduler</h1>
          <p className="text-xs md:text-sm mb-3" style={{ color: 'rgba(30,50,90,0.65)' }}>근무 신청 및 자동 근무표 생성 시스템</p>
          {settings?.department_name && (
            <p className="text-base md:text-lg font-semibold" style={{ color: '#1A2744' }}>{settings.department_name}</p>
          )}
        </div>

        {/* 기간 카드 */}
        {!loading && startDate && (
          <div className="w-full max-w-sm md:max-w-md mb-8 rounded-2xl p-4 md:p-6"
            style={{ background: 'rgba(255,255,255,0.42)', border: '1px solid rgba(255,255,255,0.65)' }}>
            <p className="text-base font-bold uppercase tracking-normal mb-2 text-center" style={{ color: '#0F1E3C' }}>근무 일정</p>
            <p className="font-bold text-lg md:text-2xl text-center mb-3" style={{ color: '#0F1E3C' }}>
              {fmtDate(startDate)} ~ {endStr}
            </p>
            {deadline && (
              <div className={`flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-sm md:text-base font-semibold ${passed ? 'bg-red-400/35 border border-red-500/50' : 'border'}`}
                style={passed ? { color: '#7A2A2A' } : { background: 'rgba(255,220,130,0.5)', borderColor: 'rgba(230,180,80,0.65)', color: '#7A4A0A' }}>
                {passed ? (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
                  </svg>
                ) : (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" /><line x1="4" y1="22" x2="4" y2="15" />
                  </svg>
                )}
                <span>{passed ? '신청 마감됨' : `마감 ${fmtDate(deadline)}`}</span>
              </div>
            )}
          </div>
        )}

        {loading && (
          <div className="mb-8 flex items-center gap-2 text-sm" style={{ color: '#3D5A8A' }}>
            <div className="w-4 h-4 border-2 rounded-full animate-spin"
              style={{ borderColor: 'rgba(90,122,170,0.3)', borderTopColor: '#5A7AAA' }} />
            서버 연결 중...
          </div>
        )}
        {!loading && serverError && (
          <div className="mb-8 flex items-center gap-2 text-sm font-semibold px-4 py-2 rounded-xl" style={{ color: '#7A2000', background: 'rgba(255,180,100,0.25)', border: '1px solid rgba(200,100,30,0.4)' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            서버를 깨우는 중입니다.<br /> 1분 후 페이지를 새로고침해주세요.
          </div>
        )}

        {/* CTA 버튼 */}
        <div className="w-full max-w-sm md:max-w-md space-y-3">
          <button
            onClick={() => navigate('/nurse/login')}
            className="w-full font-bold text-lg md:text-xl rounded-2xl py-4 md:py-5 flex items-center justify-center gap-3 active:scale-95 transition-all hover:scale-[1.02]"
            style={{ background: 'rgba(255,255,255,0.78)', color: '#2C4A7C', backdropFilter: 'blur(8px)' }}
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
            className="w-full font-semibold text-lg md:text-xl rounded-2xl py-4 md:py-5 flex items-center justify-center gap-2 active:scale-95 transition-all hover:scale-[1.02] hover:brightness-110"
            style={{ background: 'rgba(30,50,100,0.15)', border: '1px solid rgba(30,50,100,0.25)', color: '#1A2744' }}
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
      <footer className="px-5 pb-8 pt-4" style={{ borderTop: '1px solid rgba(0,0,0,0.1)' }}>
        <div className="max-w-sm mx-auto text-center">
          <p className="text-xs" style={{ color: 'rgba(20,40,80,0.45)' }}>
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
