import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Film, Download, Plus, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '../lib/api'
import { useCameraStore } from '../stores/cameraStore'
import { formatDate } from '../lib/utils'
import Modal from '../components/Modal'

interface Clip {
  id: number
  camera: number
  start_time: string
  end_time: string
  status: string
  file_path: string | null
  created_at: string
}

interface Segment {
  id: number
  camera: number
  start_time: string
  end_time: string
  duration_seconds: number
  file_path: string
}

export default function RecordingsPage() {
  const { cameras, fetchCameras } = useCameraStore()
  const [clips, setClips] = useState<Clip[]>([])
  const [segments, setSegments] = useState<Segment[]>([])
  const [selectedCamera, setSelectedCamera] = useState<number | ''>('')
  const [showClipModal, setShowClipModal] = useState(false)
  const [clipForm, setClipForm] = useState({ camera_id: '', start_time: '', end_time: '' })
  const [saving, setSaving] = useState(false)
  const [tab, setTab] = useState<'segments' | 'clips'>('segments')
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0])

  const changeDate = (delta: number) => {
    const d = new Date(selectedDate + 'T12:00:00')
    d.setDate(d.getDate() + delta)
    setSelectedDate(d.toISOString().split('T')[0])
  }

  useEffect(() => {
    fetchCameras()
    loadClips()
  }, [])

  useEffect(() => {
    if (selectedCamera) loadSegments(Number(selectedCamera))
  }, [selectedCamera, selectedDate])

  const loadClips = async () => {
    try {
      const { data } = await api.get('/recordings/clips/', { params: { page_size: 50 } })
      setClips(data.results ?? data)
    } catch {}
  }

  const loadSegments = async (cameraId: number) => {
    try {
      const from = new Date(selectedDate + 'T00:00:00').toISOString()
      const to = new Date(selectedDate + 'T23:59:59').toISOString()
      const { data } = await api.get(`/cameras/${cameraId}/timeline/`, {
        params: { from, to },
      })
      setSegments(data.results ?? data ?? [])
    } catch {}
  }

  const createClip = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api.post('/recordings/clips/', {
        camera_id: Number(clipForm.camera_id),
        start_time: new Date(clipForm.start_time).toISOString(),
        end_time: new Date(clipForm.end_time).toISOString(),
      })
      setShowClipModal(false)
      loadClips()
    } catch {}
    setSaving(false)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Gravações</h1>
        <button
          onClick={() => setShowClipModal(true)}
          className="flex items-center gap-2 bg-vms-accent hover:bg-vms-accent-hover rounded-lg px-4 py-2 text-sm font-medium transition-colors"
        >
          <Plus size={16} /> Criar Clip
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-vms-card rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab('segments')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${tab === 'segments' ? 'bg-vms-accent text-white' : 'text-vms-muted hover:text-white'}`}
        >
          Segmentos
        </button>
        <button
          onClick={() => setTab('clips')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${tab === 'clips' ? 'bg-vms-accent text-white' : 'text-vms-muted hover:text-white'}`}
        >
          Clips
        </button>
      </div>

      {tab === 'segments' && (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <select
              value={selectedCamera}
              onChange={(e) => setSelectedCamera(e.target.value ? Number(e.target.value) : '')}
              className="bg-vms-card border border-vms-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-vms-accent"
            >
              <option value="">Selecione uma câmera</option>
              {cameras.map((cam) => (
                <option key={cam.id} value={cam.id}>{cam.name}</option>
              ))}
            </select>
            <div className="flex items-center gap-1">
              <button
                onClick={() => changeDate(-1)}
                className="bg-vms-card border border-vms-border px-2 py-2 rounded-lg text-vms-muted hover:text-white hover:bg-vms-card-hover transition-colors"
              ><ChevronLeft size={16} /></button>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="bg-vms-card border border-vms-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-vms-accent"
              />
              <button
                onClick={() => changeDate(1)}
                className="bg-vms-card border border-vms-border px-2 py-2 rounded-lg text-vms-muted hover:text-white hover:bg-vms-card-hover transition-colors"
              ><ChevronRight size={16} /></button>
            </div>
          </div>

          <div className="space-y-2">
            {segments.length > 0 ? segments.map((seg) => (
              <div key={seg.id} className="bg-vms-card rounded-lg p-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Film size={16} className="text-vms-muted" />
                  <div>
                    <p className="text-sm">{formatDate(seg.start_time)} — {formatDate(seg.end_time)}</p>
                    <p className="text-xs text-vms-muted">{seg.duration_seconds}s</p>
                  </div>
                </div>
                <Link
                  to={`/recordings/${seg.camera}/playback?segment=${seg.id}`}
                  className="text-vms-accent text-sm hover:underline"
                >
                  Reproduzir
                </Link>
              </div>
            )) : (
              <p className="text-vms-muted text-sm py-8 text-center">
                {selectedCamera ? `Nenhum segmento em ${selectedDate}` : 'Selecione uma câmera para ver os segmentos'}
              </p>
            )}
          </div>
        </>
      )}

      {tab === 'clips' && (
        <div className="space-y-2">
          {clips.length > 0 ? clips.map((clip) => (
            <div key={clip.id} className="bg-vms-card rounded-lg p-3 flex items-center justify-between">
              <div>
                <p className="text-sm">Clip #{clip.id} — Câmera {clip.camera}</p>
                <p className="text-xs text-vms-muted">
                  {formatDate(clip.start_time)} → {formatDate(clip.end_time)}
                  <span className={`ml-2 ${clip.status === 'ready' ? 'text-vms-success' : clip.status === 'failed' ? 'text-vms-danger' : 'text-vms-warning'}`}>
                    {clip.status}
                  </span>
                </p>
              </div>
              {clip.status === 'ready' && (
                <a
                  href={`/api/v1/recordings/clips/${clip.id}/download/`}
                  className="flex items-center gap-1 text-vms-accent text-sm hover:underline"
                >
                  <Download size={14} /> Download
                </a>
              )}
            </div>
          )) : (
            <p className="text-vms-muted text-sm py-8 text-center">Nenhum clip criado</p>
          )}
        </div>
      )}

      {/* Clip creation modal */}
      <Modal open={showClipModal} onClose={() => setShowClipModal(false)} title="Criar Clip">
        <form onSubmit={createClip} className="space-y-4">
          <div>
            <label className="block text-sm text-vms-muted mb-1">Câmera</label>
            <select
              value={clipForm.camera_id}
              onChange={(e) => setClipForm({ ...clipForm, camera_id: e.target.value })}
              className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
              required
            >
              <option value="">Selecione</option>
              {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-vms-muted mb-1">Início</label>
              <input
                type="datetime-local"
                value={clipForm.start_time}
                onChange={(e) => setClipForm({ ...clipForm, start_time: e.target.value })}
                className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-vms-muted mb-1">Fim</label>
              <input
                type="datetime-local"
                value={clipForm.end_time}
                onChange={(e) => setClipForm({ ...clipForm, end_time: e.target.value })}
                className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
                required
              />
            </div>
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => setShowClipModal(false)} className="px-4 py-2 text-sm rounded-lg bg-vms-card-hover">Cancelar</button>
            <button type="submit" disabled={saving} className="px-4 py-2 text-sm rounded-lg bg-vms-accent hover:bg-vms-accent-hover font-medium disabled:opacity-60">
              {saving ? 'Criando...' : 'Criar Clip'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
