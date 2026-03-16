import { useState } from 'react'
import { CheckCircle2, Wifi, Radio, Monitor, ChevronRight, ChevronLeft, Loader2, Brain } from 'lucide-react'
import { clsx } from 'clsx'
import { Modal } from '@/components/ui/Modal'
import { cameraService } from '@/services/api'
import toast from 'react-hot-toast'
import type { StreamProtocol } from '@/types'

const ANALYTICS_OPTIONS = [
  { id: 'lpr',              label: 'Reconhecimento de Placa',  desc: 'Detecta e lê placas veiculares' },
  { id: 'vehicle_traffic',  label: 'Tráfego de Veículos',      desc: 'Conta e classifica veículos' },
  { id: 'human_traffic',    label: 'Tráfego Humano',           desc: 'Conta pessoas em zonas' },
  { id: 'crowd',            label: 'Detecção de Multidões',    desc: 'Alerta aglomerações' },
  { id: 'facial',           label: 'Reconhecimento Facial',    desc: 'Identifica pessoas cadastradas' },
  { id: 'intrusion',        label: 'Intrusão',                 desc: 'Detecta objetos em zona proibida' },
  { id: 'object_detection', label: 'Detecção de Objetos',      desc: 'Pessoas, animais, bagagens' },
  { id: 'heatmap',          label: 'Mapa de Calor',            desc: 'Gera mapas de densidade' },
  { id: 'line_crossing',    label: 'Cruzamento de Linha',      desc: 'Contagem direcional' },
  { id: 'loitering',        label: 'Perambulação',             desc: 'Objeto parado por muito tempo' },
  { id: 'abandoned_object', label: 'Objeto Abandonado',        desc: 'Bagagem sem dono' },
  { id: 'queue',            label: 'Detecção de Fila',         desc: 'Monitora filas e tempo de espera' },
]

interface WizardProps {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

interface FormData {
  protocol: StreamProtocol | ''
  stream_url: string
  ip: string
  port: string
  username: string
  password: string
  name: string
  address: string
  latitude: string
  longitude: string
  retention_days: 7 | 15 | 30
  ia_enabled: boolean
  analytics: string[]
}

const STEPS = ['Protocolo', 'Conexão', 'Configuração', 'Analíticos']

export function AddCameraWizard({ open, onClose, onCreated }: WizardProps) {
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState<FormData>({
    protocol: '', stream_url: '', ip: '', port: '554',
    username: '', password: '', name: '', address: '',
    latitude: '', longitude: '', retention_days: 7,
    ia_enabled: false, analytics: [],
  })

  const update = (patch: Partial<FormData>) => setForm(f => ({ ...f, ...patch }))

  const buildStreamUrl = () => {
    if (form.protocol === 'rtsp') {
      const auth = form.username ? `${form.username}:${form.password}@` : ''
      return form.stream_url || `rtsp://${auth}${form.ip}:${form.port}/stream`
    }
    if (form.protocol === 'rtmp') return form.stream_url
    return form.stream_url
  }

  const canNext = () => {
    if (step === 0) return !!form.protocol
    if (step === 1) return !!(form.stream_url || form.ip)
    if (step === 2) return !!(form.name && form.address)
    return true
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await cameraService.create({
        name: form.name,
        address: form.address,
        lat: parseFloat(form.latitude) || 0,
        lng: parseFloat(form.longitude) || 0,
        stream_protocol: form.protocol as StreamProtocol,
        stream_url: buildStreamUrl(),
        retention_days: form.retention_days,
        ia_enabled: form.ia_enabled,
      })
      toast.success('Câmera adicionada com sucesso!')
      onCreated()
      onClose()
      setStep(0)
    } catch {
      toast.error('Erro ao adicionar câmera')
    } finally {
      setSaving(false)
    }
  }

  const toggleAnalytic = (id: string) => {
    update({ analytics: form.analytics.includes(id) ? form.analytics.filter(a => a !== id) : [...form.analytics, id] })
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Adicionar Câmera"
      size="lg"
      footer={
        <div className="flex items-center gap-2 w-full">
          <button className="btn btn-ghost" onClick={step === 0 ? onClose : () => setStep(s => s - 1)}>
            <ChevronLeft size={16} />{step === 0 ? 'Cancelar' : 'Voltar'}
          </button>
          <div className="flex-1 flex justify-center gap-1.5">
            {STEPS.map((_, i) => (
              <div key={i} className={clsx('h-1.5 rounded-full transition-all', i === step ? 'w-6' : 'w-1.5')}
                style={{ background: i <= step ? 'var(--accent)' : 'var(--border)' }} />
            ))}
          </div>
          {step < 3 ? (
            <button className="btn btn-primary" onClick={() => setStep(s => s + 1)} disabled={!canNext()}>
              Próximo<ChevronRight size={16} />
            </button>
          ) : (
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? <><Loader2 size={16} className="animate-spin" />Salvando...</> : <><CheckCircle2 size={16} />Concluir</>}
            </button>
          )}
        </div>
      }
    >
      {/* Step header */}
      <div className="mb-6">
        <p className="text-xs text-t3 uppercase tracking-wider font-medium">Passo {step + 1} de {STEPS.length}</p>
        <h3 className="text-base font-semibold text-t1 mt-0.5">{STEPS[step]}</h3>
      </div>

