import { useEffect, useRef } from 'react'

export interface BoundingBox {
  bbox: [number, number, number, number] // [x1, y1, x2, y2] in pixels
  label?: string
  confidence?: number
  color?: string
}

interface DetectionOverlayProps {
  boxes: BoundingBox[]
  /** Original frame dimensions the bbox coords refer to */
  frameWidth: number
  frameHeight: number
  className?: string
}

/**
 * Canvas overlay that draws bounding boxes on top of a video element.
 *
 * Usage:
 *   <div className="relative">
 *     <VideoPlayer ... overlay={
 *       <DetectionOverlay boxes={boxes} frameWidth={1920} frameHeight={1080} />
 *     } />
 *   </div>
 *
 * The canvas fills its parent and scales bbox coordinates proportionally.
 */
export function DetectionOverlay({ boxes, frameWidth, frameHeight, className }: DetectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const parent = canvas.parentElement
    if (!parent) return

    const rect = parent.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = rect.height

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    if (frameWidth <= 0 || frameHeight <= 0) return

    const scaleX = canvas.width / frameWidth
    const scaleY = canvas.height / frameHeight

    for (const box of boxes) {
      const [x1, y1, x2, y2] = box.bbox
      const sx = x1 * scaleX
      const sy = y1 * scaleY
      const sw = (x2 - x1) * scaleX
      const sh = (y2 - y1) * scaleY

      const color = box.color ?? '#00ff00'

      // Draw box
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.strokeRect(sx, sy, sw, sh)

      // Draw label background + text
      const label = box.label
        ? `${box.label}${box.confidence != null ? ` ${Math.round(box.confidence * 100)}%` : ''}`
        : box.confidence != null ? `${Math.round(box.confidence * 100)}%` : ''

      if (label) {
        ctx.font = '12px monospace'
        const metrics = ctx.measureText(label)
        const textH = 16
        const pad = 4

        ctx.fillStyle = color
        ctx.fillRect(sx, sy - textH - pad, metrics.width + pad * 2, textH + pad)

        ctx.fillStyle = '#000'
        ctx.fillText(label, sx + pad, sy - pad - 2)
      }
    }
  }, [boxes, frameWidth, frameHeight])

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
    />
  )
}
