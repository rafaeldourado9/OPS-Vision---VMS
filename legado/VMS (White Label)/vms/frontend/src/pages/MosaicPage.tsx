import { useEffect, useState } from 'react'
import VideoPlayer from '../components/VideoPlayer'
import api from '../lib/api'
import { useCameraStore } from '../stores/cameraStore'

type GridSize = '2x2' | '3x3' | '4x4'

export default function MosaicPage() {
  const { cameras, fetchCameras } = useCameraStore()
  const [gridSize, setGridSize] = useState<GridSize>('2x2')
  const [liveUrls, setLiveUrls] = useState<Record<number, string>>({})
  const [selected, setSelected] = useState<number[]>([])

  useEffect(() => {
    fetchCameras()
  }, [])

  useEffect(() => {
    const maxCells = gridSize === '2x2' ? 4 : gridSize === '3x3' ? 9 : 16
    const cams = cameras.slice(0, maxCells)
    setSelected(cams.map((c) => c.id))

    // Fetch live URLs
    cams.forEach((cam) => {
      if (!liveUrls[cam.id]) {
        api.get(`/cameras/${cam.id}/live/`).then((r) => {
          setLiveUrls((prev) => ({ ...prev, [cam.id]: r.data.hls_url }))
        }).catch(() => {})
      }
    })
  }, [cameras, gridSize])

  const gridCols = gridSize === '2x2' ? 'grid-cols-2' : gridSize === '3x3' ? 'grid-cols-3' : 'grid-cols-4'

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Mosaico</h1>
        <div className="flex gap-2">
          {(['2x2', '3x3', '4x4'] as GridSize[]).map((size) => (
            <button
              key={size}
              onClick={() => setGridSize(size)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${gridSize === size ? 'bg-vms-accent text-white' : 'bg-vms-card text-vms-muted hover:text-white'}`}
            >
              {size}
            </button>
          ))}
        </div>
      </div>

      <div className={`grid ${gridCols} gap-2`}>
        {selected.map((camId) => {
          const cam = cameras.find((c) => c.id === camId)
          const url = liveUrls[camId]
          return (
            <div key={camId} className="bg-vms-card rounded-lg overflow-hidden relative">
              <div className="aspect-video">
                {url ? (
                  <VideoPlayer src={url} />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-vms-muted text-xs">
                    Sem stream
                  </div>
                )}
              </div>
              {cam && (
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                  <p className="text-xs font-medium truncate">{cam.name}</p>
                  <div className="flex items-center gap-1">
                    <div className={`w-1.5 h-1.5 rounded-full ${cam.is_online ? 'bg-vms-success' : 'bg-vms-danger'}`} />
                    <span className="text-[10px] text-vms-muted">{cam.location}</span>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
