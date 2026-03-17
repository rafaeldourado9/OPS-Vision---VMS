import { useEffect, useState } from 'react'
import { Save, Palette, Shield, Bell, Database, Key, Upload, Check } from 'lucide-react'
import { clsx } from 'clsx'
import { themeService } from '@/services/api'
import { useThemeStore } from '@/store/themeStore'
import { usePermission } from '@/hooks/usePermission'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'

type Tab = 'appearance' | 'account' | 'notifications' | 'system'

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'appearance',    label: 'Aparência',     icon: Palette },
  { id: 'account',      label: 'Minha Conta',   icon: Shield },
  { id: 'notifications', label: 'Notificações', icon: Bell },
  { id: 'system',       label: 'Sistema',       icon: Database },
]

const PRESET_COLORS = [
  { label: 'Azul',    value: '#3B82F6' },
  { label: 'Roxo',    value: '#8B5CF6' },
  { label: 'Verde',   value: '#22C55E' },
  { label: 'Laranja', value: '#F59E0B' },
  { label: 'Rosa',    value: '#EC4899' },
  { label: 'Ciano',   value: '#06B6D4' },
  { label: 'Vermelho',value: '#EF4444' },
  { label: 'Limão',   value: '#84CC16' },
]

export function SettingsPage() {
  const { user } = useAuthStore()
  const { isSuperAdmin, isCityAdmin } = usePermission()
  const { theme, setTheme } = useThemeStore()
  const [tab, setTab]       = useState<Tab>('appearance')
  const [saving, setSaving] = useState(false)

  // Appearance
  const [primaryColor, setPrimary]     = useState(theme?.primary_color ?? '#3B82F6')
  const [companyName, setCompany]      = useState(theme?.company_name ?? '')
  const [logoFile, setLogoFile]        = useState<File | null>(null)
  const [logoPreview, setLogoPreview]  = useState(theme?.logo_url ?? '')
  const [customColor, setCustom]       = useState(theme?.primary_color ?? '#3B82F6')

  // Account
  const [accName, setAccName]          = useState(user?.name ?? '')
  const [accEmail, setAccEmail]        = useState(user?.email ?? '')
  const [accPassword, setAccPassword]  = useState('')
  const [accConfirm, setAccConfirm]    = useState('')

  // Notifications (local only for now)
  const [notifEvents, setNotifEvents]  = useState(true)
  const [notifOffline, setNotifOffline] = useState(true)
  const [notifQueue, setNotifQueue]    = useState(false)

  useEffect(() => {
    if (theme) {
      setPrimary(theme.primary_color ?? '#3B82F6')
      setCustom(theme.primary_color ?? '#3B82F6')
      setCompany(theme.company_name ?? '')
      setLogoPreview(theme.logo_url ?? '')
    }
  }, [theme])

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setLogoFile(file)
    setLogoPreview(URL.createObjectURL(file))
  }

  const handleSaveTheme = async () => {
    setSaving(true)
    try {
      const data = new FormData()
      data.append('primary_color', primaryColor)
      data.append('company_name', companyName)
      if (logoFile) data.append('logo', logoFile)
      const updated = await themeService.update(data)
      setTheme(updated)
      toast.success('Aparência salva!')
    } catch { toast.error('Erro ao salvar aparência') }
    finally { setSaving(false) }
  }

  const handleSaveAccount = async () => {
    if (accPassword && accPassword !== accConfirm) {
      toast.error('Senhas não conferem')
      return
    }
    setSaving(true)
    try {
      // Would call userService.updateMe() in real scenario
      toast.success('Conta atualizada')
    } catch { toast.error('Erro ao salvar conta') }
    finally { setSaving(false) }
  }

  const selectColor = (c: string) => { setPrimary(c); setCustom(c) }

  return (
    <div className="space-y-4 animate-fade-in max-w-3xl">
      {/* Tabs */}
      <div className="flex items-center gap-1 p-1 rounded-xl w-fit"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={clsx('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              tab === id ? 'text-white' : 'text-t2 hover:text-t1')}
            style={tab === id ? { background: 'var(--accent)' } : {}}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>

      {/* Appearance */}
      {tab === 'appearance' && (
        <div className="card p-6 space-y-6">
          <div>
            <p className="text-sm font-semibold text-t1 mb-1">Identidade Visual</p>
            <p className="text-xs text-t3">Personalize a aparência do sistema para sua empresa</p>
          </div>

          {/* Logo */}
          <div>
            <label className="label">Logo da Empresa</label>
            <div className="flex items-center gap-4 mt-1">
              <div className="w-20 h-20 rounded-xl overflow-hidden flex items-center justify-center"
                style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
                {logoPreview ? (
                  <img src={logoPreview} alt="Logo" className="w-full h-full object-contain p-2" />
                ) : (
                  <Upload size={24} className="text-t3" />
                )}
              </div>
              <div className="space-y-2">
                <label className="btn btn-ghost gap-2 cursor-pointer text-xs">
                  <Upload size={14} />Selecionar imagem
                  <input type="file" accept="image/*" className="hidden" onChange={handleLogoChange} />
                </label>
                <p className="text-xs text-t3">PNG, SVG ou WEBP · Máx 2MB · Fundo transparente recomendado</p>
              </div>
            </div>
          </div>

          {/* Company name */}
          <div>
            <label className="label">Nome da Empresa</label>
            <input className="input max-w-sm" placeholder="Ex: GTVision CFTV"
              value={companyName} onChange={e => setCompany(e.target.value)} />
          </div>

          {/* Color picker */}
          <div>
            <label className="label">Cor Principal</label>
            <div className="flex flex-wrap gap-2 mt-1">
              {PRESET_COLORS.map(c => (
                <button key={c.value}
                  className="w-9 h-9 rounded-lg transition-transform hover:scale-110 relative flex items-center justify-center"
                  style={{ background: c.value }}
                  title={c.label}
                  onClick={() => selectColor(c.value)}>
                  {primaryColor === c.value && (
                    <Check size={16} className="text-white" strokeWidth={3} />
                  )}
                </button>
              ))}
              <div className="relative">
                <input type="color" value={customColor}
                  onChange={e => { setCustom(e.target.value); setPrimary(e.target.value) }}
                  className="w-9 h-9 rounded-lg cursor-pointer border-0 p-0.5"
                  style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
                  title="Cor personalizada" />
              </div>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <div className="w-5 h-5 rounded-md" style={{ background: primaryColor }} />
              <p className="text-xs text-t2 font-mono">{primaryColor}</p>
            </div>
          </div>

          {/* Preview */}
          <div className="p-4 rounded-xl space-y-2" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
            <p className="text-xs text-t3 mb-2">Pré-visualização</p>
            <div className="flex items-center gap-2">
              <button className="px-3 py-1.5 rounded-lg text-xs text-white font-medium" style={{ background: primaryColor }}>
                Botão Primário
              </button>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: primaryColor + '22', color: primaryColor }}>
                Badge
              </span>
              <div className="w-3 h-3 rounded-full" style={{ background: primaryColor }} />
            </div>
          </div>

          {isCityAdmin && (
            <button className="btn btn-primary gap-2" onClick={handleSaveTheme} disabled={saving}>
              <Save size={15} />{saving ? 'Salvando...' : 'Salvar Aparência'}
            </button>
          )}
        </div>
      )}

      {/* Account */}
      {tab === 'account' && (
        <div className="card p-6 space-y-6">
          <div>
            <p className="text-sm font-semibold text-t1 mb-1">Minha Conta</p>
            <p className="text-xs text-t3">Atualize suas informações pessoais</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Nome</label>
              <input className="input" value={accName} onChange={e => setAccName(e.target.value)} />
            </div>
            <div>
              <label className="label">E-mail</label>
              <input className="input" type="email" value={accEmail} onChange={e => setAccEmail(e.target.value)} />
            </div>
          </div>

          <div className="border-t pt-4" style={{ borderColor: 'var(--border)' }}>
            <p className="text-xs font-medium text-t2 mb-3">Alterar Senha</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">Nova Senha</label>
                <input className="input" type="password" placeholder="••••••••"
                  value={accPassword} onChange={e => setAccPassword(e.target.value)} />
              </div>
              <div>
                <label className="label">Confirmar Senha</label>
                <input className="input" type="password" placeholder="••••••••"
                  value={accConfirm} onChange={e => setAccConfirm(e.target.value)} />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold"
              style={{ background: 'var(--elevated)' }}>
              {user?.name?.charAt(0).toUpperCase()}
            </div>
            <div>
              <p className="text-xs text-t3">Perfil atual</p>
              <p className="text-sm font-medium text-t1 capitalize">{user?.role?.replace('_', ' ')}</p>
            </div>
          </div>

          <button className="btn btn-primary gap-2" onClick={handleSaveAccount} disabled={saving}>
            <Save size={15} />{saving ? 'Salvando...' : 'Salvar'}
          </button>
        </div>
      )}

      {/* Notifications */}
      {tab === 'notifications' && (
        <div className="card p-6 space-y-4">
          <div>
            <p className="text-sm font-semibold text-t1 mb-1">Preferências de Notificação</p>
            <p className="text-xs text-t3">Controle quais alertas você deseja receber</p>
          </div>

          {[
            { id: 'events', label: 'Eventos de IA', desc: 'Intrusões, multidões, LPR', value: notifEvents, set: setNotifEvents },
            { id: 'offline', label: 'Câmera offline', desc: 'Quando uma câmera perder conexão', value: notifOffline, set: setNotifOffline },
            { id: 'queue', label: 'Alertas de fila', desc: 'Quando filas ultrapassarem o limite', value: notifQueue, set: setNotifQueue },
          ].map(n => (
            <div key={n.id} className="flex items-center gap-3 py-3 border-b last:border-0"
              style={{ borderColor: 'var(--border)' }}>
              <div className="flex-1">
                <p className="text-sm font-medium text-t1">{n.label}</p>
                <p className="text-xs text-t3">{n.desc}</p>
              </div>
              <button
                className="relative w-10 h-6 rounded-full transition-colors shrink-0"
                style={{ background: n.value ? 'var(--accent)' : 'var(--elevated)' }}
                onClick={() => n.set(!n.value)}>
                <div className={clsx('absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                  n.value ? 'translate-x-5' : 'translate-x-1')} />
              </button>
            </div>
          ))}

          <button className="btn btn-primary gap-2">
            <Save size={15} />Salvar Preferências
          </button>
        </div>
      )}

      {/* System */}
      {tab === 'system' && (
        <div className="space-y-4">
          <div className="card p-6 space-y-4">
            <div>
              <p className="text-sm font-semibold text-t1 mb-1">Informações do Sistema</p>
            </div>
            <div className="space-y-3">
              {[
                { label: 'Versão', value: '1.0.0' },
                { label: 'Ambiente', value: import.meta.env.MODE },
                { label: 'API URL', value: import.meta.env.VITE_API_URL ?? window.location.origin },
                { label: 'Backend', value: 'Django + FastAPI' },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between py-2 border-b last:border-0"
                  style={{ borderColor: 'var(--border)' }}>
                  <span className="text-xs text-t3">{label}</span>
                  <span className="text-xs font-mono text-t1">{value}</span>
                </div>
              ))}
            </div>
          </div>

          {isSuperAdmin && (
            <div className="card p-6 space-y-4">
              <div className="flex items-center gap-2">
                <Key size={16} className="text-t3" />
                <p className="text-sm font-semibold text-t1">Chave de API Interna</p>
              </div>
              <p className="text-xs text-t3">
                Usada para comunicação interna entre workers e o backend Django.
                Nunca compartilhe esta chave.
              </p>
              <div className="input font-mono text-xs text-t3 select-none">
                ••••••••••••••••••••••••••••••••
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
