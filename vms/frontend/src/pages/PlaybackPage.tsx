import { useEffect, useState } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react'
import VideoPlayer from '../components/VideoPlayer'
import api from '../lib/api'
import { formatDate } from '../lib/utils'

interface Segment {
  id: number
  camera: number
  start_time: string
  end_time: string
  duration_seconds: number
  file_path: string
}

export default function PlaybackPage() {
  const { cameraId } = useParams<{ cameraId: string }>()
  const [searchParams] = useSearchParams()
  const [segments, setSegments] = useState<Segment[]>([])
  const [currentSegment, setCurrentSegment] = useState<Segment | null>(null)
  const [playbackUrl, setPlaybackUrl] = useState('')
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0])

  const changeDate = (delta: number) => {
    const d = new Date(selectedDate + 'T12:00:00')
    d.setDate(d.getDate() + delta)
    setSelectedDate(d.toISOString().split('T')[0])
  }

  useEffect(() => {
    if (!cameraId) return
    const from = new Date(selectedDate + 'T00:00:00').toISOString()
    const to = new Date(selectedDate + 'T23:59:59').toISOString()
    api.get(`/cameras/${cameraId}/timeline/`, { params: { from, to } })
      .then((r) => {
        const segs = r.data.results ?? r.data ?? []
        setSegments(segs)
        const segId = searchParams.get('segment')
        if (segId) {
          const found = segs.find((s: Segment) => s.id === Number(segId))
          if (found) selectSegment(found)
        }
      })
      .catch(() => {})
  }, [cameraId, selectedDate])

  const selectSegment = (seg: Segment) => {
    setCurrentSegment(seg)
    api.get(`/cameras/${cameraId}/playback/`, { params: { timestamp: seg.start_time } })
      .then((r) => {
        // Backend returns file_path; build a playback URL via the stream endpoint
        const filePath = r.data.file_path || ''
        if (filePath) setPlaybackUrl(`/api/v1/cameras/${cameraId}/stream/?timestamp=${encodeURIComponent(seg.start_time)}`)
        else setPlaybackUrl('')
      })
      .catch(() => setPlaybackUrl(''))
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <Link to="/recordings" className="text-vms-muted hover:text-white"><ArrowLeft size={20} /></Link>
        <h1 className="text-xl font-bold">Reprodução — Câmera #{cameraId}</h1>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => changeDate(-1)}
            className="bg-vms-card border border-vms-border px-2 py-1.5 rounded-lg text-vms-muted hover:text-white hover:bg-vms-card-hover transition-colors"
          ><ChevronLeft size={16} /></button>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="bg-vms-card border border-vms-border rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-vms-accent"
          />
          <button
            onClick={() => changeDate(1)}
            className="bg-vms-card border border-vms-border px-2 py-1.5 rounded-lg text-vms-muted hover:text-white hover:bg-vms-card-hover transition-colors"
          ><ChevronRight size={16} /></button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Player */}
        <div className="lg:col-span-3 bg-vms-card rounded-xl overflow-hidden">
          {playbackUrl ? (
            <div className="aspect-video">
              <VideoPlayer src={playbackUrl} mode="vod" />
            </div>
          ) : (
            <div className="aspect-video flex items-center justify-center text-vms-muted">
              Selecione um segmento para reproduzir
            </div>
          )}
          {currentSegment && (
            <div className="p-3 border-t border-vms-border text-sm text-vms-muted">
              {formatDate(currentSegment.start_time)} — {formatDate(currentSegment.end_time)} ({currentSegment.duration_seconds}s)
            </div>
          )}
        </div>

        {/* Segment list */}
        <div className="bg-vms-card rounded-xl p-3 max-h-[600px] overflow-y-auto">
          <h3 className="text-sm font-semibold mb-3">Segmentos</h3>
          <div className="space-y-1">
            {segments.map((seg) => (
              <button
                key={seg.id}
                onClick={() => selectSegment(seg)}
                className={`w-full text-left p-2 rounded-lg text-xs transition-colors ${currentSegment?.id === seg.id ? 'bg-vms-accent text-white' : 'hover:bg-vms-card-hover text-vms-muted'}`}
              >
                <p className="font-medium">{formatDate(seg.start_time)}</p>
                <p>{seg.duration_seconds}s</p>
              </button>
            ))}
            {segments.length === 0 && (
              <p className="text-vms-muted text-xs text-center py-4">Nenhum segmento</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
