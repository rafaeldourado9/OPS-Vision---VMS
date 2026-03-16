import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import api from '../lib/api'
import { formatDate } from '../lib/utils'
import Pagination from '../components/Pagination'

interface VmsEvent {
  id: number
  event_type: string
  payload: Record<string, unknown>
  camera: number | null
  plate: string | null
  confidence: number | null
  created_at: string
}

const EVENT_TYPE_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'camera.online', label: 'Câmera Online' },
  { value: 'camera.offline', label: 'Câmera Offline' },
  { value: 'alpr.detected', label: 'Placa Detectada' },
  { value: 'motion.detected', label: 'Movimento' },
  { value: 'intrusion.detected', label: 'Intrusão' },
  { value: 'fire.detected', label: 'Incêndio' },
  { value: 'face.detected', label: 'Face' },
]

export default function EventsPage() {
  const [events, setEvents] = useState<VmsEvent[]>([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState({
    event_type: '',
    plate: '',
    camera: '',
    created_at__gte: '',
    created_at__lte: '',
  })

  useEffect(() => {
    loadEvents()
  }, [page])

  const loadEvents = async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { page, page_size: 20 }
      if (filters.event_type) params.event_type = filters.event_type
      if (filters.plate) params.plate = filters.plate
      if (filters.camera) params.camera = filters.camera
      if (filters.created_at__gte) params.created_at__gte = new Date(filters.created_at__gte).toISOString()
      if (filters.created_at__lte) params.created_at__lte = new Date(filters.created_at__lte).toISOString()

      const { data } = await api.get('/events/', { params })
      setEvents(data.results ?? data)
      setCount(data.count ?? 0)
    } catch {}
    setLoading(false)
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    loadEvents()
  }

  const eventTypeColor = (type: string) => {
    if (type.includes('online')) return 'text-vms-success'
    if (type.includes('offline')) return 'text-vms-danger'
    if (type.includes('alpr')) return 'text-vms-accent'
    if (type.includes('intrusion') || type.includes('fire')) return 'text-vms-warning'
    return 'text-vms-muted'
  }

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Detecções</h1>

      {/* Filters */}
      <form onSubmit={handleSearch} className="bg-vms-card rounded-xl p-4 mb-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <select
            value={filters.event_type}
            onChange={(e) => setFilters({ ...filters, event_type: e.target.value })}
            className="bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
          >
            {EVENT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <input
            placeholder="Placa (ex: ABC1234)"
            value={filters.plate}
            onChange={(e) => setFilters({ ...filters, plate: e.target.value })}
            className="bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
          />
          <input
            placeholder="ID Câmera"
            value={filters.camera}
            onChange={(e) => setFilters({ ...filters, camera: e.target.value })}
            className="bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
          />
          <input
            type="datetime-local"
            value={filters.created_at__gte}
            onChange={(e) => setFilters({ ...filters, created_at__gte: e.target.value })}
            className="bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
            title="De"
          />
          <input
            type="datetime-local"
            value={filters.created_at__lte}
            onChange={(e) => setFilters({ ...filters, created_at__lte: e.target.value })}
            className="bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
            title="Até"
          />
          <button
            type="submit"
            className="flex items-center justify-center gap-2 bg-vms-accent hover:bg-vms-accent-hover rounded-lg text-sm font-medium transition-colors"
          >
            <Search size={14} /> Buscar
          </button>
        </div>
      </form>

      {/* Table */}
      <div className="bg-vms-card rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vms-border text-vms-muted text-xs">
              <th className="text-left px-4 py-3">Tipo</th>
              <th className="text-left px-4 py-3">Câmera</th>
              <th className="text-left px-4 py-3">Placa</th>
              <th className="text-left px-4 py-3">Confiança</th>
              <th className="text-left px-4 py-3">Data</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="text-center py-8 text-vms-muted">Carregando...</td></tr>
            ) : events.length === 0 ? (
              <tr><td colSpan={5} className="text-center py-8 text-vms-muted">Nenhum evento encontrado</td></tr>
            ) : events.map((ev) => (
              <tr key={ev.id} className="border-b border-vms-border/50 hover:bg-vms-card-hover transition-colors">
                <td className={`px-4 py-3 ${eventTypeColor(ev.event_type)}`}>
                  {ev.event_type.replace('.', ' ')}
                </td>
                <td className="px-4 py-3 text-vms-muted">#{ev.camera ?? '—'}</td>
                <td className="px-4 py-3">
                  {ev.plate ? (
                    <span className="bg-vms-accent/20 text-vms-accent px-2 py-0.5 rounded text-xs font-mono font-bold">
                      {ev.plate}
                    </span>
                  ) : '—'}
                </td>
                <td className="px-4 py-3 text-vms-muted">
                  {ev.confidence != null ? `${(ev.confidence * 100).toFixed(0)}%` : '—'}
                </td>
                <td className="px-4 py-3 text-vms-muted">{formatDate(ev.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pagination currentPage={page} totalCount={count} pageSize={20} onPageChange={setPage} />
    </div>
  )
}
