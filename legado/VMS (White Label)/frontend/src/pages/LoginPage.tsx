import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { authService, themeService } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { useThemeStore } from '@/store/themeStore'

export function LoginPage() {
  const navigate  = useNavigate()
  const { setAuth, isAuthenticated } = useAuthStore()
  const { theme, setTheme, loading: themeLoading, setLoading } = useThemeStore()

  const [email, setEmail]             = useState('')
  const [password, setPassword]       = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading]     = useState(false)
  const [error, setError]             = useState('')

  useEffect(() => {
    if (isAuthenticated()) { navigate('/'); return }
    themeService.get()
      .then(setTheme)
      .catch(() => setTheme({ name: 'VMS', primary_color: '#3B82F6' }))
      .finally(() => setLoading(false))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      const res = await authService.login({ email, password })
      setAuth(res.user, res.access, res.refresh)
      navigate('/')
    } catch (err: any) {
      if (err.response?.status === 401) setError('Email ou senha incorretos.')
      else if (err.response?.status === 423) setError('Conta bloqueada. Tente novamente em 15 minutos.')
      else setError('Erro ao fazer login. Tente novamente.')
    } finally {
      setIsLoading(false)
    }
  }

  const primary = theme?.primary_color || '#3B82F6'

  if (themeLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#0A0A0F' }}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-2 border-t-transparent mx-auto"
            style={{ borderColor: primary, borderTopColor: 'transparent' }} />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex" style={{ background: '#0A0A0F' }}>
      {/* Left — branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <img
          src="https://images.unsplash.com/photo-1557597774-9d273605dfa9?w=1200"
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0" style={{ background: primary, opacity: 0.82 }} />
        <div className="relative z-10 flex flex-col items-center justify-center w-full p-16">
          {theme?.logo_url && <img src={theme.logo_url} alt={theme.name} className="h-14 mb-8 object-contain" />}
          <h1 className="text-5xl font-bold text-white mb-3">{theme?.name || 'VMS'}</h1>
          <p className="text-lg text-white/80">Monitoramento Inteligente</p>
          <div className="mt-12 grid grid-cols-2 gap-4 w-full max-w-sm">
            {['IA Embarcada', 'Multi-Câmera', 'Analíticos', 'Dark Mode'].map(f => (
              <div key={f} className="bg-white/10 backdrop-blur-sm rounded-xl px-4 py-3 text-center">
                <p className="text-white text-sm font-medium">{f}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right — form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8"
        style={{ background: '#111118' }}>
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="lg:hidden flex justify-center mb-8">
            {theme?.logo_url
              ? <img src={theme.logo_url} alt={theme.name} className="h-12 object-contain" />
              : <div className="w-12 h-12 rounded-2xl flex items-center justify-center text-white text-xl font-bold"
                  style={{ background: primary }}>V</div>
            }
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-white">Acesso ao Sistema</h2>
            <p className="text-sm mt-1" style={{ color: '#71717A' }}>Entre com suas credenciais</p>
          </div>

          {error && (
            <div className="mb-5 p-3 rounded-lg border flex items-start gap-2 text-sm"
              style={{ background: 'rgba(239,68,68,0.08)', borderColor: 'rgba(239,68,68,0.25)', color: '#FCA5A5' }}>
              <svg className="w-4 h-4 mt-0.5 shrink-0 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                type="email" required autoFocus autoComplete="email"
                className="input"
                placeholder="seu@email.com"
                value={email} onChange={e => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="label">Senha</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  required autoComplete="current-password"
                  className="input pr-10"
                  placeholder="••••••••"
                  value={password} onChange={e => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 transition"
                  style={{ color: '#52525B' }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 px-4 text-white font-semibold rounded-lg transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-2"
              style={{ background: primary }}
            >
              {isLoading ? <><Loader2 size={16} className="animate-spin" />Entrando...</> : 'Entrar'}
            </button>
          </form>

          <div className="mt-8 text-center text-xs" style={{ color: '#52525B' }}>
            <p>{theme?.name || 'VMS'} &copy; {new Date().getFullYear()}</p>
            <div className="mt-2 flex justify-center gap-4">
              {theme?.terms_url && (
                <a href={theme.terms_url} target="_blank" rel="noreferrer"
                  className="hover:underline transition" style={{ color: primary }}>
                  Termos de Uso
                </a>
              )}
              {theme?.privacy_url && (
                <a href={theme.privacy_url} target="_blank" rel="noreferrer"
                  className="hover:underline transition" style={{ color: primary }}>
                  Privacidade
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
