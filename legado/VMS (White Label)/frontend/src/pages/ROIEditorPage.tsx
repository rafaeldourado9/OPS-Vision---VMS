import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Save, Trash2, Plus, Undo2, ArrowLeft, MousePointer, X,
  GripVertical, Eye, EyeOff, Settings2, Move, Pencil,
} from 'lucide-react'
import { clsx } from 'clsx'
import { cameraService, roiService, maskService } from '@/services/api'
import { PageSpinner } from '@/components/ui/Spinner'
import { Modal } from '@/components/ui/Modal'
import toast from 'react-hot-toast'
import type { Camera, ROI, ROIType } from '@/types'

// ---------------------------------------------------------------------------
// ROI type metadata
// ---------------------------------------------------------------------------

interface ROITypeMeta {
  value: ROIType
  label: string
  color: string
  isLine: boolean
  configFields?: ConfigFieldDef[]
}

interface ConfigFieldDef {
  key: string
  label: string
  type: 'number' | 'select' | 'multiselect' | 'text'
  default?: unknown
  min?: number
  max?: number
  options?: { value: string; label: string }[]
  placeholder?: string
}

const COCO_CLASSES = [
  'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck',
  'cat', 'dog', 'suitcase', 'backpack', 'handbag', 'umbrella',
]

const ROI_TYPES: ROITypeMeta[] = [
  {
    value: 'intrusion', label: 'Intrusão', color: '#EF4444', isLine: false,
    configFields: [
      { key: 'classes', label: 'Classes', type: 'multiselect', default: ['person'], options: COCO_CLASSES.map(c => ({ value: c, label: c })) },
    ],
  },
  {
    value: 'crowd', label: 'Detecção de Multidão', color: '#8B5CF6', isLine: false,
    configFields: [
      { key: 'threshold', label: 'Threshold (pessoas)', type: 'number', default: 5, min: 1, max: 100 },
    ],
  },
  {
    value: 'object_detected', label: 'Detecção de Objetos', color: '#06B6D4', isLine: false,
    configFields: [
      { key: 'classes', label: 'Classes', type: 'multiselect', default: ['person', 'car'], options: COCO_CLASSES.map(c => ({ value: c, label: c })) },
    ],
  },
  {
    value: 'loitering', label: 'Perambulação', color: '#EC4899', isLine: false,
    configFields: [
      { key: 'max_seconds', label: 'Tempo máximo (seg)', type: 'number', default: 30, min: 5, max: 600 },
    ],
  },
  {
    value: 'abandoned_object', label: 'Objeto Abandonado', color: '#F97316', isLine: false,
    configFields: [
      { key: 'max_seconds', label: 'Tempo sem dono (seg)', type: 'number', default: 60, min: 10, max: 600 },
    ],
  },
  {
    value: 'queue', label: 'Detecção de Fila', color: '#84CC16', isLine: false,
    configFields: [
      { key: 'threshold', label: 'Pessoas para alerta', type: 'number', default: 5, min: 1, max: 50 },
      { key: 'alert_after_seconds', label: 'Alertar após (seg)', type: 'number', default: 60, min: 10, max: 600 },
    ],
  },
  {
    value: 'lpr', label: 'Reconhecimento de Placa', color: '#22C55E', isLine: false,
    configFields: [
      { key: 'direction', label: 'Direção', type: 'select', default: 'both', options: [{ value: 'entry', label: 'Entrada' }, { value: 'exit', label: 'Saída' }, { value: 'both', label: 'Ambos' }] },
    ],
  },
  {
    value: 'facial', label: 'Reconhecimento Facial', color: '#A78BFA', isLine: false,
    configFields: [
      { key: 'similarity_threshold', label: 'Similaridade mín.', type: 'number', default: 0.6, min: 0.3, max: 0.95 },
    ],
  },
  {
    value: 'human_traffic', label: 'Tráfego Humano', color: '#3B82F6', isLine: false,
    configFields: [
      { key: 'direction', label: 'Direção', type: 'select', default: 'both', options: [{ value: 'in', label: 'Entrada' }, { value: 'out', label: 'Saída' }, { value: 'both', label: 'Ambos' }] },
    ],
  },
  {
    value: 'vehicle_traffic', label: 'Tráfego Veicular', color: '#F59E0B', isLine: false,
    configFields: [
      { key: 'direction', label: 'Direção', type: 'select', default: 'both', options: [{ value: 'in', label: 'Entrada' }, { value: 'out', label: 'Saída' }, { value: 'both', label: 'Ambos' }] },
    ],
  },
  { value: 'line_crossing', label: 'Cruzamento de Linha', color: '#FCD34D', isLine: true,
    configFields: [
      { key: 'direction', label: 'Direção', type: 'select', default: 'both', options: [{ value: 'in', label: 'Entrada' }, { value: 'out', label: 'Saída' }, { value: 'both', label: 'Ambos' }] },
    ],
  },
  { value: 'heatmap', label: 'Mapa de Calor', color: '#FB7185', isLine: false },
]

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Point = { x: number; y: number }

