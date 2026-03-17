import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus, Search, WifiOff, Trash2, ExternalLink, AlertTriangle,
  Wifi, Bot, Radio,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Spinner } from '@/components/ui/Spinner'
import { Modal } from '@/components/ui/Modal'
import { CameraWizard } from '@/components/camera/CameraWizard'
import { useCameras } from '@/hooks/useCameras'
import type { Camera } from '@/types'

const MANUFACTURER_LABELS: Record<string, string> = {
  hikvision: 'Hikvision',
  intelbras: 'Intelbras',
  dahua: 'Dahua',
  other: 'Outro',
}

export function CamerasPage() {
  const navigate = useNavigate()
  const { cameras, loading, refresh, remove } = useCameras()

  const [search, setSearch]             = useState('')
  const [wizardOpen, setWizardOpen]     = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Camera | null>(null)

  const filtered = cameras.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.location.toLowerCase().includes(search.toLowerCase()),
  )

  const online  = cameras.filter(c => c.is_online).length
  const offline = cameras.length - online

  const handleCreated = (camera: Camera) => {
    refresh()
    navigate(`/cameras/${camera.id}`)
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    await remove(deleteTarget.id, deleteTarget.name)
    setDeleteTarget(null)
  }

  if (loading) {
    return <div className="flex items-center justify-center py-32"><Spinner size="lg" /></div>
  }

  return (
    <div className="space-y-4 animate-fade-in">

      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative w-64">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-t3 pointer-events-none" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input pl-8 h-9 text-xs"
            placeholder="Buscar câmera ou local..."
          />
        </div>

        {/* Counters */}
        <div className="flex items-center gap-3">
          <Stat color="var(--success)" label="online"  value={online}  />
          <Stat color="var(--text-3)"  label="offline" value={offline} />
        </div>

        <button
          onClick={() => setWizardOpen(true)}
          className="btn btn-primary h-9 text-xs ml-auto"
        >
          <Plus size={15} /> Adicionar câmera
        </button>
      </div>

      {/* ── List ────────────────────────────────────────────────────────── */}
      {filtered.length === 0 ? (
        <EmptyState hasSearch={!!search} onAdd={() => setWizardOpen(true)} />
      ) : (
        <div className="card overflow-hidden divide-y" style={{ borderColor: 'var(--border)' }}>
          {filtered.map(camera => (
            <CameraRow
              key={camera.id}
              camera={camera}
              onView={() => navigate(`/cameras/${camera.id}`)}
              onDelete={() => setDeleteTarget(camera)}
            />
          ))}
        </div>
      )}

      {/* ── Wizard ──────────────────────────────────────────────────────── */}
      <CameraWizard
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onCreated={handleCreated}
      />

      {/* ── Delete modal ────────────────────────────────────────────────── */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Remover câmera"
        size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setDeleteTarget(null)}>Cancelar</button>
            <button className="btn btn-danger" onClick={handleDelete}>Remover</button>
          </>
        }
      >
        <div className="flex gap-3 items-start">
          <AlertTriangle size={20} className="shrink-0 mt-0.5" style={{ color: 'var(--danger)' }} />
          <div>
            <p className="text-sm text-t1">
              Remover <span className="font-semibold">"{deleteTarget?.name}"</span>?
            </p>
            <p className="text-xs text-t2 mt-1 leading-relaxed">
              O stream será interrompido e as gravações removidas conforme a política de retenção.
              Esta ação não pode ser desfeita.
            </p>
          </div>
        </div>
      </Modal>
    </div>
  )
}

// ─── CameraRow ────────────────────────────────────────────────────────────────

function CameraRow({ camera, onView, onDelete }: {
  camera: Camera
  onView: () => void
  onDelete: () => void
}) {
  return (
    <div
      className="flex items-center gap-4 px-4 py-3.5 hover:bg-elevated transition-colors cursor-pointer group"
      onClick={onView}
    >
      {/* Status indicator */}
      <div className="shrink-0 flex flex-col items-center gap-1">
        <div className="relative">
          <div className={clsx(
            'w-2.5 h-2.5 rounded-full',
            camera.is_online ? 'bg-success' : 'bg-t3',
          )} />
          {camera.is_online && (
            <div className="absolute inset-0 rounded-full bg-success animate-ping opacity-30" />
          )}
        </div>
      </div>

      {/* Name + location — takes all available space */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-t1 truncate leading-tight">{camera.name}</p>
        <p className="text-xs text-t2 truncate mt-0.5">{camera.location}</p>
      </div>

      {/* Metadata chips — fixed area, won't shrink below content */}
      <div className="flex items-center gap-2 shrink-0">
        <Chip>{MANUFACTURER_LABELS[camera.manufacturer] ?? camera.manufacturer}</Chip>
        <Chip>{camera.retention_days}d</Chip>
        <ConnectionIcon camera={camera} />
      </div>

      {/* Actions — always visible, not hidden on hover */}
      <div
        className="flex items-center gap-1 shrink-0"
        onClick={e => e.stopPropagation()}
      >
        <button
          onClick={onView}
          className="w-8 h-8 flex items-center justify-center rounded-lg text-t3 hover:text-accent hover:bg-accent/10 transition-colors"
          title="Ver detalhes"
        >
          <ExternalLink size={14} />
        </button>
        <button
          onClick={onDelete}
          className="w-8 h-8 flex items-center justify-center rounded-lg text-t3 hover:text-danger hover:bg-danger/10 transition-colors"
          title="Remover"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}

// ─── Small components ─────────────────────────────────────────────────────────

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-md text-xs text-t2 font-medium whitespace-nowrap"
      style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
    >
      {children}
    </span>
  )
}

function ConnectionIcon({ camera }: { camera: Camera }) {
  if (camera.agent) {
    return (
      <span title="Via Agent">
        <Bot size={14} className="text-t3" />
      </span>
    )
  }
  if (camera.rtsp_url) {
    return (
      <span title="RTSP direto">
        <Wifi size={14} className="text-t3" />
      </span>
    )
  }
  return (
    <span title="RTMP push">
      <Radio size={14} className="text-t3" />
    </span>
  )
}

function Stat({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
      <span className="text-xs text-t2">
        <span className="font-medium text-t1">{value}</span> {label}
      </span>
    </div>
  )
}

function EmptyState({ hasSearch, onAdd }: { hasSearch: boolean; onAdd: () => void }) {
  if (hasSearch) {
    return (
      <div className="text-center py-20 animate-fade-in">
        <Search size={28} className="mx-auto mb-2 text-t3" />
        <p className="text-sm text-t2">Nenhuma câmera encontrada</p>
        <p className="text-xs text-t3 mt-1">Tente outro termo de busca</p>
      </div>
    )
  }
  return (
    <div className="card flex flex-col items-center py-20 gap-4 animate-fade-in">
      <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
        <WifiOff size={24} className="text-t3" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-t1">Nenhuma câmera cadastrada</p>
        <p className="text-xs text-t3 mt-1">Adicione sua primeira câmera para começar</p>
      </div>
      <button onClick={onAdd} className="btn btn-primary">
        <Plus size={15} /> Adicionar câmera
      </button>
    </div>
  )
}
