import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Wifi, Bot, Radio, ChevronRight, ChevronLeft, Check, Copy, ArrowRight } from 'lucide-react'
import { clsx } from 'clsx'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui/Spinner'
import { cameraService, agentService } from '@/services/api'
import type { Agent, Camera, PushConfig } from '@/types'
import toast from 'react-hot-toast'

// ─── Schema ───────────────────────────────────────────────────────────────────

const schema = z.object({
  connection_type: z.enum(['rtsp', 'agent', 'rtmp']),
  name:            z.string().min(2, 'Mínimo 2 caracteres'),
  location:        z.string().min(2, 'Mínimo 2 caracteres'),
  manufacturer:    z.enum(['hikvision', 'intelbras', 'dahua', 'other']),
  retention_days:  z.coerce.number(),
  rtsp_url:        z.string().optional(),
  agent:           z.string().optional(),
})

type FormData = z.infer<typeof schema>

// ─── Steps ────────────────────────────────────────────────────────────────────
// RTMP mode has 5 steps (adds "Credenciais" after "Revisar")
// Other modes have 4 steps

const BASE_STEPS    = ['Tipo', 'Informações', 'Conexão', 'Revisar']
const RTMP_STEPS    = ['Tipo', 'Informações', 'Conexão', 'Revisar', 'Credenciais']

// ─── Props ────────────────────────────────────────────────────────────────────

interface Props {
  open: boolean
  onClose: () => void
  onCreated: (camera: Camera) => void
}

// ─── Component ────────────────────────────────────────────────────────────────

