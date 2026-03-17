import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Pencil, Trash2, X, Check, MousePointer } from 'lucide-react'
import { clsx } from 'clsx'
import { PageSpinner } from '@/components/ui/Spinner'
import { cameraService, roiService } from '@/services/api'
import type { Camera, ROI, ROIType, StreamInfo } from '@/types'
import toast from 'react-hot-toast'
import Hls from 'hls.js'

// ─── Constants ────────────────────────────────────────────────────────────────

const ROI_TYPES: { value: ROIType; label: string; desc: string }[] = [
  { value: 'intrusion',       label: 'Intrusão',              desc: 'Detecta pessoas na zona' },
  { value: 'human_traffic',   label: 'Tráfego Humano',        desc: 'Conta pessoas passando' },
  { value: 'vehicle_dwell',   label: 'Permanência Veicular',  desc: 'Mede tempo de parada' },
  { value: 'vehicle_traffic', label: 'Tráfego Veicular',      desc: 'Conta veículos passando' },
  { value: 'lpr',             label: 'Leitura de Placa',      desc: 'OCR de placas veiculares' },
  { value: 'line_crossing',   label: 'Cruzamento de Linha',   desc: 'Detecta cruzamento de linha' },
  { value: 'facial',          label: 'Reconhecimento Facial', desc: 'Identifica rostos cadastrados' },
  { value: 'crowd',           label: 'Multidão',              desc: 'Alerta de aglomeração' },
  { value: 'queue',           label: 'Fila',                  desc: 'Monitora comprimento de fila' },
]

const ROI_COLORS: Record<string, string> = {
  vehicle_dwell:   '#F59E0B',
  intrusion:       '#EF4444',
  human_traffic:   '#3B82F6',
  vehicle_traffic: '#8B5CF6',
  lpr:             '#22C55E',
  facial:          '#EC4899',
  line_crossing:   '#06B6D4',
  crowd:           '#F97316',
  queue:           '#A855F7',
}

const DEFAULT_COLOR = '#3B82F6'
const CLOSE_THRESHOLD = 0.025 // 2.5% of canvas width to close polygon

// ─── Types ────────────────────────────────────────────────────────────────────

type Point = [number, number] // normalized 0.0–1.0
type EditorMode = 'idle' | 'drawing'

// ─── Component ────────────────────────────────────────────────────────────────

