import { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import { Maximize2, Volume2, VolumeX, Play, Pause, Loader2, WifiOff } from 'lucide-react'
import { clsx } from 'clsx'

interface VideoPlayerProps {
  src?: string
  cameraName?: string
  autoPlay?: boolean
  muted?: boolean
  className?: string
  overlay?: React.ReactNode
}

export function VideoPlayer({
  src, cameraName, autoPlay = true, muted: initialMuted = true, className, overlay,
}: VideoPlayerProps) {
  const videoRef  = useRef<HTMLVideoElement>(null)
  const hlsRef    = useRef<Hls | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const [playing, setPlaying]   = useState(false)
  const [muted, setMuted]       = useState(initialMuted)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(false)
  const [showControls, setShowControls] = useState(false)

  useEffect(() => {
    const video = videoRef.current
    if (!video || !src) return

    setLoading(true)
    setError(false)

    if (Hls.isSupported() && src.includes('.m3u8')) {
      const hls = new Hls({ lowLatencyMode: true, maxBufferLength: 10 })
      hlsRef.current = hls
      hls.loadSource(src)
      hls.attachMedia(video)
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        if (autoPlay) video.play().catch(() => {})
      })
      hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) setError(true)
      })
    } else if (video.canPlayType('application/vnd.apple.mpegurl') || !src.includes('.m3u8')) {
      video.src = src
      if (autoPlay) video.play().catch(() => {})
    } else {
      setError(true)
    }

    return () => {
      hlsRef.current?.destroy()
      hlsRef.current = null
      video.src = ''
    }
  }, [src, autoPlay])

  const togglePlay = () => {
    const v = videoRef.current
    if (!v) return
    v.paused ? v.play() : v.pause()
  }

  const toggleMute = () => {
    const v = videoRef.current
    if (!v) return
    v.muted = !v.muted
    setMuted(v.muted)
  }

  const toggleFullscreen = () => {
    if (!containerRef.current) return
    document.fullscreenElement
      ? document.exitFullscreen()
      : containerRef.current.requestFullscreen()
  }

  return (
    <div
      ref={containerRef}
      className={clsx('relative bg-black rounded-lg overflow-hidden group select-none', className)}
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => setShowControls(false)}
    >
      {/* Video */}
      <video
        ref={videoRef}
        className="w-full h-full object-cover"
        muted={muted}
        playsInline
        onPlaying={() => { setLoading(false); setPlaying(true) }}
        onPause={() => setPlaying(false)}
        onWaiting={() => setLoading(true)}
        onError={() => setError(true)}
      />

      {/* Loading */}
      {loading && !error && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60">
          <Loader2 size={32} className="animate-spin text-white/70" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 gap-2">
          <WifiOff size={28} className="text-zinc-500" />
          <p className="text-xs text-zinc-500">Sem sinal</p>
        </div>
      )}

      {/* No source */}
      {!src && !error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
          <WifiOff size={28} className="text-zinc-600" />
          <p className="text-xs text-zinc-600">Câmera não configurada</p>
        </div>
      )}

      {/* Camera name */}
      {cameraName && (
        <div className="absolute top-2 left-2 bg-black/60 backdrop-blur-sm text-white text-xs px-2 py-0.5 rounded-md font-medium">
          {cameraName}
        </div>
      )}

      {/* Custom overlay */}
      {overlay}

      {/* Controls */}
      <div className={clsx(
        'absolute bottom-0 left-0 right-0 flex items-center gap-2 px-3 py-2 bg-gradient-to-t from-black/80 to-transparent transition-opacity duration-150',
        showControls ? 'opacity-100' : 'opacity-0',
      )}>
        <button onClick={togglePlay} className="text-white hover:text-zinc-300 transition-colors">
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </button>
        <button onClick={toggleMute} className="text-white hover:text-zinc-300 transition-colors">
          {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
        </button>
        <div className="flex-1" />
        <button onClick={toggleFullscreen} className="text-white hover:text-zinc-300 transition-colors">
          <Maximize2 size={16} />
        </button>
      </div>
    </div>
  )
}