export function CameraWizard({ open, onClose, onCreated }: Props) {
  const [step, setStep]             = useState(0)
  const [agents, setAgents]         = useState<Agent[]>([])
  const [saving, setSaving]         = useState(false)
  const [createdCamera, setCreatedCamera] = useState<Camera | null>(null)
  const [pushConfig, setPushConfig] = useState<PushConfig | null>(null)

  const { register, handleSubmit, watch, setValue, trigger, reset, formState: { errors } } =
    useForm<FormData>({
      resolver: zodResolver(schema),
      defaultValues: { connection_type: 'rtsp', manufacturer: 'other', retention_days: 7 },
    })

  const connectionType = watch('connection_type')
  const values         = watch()
  const steps          = connectionType === 'rtmp' ? RTMP_STEPS : BASE_STEPS
  const isLastStep     = step === steps.length - 1

  useEffect(() => {
    if (connectionType === 'agent' && agents.length === 0) {
      agentService.list({ page_size: 100 })
        .then(r => setAgents(r.results.filter(a => a.status === 'online')))
        .catch(() => {})
    }
  }, [connectionType])

  const handleClose = () => {
    if (createdCamera) {
      onCreated(createdCamera)
    }
    reset()
    setStep(0)
    setCreatedCamera(null)
    setPushConfig(null)
    onClose()
  }

  // ── Navigation ──────────────────────────────────────────────────────────────

  const STEP_FIELDS: (keyof FormData)[][] = [
    ['connection_type'],
    ['name', 'location', 'manufacturer', 'retention_days'],
    connectionType === 'rtsp' ? ['rtsp_url'] : connectionType === 'agent' ? ['agent'] : [],
    [], // review — no fields to validate
    [], // credentials — read only
  ]

  const next = async () => {
    const valid = await trigger(STEP_FIELDS[step])
    if (valid) setStep(s => s + 1)
  }

  const back = () => setStep(s => s - 1)

  // ── Submit (step 3 → Review confirmed) ─────────────────────────────────────

  const onSubmit = async (data: FormData) => {
    setSaving(true)
    try {
      const payload: Record<string, unknown> = {
        name:           data.name,
        location:       data.location,
        manufacturer:   data.manufacturer,
        retention_days: data.retention_days,
        rtsp_url:       data.rtsp_url ?? '',
        agent:          data.agent ?? undefined,
      }
      const camera = await cameraService.create(payload)
      setCreatedCamera(camera)

      if (data.connection_type === 'rtmp') {
        const config = await cameraService.pushConfig(String(camera.id))
        setPushConfig(config)
        setStep(4) // go to credentials step
      } else {
        toast.success(`"${camera.name}" criada com sucesso`)
        onCreated(camera)
        handleClose()
      }
    } catch (err: any) {
      const msg = err?.response?.data
        ? Object.values(err.response.data).flat().join(' ')
        : 'Erro ao criar câmera'
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  // ── Footer buttons ──────────────────────────────────────────────────────────

  const footer = (
    <div className="flex items-center justify-between w-full">
      {/* Left: back / cancel */}
      {step === steps.length - 1 && connectionType === 'rtmp' ? (
        // Credentials step: only "Ir para câmera"
        <div />
      ) : (
        <button
          type="button"
          onClick={step === 0 ? handleClose : back}
          className="btn btn-ghost"
          disabled={saving}
        >
          {step === 0 ? 'Cancelar' : <><ChevronLeft size={16} />Voltar</>}
        </button>
      )}

      {/* Right: next / submit / go to camera */}
      {step < steps.length - 1 && step < 3 ? (
        <button type="button" onClick={next} className="btn btn-primary">
          Próximo <ChevronRight size={16} />
        </button>
      ) : step === 3 ? (
        <button
          type="button"
          onClick={handleSubmit(onSubmit)}
          className="btn btn-primary"
          disabled={saving}
        >
          {saving ? <Spinner size="sm" /> : <><Check size={16} />Criar câmera</>}
        </button>
      ) : (
        // Step 4: credentials
        <button type="button" onClick={handleClose} className="btn btn-primary">
          Ir para câmera <ArrowRight size={16} />
        </button>
      )}
    </div>
  )

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Adicionar câmera"
      size="lg"
      footer={footer}
    >
      {/* Step indicator */}
      <StepIndicator steps={steps} current={step} />

      {/* Step content */}
      <div className="animate-fade-in">
        {step === 0 && <StepTipo connectionType={connectionType} setValue={setValue} />}
        {step === 1 && <StepInfo register={register} errors={errors} />}
        {step === 2 && (
          connectionType === 'rtsp'
            ? <StepRTSP register={register} errors={errors} />
            : connectionType === 'agent'
            ? <StepAgent agents={agents} value={values.agent} setValue={setValue} error={errors.agent?.message} />
            : <StepRTMPInfo />
        )}
        {step === 3 && <StepReview values={values} agents={agents} />}
        {step === 4 && pushConfig && createdCamera && (
          <StepCredentials config={pushConfig} cameraName={createdCamera.name} />
        )}
      </div>
    </Modal>
  )
}

// ─── Step indicator ───────────────────────────────────────────────────────────

function StepIndicator({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="flex items-center mb-6">
      {steps.map((label, i) => (
        <div key={label} className="flex items-center flex-1 last:flex-none">
          <div className="flex flex-col items-center gap-1">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-all"
              style={{
                background: i < current ? 'var(--success)' : i === current ? 'var(--accent)' : 'var(--elevated)',
                border: `1px solid ${i > current ? 'var(--border)' : 'transparent'}`,
                color: i > current ? 'var(--text-3)' : '#fff',
              }}
            >
              {i < current ? <Check size={13} /> : i + 1}
            </div>
            <span className={clsx('text-xs', i === current ? 'text-t1' : 'text-t3')}>{label}</span>
          </div>
          {i < steps.length - 1 && (
            <div className="flex-1 h-px mx-2 mb-4" style={{
              background: i < current ? 'var(--success)' : 'var(--border)',
            }} />
          )}
        </div>
      ))}
    </div>
  )
}

// ─── Step 1 — Tipo ────────────────────────────────────────────────────────────

const CONNECTION_TYPES = [
  {
    value: 'rtsp' as const,
    icon: Wifi,
    title: 'RTSP direto',
    desc: 'O MediaMTX puxa o stream pela URL RTSP. A câmera precisa estar acessível pela rede do servidor.',
  },
  {
    value: 'rtmp' as const,
    icon: Radio,
    title: 'RTMP push (câmera/app)',
    desc: 'A câmera ou aplicativo envia o stream via RTMP. Você receberá a URL e a chave de stream para configurar.',
  },
  {
    value: 'agent' as const,
    icon: Bot,
    title: 'Via Agent',
    desc: 'Um Agent instalado na rede local captura o RTSP e envia via RTMP. Ideal para câmeras atrás de firewall.',
  },
]

function StepTipo({ connectionType, setValue }: {
  connectionType: string
  setValue: (k: 'connection_type', v: FormData['connection_type']) => void
}) {
  return (
    <div className="space-y-2.5">
      <p className="text-xs text-t2 mb-4">Como este VMS vai receber o stream desta câmera?</p>
      {CONNECTION_TYPES.map(({ value, icon: Icon, title, desc }) => {
        const active = connectionType === value
        return (
          <button
            key={value}
            type="button"
            onClick={() => setValue('connection_type', value)}
            className={clsx(
              'w-full text-left p-4 rounded-xl border transition-all flex gap-4 items-start',
              active ? 'border-accent bg-accent/5' : 'border-border hover:border-t3 bg-elevated',
            )}
          >
            <div className={clsx(
              'w-9 h-9 rounded-lg flex items-center justify-center shrink-0 mt-0.5',
              active ? 'bg-accent/20' : 'bg-surface',
            )}>
              <Icon size={18} style={{ color: active ? 'var(--accent)' : 'var(--text-2)' }} />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-t1">{title}</p>
              <p className="text-xs text-t2 mt-0.5 leading-relaxed">{desc}</p>
            </div>
            <div className={clsx(
              'w-4 h-4 rounded-full border-2 mt-1 shrink-0',
              active ? 'border-accent bg-accent' : 'border-border',
            )} />
          </button>
        )
      })}
    </div>
  )
}

// ─── Step 2 — Informações ─────────────────────────────────────────────────────

function StepInfo({ register, errors }: { register: any; errors: any }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="col-span-2">
        <label className="label">Nome da câmera *</label>
        <input {...register('name')} className="input" placeholder="Ex: Portaria Principal" />
        {errors.name && <p className="text-xs text-danger mt-1">{errors.name.message}</p>}
      </div>
      <div className="col-span-2">
        <label className="label">Localização *</label>
        <input {...register('location')} className="input" placeholder="Ex: Entrada Bloco A, 1º andar" />
        {errors.location && <p className="text-xs text-danger mt-1">{errors.location.message}</p>}
      </div>
      <div>
        <label className="label">Fabricante</label>
        <select {...register('manufacturer')} className="input">
          <option value="hikvision">Hikvision</option>
          <option value="intelbras">Intelbras</option>
          <option value="dahua">Dahua</option>
          <option value="other">Outro</option>
        </select>
      </div>
      <div>
        <label className="label">Retenção de gravações</label>
        <select {...register('retention_days', { valueAsNumber: true })} className="input">
          <option value={7}>7 dias</option>
          <option value={15}>15 dias</option>
          <option value={30}>30 dias</option>
        </select>
      </div>
    </div>
  )
}

