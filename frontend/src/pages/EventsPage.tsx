import { useState, useEffect, useCallback } from 'react'
import { formatDistanceToNowStrict, format, parseISO } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import {
  Car, ShieldAlert, Activity, Wifi, WifiOff, Users, Hash,
  Clock, Flame, UserCircle, VideoOff, AlertTriangle, ArrowLeftRight,
  RefreshCw, ChevronDown, Search, Filter, X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { eventService, cameraService } from '@/services/api'
import { PageSpinner } from '@/components/ui/Spinner'
import type { VMSEvent, Camera } from '@/types'

// ─── Event type registry ──────────────────────────────────────────────────────

type EventCfg = { label: string; icon: LucideIcon; color: string }

const CFG: Record<string, EventCfg> = {
  'alpr.detected':                  { label: 'Placa',        icon: Car,            color: '#3B82F6' },
  'intrusion.detected':             { label: 'Intrusão',     icon: ShieldAlert,    color: '#EF4444' },
  'motion.detected':                { label: 'Movimento',    icon: Activity,       color: '#F59E0B' },
  'fire.detected':                  { label: 'Fogo',         icon: Flame,          color: '#F97316' },
  'face.detected':                  { label: 'Facial',       icon: UserCircle,     color: '#8B5CF6' },
  'camera.online':                  { label: 'Online',       icon: Wifi,           color: '#22C55E' },
  'camera.offline':                 { label: 'Offline',      icon: WifiOff,        color: '#71717A' },
  'video.loss':                     { label: 'Sem Vídeo',    icon: VideoOff,       color: '#71717A' },
  'tampering.detected':             { label: 'Adulteração',  icon: AlertTriangle,  color: '#F59E0B' },
  'line_crossing.detected':         { label: 'Cruzamento',   icon: ArrowLeftRight, color: '#06B6D4' },
  'analytics.intrusion.detected':   { label: 'Intrusão IA',  icon: ShieldAlert,    color: '#EF4444' },
  'analytics.people.count':         { label: 'Pessoas',      icon: Users,          color: '#8B5CF6' },
  'analytics.vehicle.count':        { label: 'Veículos',     icon: Car,            color: '#3B82F6' },
  'analytics.lpr.detection':        { label: 'LPR',          icon: Hash,           color: '#06B6D4' },
  'analytics.vehicle.dwell':        { label: 'Permanência',  icon: Clock,          color: '#F59E0B' },
  'analytics.face.recognized':      { label: 'Reconhecido',  icon: UserCircle,     color: '#22C55E' },
  'analytics.face.detected':        { label: 'Facial IA',    icon: UserCircle,     color: '#8B5CF6' },
}

function cfg(type: string): EventCfg {
  return CFG[type] ?? { label: type.split('.').pop() ?? type, icon: Activity, color: '#71717A' }
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function TypeBadge({ type }: { type: string }) {
  const c = cfg(type)
  const Icon = c.icon
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide whitespace-nowrap"
      style={{ color: c.color, background: c.color + '1a' }}
    >
      <Icon size={9} />
      {c.label}
    </span>
  )
}

function EventDetail({ ev }: { ev: VMSEvent }) {
  const nodes: React.ReactNode[] = []
  const p = ev.payload

  if (ev.plate) {
    nodes.push(
      <span key="plate"
        className="font-mono text-xs font-bold text-t1 tracking-widest bg-elevated px-2 py-0.5 rounded border border-border">
        {ev.plate}
      </span>
    )
  }
  if (ev.confidence != null) {
    nodes.push(
      <span key="conf" className="text-xs text-t3 tabular-nums">
        {Math.round(ev.confidence * 100)}%
      </span>
    )
  }
  if (p.count != null)
    nodes.push(<span key="count" className="text-xs text-t2">{String(p.count)} obj.</span>)
  if (p.person_count != null)
    nodes.push(<span key="pc" className="text-xs text-t2">{String(p.person_count)} pess.</span>)
  if (p.dwell_seconds != null)
    nodes.push(<span key="dwell" className="text-xs text-t3">{String(p.dwell_seconds)}s perm.</span>)
  if (p.roi_name)
    nodes.push(<span key="roi" className="text-xs text-t3 truncate max-w-[140px]">{String(p.roi_name)}</span>)

  if (nodes.length === 0) return <span className="text-xs text-t3">—</span>
  return <div className="flex items-center gap-2 flex-wrap">{nodes}</div>
}

function safeDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  try {
    const d = parseISO(iso)
    return isNaN(d.getTime()) ? null : d
  } catch { return null }
}

