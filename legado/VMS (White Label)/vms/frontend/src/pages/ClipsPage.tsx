import { useEffect, useState } from 'react'
import { Download, Scissors } from 'lucide-react'
import api from '../lib/api'
import { formatDate } from '../lib/utils'
import Pagination from '../components/Pagination'

interface Clip {
  id: number
  camera: number
  start_time: string
  end_time: string
  status: string
  file_path: string | null
  created_at: string
}

export default function ClipsPage() {
  const [clips, setClips] = useState<Clip[]>([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)

  useEffect(() => {
    loadClips()
  }, [page])

  const loadClips = async () => {
    try {
      const { data } = await api.get('/recordings/clips/', { params: { page, page_size: 20 } })
      setClips(data.results ?? data)
      setCount(data.count ?? 0)
    } catch {}
  }

  const deleteClip = async (id: number) => {
    if (!confirm('Remover este clip?')) return
    try {
      await api.delete(`/clips/${id}/`)
      loadClips()
    } catch {}
  }

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Clips</h1>

      {clips.length === 0 ? (
        <div className="text-center py-16 text-vms-muted">
          <Scissors size={48} className="mx-auto mb-3 opacity-40" />
          <p>Nenhum clip exportado</p>
        </div>
      ) : (
        <div className="space-y-2">
          {clips.map((clip) => (
            <div key={clip.id} className="bg-vms-card rounded-lg p-4 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Clip #{clip.id} — Câmera #{clip.camera}</p>
                <p className="text-xs text-vms-muted mt-0.5">
                  {formatDate(clip.start_time)} → {formatDate(clip.end_time)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-0.5 rounded ${
                  clip.status === 'ready' ? 'bg-vms-success/20 text-vms-success'
                  : clip.status === 'failed' ? 'bg-vms-danger/20 text-vms-danger'
                  : 'bg-vms-warning/20 text-vms-warning'
                }`}>
                  {clip.status}
                </span>
                {clip.status === 'ready' && (
                  <a href={`/api/v1/clips/${clip.id}/download/`} className="text-vms-accent hover:text-vms-accent-hover">
                    <Download size={16} />
                  </a>
                )}
                <button onClick={() => deleteClip(clip.id)} className="text-vms-muted hover:text-red-400 text-xs">
                  Remover
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Pagination currentPage={page} totalCount={count} pageSize={20} onPageChange={setPage} />
    </div>
  )
}