interface DrawingROI {
  id?: string
  name: string
  ia_type: ROIType
  points: Point[]
  config: Record<string, unknown>
  color: string
  isLine: boolean
  saved: boolean
  visible: boolean
}

// ---------------------------------------------------------------------------
// SVG Helpers
// ---------------------------------------------------------------------------

function pointsToSvg(pts: Point[], w: number, h: number) {
  return pts.map(p => `${p.x * w},${p.y * h}`).join(' ')
}

function centroid(pts: Point[]): Point {
  const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length
  const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length
  return { x: cx, y: cy }
}

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v))
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ROIEditorPage() {
  const { id: cameraId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const [camera, setCamera] = useState<Camera | null>(null)
  const [rois, setRois] = useState<DrawingROI[]>([])
  const [activeRoi, setActiveRoi] = useState<number | null>(null)
  const [mode, setMode] = useState<'select' | 'draw'>('select')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleteIdx, setDeleteIdx] = useState<number | null>(null)
  const [configIdx, setConfigIdx] = useState<number | null>(null)

  // Snapshot background
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null)
  const [imgSize, setImgSize] = useState({ w: 1280, h: 720 })

  // New ROI modal
  const [newType, setNewType] = useState<ROIType>('intrusion')
  const [newName, setNewName] = useState('')
  const [addModal, setAddModal] = useState(false)

  // Drag state (for point/polygon moving)
  const dragRef = useRef<{
    type: 'point' | 'polygon'
    roiIdx: number
    pointIdx?: number
    startPts?: Point[]
    startMouse?: Point
  } | null>(null)

  // ---------- Load data ----------

  useEffect(() => {
    if (!cameraId) return
    Promise.all([
      cameraService.get(cameraId),
      roiService.list({ camera_id: cameraId }),
    ]).then(([cam, roisData]) => {
      setCamera(cam)
      const loaded: DrawingROI[] = roisData.results.map((r: ROI) => {
        const meta = ROI_TYPES.find(t => t.value === r.ia_type)
        return {
          id: r.id,
          name: r.name,
          ia_type: r.ia_type,
          points: r.polygon_points.map((p: number[]) => ({ x: p[0], y: p[1] })),
          config: r.config ?? {},
          color: meta?.color ?? '#3B82F6',
          isLine: meta?.isLine ?? false,
          saved: true,
          visible: true,
        }
      })
      setRois(loaded)
    }).finally(() => setLoading(false))
  }, [cameraId])

  // Load snapshot
  useEffect(() => {
    if (!cameraId) return
    const raw = localStorage.getItem('auth-storage')
    const token = raw ? (JSON.parse(raw)?.state?.accessToken ?? '') : ''
    const url = `/api/v1/cameras/${cameraId}/snapshot/?t=${Date.now()}&token=${token}`
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.src = url
    img.onload = () => {
      setSnapshotUrl(url)
      setImgSize({ w: img.naturalWidth, h: img.naturalHeight })
    }
    img.onerror = () => setSnapshotUrl(null)
  }, [cameraId])

  // ---------- SVG coordinate helpers ----------

  const svgPoint = useCallback((e: React.MouseEvent | MouseEvent): Point => {
    const svg = svgRef.current!
    const rect = svg.getBoundingClientRect()
    return {
      x: clamp((e.clientX - rect.left) / rect.width, 0, 1),
      y: clamp((e.clientY - rect.top) / rect.height, 0, 1),
    }
  }, [])

  // ---------- Drawing mode handlers ----------

  const handleSvgClick = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (mode !== 'draw' || activeRoi === null) return
    const pt = svgPoint(e)
    const roi = rois[activeRoi]

    // Auto-close polygon: click near first point
    if (!roi.isLine && roi.points.length >= 3) {
      const first = roi.points[0]
      const svg = svgRef.current!
      const rect = svg.getBoundingClientRect()
      const dist = Math.hypot((pt.x - first.x) * rect.width, (pt.y - first.y) * rect.height)
      if (dist < 15) {
        setMode('select')
        toast.success('Polígono fechado.')
        return
      }
    }

    // Auto-close line: 2 points
    if (roi.isLine && roi.points.length >= 1) {
      setRois(prev => prev.map((r, i) =>
        i === activeRoi ? { ...r, points: [...r.points, pt], saved: false } : r
      ))
      setMode('select')
      toast.success('Linha definida.')
      return
    }

    setRois(prev => prev.map((r, i) =>
      i === activeRoi ? { ...r, points: [...r.points, pt], saved: false } : r
    ))
  }, [mode, activeRoi, rois, svgPoint])

  const handleSvgDblClick = useCallback(() => {
    if (mode !== 'draw' || activeRoi === null) return
    const roi = rois[activeRoi]
    if (roi.points.length >= 3) {
      setMode('select')
      toast.success('Polígono fechado.')
    }
  }, [mode, activeRoi, rois])

  // ---------- Drag handlers (SVG) ----------

  const startPointDrag = useCallback((roiIdx: number, pointIdx: number, e: React.MouseEvent) => {
    if (mode !== 'select') return
    e.preventDefault()
    e.stopPropagation()
    setActiveRoi(roiIdx)
    dragRef.current = { type: 'point', roiIdx, pointIdx }

    const handleMove = (me: MouseEvent) => {
      const pt = svgPoint(me)
      setRois(prev => prev.map((r, i) => {
        if (i !== roiIdx) return r
        const newPts = [...r.points]
        newPts[pointIdx] = pt
        return { ...r, points: newPts, saved: false }
      }))
    }
    const handleUp = () => {
      dragRef.current = null
      document.removeEventListener('mousemove', handleMove)
      document.removeEventListener('mouseup', handleUp)
    }
    document.addEventListener('mousemove', handleMove)
    document.addEventListener('mouseup', handleUp)
  }, [mode, svgPoint])

  const startPolygonDrag = useCallback((roiIdx: number, e: React.MouseEvent) => {
    if (mode !== 'select') return
    e.preventDefault()
    e.stopPropagation()
    setActiveRoi(roiIdx)
    const startMouse = svgPoint(e)
    const startPts = [...rois[roiIdx].points]
    dragRef.current = { type: 'polygon', roiIdx, startPts, startMouse }

    const handleMove = (me: MouseEvent) => {
      const current = svgPoint(me)
      const dx = current.x - startMouse.x
      const dy = current.y - startMouse.y
      setRois(prev => prev.map((r, i) => {
        if (i !== roiIdx) return r
        const newPts = startPts.map(p => ({
          x: clamp(p.x + dx, 0, 1),
          y: clamp(p.y + dy, 0, 1),
        }))
        return { ...r, points: newPts, saved: false }
      }))
    }
    const handleUp = () => {
      dragRef.current = null
      document.removeEventListener('mousemove', handleMove)
      document.removeEventListener('mouseup', handleUp)
    }
    document.addEventListener('mousemove', handleMove)
    document.addEventListener('mouseup', handleUp)
  }, [mode, rois, svgPoint])

  // ---------- Keyboard ----------

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (mode !== 'draw' || activeRoi === null) return
      if (e.key === 'Enter') {
        setMode('select')
        toast.success('Polígono fechado.')
      } else if (e.key === 'Escape') {
        setMode('select')
      } else if (e.key === 'z' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        setRois(prev => prev.map((r, i) =>
          i === activeRoi ? { ...r, points: r.points.slice(0, -1) } : r
        ))
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [mode, activeRoi])

  // ---------- CRUD ----------

  const startNewROI = () => {
    const meta = ROI_TYPES.find(t => t.value === newType)!
    const defaultConfig: Record<string, unknown> = {}
    meta.configFields?.forEach(f => {
      if (f.default !== undefined) defaultConfig[f.key] = f.default
    })
    const roi: DrawingROI = {
      name: newName || meta.label,
      ia_type: newType,
      points: [],
      config: defaultConfig,
      color: meta.color,
      isLine: meta.isLine,
      saved: false,
      visible: true,
    }
    setRois(prev => [...prev, roi])
    setActiveRoi(rois.length)
    setMode('draw')
    setAddModal(false)
    setNewName('')
    toast(meta.isLine
      ? 'Clique 2 pontos para a linha.'
      : 'Clique para adicionar pontos. Enter ou duplo clique para fechar.', { icon: '✏️' })
  }

  const handleSaveROI = async (idx: number) => {
    if (!cameraId) return
    const roi = rois[idx]
    if (roi.points.length < (roi.isLine ? 2 : 3)) {
      toast.error(roi.isLine ? 'Linha precisa de 2 pontos' : 'Polígono precisa de 3 pontos')
      return
    }
    setSaving(true)
    try {
      const polygon = roi.points.map(p => [p.x, p.y])
      if (roi.id) {
        await roiService.update(roi.id, {
          name: roi.name, ia_type: roi.ia_type, polygon_points: polygon, config: roi.config,
        })
      } else {
        const created = await roiService.create({
          camera: cameraId, name: roi.name, ia_type: roi.ia_type,
          polygon_points: polygon, enabled: true, config: roi.config,
        })
        setRois(prev => prev.map((r, i) => i === idx ? { ...r, id: created.id, saved: true } : r))
      }
      setRois(prev => prev.map((r, i) => i === idx ? { ...r, saved: true } : r))
      toast.success('ROI salva!')
    } catch { toast.error('Erro ao salvar ROI') }
    finally { setSaving(false) }
  }

  const handleDeleteROI = async (idx: number) => {
    const roi = rois[idx]
    try {
      if (roi.id) await roiService.delete(roi.id)
      setRois(prev => prev.filter((_, i) => i !== idx))
      if (activeRoi === idx) { setActiveRoi(null); setMode('select') }
      else if (activeRoi !== null && activeRoi > idx) setActiveRoi(activeRoi - 1)
      toast.success('ROI removida')
    } catch { toast.error('Erro ao remover') }
    setDeleteIdx(null)
  }

  // ---------- Config panel helpers ----------

  const activeConfig = configIdx !== null ? rois[configIdx] : null
  const activeMeta = activeConfig ? ROI_TYPES.find(t => t.value === activeConfig.ia_type) : null

  const updateConfig = (key: string, value: unknown) => {
    if (configIdx === null) return
    setRois(prev => prev.map((r, i) =>
      i === configIdx ? { ...r, config: { ...r.config, [key]: value }, saved: false } : r
    ))
  }

  // ---------- Aspect ratio ----------

  const aspectRatio = imgSize.w / imgSize.h
  const svgViewBox = `0 0 1000 ${Math.round(1000 / aspectRatio)}`
  const svgW = 1000
  const svgH = Math.round(1000 / aspectRatio)

  // ---------- Render ----------

  if (loading) return <PageSpinner />

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button className="btn btn-ghost w-8 h-8 p-0" onClick={() => navigate(`/cameras/${cameraId}`)}>
          <ArrowLeft size={18} />
        </button>
        <div>
          <p className="text-sm font-semibold text-t1">Editor de ROI — {camera?.name}</p>
          <p className="text-xs text-t3">
            {mode === 'draw'
              ? 'Modo desenho — clique para adicionar pontos'
              : 'Modo seleção — arraste pontos ou polígonos para ajustar'}
          </p>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-1 text-xs">
          <button
            className={clsx('btn gap-1 text-xs', mode === 'select' ? 'btn-primary' : 'btn-ghost')}
            onClick={() => setMode('select')}>
            <Move size={14} />Selecionar
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* SVG Canvas */}
        <div className="lg:col-span-3" ref={containerRef}>
          <div className="card overflow-hidden bg-black">
            <svg
              ref={svgRef}
              viewBox={svgViewBox}
              className={clsx('w-full block', mode === 'draw' ? 'cursor-crosshair' : 'cursor-default')}
              onClick={handleSvgClick}
              onDoubleClick={handleSvgDblClick}
              style={{ userSelect: 'none' }}
            >
              {/* Snapshot background */}
              {snapshotUrl && (
                <image href={snapshotUrl} x="0" y="0" width={svgW} height={svgH} preserveAspectRatio="xMidYMid slice" />
              )}
              {/* Dark overlay */}
              <rect x="0" y="0" width={svgW} height={svgH} fill="rgba(0,0,0,0.25)" pointerEvents="none" />

              {/* ROIs */}
              {rois.map((roi, idx) => {
                if (!roi.visible || roi.points.length === 0) return null
                const isActive = activeRoi === idx
                const color = roi.color
                const pts = roi.points.map(p => ({ x: p.x * svgW, y: p.y * svgH }))
                const center = centroid(pts)

                return (
                  <g key={idx}>
                    {/* Polygon / Line */}
                    {roi.isLine ? (
                      <polyline
                        points={pts.map(p => `${p.x},${p.y}`).join(' ')}
                        fill="none"
                        stroke={color}
                        strokeWidth={isActive ? 4 : 2.5}
                        strokeDasharray={isActive ? 'none' : '10 5'}
                        style={{ cursor: mode === 'select' && isActive ? 'grab' : 'pointer', pointerEvents: 'stroke' }}
                        onMouseDown={e => mode === 'select' && isActive ? startPolygonDrag(idx, e) : setActiveRoi(idx)}
                        onClick={e => { e.stopPropagation(); setActiveRoi(idx) }}
                      />
                    ) : (
                      <polygon
                        points={pts.map(p => `${p.x},${p.y}`).join(' ')}
                        fill={color + (isActive ? '40' : '20')}
                        stroke={isActive ? '#fff' : color}
                        strokeWidth={isActive ? 3 : 2}
                        style={{ cursor: mode === 'select' && isActive ? 'grab' : 'pointer' }}
                        onMouseDown={e => mode === 'select' && isActive ? startPolygonDrag(idx, e) : setActiveRoi(idx)}
                        onClick={e => { e.stopPropagation(); setActiveRoi(idx) }}
                      />
                    )}

                    {/* Draggable points (only when active + select mode) */}
                    {isActive && mode === 'select' && pts.map((p, pIdx) => (
                      <circle
                        key={pIdx}
                        cx={p.x} cy={p.y} r={10}
                        fill={color} stroke="#fff" strokeWidth={2}
                        style={{ cursor: 'move' }}
                        onMouseDown={e => startPointDrag(idx, pIdx, e)}
                      />
                    ))}

                    {/* Label */}
                    <text
                      x={center.x} y={center.y}
                      textAnchor="middle" dominantBaseline="middle"
                      fill={color} stroke="rgba(0,0,0,0.7)" strokeWidth={3}
                      paintOrder="stroke" fontSize={isActive ? 22 : 18} fontWeight="bold"
                      style={{ pointerEvents: 'none' }}
                    >
                      {roi.name}
                    </text>
                  </g>
                )
              })}
            </svg>
          </div>

          {/* Canvas toolbar */}
          <div className="flex items-center gap-2 mt-2">
            {mode === 'draw' && (
              <>
                <p className="text-xs text-t3 flex-1">
                  <span className="text-accent font-medium">Desenhando</span> — clique para pontos · Enter/duplo clique fecha · Ctrl+Z desfaz
                </p>
                <button className="btn btn-ghost gap-1 text-xs" onClick={() => {
                  if (activeRoi !== null) setRois(prev => prev.map((r, i) =>
                    i === activeRoi ? { ...r, points: r.points.slice(0, -1) } : r
                  ))
                }}>
                  <Undo2 size={14} />Desfazer
                </button>
                <button className="btn btn-ghost gap-1 text-xs text-danger" onClick={() => setMode('select')}>
                  <X size={14} />Cancelar
                </button>
              </>
            )}
            {mode === 'select' && (
              <p className="text-xs text-t3">
                <MousePointer size={12} className="inline mr-1" />
                Clique numa ROI para selecionar · Arraste pontos para ajustar · Arraste polígono para mover
              </p>
            )}
          </div>
        </div>

        {/* ROI Panel */}
        <div className="space-y-3">
          <button className="btn btn-primary w-full gap-2" onClick={() => setAddModal(true)} disabled={mode === 'draw'}>
            <Plus size={15} />Nova ROI
          </button>

          <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
            {rois.length === 0 && (
              <div className="card p-6 text-center">
                <p className="text-xs text-t3">Nenhuma ROI configurada</p>
              </div>
            )}
            {rois.map((roi, idx) => {
              const meta = ROI_TYPES.find(t => t.value === roi.ia_type)
              const isActive = activeRoi === idx
              return (
                <div key={idx}
                  className={clsx('card p-3 cursor-pointer transition-all', isActive && 'ring-1')}
                  style={isActive ? { boxShadow: `0 0 0 1px ${roi.color}` } : {}}
                  onClick={() => { setActiveRoi(idx); setMode('select') }}>
                  <div className="flex items-start gap-2">
                    <div className="w-3 h-3 rounded-sm mt-0.5 shrink-0" style={{ background: roi.color }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-t1 truncate">{roi.name}</p>
                      <p className="text-xs text-t3">{meta?.label}</p>
                      <p className="text-xs text-t3">{roi.points.length} pontos {!roi.saved && '· não salvo'}</p>
                    </div>
                    <div className="flex flex-col gap-1">
                      {/* Toggle visibility */}
                      <button className="btn btn-ghost w-6 h-6 p-0 rounded-md" title={roi.visible ? 'Ocultar' : 'Mostrar'}
                        onClick={e => { e.stopPropagation(); setRois(prev => prev.map((r, i) => i === idx ? { ...r, visible: !r.visible } : r)) }}>
                        {roi.visible ? <Eye size={12} /> : <EyeOff size={12} />}
                      </button>
                      {/* Config */}
                      {meta?.configFields && (
                        <button className="btn btn-ghost w-6 h-6 p-0 rounded-md" title="Configurar"
                          onClick={e => { e.stopPropagation(); setConfigIdx(idx) }}>
                          <Settings2 size={12} />
                        </button>
                      )}
                      {/* Redraw */}
                      <button className="btn btn-ghost w-6 h-6 p-0 rounded-md" title="Redesenhar"
                        onClick={e => {
                          e.stopPropagation()
                          setRois(prev => prev.map((r, i) => i === idx ? { ...r, points: [], saved: false } : r))
                          setActiveRoi(idx)
                          setMode('draw')
                        }}>
                        <Pencil size={12} />
                      </button>
                      {/* Save */}
                      {!roi.saved && (
                        <button className="btn btn-primary w-6 h-6 p-0 rounded-md" title="Salvar"
                          disabled={saving}
                          onClick={e => { e.stopPropagation(); handleSaveROI(idx) }}>
                          <Save size={12} />
                        </button>
                      )}
                      {/* Delete */}
                      <button className="btn btn-ghost w-6 h-6 p-0 rounded-md text-danger hover:text-danger" title="Remover"
                        onClick={e => { e.stopPropagation(); setDeleteIdx(idx) }}>
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* ROI type legend */}
          <div className="card p-3">
            <p className="text-xs font-medium text-t2 mb-2">Tipos disponíveis</p>
            <div className="space-y-1">
              {ROI_TYPES.map(t => (
                <div key={t.value} className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-sm shrink-0" style={{ background: t.color }} />
                  <p className="text-xs text-t3">{t.label}</p>
                  {t.isLine && <span className="text-[10px] text-t3 ml-auto">linha</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ─── Add ROI Modal ─── */}
      <Modal open={addModal} onClose={() => setAddModal(false)} title="Nova Área de Análise" size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setAddModal(false)}>Cancelar</button>
            <button className="btn btn-primary gap-2" onClick={startNewROI}>
              <Plus size={15} />Iniciar Desenho
            </button>
          </>
        }>
        <div className="space-y-4">
          <div>
            <label className="label">Tipo de Analítico</label>
            <select className="input" value={newType} onChange={e => setNewType(e.target.value as ROIType)}>
              {ROI_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}{t.isLine ? ' (linha)' : ''}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Nome da ROI <span className="text-t3">(opcional)</span></label>
            <input className="input" placeholder="Ex: Entrada Principal"
              value={newName} onChange={e => setNewName(e.target.value)} />
          </div>
          <div className="flex items-center gap-2 p-3 rounded-lg text-xs text-t3" style={{ background: 'var(--elevated)' }}>
            <div className="w-3 h-3 rounded-sm shrink-0" style={{ background: ROI_TYPES.find(t => t.value === newType)?.color }} />
            {ROI_TYPES.find(t => t.value === newType)?.isLine
              ? 'Clique 2 pontos para definir a linha de cruzamento'
              : 'Clique no canvas para adicionar vértices do polígono'}
          </div>
        </div>
      </Modal>

      {/* ─── Config Modal ─── */}
      <Modal open={configIdx !== null} onClose={() => setConfigIdx(null)}
        title={activeConfig ? `Configurar — ${activeConfig.name}` : ''} size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setConfigIdx(null)}>Fechar</button>
            {configIdx !== null && !rois[configIdx].saved && (
              <button className="btn btn-primary gap-2" disabled={saving}
                onClick={() => { handleSaveROI(configIdx); setConfigIdx(null) }}>
                <Save size={15} />Salvar
              </button>
            )}
          </>
        }>
        {activeMeta?.configFields && (
          <div className="space-y-4">
            {activeMeta.configFields.map(field => (
              <div key={field.key}>
                <label className="label">{field.label}</label>
                {field.type === 'number' && (
                  <input
                    type="number"
                    className="input"
                    min={field.min} max={field.max}
                    step={field.max && field.max < 1 ? 0.05 : 1}
                    value={(activeConfig?.config[field.key] as number) ?? field.default ?? ''}
                    onChange={e => updateConfig(field.key, parseFloat(e.target.value) || 0)}
                  />
                )}
                {field.type === 'select' && (
                  <select className="input"
                    value={(activeConfig?.config[field.key] as string) ?? field.default ?? ''}
                    onChange={e => updateConfig(field.key, e.target.value)}>
                    {field.options?.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                )}
                {field.type === 'multiselect' && (
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {field.options?.map(o => {
                      const selected = ((activeConfig?.config[field.key] as string[]) ?? (field.default as string[]) ?? [])
                      const isOn = selected.includes(o.value)
                      return (
                        <button key={o.value}
                          className={clsx('px-2 py-0.5 rounded text-xs border transition-all',
                            isOn ? 'bg-accent/20 border-accent text-accent' : 'border-border text-t3 hover:border-t2')}
                          onClick={() => {
                            const next = isOn ? selected.filter(v => v !== o.value) : [...selected, o.value]
                            updateConfig(field.key, next)
                          }}>
                          {o.label}
                        </button>
                      )
                    })}
                  </div>
                )}
                {field.type === 'text' && (
                  <input className="input" placeholder={field.placeholder}
                    value={(activeConfig?.config[field.key] as string) ?? ''}
                    onChange={e => updateConfig(field.key, e.target.value)} />
                )}
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* ─── Delete Confirm ─── */}
      <Modal open={deleteIdx !== null} onClose={() => setDeleteIdx(null)} title="Remover ROI" size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setDeleteIdx(null)}>Cancelar</button>
            <button className="btn btn-danger" onClick={() => deleteIdx !== null && handleDeleteROI(deleteIdx)}>
              <Trash2 size={15} />Remover
            </button>
          </>
        }>
        <p className="text-sm text-t2">
          Tem certeza que deseja remover a ROI <strong className="text-t1">"{rois[deleteIdx ?? 0]?.name}"</strong>?
        </p>
      </Modal>
    </div>
  )
}