// ─── Step 3a — RTSP ───────────────────────────────────────────────────────────

function StepRTSP({ register, errors }: { register: any; errors: any }) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-t2">Insira a URL RTSP. O MediaMTX vai conectar diretamente a este endereço.</p>
      <div>
        <label className="label">URL RTSP *</label>
        <input
          {...register('rtsp_url')}
          className="input font-mono text-xs"
          placeholder="rtsp://usuario:senha@192.168.1.100:554/stream1"
        />
        {errors.rtsp_url && <p className="text-xs text-danger mt-1">{errors.rtsp_url.message}</p>}
      </div>
      <div className="p-3 rounded-lg text-xs text-t2 leading-relaxed"
        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
        💡 Formato típico Hikvision: <span className="text-t1 font-mono">rtsp://admin:senha@IP:554/Streaming/Channels/101</span>
      </div>
    </div>
  )
}

// ─── Step 3b — RTMP info ──────────────────────────────────────────────────────

function StepRTMPInfo() {
  return (
    <div className="space-y-4">
      <p className="text-xs text-t2">
        Após criar a câmera, você receberá a <strong className="text-t1">URL do servidor RTMP</strong> e a{' '}
        <strong className="text-t1">chave de stream</strong> para configurar no seu aplicativo ou câmera IP.
      </p>
      <div className="space-y-2">
        {[
          { label: 'Servidor RTMP', example: 'rtmp://vms.exemplo.com:1935' },
          { label: 'Chave de stream', example: 'tenant-1/cam-5' },
        ].map(({ label, example }) => (
          <div key={label} className="flex items-center gap-3 p-3 rounded-lg"
            style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
            <div>
              <p className="text-xs font-medium text-t2">{label}</p>
              <p className="text-xs font-mono text-t3 mt-0.5">{example}</p>
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-t3">
        Compatível com Hikvision, Intelbras, Dahua, OBS, FFmpeg e qualquer app com suporte a RTMP push.
      </p>
    </div>
  )
}

// ─── Step 3c — Agent ──────────────────────────────────────────────────────────

function StepAgent({ agents, value, setValue, error }: {
  agents: Agent[]
  value: string | undefined
  setValue: (k: 'agent', v: string) => void
  error: string | undefined
}) {
  if (agents.length === 0) {
    return (
      <div className="text-center py-8 text-t2">
        <Bot size={32} className="mx-auto mb-2 text-t3" />
        <p className="text-sm">Nenhum Agent online</p>
        <p className="text-xs text-t3 mt-1">Acesse Agentes → Novo agent para instalar um na rede local.</p>
      </div>
    )
  }
  return (
    <div className="space-y-3">
      <p className="text-xs text-t2">Selecione o Agent que irá capturar o stream desta câmera.</p>
      {agents.map(agent => (
        <button key={agent.id} type="button" onClick={() => setValue('agent', agent.id)}
          className={clsx(
            'w-full text-left p-3 rounded-lg border transition-all flex items-center gap-3',
            value === agent.id ? 'border-accent bg-accent/5' : 'border-border hover:border-t3 bg-elevated',
          )}
        >
          <div className="w-2 h-2 rounded-full bg-success shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-t1">{agent.name}</p>
            {agent.version && <p className="text-xs text-t3">v{agent.version}</p>}
          </div>
          <div className={clsx(
            'w-4 h-4 rounded-full border-2 shrink-0',
            value === agent.id ? 'border-accent bg-accent' : 'border-border',
          )} />
        </button>
      ))}
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  )
}

// ─── Step 4 — Revisar ─────────────────────────────────────────────────────────

const MANUFACTURER_LABELS: Record<string, string> = {
  hikvision: 'Hikvision', intelbras: 'Intelbras', dahua: 'Dahua', other: 'Outro',
}

const CONNECTION_LABELS: Record<string, string> = {
  rtsp: 'RTSP direto', rtmp: 'RTMP push', agent: 'Via Agent',
}

function StepReview({ values, agents }: { values: Partial<FormData>; agents: Agent[] }) {
  const agentName = values.agent
    ? agents.find(a => a.id === values.agent)?.name ?? values.agent
    : null

  const rows = [
    { label: 'Tipo de conexão', value: CONNECTION_LABELS[values.connection_type ?? ''] },
    { label: 'Nome',            value: values.name },
    { label: 'Localização',     value: values.location },
    { label: 'Fabricante',      value: MANUFACTURER_LABELS[values.manufacturer ?? ''] },
    { label: 'Retenção',        value: `${values.retention_days} dias` },
    ...(values.connection_type === 'rtsp'  ? [{ label: 'URL RTSP', value: values.rtsp_url }] : []),
    ...(values.connection_type === 'agent' ? [{ label: 'Agent',    value: agentName }]       : []),
    ...(values.connection_type === 'rtmp'  ? [{ label: 'Stream',   value: 'Gerado após criação' }] : []),
  ]

  return (
    <div className="space-y-0">
      <p className="text-xs text-t2 mb-4">Confira os dados antes de criar a câmera.</p>
      {rows.map(({ label, value }) => (
        <div key={label} className="flex items-start justify-between py-2.5 border-b last:border-0"
          style={{ borderColor: 'var(--border)' }}>
          <span className="text-xs text-t2">{label}</span>
          <span className="text-xs text-t1 text-right max-w-[60%] break-all font-mono">{value ?? '—'}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Step 5 — Credenciais RTMP ────────────────────────────────────────────────

function CopyField({ label, value }: { label: string; value: string }) {
  const copy = () => {
    navigator.clipboard.writeText(value)
    toast.success(`${label} copiado`)
  }
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex gap-2">
        <input readOnly value={value} className="input font-mono text-xs flex-1" />
        <button type="button" onClick={copy}
          className="btn btn-ghost h-9 px-3 shrink-0"
          title="Copiar">
          <Copy size={14} />
        </button>
      </div>
    </div>
  )
}

function StepCredentials({ config, cameraName }: { config: PushConfig; cameraName: string }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 p-3 rounded-lg bg-success/15 border border-success/30 rounded-lg">
        <Check size={16} className="shrink-0" style={{ color: 'var(--success)' }} />
        <p className="text-xs font-medium" style={{ color: 'var(--success)' }}>
          "{cameraName}" criada com sucesso!
        </p>
      </div>

      <p className="text-xs text-t2">
        Configure estes valores no aplicativo, câmera IP ou software de streaming:
      </p>

      <CopyField label="Servidor RTMP" value={config.rtmp_url} />
      <CopyField label="Chave de stream (path)" value={config.stream_key} />
      <CopyField label="Usuário" value={config.username} />
      <CopyField label="Senha (token)" value={config.password} />

      <details className="group">
        <summary className="text-xs text-t3 cursor-pointer hover:text-t2 transition-colors select-none">
          URL completa com credenciais embutidas ▸
        </summary>
        <div className="mt-2">
          <CopyField label="" value={config.full_url} />
        </div>
      </details>

      <div className="p-3 rounded-lg text-xs text-t2 leading-relaxed"
        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
        💡 <strong className="text-t1">OBS:</strong> Transmissão → Personalizado → Servidor + Chave de Stream.<br />
        💡 <strong className="text-t1">Hikvision/Intelbras:</strong> Rede → RTMP → Server Address + Stream Key + autenticação.
      </div>
    </div>
  )
}
