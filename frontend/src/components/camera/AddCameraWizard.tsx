import { useState } from 'react'
import { CheckCircle2, Wifi, Radio, Monitor, ChevronRight, ChevronLeft, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { Modal } from '@/components/ui/Modal'
import { cameraService } from '@/services/api'
import toast from 'react-hot-toast'
import type { Manufacturer } from '@/types'

interface WizardProps {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

interface FormData {
  manufacturer: Manufacturer | ''
  rtsp_url: string
  ip: string
  port: string
  username: string
  password: string
  name: string
  location: string
  retention_days: 7 | 15 | 30
}

const STEPS = ['Protocolo', 'Conexão', 'Configuração']

export function AddCameraWizard({ open, onClose, onCreated }: WizardProps) {
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState<FormData>({
    manufacturer: '', rtsp_url: '', ip: '', port: '554',
    username: '', password: '', name: '', location: '',
    retention_days: 7,
  })

  const update = (patch: Partial<FormData>) => setForm(f => ({ ...f, ...patch }))

  const buildRtspUrl = () => {
    const auth = form.username ? `${form.username}:${form.password}@` : ''
    return form.rtsp_url || `rtsp://${auth}${form.ip}:${form.port}/stream`
  }

  const canNext = () => {
    if (step === 0) return !!form.manufacturer
    if (step === 1) return !!(form.rtsp_url || form.ip)
    if (step === 2) return !!(form.name && form.location)
    return true
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await cameraService.create({
        name: form.name,
        location: form.location,
        rtsp_url: buildRtspUrl(),
        manufacturer: form.manufacturer as Manufacturer,
        retention_days: form.retention_days,
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
          {step < STEPS.length - 1 ? (
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

      {/* Step 0 — Fabricante */}
      {step === 0 && (
        <div className="grid grid-cols-2 gap-3">
          {[
            { mfr: 'hikvision', icon: Wifi,    label: 'Hikvision',  desc: 'Câmeras Hikvision' },
            { mfr: 'intelbras', icon: Monitor, label: 'Intelbras',  desc: 'Câmeras Intelbras' },
            { mfr: 'dahua',     icon: Radio,   label: 'Dahua',      desc: 'Câmeras Dahua' },
            { mfr: 'other',     icon: Monitor, label: 'Outro',      desc: 'Outro fabricante' },
          ].map(({ mfr, icon: Icon, label, desc }) => (
            <button
              key={mfr}
              onClick={() => update({ manufacturer: mfr as Manufacturer })}
              className={clsx(
                'flex flex-col items-center gap-2 rounded-xl p-5 border-2 transition-all text-center',
                form.manufacturer === mfr
                  ? 'border-transparent'
                  : 'border-border hover:border-elevated hover:bg-elevated',
              )}
              style={form.manufacturer === mfr ? { borderColor: 'var(--accent)', background: 'rgba(59,130,246,0.08)' } : {}}
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
          <div>
            <label className="label">URL RTSP Completa (opcional)</label>
            <input className="input" placeholder="rtsp://usuario:senha@192.168.1.100:554/stream"
              value={form.rtsp_url} onChange={e => update({ rtsp_url: e.target.value })} />
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
          <div className="p-3 rounded-lg text-xs text-t2" style={{ background: 'var(--elevated)' }}>
            URL gerada: <code className="text-accent">{buildRtspUrl() || '—'}</code>
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
            <label className="label">Localização *</label>
            <input className="input" placeholder="Ex: Rua das Flores, 123 — Bloco A"
              value={form.location} onChange={e => update({ location: e.target.value })} />
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
    </Modal>
  )
}
