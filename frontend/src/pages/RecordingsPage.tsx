import { useEffect, useState, useRef } from 'react'
import { ChevronLeft, ChevronRight, Calendar, Scissors } from 'lucide-react'
import { format, addDays, subDays, startOfDay } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { cameraService, segmentService, clipService } from '@/services/api'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import { PageSpinner } from '@/components/ui/Spinner'
import { Modal } from '@/components/ui/Modal'
import toast from 'react-hot-toast'
import type { Camera, Segment } from '@/types'

// 24h em minutos = 1440
const MINUTES_IN_DAY = 1440

function minutesToTime(m: number) {
  const h = Math.floor(m / 60).toString().padStart(2, '0')
  const min = (m % 60).toString().padStart(2, '0')
  return `${h}:${min}`
}

export function RecordingsPage() {
  const [cameras, setCameras]     = useState<Camera[]>([])
  const [selCam, setSelCam]       = useState<Camera | null>(null)
  const [selDate, setSelDate]     = useState(new Date())
  const [segments, setSegments]   = useState<Segment[]>([])
  const [streamUrl, setStreamUrl] = useState<string>('')
  const [loading, setLoading]     = useState(false)
  const [clipModal, setClipModal] = useState(false)
  const [clipName, setClipName]   = useState('')
  const [clipRange, setClipRange] = useState<[number, number]>([0, 60])
  const timelineRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    cameraService.list({ page_size: 100 }).then(r => {
      setCameras(r.results)
      if (r.results.length > 0) setSelCam(r.results[0])
    })
  }, [])

  useEffect(() => {
    if (!selCam) return
    setLoading(true)
    const dateStr = format(selDate, 'yyyy-MM-dd')
    segmentService.list({ camera_id: selCam.id, date: dateStr, page_size: 200 })
      .then(r => setSegments(r.results))
      .finally(() => setLoading(false))

    cameraService.streamUrl(selCam.id)
      .then(s => setStreamUrl(s.hls || ''))
      .catch(() => setStreamUrl(''))
  }, [selCam, selDate])

  // Converte segment para minutos do dia
  const segToMinutes = (seg: Segment) => {
    const start = new Date(seg.started_at)
    return { start: start.getHours() * 60 + start.getMinutes(), dur: Math.ceil(seg.duration_seconds / 60) }
  }

  const handleTimelineClick = (e: React.MouseEvent) => {
    if (!timelineRef.current) return
    const rect = timelineRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const minutes = Math.floor((x / rect.width) * MINUTES_IN_DAY)
    setClipRange([Math.max(0, minutes - 5), Math.min(MINUTES_IN_DAY, minutes + 5)])
  }

  const handleCreateClip = async () => {
    if (!selCam || !clipName) return
    const base = startOfDay(selDate)
    const started = new Date(base.getTime() + clipRange[0] * 60000).toISOString()
    const ended   = new Date(base.getTime() + clipRange[1] * 60000).toISOString()
    try {
      await clipService.create({ camera: selCam.id, name: clipName, started_at: started, ended_at: ended })
      toast.success('Clip criado! Processando...')
      setClipModal(false)
      setClipName('')
    } catch { toast.error('Erro ao criar clip') }
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-3">
        <select className="input max-w-xs" value={selCam?.id ?? ''}
          onChange={e => setSelCam(cameras.find(c => c.id === e.target.value) ?? null)}>
          {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        <div className="flex items-center gap-1">
          <button className="btn btn-ghost w-8 h-8 p-0" onClick={() => setSelDate(d => subDays(d, 1))}>
            <ChevronLeft size={16} />
          </button>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
            <Calendar size={14} className="text-t3" />
            {format(selDate, "dd 'de' MMM, yyyy", { locale: ptBR })}
          </div>
          <button className="btn btn-ghost w-8 h-8 p-0" onClick={() => setSelDate(d => addDays(d, 1))}
            disabled={selDate >= new Date()}>
            <ChevronRight size={16} />
          </button>
        </div>
        <input type="date" className="input max-w-[160px]" value={format(selDate, 'yyyy-MM-dd')}
          onChange={e => setSelDate(new Date(e.target.value + 'T00:00:00'))} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Player */}
        <div className="lg:col-span-3 space-y-3">
          <VideoPlayer src={streamUrl} cameraName={selCam?.name} className="aspect-video w-full" />
          <button className="btn btn-primary w-full gap-2" onClick={() => setClipModal(true)}>
            <Scissors size={15} />Criar Clip do Período
          </button>
        </div>

        {/* Timeline + segments */}
        <div className="lg:col-span-2 card p-4 space-y-4">
          <div>
            <p className="text-sm font-semibold text-t1">Timeline — {format(selDate, 'dd/MM/yyyy')}</p>
            <p className="text-xs text-t3 mt-0.5">{segments.length} segmentos gravados</p>
          </div>

          {loading ? <PageSpinner /> : (
            <>
              {/* 24h bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-t3">
                  <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span>
                </div>
                <div
                  ref={timelineRef}
                  className="relative h-8 rounded-lg overflow-hidden cursor-crosshair"
                  style={{ background: 'var(--elevated)' }}
                  onClick={handleTimelineClick}
                >
                  {segments.map((seg, i) => {
                    const { start, dur } = segToMinutes(seg)
                    return (
                      <div key={i}
                        className="absolute top-0 h-full rounded-sm opacity-80"
                        style={{
                          left: `${(start / MINUTES_IN_DAY) * 100}%`,
                          width: `${(dur / MINUTES_IN_DAY) * 100}%`,
                          background: 'var(--accent)',
                        }}
                      />
                    )
                  })}
                  {/* Clip range highlight */}
                  <div className="absolute top-0 h-full opacity-40 pointer-events-none"
                    style={{
                      left: `${(clipRange[0] / MINUTES_IN_DAY) * 100}%`,
                      width: `${((clipRange[1] - clipRange[0]) / MINUTES_IN_DAY) * 100}%`,
                      background: '#F59E0B',
                    }}
                  />
                </div>
              </div>

              {/* Segments list */}
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {segments.length === 0 ? (
                  <p className="text-xs text-t3 text-center py-6">Nenhuma gravação neste dia</p>
                ) : segments.map((seg, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs hover:bg-elevated transition">
                    <div className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
                    <span className="text-t1 font-medium">
                      {format(new Date(seg.started_at), 'HH:mm')} — {format(new Date(seg.ended_at), 'HH:mm')}
                    </span>
                    <span className="text-t3 ml-auto">{Math.round(seg.duration_seconds / 60)}min</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Clip modal */}
      <Modal open={clipModal} onClose={() => setClipModal(false)} title="Criar Clip"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setClipModal(false)}>Cancelar</button>
            <button className="btn btn-primary" onClick={handleCreateClip} disabled={!clipName}>
              <Scissors size={15} />Criar Clip
            </button>
          </>
        }>
        <div className="space-y-4">
          <div>
            <label className="label">Nome do Clip</label>
            <input className="input" placeholder="Ex: Incidente 14:30" value={clipName}
              onChange={e => setClipName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Início</label>
              <input type="time" className="input"
                value={minutesToTime(clipRange[0])}
                onChange={e => {
                  const [h, m] = e.target.value.split(':').map(Number)
                  setClipRange(r => [h * 60 + m, r[1]])
                }} />
            </div>
            <div>
              <label className="label">Fim</label>
              <input type="time" className="input"
                value={minutesToTime(clipRange[1])}
                onChange={e => {
                  const [h, m] = e.target.value.split(':').map(Number)
                  setClipRange(r => [r[0], h * 60 + m])
                }} />
            </div>
          </div>
          <p className="text-xs text-t3">Câmera: <strong className="text-t2">{selCam?.name}</strong> · Data: <strong className="text-t2">{format(selDate, 'dd/MM/yyyy')}</strong></p>
        </div>
      </Modal>
    </div>
  )
}
