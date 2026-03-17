import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Settings, Map, Brain, Wifi, WifiOff, Edit2, Save, X, Film, ShieldAlert } from 'lucide-react'
import { clsx } from 'clsx'
import { format } from 'date-fns'
import { cameraService, roiService, detectionService, clipService } from '@/services/api'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { usePermission } from '@/hooks/usePermission'
import toast from 'react-hot-toast'
import type { Camera, ROI, Detection, Clip } from '@/types'

type Tab = 'live' | 'info' | 'rois' | 'events' | 'clips'

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'live',   label: 'Ao Vivo',   icon: Wifi },
  { id: 'info',   label: 'Informações', icon: Settings },
  { id: 'rois',   label: 'ROIs',      icon: Map },
  { id: 'events', label: 'Eventos',   icon: ShieldAlert },
  { id: 'clips',  label: 'Clips',     icon: Film },
]

const EVENT_LABELS: Record<string, string> = {
  lpr: 'Placa LPR', crowd: 'Multidão', intrusion: 'Intrusão',
  object_detected: 'Objeto', vehicle_traffic: 'Veículo', human_traffic: 'Pessoa',
  line_crossing: 'Cruzamento', loitering: 'Perambulação', abandoned_object: 'Abandonado',
  queue_alert: 'Fila', facial_match: 'Facial', facial_unknown: 'Desconhecido',
}

