import { useEffect, useState, useCallback } from 'react'
import { Search, Filter, Download, Eye, ChevronLeft, ChevronRight, X } from 'lucide-react'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { clsx } from 'clsx'
import { detectionService, cameraService } from '@/services/api'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import type { Detection, Camera } from '@/types'

const EVENT_LABELS: Record<string, string> = {
  lpr: 'Placa LPR',
  crowd: 'Multidão',
  intrusion: 'Intrusão',
  object_detected: 'Objeto Detectado',
  vehicle_traffic: 'Tráfego Veicular',
  human_traffic: 'Tráfego Humano',
  line_crossing: 'Cruzamento de Linha',
  loitering: 'Perambulação',
  abandoned_object: 'Objeto Abandonado',
  queue_alert: 'Alerta de Fila',
  facial_match: 'Reconhecimento Facial',
  facial_unknown: 'Rosto Desconhecido',
}

const EVENT_VARIANT: Record<string, 'info' | 'success' | 'warning' | 'danger'> = {
  lpr: 'info',
  crowd: 'warning',
  intrusion: 'danger',
  object_detected: 'info',
  vehicle_traffic: 'info',
  human_traffic: 'info',
  line_crossing: 'warning',
  loitering: 'warning',
  abandoned_object: 'danger',
  queue_alert: 'warning',
  facial_match: 'success',
  facial_unknown: 'danger',
}

const PAGE_SIZE = 20

