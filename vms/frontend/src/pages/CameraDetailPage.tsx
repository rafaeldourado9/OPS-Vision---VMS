import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Wifi, WifiOff } from 'lucide-react'
import VideoPlayer from '../components/VideoPlayer'
import api from '../lib/api'
import type { Camera } from '../stores/cameraStore'

interface LiveData {
  camera_id: number
  is_online: boolean
  hls_url: string
  webrtc_url: string
}

export default function CameraDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [camera, setCamera] = useState<Camera | null>(null)
  const [live, setLive] = useState<LiveData | null>(null)

  useEffect(() => {
    if (!id) return
    api.get(`/cameras/${id}/`).then((r) => setCamera(r.data)).catch(() => {})
    api.get(`/cameras/${id}/live/`).then((r) => setLive(r.data)).catch(() => {})
  }, [id])

  if (!camera) return <p className="text-vms-muted">Carregando...</p>

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Link to="/cameras" className="text-vms-muted hover:text-white">
          <ArrowLeft size={20} />
        </Link>
        <div>
          <h1 className="text-xl font-bold">{camera.name}</h1>
          <p className="text-vms-muted text-sm">{camera.location}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {camera.is_online ? (
            <span className="flex items-center gap-1 text-vms-success text-sm"><Wifi size={14} /> Online</span>
          ) : (
            <span className="flex items-center gap-1 text-vms-danger text-sm"><WifiOff size={14} /> Offline</span>
          )}
        </div>
      </div>

      {/* Live player */}
      <div className="bg-vms-card rounded-xl overflow-hidden mb-6">
        {live?.hls_url ? (
          <div className="aspect-video">
            <VideoPlayer src={live.hls_url} />
          </div>
        ) : (
          <div className="aspect-video flex items-center justify-center text-vms-muted">
            Stream indisponível
          </div>
        )}
      </div>

      {/* Info grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Fabricante', value: camera.manufacturer },
          { label: 'Retenção', value: `${camera.retention_days} dias` },
          { label: 'RTSP', value: camera.rtsp_url ? '••••••' : 'N/A' },
          { label: 'ID', value: `#${camera.id}` },
        ].map((item) => (
          <div key={item.label} className="bg-vms-card rounded-xl p-4">
            <p className="text-vms-muted text-xs mb-1">{item.label}</p>
            <p className="text-sm font-medium truncate">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-3 mt-6">
        <Link
          to={`/recordings/${camera.id}/playback`}
          className="px-4 py-2 text-sm rounded-lg bg-vms-card hover:bg-vms-card-hover border border-vms-border transition-colors"
        >
          Ver Gravações
        </Link>
      </div>
    </div>
  )
}