export function ROIEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [camera, setCamera]     = useState<Camera | null>(null)
  const [stream, setStream]     = useState<StreamInfo | null>(null)
  const [rois, setRois]         = useState<ROI[]>([])
  const [loading, setLoading]   = useState(true)
  const [saving, setSaving]     = useState(false)

  // Drawing state
  const [mode, setMode]               = useState<EditorMode>('idle')
  const [draftPts, setDraftPts]       = useState<Point[]>([])
  const [cursor, setCursor]           = useState<Point | null>(null)
  const [selectedRoi, setSelectedRoi] = useState<string | null>(null)

  // Form (shown when polygon is closed)
  const [formOpen, setFormOpen]       = useState(false)
  const [pendingPts, setPendingPts]   = useState<Point[]>([])
  const [formName, setFormName]       = useState('')
  const [formType, setFormType]       = useState<ROIType>('intrusion')

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const videoRef  = useRef<HTMLVideoElement>(null)

  // ── Data loading ─────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!id) return
    Promise.all([
      cameraService.get(id),
      cameraService.live(id).catch(() => null),
      roiService.list({ camera: id }),
    ]).then(([cam, str, roiData]) => {
      setCamera(cam)
      setStream(str)
      setRois(roiData.results)
    }).catch(() => toast.error('Erro ao carregar dados'))
      .finally(() => setLoading(false))
  }, [id])

  // ── HLS player ───────────────────────────────────────────────────────────────

  useEffect(() => {
    const video = videoRef.current
    const src = stream?.hls_url
    if (!video || !src) return

    if (Hls.isSupported() && src.includes('.m3u8')) {
      const hls = new Hls({ lowLatencyMode: true, maxBufferLength: 5 })
      hls.loadSource(src)
      hls.attachMedia(video)
      hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}))
      return () => { hls.destroy(); video.src = '' }
    } else {
      video.src = src
      video.play().catch(() => {})
    }
  }, [stream?.hls_url])

  // ── Canvas draw ───────────────────────────────────────────────────────────────

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const W = canvas.width
    const H = canvas.height

    ctx.clearRect(0, 0, W, H)

    // Draw saved ROIs
    rois.forEach(roi => {
      if (roi.polygon_points.length < 3) return
      const color = ROI_COLORS[roi.ia_type] ?? DEFAULT_COLOR
      const selected = roi.id === selectedRoi

      ctx.beginPath()
      roi.polygon_points.forEach(([x, y], i) => {
        i === 0 ? ctx.moveTo(x * W, y * H) : ctx.lineTo(x * W, y * H)
      })
      ctx.closePath()
      ctx.fillStyle = color + (selected ? '40' : '25')
      ctx.fill()
      ctx.strokeStyle = color
      ctx.lineWidth = selected ? 2.5 : 1.5
      ctx.stroke()

      // Label at centroid
      const cx = roi.polygon_points.reduce((s, [x]) => s + x, 0) / roi.polygon_points.length
      const cy = roi.polygon_points.reduce((s, [, y]) => s + y, 0) / roi.polygon_points.length
      ctx.font = '11px Inter, sans-serif'
      ctx.fillStyle = '#fff'
      ctx.textAlign = 'center'
      ctx.fillText(roi.name, cx * W, cy * H)
      ctx.textAlign = 'left'
    })

    // Draw draft polygon
    if (draftPts.length > 0) {
      ctx.beginPath()
      draftPts.forEach(([x, y], i) => {
        i === 0 ? ctx.moveTo(x * W, y * H) : ctx.lineTo(x * W, y * H)
      })
      ctx.strokeStyle = 'rgba(255,255,255,0.9)'
      ctx.lineWidth = 1.5
      ctx.setLineDash([])
      ctx.stroke()

      // Dashed line to cursor
      if (cursor) {
        const [lx, ly] = draftPts[draftPts.length - 1]
        ctx.beginPath()
        ctx.moveTo(lx * W, ly * H)
        ctx.lineTo(cursor[0] * W, cursor[1] * H)
        ctx.strokeStyle = 'rgba(255,255,255,0.4)'
        ctx.setLineDash([4, 4])
        ctx.stroke()
        ctx.setLineDash([])
      }

      // Draw each point
      draftPts.forEach(([x, y], i) => {
        const isFirst = i === 0
        const nearFirst = isFirst && cursor && draftPts.length >= 3 &&
          Math.hypot(cursor[0] - x, cursor[1] - y) < CLOSE_THRESHOLD

        ctx.beginPath()
        ctx.arc(x * W, y * H, nearFirst ? 8 : isFirst ? 6 : 4, 0, Math.PI * 2)
        ctx.fillStyle = nearFirst ? '#22C55E' : isFirst ? 'var(--accent)' : '#fff'
        ctx.fill()
        ctx.strokeStyle = '#000'
        ctx.lineWidth = 1
        ctx.stroke()
      })
    }
  }, [rois, draftPts, cursor, selectedRoi])

  // Resize canvas to match container and redraw
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const resize = () => {
      const parent = canvas.parentElement
      if (!parent) return
      const { width, height } = parent.getBoundingClientRect()
      canvas.width = width
      canvas.height = height
      draw()
    }

    const observer = new ResizeObserver(resize)
    observer.observe(canvas.parentElement!)
    resize()
    return () => observer.disconnect()
  }, [draw])

  useEffect(() => { draw() }, [draw])

  // ── Canvas interaction ────────────────────────────────────────────────────────

  const toNorm = (e: React.MouseEvent<HTMLCanvasElement>): Point => {
    const rect = e.currentTarget.getBoundingClientRect()
    return [
      (e.clientX - rect.left) / rect.width,
      (e.clientY - rect.top) / rect.height,
    ]
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (mode !== 'drawing') return
    setCursor(toNorm(e))
  }

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const pt = toNorm(e)

    if (mode === 'idle') {
      // Select a saved ROI
      const canvas = canvasRef.current
      if (!canvas) return
      const W = canvas.width, H = canvas.height
      for (const roi of rois) {
        if (roi.polygon_points.length < 3) continue
        const poly = roi.polygon_points.map(([x, y]) => ({ x: x * W, y: y * H }))
        if (pointInPolygon(pt[0] * W, pt[1] * H, poly)) {
          setSelectedRoi(prev => prev === roi.id ? null : roi.id)
          return
        }
      }
      setSelectedRoi(null)
      return
    }

    if (mode === 'drawing') {
      // Try to close polygon
      if (draftPts.length >= 3) {
        const [fx, fy] = draftPts[0]
        if (Math.hypot(pt[0] - fx, pt[1] - fy) < CLOSE_THRESHOLD) {
          closeDraft()
          return
        }
      }
      setDraftPts(prev => [...prev, pt])
    }
  }

  const handleDoubleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    if (mode === 'drawing' && draftPts.length >= 3) closeDraft()
  }

  const closeDraft = () => {
    setPendingPts(draftPts)
    setDraftPts([])
    setCursor(null)
    setMode('idle')
    setFormName('')
    setFormType('intrusion')
    setFormOpen(true)
  }

  const cancelDraft = () => {
    setDraftPts([])
    setCursor(null)
    setMode('idle')
  }

  // ── Save ROI ──────────────────────────────────────────────────────────────────

  const saveROI = async () => {
    if (!formName.trim() || pendingPts.length < 3 || !id) return
    setSaving(true)
    try {
      const roi = await roiService.create({
        camera: id,
        name: formName.trim(),
        ia_type: formType,
        polygon_points: pendingPts,
      })
      setRois(prev => [...prev, roi])
      setFormOpen(false)
      toast.success(`ROI "${roi.name}" criada`)
    } catch {
      toast.error('Erro ao salvar ROI')
    } finally {
      setSaving(false)
    }
  }

  // ── Delete selected ROI ───────────────────────────────────────────────────────

  const deleteSelected = async () => {
    if (!selectedRoi) return
    try {
      await roiService.delete(selectedRoi)
      setRois(prev => prev.filter(r => r.id !== selectedRoi))
      setSelectedRoi(null)
      toast.success('ROI removida')
    } catch {
      toast.error('Erro ao remover ROI')
    }
  }

  // ── ESC cancels drawing ───────────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { cancelDraft(); setFormOpen(false) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  if (loading) return <PageSpinner />

  const selectedRoiObj = rois.find(r => r.id === selectedRoi)

  return (
    <div className="flex flex-col h-full animate-fade-in" style={{ height: 'calc(100vh - 56px - 2rem)' }}>

      {/* Header */}
      <div className="flex items-center gap-3 mb-3 shrink-0">
        <button onClick={() => navigate(`/cameras/${id}`)} className="btn btn-ghost w-8 h-8 p-0">
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-t1">Configurar ROIs</p>
          <p className="text-xs text-t3">{camera?.name}</p>
        </div>

        {/* Mode toggle */}
        {mode === 'idle' ? (
          <button
            onClick={() => { setMode('drawing'); setSelectedRoi(null) }}
            className="btn btn-primary text-xs h-9"
          >
            <Pencil size={14} /> Nova zona
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-xs text-warning animate-pulse">
              {draftPts.length === 0
                ? 'Clique para iniciar o polígono'
                : draftPts.length < 3
                ? `${draftPts.length} ponto${draftPts.length > 1 ? 's' : ''} — mínimo 3`
                : 'Clique no 1º ponto ou dê duplo clique para fechar'}
            </span>
            <button onClick={cancelDraft} className="btn btn-ghost text-xs h-9">
              <X size={14} /> Cancelar
            </button>
          </div>
        )}
      </div>

      {/* Main: video+canvas + sidebar */}
      <div className="flex gap-4 flex-1 min-h-0">

        {/* Canvas workspace */}
        <div className="flex-1 relative rounded-xl overflow-hidden bg-black">
          <video
            ref={videoRef}
            className="absolute inset-0 w-full h-full object-contain"
            muted
            playsInline
          />

          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full"
            style={{ cursor: mode === 'drawing' ? 'crosshair' : 'default' }}
            onMouseMove={handleMouseMove}
            onMouseLeave={() => setCursor(null)}
            onClick={handleClick}
            onDoubleClick={handleDoubleClick}
          />

          {/* No stream */}
          {!stream?.hls_url && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/60">
              <p className="text-xs text-zinc-500">Câmera offline — desenhe sobre a área em branco</p>
            </div>
          )}

          {/* Hint */}
          {mode === 'idle' && rois.length === 0 && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-lg text-xs text-zinc-300">
              Clique em "Nova zona" para desenhar uma ROI
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="w-56 shrink-0 flex flex-col gap-3">

          {/* Selected ROI actions */}
          {selectedRoiObj && (
            <div className="card p-3 space-y-2 border-accent/40" style={{ borderColor: 'var(--accent)' }}>
              <p className="text-xs font-semibold text-t1">{selectedRoiObj.name}</p>
              <p className="text-xs text-t3">{selectedRoiObj.ia_type}</p>
              <button onClick={deleteSelected} className="btn btn-danger text-xs w-full h-7">
                <Trash2 size={12} /> Remover ROI
              </button>
              <button onClick={() => setSelectedRoi(null)} className="btn btn-ghost text-xs w-full h-7">
                <MousePointer size={12} /> Desselecionar
              </button>
            </div>
          )}

          {/* ROI list */}
          <div className="card p-3 flex-1 overflow-y-auto">
            <p className="text-xs font-semibold text-t2 uppercase tracking-wide mb-2">
              Zonas ({rois.length})
            </p>
            {rois.length === 0 ? (
              <p className="text-xs text-t3 text-center py-4">Nenhuma ROI ainda</p>
            ) : (
              <div className="space-y-1">
                {rois.map(roi => (
                  <button
                    key={roi.id}
                    onClick={() => setSelectedRoi(prev => prev === roi.id ? null : roi.id)}
                    className={clsx(
                      'w-full flex items-center gap-2 p-2 rounded-lg text-left transition-colors',
                      selectedRoi === roi.id ? 'bg-accent/10 border border-accent/30' : 'hover:bg-elevated',
                    )}
                  >
                    <div className="w-2.5 h-2.5 rounded-sm shrink-0"
                      style={{ background: ROI_COLORS[roi.ia_type] ?? DEFAULT_COLOR }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-t1 truncate">{roi.name}</p>
                      <p className="text-xs text-t3 truncate">{roi.ia_type}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Instructions */}
          <div className="card p-3 text-xs text-t3 space-y-1">
            <p className="font-medium text-t2">Como usar</p>
            <p>• Clique para adicionar pontos</p>
            <p>• Feche no 1º ponto ou duplo-clique</p>
            <p>• Clique numa ROI para selecioná-la</p>
            <p>• ESC cancela o desenho</p>
          </div>
        </div>
      </div>

      {/* ROI form modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.6)' }}>
          <div className="card p-5 w-80 space-y-4 animate-slide-in" style={{ background: 'var(--surface)' }}>
            <p className="text-sm font-semibold text-t1">Nova zona de análise</p>

            <div>
              <label className="label">Nome</label>
              <input
                autoFocus
                className="input"
                placeholder="Ex: Vaga 01, Zona Norte..."
                value={formName}
                onChange={e => setFormName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && formName.trim() && saveROI()}
              />
            </div>

            <div>
              <label className="label">Tipo de análise</label>
              <select className="input" value={formType} onChange={e => setFormType(e.target.value as ROIType)}>
                {ROI_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label} — {t.desc}</option>
                ))}
              </select>
              <p className="text-[11px] text-t3 mt-1.5">
                {ROI_TYPES.find(t => t.value === formType)?.desc}
              </p>
            </div>

            <div className="flex gap-2 pt-1">
              <button
                className="btn btn-ghost flex-1"
                onClick={() => { setFormOpen(false); setPendingPts([]) }}
              >
                Cancelar
              </button>
              <button
                className="btn btn-primary flex-1"
                disabled={!formName.trim() || saving}
                onClick={saveROI}
              >
                <Check size={14} /> Salvar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function pointInPolygon(px: number, py: number, poly: { x: number; y: number }[]): boolean {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x, yi = poly[i].y
    const xj = poly[j].x, yj = poly[j].y
    if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}