function RelTs({ iso }: { iso: string | null | undefined }) {
  const d = safeDate(iso)
  if (!d) return <span className="text-[11px] text-t3">—</span>
  return (
    <span
      title={format(d, 'dd/MM/yyyy HH:mm:ss')}
      className="text-[11px] text-t3 whitespace-nowrap tabular-nums cursor-default"
    >
      {formatDistanceToNowStrict(d, { locale: ptBR, addSuffix: true })}
    </span>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 30
const TYPE_OPTIONS = Object.entries(CFG).map(([v, c]) => ({ value: v, label: c.label }))

export function EventsPage() {
  const [events, setEvents]       = useState<VMSEvent[]>([])
  const [cameras, setCameras]     = useState<Camera[]>([])
  const [total, setTotal]         = useState(0)
  const [page, setPage]           = useState(1)
  const [loading, setLoading]     = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  // filters
  const [cameraId, setCameraId]   = useState('')
  const [eventType, setEventType] = useState('')
  const [plate, setPlate]         = useState('')
  const [plateInput, setPlateInput] = useState('')

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const load = useCallback(async (spinner = false) => {
    spinner ? setLoading(true) : setRefreshing(true)
    try {
      const params: Record<string, unknown> = { page, page_size: PAGE_SIZE, ordering: '-created_at' }
      if (cameraId)  params.camera     = cameraId
      if (eventType) params.event_type = eventType
      if (plate)     params.plate      = plate
      const res = await eventService.list(params)
      setEvents(res.results)
      setTotal(res.count)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [page, cameraId, eventType, plate])

  useEffect(() => {
    cameraService.list({ page_size: 200 }).then(r => setCameras(r.results))
  }, [])

  useEffect(() => { load(true) }, [load])

  useEffect(() => {
    if (!autoRefresh) return
    const t = setInterval(() => load(false), 12_000)
    return () => clearInterval(t)
  }, [autoRefresh, load])

  const applyPlate = () => { setPlate(plateInput.trim().toUpperCase()); setPage(1) }

  const clearAll = () => {
    setCameraId(''); setEventType(''); setPlate(''); setPlateInput(''); setPage(1)
  }

  const hasFilters = !!(cameraId || eventType || plate)

  if (loading) return <PageSpinner />

  return (
    <div className="space-y-3 animate-fade-in">

      {/* ── Filter bar ── */}
      <div className="card p-3">
        <div className="flex flex-wrap items-center gap-2">

          <select
            value={cameraId}
            onChange={e => { setCameraId(e.target.value); setPage(1) }}
            className="input text-xs h-8 min-w-[160px]"
          >
            <option value="">Todas as câmeras</option>
            {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>

          <select
            value={eventType}
            onChange={e => { setEventType(e.target.value); setPage(1) }}
            className="input text-xs h-8 min-w-[148px]"
          >
            <option value="">Todos os tipos</option>
            {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <div className="flex items-center gap-1">
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-t3 pointer-events-none" />
              <input
                value={plateInput}
                onChange={e => setPlateInput(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && applyPlate()}
                placeholder="Placa…"
                className="input text-xs h-8 pl-7 w-28 font-mono uppercase tracking-widest"
              />
            </div>
            <button onClick={applyPlate} className="btn btn-ghost h-8 px-2">
              <Filter size={12} />
            </button>
          </div>

          {hasFilters && (
            <button onClick={clearAll} className="btn btn-ghost h-8 px-2.5 text-xs text-t3 hover:text-danger gap-1">
              <X size={12} /> Limpar
            </button>
          )}

          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs text-t3 tabular-nums">{total.toLocaleString()} eventos</span>
            <button
              onClick={() => setAutoRefresh(v => !v)}
              className={`btn btn-ghost h-8 px-2.5 text-xs gap-1.5 ${autoRefresh ? 'text-accent' : 'text-t3'}`}
            >
              <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
              {autoRefresh ? 'Live' : 'Pausado'}
            </button>
          </div>
        </div>
      </div>

      {/* ── Event list ── */}
      <div className="card overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-[112px_160px_1fr_120px_28px] gap-3 px-4 py-2 border-b border-border">
          {['Tipo', 'Câmera', 'Detalhe', 'Quando', ''].map(h => (
            <span key={h} className="text-[10px] font-semibold text-t3 uppercase tracking-wider">{h}</span>
          ))}
        </div>

        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-t3">
            <ShieldAlert size={28} strokeWidth={1.5} className="opacity-25" />
            <p className="text-sm">Nenhum evento encontrado</p>
            {hasFilters && (
              <button onClick={clearAll} className="btn btn-ghost text-xs h-7 px-3">
                Limpar filtros
              </button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-border">
            {events.map(ev => {
              const c = cfg(ev.event_type)
              const expanded = expandedId === ev.id
              return (
                <div key={ev.id} style={{ borderLeft: `2px solid ${c.color}` }}>
                  <div
                    className="grid grid-cols-[112px_160px_1fr_120px_28px] gap-3 items-center px-4 py-2.5 hover:bg-elevated/40 transition-colors cursor-pointer"
                    onClick={() => setExpandedId(expanded ? null : ev.id)}
                  >
                    <TypeBadge type={ev.event_type} />

                    <span className="text-xs text-t2 truncate">
                      {ev.camera_name ?? `CAM-${ev.camera}`}
                    </span>

                    <EventDetail ev={ev} />

                    <RelTs iso={ev.created_at} />

                    <ChevronDown
                      size={13}
                      className={`text-t3 transition-transform justify-self-center ${expanded ? 'rotate-180' : ''}`}
                    />
                  </div>

                  {expanded && (
                    <div
                      className="px-4 py-3 bg-bg/50 border-t border-border/50 space-y-2"
                      onClick={e => e.stopPropagation()}
                    >
                      <div className="flex items-center gap-4 flex-wrap text-[11px] text-t3">
                        <span>ID: <span className="font-mono text-t2">{ev.id}</span></span>
                        <span>{safeDate(ev.created_at) ? format(safeDate(ev.created_at)!, 'dd/MM/yyyy HH:mm:ss') : '—'}</span>
                        {ev.confidence != null && (
                          <span>Confiança: <span className="text-t2">{Math.round(ev.confidence * 100)}%</span></span>
                        )}
                      </div>
                      {Object.keys(ev.payload).length > 0 && (
                        <pre className="text-[11px] text-t2 font-mono bg-elevated px-3 py-2 rounded overflow-auto max-h-32 leading-relaxed">
                          {JSON.stringify(ev.payload, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-t3">
            Página {page} de {totalPages} · {total.toLocaleString()} total
          </p>
          <div className="flex items-center gap-1">
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
              className="btn btn-ghost text-xs h-7 px-3 disabled:opacity-30"
            >
              ‹ Anterior
            </button>

            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              const start = Math.max(1, Math.min(page - 3, totalPages - 6))
              return start + i
            }).filter(n => n >= 1 && n <= totalPages).map(n => (
              <button
                key={n}
                onClick={() => setPage(n)}
                className={`btn text-xs h-7 w-7 p-0 ${n === page ? 'btn-primary' : 'btn-ghost'}`}
              >
                {n}
              </button>
            ))}

            <button
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
              className="btn btn-ghost text-xs h-7 px-3 disabled:opacity-30"
            >
              Próxima ›
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