export function CameraDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { isCityAdmin } = usePermission()

  const [tab, setTab]           = useState<Tab>('live')
  const [camera, setCamera]     = useState<Camera | null>(null)
  const [streamUrl, setStream]  = useState('')
  const [rois, setRois]         = useState<ROI[]>([])
  const [detections, setDets]   = useState<Detection[]>([])
  const [clips, setClips]       = useState<Clip[]>([])
  const [loading, setLoading]   = useState(true)
  const [editing, setEditing]   = useState(false)
  const [editForm, setEditForm] = useState<Partial<Camera>>({})

  useEffect(() => {
    if (!id) return
    Promise.all([
      cameraService.get(id),
      cameraService.streamUrl(id).catch(() => ({ hls: '' })),
    ]).then(([cam, stream]) => {
      setCamera(cam)
      setEditForm(cam)
      setStream(stream.hls ?? '')
    }).finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!id || tab === 'live' || tab === 'info') return
    if (tab === 'rois') roiService.list({ camera_id: id }).then(r => setRois(r.results))
    if (tab === 'events') detectionService.list({ camera_id: id, page_size: 20 }).then(r => setDets(r.results))
    if (tab === 'clips') clipService.list({ camera: id }).then(r => setClips(r.results))
  }, [id, tab])

  const handleSave = async () => {
    if (!id || !camera) return
    try {
      const updated = await cameraService.update(id, editForm)
      setCamera(updated)
      setEditing(false)
      toast.success('Câmera atualizada')
    } catch { toast.error('Erro ao salvar') }
  }

  const toggleROI = async (roi: ROI) => {
    try {
      await roiService.update(roi.id, { enabled: !roi.enabled })
      setRois(prev => prev.map(r => r.id === roi.id ? { ...r, enabled: !r.enabled } : r))
    } catch { toast.error('Erro ao atualizar ROI') }
  }

  if (loading) return <PageSpinner />
  if (!camera) return <div className="text-t3 text-center py-16">Câmera não encontrada</div>

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button className="btn btn-ghost w-8 h-8 p-0" onClick={() => navigate('/cameras')}>
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-base font-semibold text-t1 truncate">{camera.name}</p>
            <Badge variant={camera.online ? 'success' : 'danger'} dot>
              {camera.online ? 'Online' : 'Offline'}
            </Badge>
            {camera.ia_enabled && <Badge variant="info"><Brain size={10} />IA Ativa</Badge>}
          </div>
          <p className="text-xs text-t3 truncate">{camera.address}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 p-1 rounded-xl w-fit"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
        {TABS.map(({ id: tid, label, icon: Icon }) => (
          <button key={tid} onClick={() => setTab(tid)}
            className={clsx('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              tab === tid ? 'text-white' : 'text-t2 hover:text-t1')}
            style={tab === tid ? { background: 'var(--accent)' } : {}}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>

      {/* Live */}
      {tab === 'live' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <VideoPlayer src={streamUrl} cameraName={camera.name} className="aspect-video w-full" />
          </div>
          <div className="space-y-3">
            <div className="card p-4 space-y-3">
              <p className="text-xs font-semibold text-t2 uppercase tracking-wide">Status</p>
              <div className="space-y-2">
                {[
                  { label: 'Protocolo', value: camera.stream_protocol?.toUpperCase() },
                  { label: 'Retenção', value: `${camera.retention_days} dias` },
                  { label: 'IA', value: camera.ia_enabled ? 'Ativa' : 'Desativada' },
                  { label: 'Resolução', value: camera.resolution ?? '—' },
                  { label: 'FPS', value: camera.fps ? `${camera.fps}fps` : '—' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between">
                    <span className="text-xs text-t3">{label}</span>
                    <span className="text-xs text-t1 font-medium">{value}</span>
                  </div>
                ))}
              </div>
            </div>
            <button className="btn btn-primary w-full gap-2" onClick={() => navigate(`/cameras/${id}/roi`)}>
              <Map size={15} />Editor de ROI
            </button>
          </div>
        </div>
      )}

      {/* Info */}
      {tab === 'info' && (
        <div className="card p-6 max-w-2xl">
          <div className="flex items-center justify-between mb-6">
            <p className="text-sm font-semibold text-t1">Informações da Câmera</p>
            {isCityAdmin && !editing && (
              <button className="btn btn-ghost gap-2 text-xs" onClick={() => setEditing(true)}>
                <Edit2 size={14} />Editar
              </button>
            )}
            {editing && (
              <div className="flex gap-2">
                <button className="btn btn-ghost text-xs gap-1" onClick={() => { setEditing(false); setEditForm(camera) }}>
                  <X size={14} />Cancelar
                </button>
                <button className="btn btn-primary text-xs gap-1" onClick={handleSave}>
                  <Save size={14} />Salvar
                </button>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { label: 'Nome', field: 'name', type: 'text' },
              { label: 'Endereço / Localização', field: 'address', type: 'text' },
              { label: 'URL do Stream', field: 'stream_url', type: 'text' },
              { label: 'Protocolo', field: 'stream_protocol', type: 'select', options: ['rtsp', 'rtmp', 'hls'] },
              { label: 'Retenção (dias)', field: 'retention_days', type: 'number' },
              { label: 'Latitude', field: 'lat', type: 'number' },
              { label: 'Longitude', field: 'lng', type: 'number' },
            ].map(({ label, field, type, options }) => (
              <div key={field}>
                <label className="label">{label}</label>
                {editing ? (
                  type === 'select' ? (
                    <select className="input" value={(editForm as any)[field] ?? ''}
                      onChange={e => setEditForm(f => ({ ...f, [field]: e.target.value }))}>
                      {options!.map(o => <option key={o} value={o}>{o.toUpperCase()}</option>)}
                    </select>
                  ) : (
                    <input className="input" type={type}
                      value={(editForm as any)[field] ?? ''}
                      onChange={e => setEditForm(f => ({ ...f, [field]: type === 'number' ? Number(e.target.value) : e.target.value }))} />
                  )
                ) : (
                  <p className="text-sm text-t1 mt-1">{(camera as any)[field] ?? '—'}</p>
                )}
              </div>
            ))}
          </div>

          {editing && (
            <div className="mt-4 flex items-center gap-3">
              <label className="label mb-0">IA Habilitada</label>
              <button
                className={clsx('relative w-10 h-6 rounded-full transition-colors shrink-0',
                  editForm.ia_enabled ? 'bg-accent' : 'bg-elevated')}
                style={editForm.ia_enabled ? { background: 'var(--accent)' } : {}}
                onClick={() => setEditForm(f => ({ ...f, ia_enabled: !f.ia_enabled }))}>
                <div className={clsx('absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                  editForm.ia_enabled ? 'translate-x-5' : 'translate-x-1')} />
              </button>
            </div>
          )}
        </div>
      )}

      {/* ROIs */}
      {tab === 'rois' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-t3">{rois.length} ROIs configuradas</p>
            <button className="btn btn-primary gap-2" onClick={() => navigate(`/cameras/${id}/roi`)}>
              <Map size={15} />Abrir Editor de ROI
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {rois.map(roi => (
              <div key={roi.id} className="card p-4 flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-t1">{roi.name}</p>
                  <p className="text-xs text-t3">{roi.ia_type}</p>
                  <p className="text-xs text-t3">{roi.polygon_points?.length ?? 0} pontos</p>
                </div>
                <button
                  className={clsx('relative w-10 h-6 rounded-full transition-colors shrink-0',
                    roi.enabled ? '' : 'bg-elevated')}
                  style={roi.enabled ? { background: 'var(--accent)' } : {}}
                  onClick={() => toggleROI(roi)}>
                  <div className={clsx('absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                    roi.enabled ? 'translate-x-5' : 'translate-x-1')} />
                </button>
              </div>
            ))}
            {rois.length === 0 && (
              <div className="col-span-full card p-16 text-center">
                <Map size={32} className="text-t3 mx-auto mb-3" />
                <p className="text-t3 text-sm">Nenhuma ROI configurada</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Events */}
      {tab === 'events' && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
                {['Evento', 'Confiança', 'Data/Hora'].map(h => (
                  <th key={h} className="px-4 py-3 text-xs font-medium text-t3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {detections.map(d => (
                <tr key={d.id} className="border-b hover:bg-elevated transition"
                  style={{ borderColor: 'var(--border)' }}>
                  <td className="px-4 py-3">
                    <Badge variant="info">{EVENT_LABELS[d.event_type] ?? d.event_type}</Badge>
                  </td>
                  <td className="px-4 py-3 text-t2 text-xs">{Math.round(d.confidence * 100)}%</td>
                  <td className="px-4 py-3 text-t3 text-xs">{format(new Date(d.detected_at), 'dd/MM/yy HH:mm:ss')}</td>
                </tr>
              ))}
              {detections.length === 0 && (
                <tr><td colSpan={3} className="px-4 py-12 text-center text-t3 text-sm">Nenhum evento recente</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Clips */}
      {tab === 'clips' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {clips.map(clip => (
            <div key={clip.id} className="card overflow-hidden">
              <div className="aspect-video bg-black flex items-center justify-center">
                {clip.file_url ? (
                  <VideoPlayer src={clip.file_url} cameraName={clip.name} className="w-full h-full" />
                ) : (
                  <Film size={24} className="text-t3" />
                )}
              </div>
              <div className="p-3">
                <p className="text-sm font-medium text-t1 truncate">{clip.name}</p>
                <p className="text-xs text-t3">{format(new Date(clip.created_at), 'dd/MM/yyyy HH:mm')}</p>
                <Badge variant={clip.status === 'ready' ? 'success' : clip.status === 'error' ? 'danger' : 'warning'}
                  className="mt-2">
                  {clip.status}
                </Badge>
              </div>
            </div>
          ))}
          {clips.length === 0 && (
            <div className="col-span-full card p-16 text-center">
              <Film size={32} className="text-t3 mx-auto mb-3" />
              <p className="text-t3 text-sm">Nenhum clip criado</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
