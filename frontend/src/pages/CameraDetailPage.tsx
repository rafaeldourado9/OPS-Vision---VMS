import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft, PenLine, Trash2, AlertTriangle, MapPin,
  HardDrive, Cpu, Wifi, WifiOff, RefreshCw,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { PageSpinner } from '@/components/ui/Spinner'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import { cameraService, roiService } from '@/services/api'
import type { Camera, ROI, StreamInfo } from '@/types'
import toast from 'react-hot-toast'

const ROI_TYPE_LABELS: Record<string, string> = {
  vehicle_dwell:   'Permanência Veicular',
  intrusion:       'Intrusão',
  human_traffic:   'Tráfego Humano',
  vehicle_traffic: 'Tráfego Veicular',
  lpr:             'Leitura de Placa',
  facial:          'Reconhecimento Facial',
  crowd:           'Multidão',
  line_crossing:   'Cruzamento de Linha',
  loitering:       'Perambulação',
  queue:           'Fila',
  heatmap:         'Mapa de Calor',
}

const ROI_TYPE_COLORS: Record<string, string> = {
  vehicle_dwell:   '#F59E0B',
  intrusion:       '#EF4444',
  human_traffic:   '#3B82F6',
  vehicle_traffic: '#8B5CF6',
  lpr:             '#22C55E',
  facial:          '#EC4899',
}

const MANUFACTURER_LABELS: Record<string, string> = {
  hikvision: 'Hikvision', intelbras: 'Intelbras', dahua: 'Dahua', other: 'Outro',
}

export function CameraDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [camera, setCamera]   = useState<Camera | null>(null)
  const [stream, setStream]   = useState<StreamInfo | null>(null)
  const [rois, setRois]       = useState<ROI[]>([])
  const [loading, setLoading] = useState(true)
  const [deleteRoi, setDeleteRoi] = useState<ROI | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([
      cameraService.get(id),
      cameraService.live(id).catch(() => null),
      roiService.list({ camera: id }),
    ]).then(([cam, str, roiData]) => {
      setCamera(cam)
      setStream(str)
      setRois(roiData.results)
    }).catch(() => toast.error('Erro ao carregar câmera'))
      .finally(() => setLoading(false))
  }, [id, refreshKey])

  const handleDeleteRoi = async () => {
    if (!deleteRoi) return
    try {
      await roiService.delete(deleteRoi.id)
      setRois(prev => prev.filter(r => r.id !== deleteRoi.id))
      toast.success('ROI removida')
    } catch {
      toast.error('Erro ao remover ROI')
    } finally {
      setDeleteRoi(null)
    }
  }

  if (loading) return <PageSpinner />
  if (!camera) return (
    <div className="flex flex-col items-center justify-center py-32 gap-3">
      <WifiOff size={32} className="text-t3" />
      <p className="text-sm text-t2">Câmera não encontrada</p>
      <button onClick={() => navigate('/cameras')} className="btn btn-ghost text-xs">Voltar</button>
    </div>
  )

  return (
    <div className="space-y-4 animate-fade-in">

      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/cameras')} className="btn btn-ghost w-8 h-8 p-0">
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-sm font-semibold text-t1 truncate">{camera.name}</h1>
            <Badge variant={camera.is_online ? 'success' : 'danger'} dot>
              {camera.is_online ? 'Online' : 'Offline'}
            </Badge>
          </div>
          <p className="text-xs text-t3">{camera.location}</p>
        </div>
        <button onClick={() => setRefreshKey(k => k + 1)} className="btn btn-ghost w-8 h-8 p-0" title="Atualizar">
          <RefreshCw size={15} />
        </button>
        <button onClick={() => navigate(`/cameras/${id}/roi`)} className="btn btn-primary text-xs h-9">
          <PenLine size={14} /> Configurar ROIs
        </button>
      </div>

      {/* Body */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Player */}
        <div className="lg:col-span-2">
          <VideoPlayer
            src={stream?.hls_url}
            cameraName={camera.name}
            className="w-full aspect-video"
          />
        </div>

        {/* Sidebar */}
        <div className="space-y-3">

          {/* Info card */}
          <div className="card p-4 space-y-3">
            <p className="text-xs font-semibold text-t2 uppercase tracking-wide">Informações</p>
            <InfoRow icon={MapPin}    label="Localização" value={camera.location} />
            <InfoRow icon={Cpu}       label="Fabricante"  value={MANUFACTURER_LABELS[camera.manufacturer] ?? camera.manufacturer} />
            <InfoRow icon={HardDrive} label="Retenção"    value={`${camera.retention_days} dias`} />
            <InfoRow
              icon={camera.is_online ? Wifi : WifiOff}
              label="Status"
              value={camera.is_online ? 'Online' : 'Offline'}
              valueClass={camera.is_online ? 'text-success' : 'text-danger'}
            />
          </div>

          {/* ROIs card */}
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-t2 uppercase tracking-wide">Zonas de análise</p>
              <button onClick={() => navigate(`/cameras/${id}/roi`)} className="text-xs text-accent hover:underline">
                + Adicionar
              </button>
            </div>

            {rois.length === 0 ? (
              <div className="text-center py-5">
                <PenLine size={18} className="mx-auto text-t3 mb-2" />
                <p className="text-xs text-t3">Nenhuma ROI configurada</p>
                <button onClick={() => navigate(`/cameras/${id}/roi`)} className="btn btn-ghost text-xs mt-2 h-7">
                  Configurar agora
                </button>
              </div>
            ) : (
              <div className="space-y-1">
                {rois.map(roi => (
                  <div key={roi.id} className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-elevated transition-colors group">
                    <div className="w-2.5 h-2.5 rounded-sm shrink-0"
                      style={{ background: ROI_TYPE_COLORS[roi.ia_type] ?? 'var(--accent)' }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-t1 truncate">{roi.name}</p>
                      <p className="text-xs text-t3">{ROI_TYPE_LABELS[roi.ia_type] ?? roi.ia_type}</p>
                    </div>
                    <button
                      onClick={() => setDeleteRoi(roi)}
                      className="w-6 h-6 flex items-center justify-center text-t3 hover:text-danger rounded transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Delete ROI confirm */}
      <Modal
        open={!!deleteRoi}
        onClose={() => setDeleteRoi(null)}
        title="Remover ROI"
        size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setDeleteRoi(null)}>Cancelar</button>
            <button className="btn btn-danger" onClick={handleDeleteRoi}>Remover</button>
          </>
        }
      >
        <div className="flex gap-3 items-start">
          <AlertTriangle size={18} className="shrink-0 mt-0.5" style={{ color: 'var(--danger)' }} />
          <p className="text-sm text-t1">
            Remover a zona <span className="font-semibold">"{deleteRoi?.name}"</span>?
            O analytics associado será desativado.
          </p>
        </div>
      </Modal>
    </div>
  )
}

function InfoRow({ icon: Icon, label, value, valueClass }: {
  icon: React.ElementType; label: string; value: string; valueClass?: string
}) {
  return (
    <div className="flex items-center gap-2.5">
      <Icon size={13} className="text-t3 shrink-0" />
      <span className="text-xs text-t2 w-20 shrink-0">{label}</span>
      <span className={clsx('text-xs font-medium text-t1 truncate', valueClass)}>{value}</span>
    </div>
  )
}
