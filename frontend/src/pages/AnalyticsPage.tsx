import { useState, useEffect, useCallback, useRef } from 'react'
import { formatDistanceToNowStrict, format, parseISO } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import {
  Car, Users, ShieldAlert, Hash, UserCircle, CheckCircle, XCircle,
  Minus, RefreshCw, ImageOff, Download, ZoomIn, X, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { analyticsDwellService, analyticsFaceService, eventService } from '@/services/api'
import { PageSpinner } from '@/components/ui/Spinner'
import type { DwellEvent, FaceDetectionEvent, VMSEvent } from '@/types'

// ─── Types ────────────────────────────────────────────────────────────────────

type TabId = 'all' | 'vehicles' | 'people' | 'intrusion' | 'plates' | 'facial'

const TABS: { id: TabId; label: string; icon: typeof Car; color: string }[] = [
  { id: 'all',       label: 'Todos',     icon: RefreshCw,   color: '#71717A' },
  { id: 'vehicles',  label: 'Veículos',  icon: Car,         color: '#3B82F6' },
  { id: 'people',    label: 'Pessoas',   icon: Users,       color: '#8B5CF6' },
  { id: 'intrusion', label: 'Intrusão',  icon: ShieldAlert, color: '#EF4444' },
  { id: 'plates',    label: 'Placas',    icon: Hash,        color: '#06B6D4' },
  { id: 'facial',    label: 'Facial',    icon: UserCircle,  color: '#A855F7' },
]

// ─── Unified detection item ───────────────────────────────────────────────────

interface DetectionItem {
  id: string
  type: TabId
  camera_name: string
  frame_path: string
  timestamp: string
  // type-specific
  dwell_seconds?: number | null
  is_valid?: boolean | null
  track_id?: number
  roi_name?: string
  count?: number
  plate?: string
  confidence?: number
  is_unknown?: boolean
  profile_name?: string | null
  detection_count?: number
}

function dwellToItem(ev: DwellEvent): DetectionItem {
  return {
    id: `dwell-${ev.id}`,
    type: 'vehicles',
    camera_name: ev.camera_name ?? `CAM-${ev.camera}`,
    frame_path: ev.frame_path,
    timestamp: ev.entered_at,
    dwell_seconds: ev.dwell_seconds,
    is_valid: ev.is_valid,
    track_id: ev.track_id,
    roi_name: ev.roi_name ?? undefined,
  }
}

function eventToItem(ev: VMSEvent): DetectionItem {
  const p = ev.payload
  let type: TabId = 'all'
  if (ev.event_type.includes('intrusion')) type = 'intrusion'
  else if (ev.event_type.includes('people') || ev.event_type.includes('motion')) type = 'people'
  else if (ev.event_type.includes('lpr') || ev.event_type === 'alpr.detected') type = 'plates'
  else if (ev.event_type.includes('face')) type = 'facial'
  else if (ev.event_type.includes('vehicle')) type = 'vehicles'

  return {
    id: `event-${ev.id}`,
    type,
    camera_name: ev.camera_name ?? `CAM-${ev.camera}`,
    frame_path: (p.frame_path as string) ?? '',
    timestamp: ev.created_at,
    roi_name: (p.roi_name as string) ?? undefined,
    count: p.count != null ? Number(p.count) : undefined,
    plate: ev.plate ?? undefined,
    confidence: ev.confidence ?? undefined,
    detection_count: p.detection_count != null ? Number(p.detection_count) : undefined,
  }
}

function faceToItem(ev: FaceDetectionEvent): DetectionItem {
  return {
    id: `face-${ev.id}`,
    type: 'facial',
    camera_name: ev.camera_name ?? `CAM-${ev.camera}`,
    frame_path: ev.frame_path,
    timestamp: ev.created_at,
    roi_name: ev.roi_name ?? undefined,
    confidence: ev.confidence,
    is_unknown: ev.is_unknown,
    profile_name: ev.profile_name,
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function snapshotUrl(path: string): string {
  return path.replace('/recordings/snapshots/', '/snapshots/')
}

function fmtDwell(sec: number | null | undefined) {
  if (sec == null) return null
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60), s = sec % 60
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

function safeParseISO(iso: string | null | undefined): Date | null {
  if (!iso) return null
  try {
    const d = parseISO(iso)
    if (isNaN(d.getTime())) return null
    return d
  } catch {
    return null
  }
}

function safeRelTime(iso: string | null | undefined): string {
  const d = safeParseISO(iso)
  if (!d) return '—'
  try {
    return formatDistanceToNowStrict(d, { locale: ptBR, addSuffix: true })
  } catch {
    return '—'
  }
}

function safeFormat(iso: string | null | undefined, fmt: string): string {
  const d = safeParseISO(iso)
  if (!d) return '—'
  try {
    return format(d, fmt)
  } catch {
    return '—'
  }
}

// ─── Lightbox ────────────────────────────────────────────────────────────────

function Lightbox({
  items, index, onClose, onPrev, onNext,
}: {
  items: DetectionItem[]
  index: number
  onClose: () => void
  onPrev: () => void
  onNext: () => void
}) {
  const item = items[index]
  const url = snapshotUrl(item.frame_path)
  const [scale, setScale] = useState(1)
  const imgRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    setScale(1)
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft') onPrev()
      if (e.key === 'ArrowRight') onNext()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [index])

  const handleDownload = () => {
    const a = document.createElement('a')
    a.href = url
    a.download = item.frame_path.split('/').pop() ?? 'snapshot.jpg'
    a.click()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90"
      onClick={onClose}
    >
      {/* Controls bar */}
      <div
        className="absolute top-0 left-0 right-0 flex items-center justify-between px-4 py-3 bg-gradient-to-b from-black/60 to-transparent"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center gap-3">
          <span className="text-xs text-white/60">{index + 1} / {items.length}</span>
          <span className="text-sm font-medium text-white">{item.camera_name}</span>
          {item.roi_name && <span className="text-xs text-white/50">{item.roi_name}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setScale(s => Math.min(s + 0.5, 4))}
            className="btn btn-ghost text-white/70 hover:text-white h-8 w-8 p-0"
          >
            <ZoomIn size={16} />
          </button>
          <button
            onClick={() => setScale(1)}
            className="btn btn-ghost text-white/70 hover:text-white h-8 px-2 text-xs"
          >
            {Math.round(scale * 100)}%
          </button>
          <button
            onClick={handleDownload}
            className="btn btn-ghost text-white/70 hover:text-white h-8 w-8 p-0"
          >
            <Download size={16} />
          </button>
          <button
            onClick={onClose}
            className="btn btn-ghost text-white/70 hover:text-white h-8 w-8 p-0"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Image */}
      <div className="relative flex items-center justify-center max-w-[90vw] max-h-[85vh]"
        onClick={e => e.stopPropagation()}>
        <img
          ref={imgRef}
          src={url}
          alt="snapshot"
          style={{ transform: `scale(${scale})`, transition: 'transform 0.2s', maxHeight: '80vh', maxWidth: '88vw' }}
          className="object-contain rounded cursor-zoom-in select-none"
          onClick={() => setScale(s => s >= 3 ? 1 : s + 0.5)}
          draggable={false}
        />
      </div>

      {/* Prev/Next arrows */}
      {index > 0 && (
        <button
          className="absolute left-3 top-1/2 -translate-y-1/2 btn btn-ghost text-white/70 hover:text-white h-10 w-10 p-0 bg-black/30 rounded-full"
          onClick={e => { e.stopPropagation(); onPrev() }}
        >
          <ChevronLeft size={22} />
        </button>
      )}
      {index < items.length - 1 && (
        <button
          className="absolute right-3 top-1/2 -translate-y-1/2 btn btn-ghost text-white/70 hover:text-white h-10 w-10 p-0 bg-black/30 rounded-full"
          onClick={e => { e.stopPropagation(); onNext() }}
        >
          <ChevronRight size={22} />
        </button>
      )}

      {/* Bottom info */}
      <div className="absolute bottom-0 left-0 right-0 px-4 py-3 bg-gradient-to-t from-black/60 to-transparent text-center">
        <p className="text-xs text-white/50">
          {safeFormat(item.timestamp, 'dd/MM/yyyy HH:mm:ss')}
          {item.dwell_seconds != null && ` · ${fmtDwell(item.dwell_seconds)}`}
          {item.plate && ` · ${item.plate}`}
          {item.count != null && ` · ${item.count} pess.`}
        </p>
      </div>
    </div>
  )
}

// ─── Thumbnail with fallback ──────────────────────────────────────────────────

function Thumb({ path, onClick }: { path: string; onClick: () => void }) {
  const [err, setErr] = useState(false)
  if (!path || err) {
    return (
      <div
        className="w-20 h-14 shrink-0 rounded bg-elevated flex items-center justify-center cursor-default"
        onClick={onClick}
      >
        <ImageOff size={16} className="text-t3 opacity-40" />
      </div>
    )
  }
  return (
    <div className="w-20 h-14 shrink-0 rounded overflow-hidden cursor-pointer group relative" onClick={onClick}>
      <img
        src={snapshotUrl(path)}
        alt="snapshot"
        onError={() => setErr(true)}
        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
      />
      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 flex items-center justify-center transition-all">
        <ZoomIn size={14} className="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </div>
  )
}

// ─── Detection row ───────────────────────────────────────────────────────────

const TYPE_CFG: Record<string, { label: string; color: string }> = {
  vehicles:  { label: 'Veículo',   color: '#3B82F6' },
  people:    { label: 'Pessoas',   color: '#8B5CF6' },
  intrusion: { label: 'Intrusão',  color: '#EF4444' },
  plates:    { label: 'Placa',     color: '#06B6D4' },
  facial:    { label: 'Facial',    color: '#A855F7' },
  all:       { label: 'Evento',    color: '#71717A' },
}

function DetectionRow({
  item, onZoom, onDownload,
}: {
  item: DetectionItem
  onZoom: () => void
  onDownload: () => void
}) {
  const cfg = TYPE_CFG[item.type] ?? TYPE_CFG.all

  return (
    <div
      className="flex items-center gap-3 px-4 py-2.5 hover:bg-elevated/40 transition-colors border-b border-border last:border-0"
      style={{ borderLeft: `2px solid ${cfg.color}` }}
    >
      {/* Thumbnail */}
      <Thumb path={item.frame_path} onClick={onZoom} />

      {/* Type badge */}
      <span
        className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide w-20 text-center"
        style={{ color: cfg.color, background: cfg.color + '1a' }}
      >
        {cfg.label}
      </span>

      {/* Camera */}
      <div className="w-36 shrink-0 min-w-0">
        <p className="text-xs font-medium text-t1 truncate">{item.camera_name}</p>
        {item.roi_name && <p className="text-[11px] text-t3 truncate">{item.roi_name}</p>}
      </div>

      {/* Details */}
      <div className="flex-1 min-w-0 flex items-center gap-2 flex-wrap">
        {item.plate && (
          <span className="font-mono text-xs font-bold text-t1 tracking-widest bg-elevated px-2 py-0.5 rounded border border-border">
            {item.plate}
          </span>
        )}
        {item.confidence != null && (
          <span className="text-xs text-t3 tabular-nums">{Math.round(item.confidence * 100)}%</span>
        )}
        {item.dwell_seconds != null && (
          <span className="text-xs font-semibold text-t2">{fmtDwell(item.dwell_seconds)}</span>
        )}
        {item.is_valid === true && (
          <span className="flex items-center gap-0.5 text-[10px] text-success font-medium">
            <CheckCircle size={10} /> válido
          </span>
        )}
        {item.count != null && (
          <span className="text-xs font-semibold" style={{ color: cfg.color }}>
            {item.count} {item.type === 'people' ? 'pess.' : 'obj.'}
          </span>
        )}
        {item.detection_count != null && (
          <span className="text-xs font-semibold" style={{ color: cfg.color }}>
            {item.detection_count} detectados
          </span>
        )}
        {item.is_unknown === false && item.profile_name && (
          <span className="text-xs text-success font-medium truncate">{item.profile_name}</span>
        )}
        {item.is_unknown === true && (
          <span className="text-xs text-warning">Desconhecido</span>
        )}
        {item.track_id != null && (
          <span className="text-[11px] text-t3">#{item.track_id}</span>
        )}
      </div>

      {/* Timestamp */}
      <span
        title={safeFormat(item.timestamp, 'dd/MM/yyyy HH:mm:ss')}
        className="text-[11px] text-t3 whitespace-nowrap tabular-nums shrink-0 cursor-default"
      >
        {safeRelTime(item.timestamp)}
      </span>

      {/* Actions */}
      <div className="flex items-center gap-1 shrink-0">
        <button onClick={onZoom} className="btn btn-ghost h-7 w-7 p-0 text-t3 hover:text-t1">
          <ZoomIn size={13} />
        </button>
        {item.frame_path && (
          <button onClick={onDownload} className="btn btn-ghost h-7 w-7 p-0 text-t3 hover:text-t1">
            <Download size={13} />
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 30

export function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('all')
  const [items, setItems]         = useState<DetectionItem[]>([])
  const [total, setTotal]         = useState(0)
  const [page, setPage]           = useState(1)
  const [loading, setLoading]     = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null)

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const load = useCallback(async (spinner = false) => {
    spinner ? setLoading(true) : setRefreshing(true)
    try {
      const params = { page, page_size: PAGE_SIZE, ordering: '-created_at' }

      if (activeTab === 'vehicles' || activeTab === 'all') {
        const dwellParams = { ...params, ordering: '-entered_at' }
        const res = await analyticsDwellService.list(activeTab === 'all' ? { page_size: 50, ordering: '-entered_at' } : dwellParams)
        if (activeTab === 'vehicles') {
          setItems(res.results.map(dwellToItem))
          setTotal(res.count)
          return
        }
      }

      if (activeTab === 'facial') {
        const res = await analyticsFaceService.list(params)
        setItems(res.results.map(faceToItem))
        setTotal(res.count)
        return
      }

      // For 'all' or other event-based tabs
      const evParams: Record<string, unknown> = { ...params }
      if (activeTab === 'intrusion') evParams.event_type = 'intrusion.detected'
      else if (activeTab === 'people') evParams.event_type = 'motion.detected'
      else if (activeTab === 'plates') evParams.event_type = 'alpr.detected'

      const evRes = await eventService.list(evParams)

      if (activeTab === 'all') {
        // Combine dwell + events, re-sort by time
        const dwellRes = await analyticsDwellService.list({ page_size: 20, ordering: '-entered_at' })
        const combined = [
          ...dwellRes.results.map(dwellToItem),
          ...evRes.results.map(eventToItem),
        ].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        setItems(combined.slice(0, PAGE_SIZE))
        setTotal(evRes.count + dwellRes.count)
      } else {
        setItems(evRes.results.map(eventToItem))
        setTotal(evRes.count)
      }
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [activeTab, page])

  useEffect(() => { load(true) }, [load])

  // Auto-refresh every 15s
  useEffect(() => {
    const t = setInterval(() => load(false), 15_000)
    return () => clearInterval(t)
  }, [load])

  const handleTabChange = (tab: TabId) => {
    setActiveTab(tab)
    setPage(1)
    setLightboxIdx(null)
  }

  const handleDownload = (item: DetectionItem) => {
    if (!item.frame_path) return
    const a = document.createElement('a')
    a.href = snapshotUrl(item.frame_path)
    a.download = item.frame_path.split('/').pop() ?? 'snapshot.jpg'
    a.click()
  }

  // Items with snapshots only (for lightbox navigation)
  const lightboxItems = items.filter(i => i.frame_path)

  if (loading) return <PageSpinner />

  return (
    <div className="space-y-3 animate-fade-in">

      {/* ── Tab bar ── */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-1 p-1 bg-surface rounded-xl border border-border flex-wrap">
          {TABS.map(t => {
            const Icon = t.icon
            const active = t.id === activeTab
            return (
              <button
                key={t.id}
                onClick={() => handleTabChange(t.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  active ? 'shadow-sm' : 'text-t3 hover:text-t2 hover:bg-elevated/50'
                }`}
                style={active ? { background: t.color + '20', color: t.color } : {}}
              >
                <Icon size={12} />
                {t.label}
              </button>
            )
          })}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-t3 tabular-nums">{total.toLocaleString()} detecções</span>
          <button onClick={() => load(false)} className="btn btn-ghost h-8 px-2.5 text-xs gap-1.5 text-t3">
            <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
            Atualizar
          </button>
        </div>
      </div>

      {/* ── Table header ── */}
      <div className="card overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-elevated/30">
          <span className="w-20 shrink-0 text-[10px] font-semibold text-t3 uppercase tracking-wider">Foto</span>
          <span className="w-20 shrink-0 text-[10px] font-semibold text-t3 uppercase tracking-wider">Tipo</span>
          <span className="w-36 shrink-0 text-[10px] font-semibold text-t3 uppercase tracking-wider">Câmera / ROI</span>
          <span className="flex-1 text-[10px] font-semibold text-t3 uppercase tracking-wider">Detalhe</span>
          <span className="text-[10px] font-semibold text-t3 uppercase tracking-wider shrink-0">Quando</span>
          <span className="w-16 text-[10px] font-semibold text-t3 uppercase tracking-wider shrink-0 text-right">Ações</span>
        </div>

        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-t3">
            <div className="w-12 h-12 rounded-full bg-elevated flex items-center justify-center">
              <ShieldAlert size={20} strokeWidth={1.5} className="opacity-40" />
            </div>
            <p className="text-sm">Nenhuma detecção registrada</p>
            {activeTab !== 'all' && (
              <p className="text-xs">Configure ROIs do tipo correspondente na câmera para ativar</p>
            )}
          </div>
        ) : (
          <div>
            {items.map((item, idx) => {
              const lightboxIndex = lightboxItems.findIndex(i => i.id === item.id)
              return (
                <DetectionRow
                  key={item.id}
                  item={item}
                  onZoom={() => lightboxIndex >= 0 && setLightboxIdx(lightboxIndex)}
                  onDownload={() => handleDownload(item)}
                />
              )
            })}
          </div>
        )}
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-t3">Página {page} de {totalPages}</p>
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

      {/* ── Lightbox ── */}
      {lightboxIdx !== null && lightboxItems.length > 0 && (
        <Lightbox
          items={lightboxItems}
          index={lightboxIdx}
          onClose={() => setLightboxIdx(null)}
          onPrev={() => setLightboxIdx(i => Math.max(0, i! - 1))}
          onNext={() => setLightboxIdx(i => Math.min(lightboxItems.length - 1, i! + 1))}
        />
      )}
    </div>
  )
}