export function DetectionsPage() {
  const [detections, setDetections] = useState<Detection[]>([])
  const [cameras, setCameras]       = useState<Camera[]>([])
  const [loading, setLoading]       = useState(true)
  const [total, setTotal]           = useState(0)
  const [page, setPage]             = useState(1)

  const [search, setSearch]         = useState('')
  const [camFilter, setCamFilter]   = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [dateFrom, setDateFrom]     = useState('')
  const [dateTo, setDateTo]         = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const [selected, setSelected]     = useState<Detection | null>(null)

  useEffect(() => {
    cameraService.list({ page_size: 100 }).then(r => setCameras(r.results))
  }, [])

  const load = useCallback(() => {
    setLoading(true)
    const params: Record<string, any> = { page, page_size: PAGE_SIZE }
    if (camFilter) params.camera_id = camFilter
    if (typeFilter) params.event_type = typeFilter
    if (dateFrom) params.started_after = dateFrom
    if (dateTo) params.started_before = dateTo + 'T23:59:59'

    detectionService.list(params)
      .then(r => { setDetections(r.results); setTotal(r.count) })
      .finally(() => setLoading(false))
  }, [page, camFilter, typeFilter, dateFrom, dateTo])

  useEffect(() => { load() }, [load])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const exportCsv = () => {
    const rows = [
      ['ID', 'Câmera', 'Evento', 'Confiança', 'Data/Hora', 'Metadados'],
      ...detections.map(d => [
        d.id,
        cameras.find(c => c.id === d.camera_id)?.name ?? d.camera_id,
        EVENT_LABELS[d.event_type] ?? d.event_type,
        `${Math.round(d.confidence * 100)}%`,
        format(new Date(d.detected_at), 'dd/MM/yyyy HH:mm:ss'),
        JSON.stringify(d.metadata),
      ]),
    ]
    const csv = rows.map(r => r.map(c => `"${c}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'deteccoes.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const clearFilters = () => {
    setCamFilter(''); setTypeFilter(''); setDateFrom(''); setDateTo(''); setPage(1)
  }

  const activeFilters = [camFilter, typeFilter, dateFrom, dateTo].filter(Boolean).length

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-t3" />
          <input className="input pl-9" placeholder="Buscar eventos..."
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>

        <button
          className={clsx('btn btn-ghost gap-2 relative', activeFilters > 0 && 'text-accent')}
          onClick={() => setShowFilters(!showFilters)}>
          <Filter size={15} />Filtros
          {activeFilters > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full text-[10px] flex items-center justify-center text-white" style={{ background: 'var(--accent)' }}>
              {activeFilters}
            </span>
          )}
        </button>

        <button className="btn btn-ghost gap-2" onClick={exportCsv}>
          <Download size={15} />Exportar CSV
        </button>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="card p-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className="label">Câmera</label>
              <select className="input" value={camFilter} onChange={e => { setCamFilter(e.target.value); setPage(1) }}>
                <option value="">Todas</option>
                {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Tipo de Evento</label>
              <select className="input" value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPage(1) }}>
                <option value="">Todos</option>
                {Object.entries(EVENT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Data Início</label>
              <input type="date" className="input" value={dateFrom}
                onChange={e => { setDateFrom(e.target.value); setPage(1) }} />
            </div>
            <div>
              <label className="label">Data Fim</label>
              <input type="date" className="input" value={dateTo}
                onChange={e => { setDateTo(e.target.value); setPage(1) }} />
            </div>
          </div>
          {activeFilters > 0 && (
            <button className="btn btn-ghost text-xs mt-3 gap-1" onClick={clearFilters}>
              <X size={12} />Limpar filtros
            </button>
          )}
        </div>
      )}

      {/* Stats */}
      <p className="text-xs text-t3">{total.toLocaleString()} eventos encontrados</p>

      {/* Table */}
      {loading ? <PageSpinner /> : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
                {['Câmera', 'Evento', 'Confiança', 'Metadados', 'Data/Hora', ''].map(h => (
                  <th key={h} className="px-4 py-3 text-xs font-medium text-t3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {detections
                .filter(d => !search || (EVENT_LABELS[d.event_type] ?? d.event_type).toLowerCase().includes(search.toLowerCase()))
                .map(d => {
                  const cam = cameras.find(c => c.id === d.camera_id)
                  return (
                    <tr key={d.id}
                      className="border-b hover:bg-elevated transition cursor-pointer"
                      style={{ borderColor: 'var(--border)' }}
                      onClick={() => setSelected(d)}>
                      <td className="px-4 py-3">
                        <p className="font-medium text-t1 text-xs">{cam?.name ?? '—'}</p>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={EVENT_VARIANT[d.event_type] ?? 'info'}>
                          {EVENT_LABELS[d.event_type] ?? d.event_type}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-t2 text-xs">{Math.round(d.confidence * 100)}%</td>
                      <td className="px-4 py-3 text-t3 text-xs max-w-xs truncate">
                        {d.event_type === 'lpr' && d.metadata?.plate && (
                          <span className="font-mono font-bold text-t1">{d.metadata.plate}</span>
                        )}
                        {d.event_type === 'facial_match' && d.metadata?.name && (
                          <span className="text-t2">{d.metadata.name}</span>
                        )}
                        {['crowd', 'queue_alert'].includes(d.event_type) && d.metadata?.count != null && (
                          <span>{d.metadata.count} pessoas</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-t3 text-xs whitespace-nowrap">
                        {format(new Date(d.detected_at), "dd/MM/yy HH:mm:ss")}
                      </td>
                      <td className="px-4 py-3">
                        <button className="btn btn-ghost w-7 h-7 p-0 rounded-md"
                          onClick={e => { e.stopPropagation(); setSelected(d) }}>
                          <Eye size={14} />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              {detections.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-16 text-center text-t3 text-sm">
                    Nenhum evento encontrado
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
              <p className="text-xs text-t3">Página {page} de {totalPages}</p>
              <div className="flex items-center gap-1">
                <button className="btn btn-ghost w-8 h-8 p-0" disabled={page <= 1}
                  onClick={() => setPage(p => p - 1)}>
                  <ChevronLeft size={16} />
                </button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const p = Math.max(1, Math.min(page - 2, totalPages - 4)) + i
                  return (
                    <button key={p}
                      className={clsx('w-8 h-8 rounded-md text-xs font-medium transition',
                        p === page ? 'text-white' : 'text-t2 hover:text-t1 hover:bg-elevated')}
                      style={p === page ? { background: 'var(--accent)' } : {}}
                      onClick={() => setPage(p)}>{p}</button>
                  )
                })}
                <button className="btn btn-ghost w-8 h-8 p-0" disabled={page >= totalPages}
                  onClick={() => setPage(p => p + 1)}>
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Detail modal */}
      <Modal open={!!selected} onClose={() => setSelected(null)} title="Detalhe do Evento" size="lg">
        {selected && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="label">Tipo</p>
                <Badge variant={EVENT_VARIANT[selected.event_type] ?? 'info'}>
                  {EVENT_LABELS[selected.event_type] ?? selected.event_type}
                </Badge>
              </div>
              <div>
                <p className="label">Confiança</p>
                <p className="text-t1 font-semibold">{Math.round(selected.confidence * 100)}%</p>
              </div>
              <div>
                <p className="label">Câmera</p>
                <p className="text-t1">{cameras.find(c => c.id === selected.camera_id)?.name ?? selected.camera_id}</p>
              </div>
              <div>
                <p className="label">Data/Hora</p>
                <p className="text-t1">{format(new Date(selected.detected_at), "dd/MM/yyyy HH:mm:ss", { locale: ptBR })}</p>
              </div>
            </div>

            {selected.thumbnail_url && (
              <div>
                <p className="label mb-2">Snapshot</p>
                <div className="relative max-w-sm">
                  <img
                    src={selected.thumbnail_url}
                    alt="Snapshot"
                    className="w-full rounded-lg border"
                    style={{ borderColor: 'var(--border)' }}
                  />
                  {/* Bounding box overlay via CSS for static images */}
                  {selected.metadata?.bbox && (
                    <div
                      className="absolute border-2 border-green-400 rounded-sm pointer-events-none"
                      style={{
                        // bbox coords are [x1,y1,x2,y2] in original frame pixels
                        // The image scales proportionally, so use percentages
                        left: `${(selected.metadata.bbox[0] / (selected.metadata.frame_width || 1920)) * 100}%`,
                        top: `${(selected.metadata.bbox[1] / (selected.metadata.frame_height || 1080)) * 100}%`,
                        width: `${((selected.metadata.bbox[2] - selected.metadata.bbox[0]) / (selected.metadata.frame_width || 1920)) * 100}%`,
                        height: `${((selected.metadata.bbox[3] - selected.metadata.bbox[1]) / (selected.metadata.frame_height || 1080)) * 100}%`,
                      }}
                    >
                      {selected.metadata.plate && (
                        <span className="absolute -top-5 left-0 text-[10px] bg-green-400 text-black px-1 rounded font-mono font-bold">
                          {selected.metadata.plate}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div>
              <p className="label mb-2">Metadados</p>
              <pre className="text-xs text-t2 p-3 rounded-lg overflow-auto max-h-48"
                style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
                {JSON.stringify(selected.metadata, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
