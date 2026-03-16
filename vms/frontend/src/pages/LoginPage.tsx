import { useState } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { Eye, EyeOff } from 'lucide-react'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const login = useAuthStore((s) => s.login)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const navigate = useNavigate()

  if (isAuthenticated) return <Navigate to="/" replace />

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/')
    } catch {
      setError('Credenciais inválidas. Verifique email e senha.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left — Branding */}
      <div className="hidden lg:flex flex-1 relative overflow-hidden bg-gradient-to-br from-blue-600 via-blue-500 to-blue-700 items-center justify-center">
        {/* Camera pattern SVG background */}
        <div className="absolute inset-0 opacity-20">
          <svg className="w-full h-full" viewBox="0 0 800 600" fill="none" xmlns="http://www.w3.org/2000/svg">
            {Array.from({ length: 20 }).map((_, i) => (
              <g key={i} transform={`translate(${(i % 5) * 170 + 40}, ${Math.floor(i / 5) * 160 + 40}) rotate(-30)`}>
                <rect x="0" y="10" width="60" height="35" rx="4" stroke="white" strokeWidth="2" fill="none" />
                <rect x="50" y="18" width="20" height="18" rx="9" stroke="white" strokeWidth="2" fill="none" />
                <rect x="-15" y="35" width="8" height="15" rx="2" fill="white" opacity="0.5" />
              </g>
            ))}
          </svg>
        </div>

        <div className="relative z-10 text-center text-white px-8">
          <h1 className="text-5xl font-bold mb-3">VMS</h1>
          <p className="text-xl opacity-90 mb-10">Monitoramento Inteligente</p>
          <div className="grid grid-cols-2 gap-3 max-w-xs mx-auto">
            {['IA Embarcada', 'Multi-Câmera', 'Analíticos', 'Dark Mode'].map((badge) => (
              <div
                key={badge}
                className="bg-white/20 backdrop-blur-sm rounded-lg px-4 py-2 text-sm font-medium"
              >
                {badge}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right — Login form */}
      <div className="flex-1 flex items-center justify-center bg-vms-bg p-8">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="lg:hidden text-center mb-8">
            <div className="w-12 h-12 rounded-xl bg-vms-accent flex items-center justify-center text-white font-bold text-xl mx-auto mb-2">
              V
            </div>
            <h1 className="text-2xl font-bold">VMS</h1>
          </div>

          <h2 className="text-2xl font-bold mb-1">Acesso ao Sistema</h2>
          <p className="text-vms-muted mb-8">Entre com suas credenciais</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm text-vms-muted mb-1.5">Email</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-vms-card border border-vms-border rounded-lg px-4 py-3 text-white placeholder-vms-muted-dark focus:outline-none focus:border-vms-accent transition-colors"
                placeholder="admin@vms.dev"
                required
                autoFocus
              />
            </div>

            <div>
              <label className="block text-sm text-vms-muted mb-1.5">Senha</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-vms-card border border-vms-border rounded-lg px-4 py-3 text-white placeholder-vms-muted-dark focus:outline-none focus:border-vms-accent transition-colors pr-10"
                  placeholder="••••••••"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-vms-muted hover:text-white"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-vms-accent hover:bg-vms-accent-hover disabled:opacity-60 rounded-lg py-3 font-semibold transition-colors"
            >
              {loading ? 'Entrando...' : 'Entrar'}
            </button>
          </form>

          <p className="text-center text-vms-muted-dark text-sm mt-10">VMS © 2026</p>
        </div>
      </div>
    </div>
  )
}
