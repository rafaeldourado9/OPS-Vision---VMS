import { useEffect, useState } from 'react'
import { Search, Download, Trash2, Film, Clock, RefreshCw } from 'lucide-react'
import { format } from 'date-fns'
import { clsx } from 'clsx'
import { clipService, cameraService } from '@/services/api'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { usePermission } from '@/hooks/usePermission'
import toast from 'react-hot-toast'
import type { Clip, Camera } from '@/types'

type StatusFilter = 'all' | 'ready' | 'processing' | 'error'

export function ClipsPage() {
  const { isCityAdmin } = usePermission()
  const [clips, setClips]       = useState<Clip[]>([])
  const [cameras, setCameras]   = useState<Camera[]>([])
  const [loading, setLoading]   = useState(true)
  const [search, setSearch]     = useState('')
  const [camFilter, setCamFilter] = useState('')
  const [statusFilter, setStatus] = useState<StatusFilter>('all')
  const [playing, setPlaying]   = useState<Clip | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    clipService.list({ page_size: 100, ...(camFilter ? { camera: camFilter } : {}) })
      .then(r => setClips(r.results))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    cameraService.list({ page_size: 100 }).then(r => setCameras(r.results))
  }, [])

  useEffect(() => { load() }, [camFilter])

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await clipService.delete(deleteId)
      toast.success('Clip removido')
      setDeleteId(null)
      load()
    } catch { toast.error('Erro ao remover clip') }
  }

  const handleDownload = (clip: Clip) => {
    if (!clip.file_url) { toast.error('Arquivo não disponível'); return }
    const a = document.createElement('a')
    a.href = clip.file_url
    a.download = `${clip.name}.mp4`
    a.click()
  }

  const filtered = clips.filter(c => {
    if (statusFilter !== 'all' && c.status !== statusFilter) return false
    if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const statusVariant = (s: string) => {
    if (s === 'ready') return 'success'
    if (s === 'error') return 'danger'
    return 'warning'
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-t3" />
          <input className="input pl-9" placeholder="Buscar clips..."
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>

        <select className="input max-w-[180px]" value={camFilter} onChange={e => setCamFilter(e.target.value)}>
          <option value="">Todas as câmeras</option>
          {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        <div className="flex items-center gap-1 p-1 rounded-lg"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
          {([
            { id: 'all', label: 'Todos' },
            { id: 'ready', label: 'Prontos' },
            { id: 'processing', label: 'Processando' },
            { id: 'error', label: 'Erro' },
          ] as { id: StatusFilter; label: string }[]).map(f => (
            <button key={f.id} onClick={() => setStatus(f.id)}
              className={clsx('px-3 py-1 rounded-md text-xs font-medium transition',
                statusFilter === f.id ? 'text-white' : 'text-t2 hover:text-t1')}
              style={statusFilter === f.id ? { background: 'var(--accent)' } : {}}>
              {f.label}
            </button>
          ))}
        </div>

        <button className="btn btn-ghost gap-2" onClick={load}>
          <RefreshCw size={14} />
        </button>
      </div>

      <p className="text-xs text-t3">{filtered.length} clip(s)</p>

      {loading ? <PageSpinner /> : (
        <>
          {filtered.length === 0 ? (
            <div className="card p-16 text-center">
              <Film size={40} className="text-t3 mx-auto mb-4" />
              <p className="text-t2 font-medium">Nenhum clip encontrado</p>
              <p className="text-xs text-t3 mt-1">Crie clips na página de Gravações</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filtered.map(clip => {
                const cam = cameras.find(c => c.id === clip.camera)
                return (
                  <div key={clip.id} className="card overflow-hidden group flex flex-col">
                    {/* Thumbnail / player */}
                    <div className="aspect-video bg-black relative cursor-pointer"
                      onClick={() => clip.status === 'ready' && setPlaying(clip)}>
                      {clip.thumbnail_url ? (
                        <img src={clip.thumbnail_url} alt={clip.name}
                          className="w-full h-full object-cover opacity-70 group-hover:opacity-90 transition" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <Film size={28} className="text-t3" />
                        </div>
                      )}
                      {clip.status === 'processing' && (
                        <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                          <div className="flex flex-col items-center gap-2">
                            <Clock size={20} className="text-yellow-400 animate-spin" />
                            <p className="text-xs text-yellow-400">Processando...</p>
                          </div>
                        </div>
                      )}
                      {clip.status === 'ready' && (
                        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition">
                          <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur flex items-center justify-center">
                            <div className="w-0 h-0 border-t-[8px] border-t-transparent border-l-[14px] border-l-white border-b-[8px] border-b-transparent ml-1" />
                          </div>
                        </div>
                      )}
                      <div className="absolute top-2 right-2">
                        <Badge variant={statusVariant(clip.status) as any}>{clip.status}</Badge>
                      </div>
                    </div>

                    {/* Info */}
                    <div className="p-3 flex-1 flex flex-col gap-1">
                      <p className="text-sm font-medium text-t1 truncate">{clip.name}</p>
                      {cam && <p className="text-xs text-t3">{cam.name}</p>}
                      <p className="text-xs text-t3">
                        {format(new Date(clip.started_at), 'dd/MM/yyyy')} ·{' '}
                        {format(new Date(clip.started_at), 'HH:mm')} → {format(new Date(clip.ended_at), 'HH:mm')}
                      </p>
                      <p className="text-xs text-t3">Criado: {format(new Date(clip.created_at), 'dd/MM/yy HH:mm')}</p>

                      <div className="flex items-center gap-1 mt-2">
                        {clip.status === 'ready' && (
                          <button className="btn btn-ghost flex-1 gap-1 text-xs" onClick={() => handleDownload(clip)}>
                            <Download size={13} />Download
                          </button>
                        )}
                        {isCityAdmin && (
                          <button className="btn btn-ghost w-8 h-8 p-0 text-danger hover:text-danger"
                            onClick={() => setDeleteId(clip.id)}>
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {/* Player modal */}
      <Modal open={!!playing} onClose={() => setPlaying(null)} title={playing?.name ?? ''} size="xl">
        {playing?.file_url && (
          <VideoPlayer src={playing.file_url} cameraName={playing.name} className="aspect-video w-full" />
        )}
      </Modal>

      {/* Delete confirm */}
      <Modal open={!!deleteId} onClose={() => setDeleteId(null)} title="Remover Clip" size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setDeleteId(null)}>Cancelar</button>
            <button className="btn btn-danger" onClick={handleDelete}>
              <Trash2 size={15} />Remover
            </button>
          </>
        }>
        <p className="text-sm text-t2">Tem certeza que deseja remover este clip? Esta ação não pode ser desfeita.</p>
      </Modal>
    </div>
  )
}
