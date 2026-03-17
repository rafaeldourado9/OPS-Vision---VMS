import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Wifi, WifiOff, Brain, Layers, RefreshCw } from 'lucide-react'
import { GoogleMap, useJsApiLoader, Marker, InfoWindow } from '@react-google-maps/api'
import { clsx } from 'clsx'
import { cameraService } from '@/services/api'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import type { Camera } from '@/types'

const GOOGLE_MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY ?? import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? ''

const MAP_STYLE_DARK: google.maps.MapTypeStyle[] = [
  { elementType: 'geometry', stylers: [{ color: '#1a1a24' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#111118' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#746855' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#252530' }] },
  { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#212a37' }] },
  { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#9ca5b3' }] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#746855' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#17263c' }] },
  { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#515c6d' }] },
  { featureType: 'poi', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', stylers: [{ visibility: 'off' }] },
]

const createMarkerIcon = (online: boolean, iaEnabled: boolean): google.maps.Symbol => ({
  path: google.maps.SymbolPath.CIRCLE,
  scale: 10,
  fillColor: online ? (iaEnabled ? '#3B82F6' : '#22C55E') : '#EF4444',
  fillOpacity: 1,
  strokeColor: '#ffffff',
  strokeWeight: 2,
})

type FilterStatus = 'all' | 'online' | 'offline' | 'ia'

export function MapPage() {
  const navigate = useNavigate()
  const [cameras, setCameras]       = useState<Camera[]>([])
  const [loading, setLoading]       = useState(true)
  const [selected, setSelected]     = useState<Camera | null>(null)
  const [filter, setFilter]         = useState<FilterStatus>('all')
  const [mapRef, setMapRef]         = useState<google.maps.Map | null>(null)
  const [center, setCenter]         = useState({ lat: -14.235, lng: -51.925 }) // Brazil center

  const { isLoaded } = useJsApiLoader({
    googleMapsApiKey: GOOGLE_MAPS_KEY,
    libraries: ['places'],
  })

  const loadCameras = useCallback(() => {
    setLoading(true)
    cameraService.list({ page_size: 500 })
      .then(r => {
        setCameras(r.results)
        // Center map on cameras centroid
        const withCoords = r.results.filter((c: Camera) => c.lat && c.lng)
        if (withCoords.length > 0) {
          const avgLat = withCoords.reduce((s: number, c: Camera) => s + (c.lat ?? 0), 0) / withCoords.length
          const avgLng = withCoords.reduce((s: number, c: Camera) => s + (c.lng ?? 0), 0) / withCoords.length
          setCenter({ lat: avgLat, lng: avgLng })
        }
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadCameras() }, [loadCameras])

  const filtered = cameras.filter(c => {
    if (filter === 'online') return c.online
    if (filter === 'offline') return !c.online
    if (filter === 'ia') return c.ia_enabled
    return true
  }).filter(c => c.lat && c.lng)

  const withoutCoords = cameras.filter(c => !c.lat || !c.lng)

  if (!GOOGLE_MAPS_KEY) {
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="card p-8 text-center space-y-3">
          <Layers size={40} className="text-t3 mx-auto" />
          <p className="text-t2 font-medium">Google Maps não configurado</p>
          <p className="text-xs text-t3">Defina <code className="text-accent">VITE_GOOGLE_MAPS_KEY</code> no .env do frontend para habilitar o mapa tático.</p>
        </div>
        <CameraListFallback cameras={cameras} navigate={navigate} />
      </div>
    )
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 p-1 rounded-lg"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
          {([
            { id: 'all', label: `Todas (${cameras.length})` },
            { id: 'online', label: `Online (${cameras.filter(c => c.online).length})` },
            { id: 'offline', label: `Offline (${cameras.filter(c => !c.online).length})` },
            { id: 'ia', label: `Com IA (${cameras.filter(c => c.ia_enabled).length})` },
          ] as { id: FilterStatus; label: string }[]).map(f => (
            <button key={f.id} onClick={() => setFilter(f.id)}
              className={clsx('px-3 py-1 rounded-md text-xs font-medium transition',
                filter === f.id ? 'text-white' : 'text-t2 hover:text-t1')}
              style={filter === f.id ? { background: 'var(--accent)' } : {}}>
              {f.label}
            </button>
          ))}
        </div>
        <button className="btn btn-ghost gap-2 ml-auto" onClick={loadCameras}>
          <RefreshCw size={14} />Atualizar
        </button>
      </div>

      {/* Map */}
      <div className="card overflow-hidden" style={{ height: '65vh' }}>
        {!isLoaded || loading ? (
          <div className="h-full flex items-center justify-center">
            <PageSpinner />
          </div>
        ) : (
          <GoogleMap
            mapContainerStyle={{ width: '100%', height: '100%' }}
            center={center}
            zoom={filtered.length > 0 ? 12 : 5}
            options={{
              styles: MAP_STYLE_DARK,
              disableDefaultUI: false,
              zoomControl: true,
              mapTypeControl: false,
              streetViewControl: false,
              fullscreenControl: true,
            }}
            onLoad={map => setMapRef(map)}>

            {filtered.map(cam => (
              <Marker
                key={cam.id}
                position={{ lat: cam.lat!, lng: cam.lng! }}
                icon={createMarkerIcon(cam.online, cam.ia_enabled)}
                onClick={() => setSelected(cam)}
                title={cam.name}
              />
            ))}

            {selected && selected.lat && selected.lng && (
              <InfoWindow
                position={{ lat: selected.lat, lng: selected.lng }}
                onCloseClick={() => setSelected(null)}>
                <div style={{ background: '#111118', color: '#e2e8f0', borderRadius: 8, padding: 12, minWidth: 200 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%',
                      background: selected.online ? '#22C55E' : '#EF4444'
                    }} />
                    <strong style={{ fontSize: 13 }}>{selected.name}</strong>
                  </div>
                  <p style={{ fontSize: 11, color: '#94a3b8', marginBottom: 6 }}>{selected.address}</p>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{
                      fontSize: 10, padding: '2px 6px', borderRadius: 4,
                      background: selected.online ? '#166534' : '#7f1d1d',
                      color: selected.online ? '#4ade80' : '#f87171'
                    }}>
                      {selected.online ? 'Online' : 'Offline'}
                    </span>
                    {selected.ia_enabled && (
                      <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: '#1e3a5f', color: '#60a5fa' }}>
                        IA Ativa
                      </span>
                    )}
                    <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: '#1a1a24', color: '#94a3b8' }}>
                      {selected.stream_protocol?.toUpperCase()}
                    </span>
                  </div>
                  <button
                    style={{
                      marginTop: 10, width: '100%', padding: '6px 12px', borderRadius: 6,
                      background: '#3B82F6', color: '#fff', fontSize: 12, border: 'none', cursor: 'pointer'
                    }}
                    onClick={() => navigate(`/cameras/${selected.id}`)}>
                    Ver Câmera →
                  </button>
                </div>
              </InfoWindow>
            )}
          </GoogleMap>
        )}
      </div>

      {/* Cameras without coords warning */}
      {withoutCoords.length > 0 && (
        <div className="card p-4">
          <p className="text-xs text-t3 mb-3">
            {withoutCoords.length} câmera(s) sem coordenadas GPS — não exibidas no mapa
          </p>
          <div className="flex flex-wrap gap-2">
            {withoutCoords.map(c => (
              <button key={c.id}
                className="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs transition hover:bg-elevated"
                style={{ border: '1px solid var(--border)' }}
                onClick={() => navigate(`/cameras/${c.id}`)}>
                <div className={clsx('w-1.5 h-1.5 rounded-full', c.online ? 'bg-green-500' : 'bg-red-500')} />
                {c.name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function CameraListFallback({ cameras, navigate }: { cameras: Camera[]; navigate: (p: string) => void }) {
  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <p className="text-sm font-semibold text-t1">Câmeras cadastradas</p>
      </div>
      <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
        {cameras.map(cam => (
          <div key={cam.id}
            className="flex items-center gap-3 px-4 py-3 hover:bg-elevated transition cursor-pointer"
            onClick={() => navigate(`/cameras/${cam.id}`)}>
            <div className={clsx('w-2 h-2 rounded-full shrink-0', cam.online ? 'bg-green-500' : 'bg-red-500')} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-t1">{cam.name}</p>
              <p className="text-xs text-t3">{cam.address || (cam.lat && cam.lng ? `${cam.lat}, ${cam.lng}` : 'Sem localização')}</p>
            </div>
            <Badge variant={cam.online ? 'success' : 'danger'}>{cam.online ? 'Online' : 'Offline'}</Badge>
          </div>
        ))}
      </div>
    </div>
  )
}
