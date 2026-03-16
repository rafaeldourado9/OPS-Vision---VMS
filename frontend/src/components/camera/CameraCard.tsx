import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play, Settings, Wifi, WifiOff, Brain } from 'lucide-react'
import { clsx } from 'clsx'
import { Badge } from '@/components/ui/Badge'
import type { Camera } from '@/types'

interface CameraCardProps {
  camera: Camera
  thumbnail?: string
}

export function CameraCard({ camera, thumbnail }: CameraCardProps) {
  const navigate = useNavigate()
  const [imgError, setImgError] = useState(false)

  return (
    <div
      className="card overflow-hidden cursor-pointer group transition-all hover:border-accent/50"
      onClick={() => navigate(`/cameras/${camera.id}`)}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-black">
        {thumbnail && !imgError ? (
          <img
            src={`data:image/jpeg;base64,${thumbnail}`}
            alt={camera.name}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <WifiOff size={24} className="text-zinc-700" />
          </div>
        )}

        {/* Status dot */}
        <div className={clsx(
          'absolute top-2 right-2 w-2 h-2 rounded-full shadow-lg',
          camera.online ? 'bg-green-500' : 'bg-red-500',
        )} />

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
          <button
            className="w-9 h-9 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center text-white hover:bg-white/20 transition"
            onClick={(e) => { e.stopPropagation(); navigate(`/cameras/${camera.id}`) }}
          >
            <Play size={16} />
          </button>
          <button
            className="w-9 h-9 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center text-white hover:bg-white/20 transition"
            onClick={(e) => { e.stopPropagation(); navigate(`/cameras/${camera.id}/roi`) }}
          >
            <Settings size={16} />
          </button>
        </div>
      </div>

      {/* Info */}
      <div className="px-3 py-2.5">
        <p className="text-sm font-medium text-t1 truncate">{camera.name}</p>
        <p className="text-xs text-t3 truncate mt-0.5">{camera.address}</p>
        <div className="flex items-center gap-2 mt-2">
          <Badge variant={camera.online ? 'success' : 'danger'} dot>
            {camera.online ? 'Online' : 'Offline'}
          </Badge>
          {camera.ia_enabled && (
            <Badge variant="info">
              <Brain size={10} />
              IA
            </Badge>
          )}
          <span className="text-xs text-t3 ml-auto uppercase">{camera.stream_protocol}</span>
        </div>
      </div>
    </div>
  )
}