      {/* Step 0 — Protocolo */}
      {step === 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { proto: 'rtsp', icon: Wifi,    label: 'RTSP',  desc: 'IP Cameras, DVR/NVR' },
            { proto: 'rtmp', icon: Radio,   label: 'RTMP',  desc: 'Push stream' },
            { proto: 'rtsp', icon: Monitor, label: 'IP Cam', desc: 'Câmera IP local' },
          ].map(({ proto, icon: Icon, label, desc }, i) => (
            <button
              key={i}
              onClick={() => update({ protocol: proto as StreamProtocol })}
              className={clsx(
                'flex flex-col items-center gap-2 rounded-xl p-5 border-2 transition-all text-center',
                form.protocol === proto && i === 0 && label === 'RTSP' ? 'border-accent bg-accent/10' :
                form.protocol === proto && label === 'RTMP' ? 'border-accent bg-accent/10' :
                form.protocol === proto ? 'border-accent bg-accent/10' : 'border-border hover:border-elevated hover:bg-elevated',
              )}
              style={form.protocol === proto ? { borderColor: 'var(--accent)' } : {}}
            >
              <Icon size={28} className="text-t2" />
              <div>
                <p className="text-sm font-semibold text-t1">{label}</p>
                <p className="text-xs text-t3">{desc}</p>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Step 1 — Conexão */}
      {step === 1 && (
        <div className="space-y-4">
          {form.protocol === 'rtsp' && (
            <>
              <div>
                <label className="label">URL Completa (opcional)</label>
                <input className="input" placeholder="rtsp://usuario:senha@192.168.1.100:554/stream"
                  value={form.stream_url} onChange={e => update({ stream_url: e.target.value })} />
                <p className="text-xs text-t3 mt-1">Ou preencha os campos abaixo</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Endereço IP</label>
                  <input className="input" placeholder="192.168.1.100"
                    value={form.ip} onChange={e => update({ ip: e.target.value })} />
                </div>
                <div>
                  <label className="label">Porta</label>
                  <input className="input" placeholder="554"
                    value={form.port} onChange={e => update({ port: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Usuário</label>
                  <input className="input" placeholder="admin"
                    value={form.username} onChange={e => update({ username: e.target.value })} />
                </div>
                <div>
                  <label className="label">Senha</label>
                  <input type="password" className="input" placeholder="••••••"
                    value={form.password} onChange={e => update({ password: e.target.value })} />
                </div>
              </div>
            </>
          )}
          {form.protocol === 'rtmp' && (
            <div>
              <label className="label">URL do Stream</label>
              <input className="input" placeholder="rtmp://servidor/live/stream-key"
                value={form.stream_url} onChange={e => update({ stream_url: e.target.value })} />
            </div>
          )}
          <div className="p-3 rounded-lg text-xs text-t2" style={{ background: 'var(--elevated)' }}>
            URL gerada: <code className="text-accent">{buildStreamUrl() || '—'}</code>
          </div>
        </div>
      )}

      {/* Step 2 — Configuração */}
      {step === 2 && (
        <div className="space-y-4">
          <div>
            <label className="label">Nome da Câmera *</label>
            <input className="input" placeholder="Ex: Entrada Principal"
              value={form.name} onChange={e => update({ name: e.target.value })} />
          </div>
          <div>
            <label className="label">Localização / Endereço *</label>
            <input className="input" placeholder="Ex: Rua das Flores, 123"
              value={form.address} onChange={e => update({ address: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Latitude</label>
              <input className="input" placeholder="-23.5505"
                value={form.latitude} onChange={e => update({ latitude: e.target.value })} />
            </div>
            <div>
              <label className="label">Longitude</label>
              <input className="input" placeholder="-46.6333"
                value={form.longitude} onChange={e => update({ longitude: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="label">Retenção de Gravação</label>
            <div className="flex gap-2">
              {([7, 15, 30] as const).map(d => (
                <button key={d} onClick={() => update({ retention_days: d })}
                  className={clsx('flex-1 py-2 rounded-lg text-sm font-medium border transition-all',
                    form.retention_days === d ? 'text-white border-transparent' : 'text-t2 border-border hover:border-elevated')}
                  style={form.retention_days === d ? { background: 'var(--accent)', borderColor: 'transparent' } : {}}>
                  {d} dias
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Step 3 — Analíticos */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3 rounded-lg border"
            style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-2">
              <Brain size={18} style={{ color: 'var(--accent)' }} />
              <div>
                <p className="text-sm font-medium text-t1">Habilitar IA</p>
                <p className="text-xs text-t3">Ativa o processamento de analíticos</p>
              </div>
            </div>
            <button
              onClick={() => update({ ia_enabled: !form.ia_enabled })}
              className={clsx('w-11 h-6 rounded-full transition-colors relative', form.ia_enabled ? '' : 'bg-elevated')}
              style={form.ia_enabled ? { background: 'var(--accent)' } : {}}
            >
              <span className={clsx('absolute top-1 w-4 h-4 rounded-full bg-white transition-all shadow-sm',
                form.ia_enabled ? 'left-6' : 'left-1')} />
            </button>
          </div>

          {form.ia_enabled && (
            <div className="grid grid-cols-2 gap-2">
              {ANALYTICS_OPTIONS.map(opt => (
                <button
                  key={opt.id}
                  onClick={() => toggleAnalytic(opt.id)}
                  className={clsx(
                    'text-left p-3 rounded-lg border-2 transition-all',
                    form.analytics.includes(opt.id)
                      ? 'border-transparent text-t1'
                      : 'border-border text-t2 hover:border-elevated',
                  )}
                  style={form.analytics.includes(opt.id) ? { borderColor: 'var(--accent)', background: 'rgba(59,130,246,0.08)' } : {}}
                >
                  <p className="text-xs font-semibold">{opt.label}</p>
                  <p className="text-xs text-t3 mt-0.5">{opt.desc}</p>
                </button>
              ))}
            </div>
          )}
          {!form.ia_enabled && (
            <p className="text-sm text-t3 text-center py-4">
              Ative a IA para selecionar os analíticos disponíveis.
            </p>
          )}
        </div>
      )}
    </Modal>
  )
}
