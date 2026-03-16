import { useEffect, useState, useCallback } from 'react'
import { Plus, LayoutGrid, Maximize2 } from 'lucide-react'
import { clsx } from 'clsx'
import { cameraService } from '@/services/api'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import type { Camera, StreamUrl } from '@/types'

type Layout = '1x1' | '2x2' | '3x3' | '4x4' | '1+3' | '2+4'

const LAYOUTS: { id: Layout; label: string; slots: number }[] = [
  { id: '1x1', label: '1×1', slots: 1 },
  { id: '2x2', label: '2×2', slots: 4 },
  { id: '3x3', label: '3×3', slots: 9 },
  { id: '4x4', label: '4×4', slots: 16 },
  { id: '1+3', label: '1+3', slots: 4 },
  { id: '2+4', label: '2+4', slots: 6 },
]

interface Slot { cameraId: string | null; streamUrl: string | null }

const makeSlots = (n: number): Slot[] => Array.from({ length: n }, () => ({ cameraId: null, streamUrl: null }))

export function MosaicPage() {
  const [layout, setLayout]   = useState<Layout>('2x2')
  const [cameras, setCameras] = useState<Camera[]>([])
  const [slots, setSlots]     = useState<Slot[]>(makeSlots(4))
  const [streams, setStreams]  = useState<Record<string, string>>({})

  useEffect(() => {
    cameraService.list({ page_size: 100 }).then(r => setCameras(r.results))
  }, [])

  const changeLayout = (l: Layout) => {
    setLayout(l)
    const n = LAYOUTS.find(x => x.id === l)!.slots
    setSlots(makeSlots(n))
  }

  const assignCamera = async (slotIdx: number, camId: string) => {
    const cam = cameras.find(c => c.id === camId)
    if (!cam) return

    let url = streams[camId]
    if (!url) {
      try {
        const s: StreamUrl = await cameraService.streamUrl(camId)
        url = s.hls || ''
        setStreams(prev => ({ ...prev, [camId]: url }))
      } catch { url = '' }
    }

    setSlots(prev => prev.map((s, i) => i === slotIdx ? { cameraId: camId, streamUrl: url } : s))
  }

  const gridClass = {
    '1x1': 'grid-cols-1',
    '2x2': 'grid-cols-2',
    '3x3': 'grid-cols-3',
    '4x4': 'grid-cols-4',
    '1+3': 'grid-cols-2',
    '2+4': 'grid-cols-3',
  }[layout]

  const renderSlot = (slot: Slot, idx: number, big = false) => {
    const cam = cameras.find(c => c.id === slot.cameraId)
    return (
      <div key={idx} className={clsx('relative rounded-lg overflow-hidden bg-black group', big ? 'row-span-2 col-span-2' : '')}>
        {slot.streamUrl ? (
          <VideoPlayer src={slot.streamUrl} cameraName={cam?.name} className="w-full h-full" />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center gap-3 min-h-[180px]">
            <Plus size={22} className="text-zinc-700" />
            <select
              className="text-xs text-t2 bg-elevated border border-border rounded-lg px-3 py-1.5 cursor-pointer max-w-[160px]"
              value=""
              onChange={e => assignCamera(idx, e.target.value)}
            >
              <option value="" disabled>Selecionar câmera</option>
              {cameras.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
        )}
        {slot.cameraId && (
          <button
            className="absolute top-2 right-2 w-7 h-7 rounded-md bg-black/60 text-white opacity-0 group-hover:opacity-100 transition flex items-center justify-center"
            onClick={() => setSlots(prev => prev.map((s, i) => i === idx ? { cameraId: null, streamUrl: null } : s))}
          >
            ×
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col gap-3 animate-fade-in">
      {/* Toolbar */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-1 p-1 rounded-lg" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
          {LAYOUTS.map(l => (
            <button key={l.id} onClick={() => changeLayout(l.id)}
              className={clsx('px-3 py-1 rounded-md text-xs font-medium transition',
                layout === l.id ? 'text-white' : 'text-t2 hover:text-t1')}
              style={layout === l.id ? { background: 'var(--accent)' } : {}}>
              {l.label}
            </button>
          ))}
        </div>
        <button className="btn btn-ghost ml-auto" onClick={() => document.documentElement.requestFullscreen?.()}>
          <Maximize2 size={15} />Tela Cheia
        </button>
      </div>

      {/* Mosaic grid */}
      <div className={clsx('flex-1 grid gap-2 min-h-0', gridClass)}>
        {layout === '1+3' ? (
          <>
            {renderSlot(slots[0], 0, true)}
            {slots.slice(1).map((s, i) => renderSlot(s, i + 1))}
          </>
        ) : layout === '2+4' ? (
          <>
            {renderSlot(slots[0], 0, true)}
            {renderSlot(slots[1], 1, true)}
            {slots.slice(2).map((s, i) => renderSlot(s, i + 2))}
          </>
        ) : (
          slots.map((s, i) => renderSlot(s, i))
        )}
      </div>
    </div>
  )
}
