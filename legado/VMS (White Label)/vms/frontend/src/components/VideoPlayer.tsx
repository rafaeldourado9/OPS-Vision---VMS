import { useCallback, useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import { Maximize, Minimize, Pause, Play, Volume2, VolumeX } from 'lucide-react'

function fmtTime(s: number): string {
  if (!isFinite(s) || isNaN(s) || s < 0) return '--:--'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

interface VideoPlayerProps {
  src: string
  autoPlay?: boolean
  /** 'live' = LIVE badge, no seekbar. 'vod' = seekbar + timestamps. Default: 'live' */
  mode?: 'live' | 'vod'
  className?: string
}

export default function VideoPlayer({ src, autoPlay = true, mode = 'live', className = '' }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const hlsRef = useRef<Hls | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(true)
  const [muted, setMuted] = useState(true)
  const [volume, setVolume] = useState(1)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [buffered, setBuffered] = useState(0)
  const [showCtrl, setShowCtrl] = useState(true)
  const [isFs, setIsFs] = useState(false)
  const [err, setErr] = useState(false)

  // HLS / native setup
  useEffect(() => {
    const video = videoRef.current
    if (!video || !src) return
    setErr(false)
    setLoading(true)
    setPlaying(false)
    setCurrentTime(0)
    setDuration(0)

    if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: mode === 'live',
        liveSyncDurationCount: 3,
        maxBufferLength: mode === 'vod' ? 60 : 30,
      })
      hlsRef.current = hls
      hls.loadSource(src)
      hls.attachMedia(video)
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        setLoading(false)
        if (autoPlay) video.play().catch(() => {})
      })
      hls.on(Hls.Events.ERROR, (_ev, data) => {
        if (data.fatal) {
          if (data.type === Hls.ErrorTypes.NETWORK_ERROR) setTimeout(() => hls.startLoad(), 3000)
          else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) hls.recoverMediaError()
          else { setErr(true); setLoading(false) }
        }
      })
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src
      setLoading(false)
      if (autoPlay) video.play().catch(() => {})
    }

    return () => { hlsRef.current?.destroy(); hlsRef.current = null }
  }, [src, autoPlay, mode])

  // Media event listeners
  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    const onPlay = () => setPlaying(true)
    const onPause = () => setPlaying(false)
    const onWait = () => setLoading(true)
    const onCan = () => setLoading(false)
    const onTime = () => {
      setCurrentTime(v.currentTime)
      if (v.buffered.length > 0) setBuffered(v.buffered.end(v.buffered.length - 1))
    }
    const onDur = () => setDuration(v.duration)
    const onFs = () => setIsFs(!!document.fullscreenElement)
    v.addEventListener('play', onPlay)
    v.addEventListener('pause', onPause)
    v.addEventListener('waiting', onWait)
    v.addEventListener('canplay', onCan)
    v.addEventListener('timeupdate', onTime)
    v.addEventListener('durationchange', onDur)
    document.addEventListener('fullscreenchange', onFs)
    return () => {
      v.removeEventListener('play', onPlay)
      v.removeEventListener('pause', onPause)
      v.removeEventListener('waiting', onWait)
      v.removeEventListener('canplay', onCan)
      v.removeEventListener('timeupdate', onTime)
      v.removeEventListener('durationchange', onDur)
      document.removeEventListener('fullscreenchange', onFs)
    }
  }, [])

  const nudgeCtrl = useCallback(() => {
    setShowCtrl(true)
    if (hideTimer.current) clearTimeout(hideTimer.current)
    hideTimer.current = setTimeout(() => setShowCtrl(false), 3000)
  }, [])

  const togglePlay = useCallback(() => {
    const v = videoRef.current
    if (!v) return
    if (v.paused) v.play().catch(() => {})
    else v.pause()
  }, [])

  const handleVolume = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const v = videoRef.current
    if (!v) return
    const val = Number(e.target.value)
    v.volume = val
    v.muted = val === 0
    setVolume(val)
    setMuted(val === 0)
  }, [])

  const handleSeek = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const v = videoRef.current
    if (!v || !isFinite(duration)) return
    const val = Number(e.target.value)
    v.currentTime = val
    setCurrentTime(val)
  }, [duration])

  const toggleFs = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    if (!document.fullscreenElement) el.requestFullscreen().catch(() => {})
    else document.exitFullscreen()
  }, [])

  const isLive = mode === 'live' || !isFinite(duration) || duration === 0
  const prog = (isLive || duration === 0) ? 0 : Math.min((currentTime / duration) * 100, 100)
  const buf = (isLive || duration === 0) ? 0 : Math.min((buffered / duration) * 100, 100)

  return (
    <div
      ref={containerRef}
      className={`relative bg-black overflow-hidden w-full h-full select-none cursor-pointer ${className}`}
      onMouseMove={nudgeCtrl}
      onMouseEnter={nudgeCtrl}
      onMouseLeave={() => playing && setShowCtrl(false)}
      onClick={togglePlay}
    >
      <video ref={videoRef} className="w-full h-full object-contain" muted={muted} playsInline />

      {/* Loading spinner */}
      {loading && !err && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 pointer-events-none">
          <div className="w-10 h-10 rounded-full border-2 border-white/20 border-t-white animate-spin" />
        </div>
      )}

      {/* Error */}
      {err && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/80 pointer-events-none">
          <span className="text-3xl">⚠️</span>
          <p className="text-sm text-gray-400">Falha ao carregar stream</p>
        </div>
      )}

      {/* LIVE badge */}
      {isLive && !err && !loading && (
        <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-red-600/90 text-white text-xs font-bold px-2.5 py-1 rounded-full pointer-events-none">
          <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
          AO VIVO
        </div>
      )}

      {/* Controls overlay */}
      <div
        className={`absolute inset-x-0 bottom-0 transition-opacity duration-300 ${
          showCtrl || !playing ? 'opacity-100' : 'opacity-0'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Gradient scrim */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent pointer-events-none" />

        {/* Seekbar — VOD only */}
        {!isLive && (
          <div className="relative px-4 pt-5 pb-0">
            <div className="relative h-5 flex items-center group/seek">
              {/* Track */}
              <div className="relative w-full h-1 rounded-full bg-white/20 pointer-events-none">
                <div className="absolute inset-y-0 left-0 rounded-full bg-white/30" style={{ width: `${buf}%` }} />
                <div className="absolute inset-y-0 left-0 rounded-full bg-blue-500" style={{ width: `${prog}%` }} />
              </div>
              {/* Thumb dot */}
              <div
                className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full bg-white shadow-lg opacity-0 group-hover/seek:opacity-100 transition-opacity pointer-events-none"
                style={{ left: `${prog}%` }}
              />
              {/* Invisible range input for interaction */}
              <input
                type="range"
                min={0}
                max={duration || 100}
                step={0.25}
                value={currentTime}
                onChange={handleSeek}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
            </div>
          </div>
        )}

        {/* Buttons */}
        <div className="relative flex items-center gap-1 px-3 py-2">
          <button
            onClick={() => togglePlay()}
            className="text-white hover:text-blue-400 transition-colors p-1.5 rounded-lg"
            title={playing ? 'Pausar' : 'Reproduzir'}
          >
            {playing ? <Pause size={18} /> : <Play size={18} />}
          </button>

          {!isLive && (
            <span className="text-xs text-gray-300 tabular-nums select-none ml-0.5">
              {fmtTime(currentTime)} / {fmtTime(duration)}
            </span>
          )}

          <div className="flex-1" />

          <button
            onClick={() => { const v = videoRef.current; if (!v) return; v.muted = !v.muted; setMuted(v.muted) }}
            className="text-white hover:text-blue-400 transition-colors p-1.5 rounded-lg"
            title="Volume"
          >
            {muted || volume === 0 ? <VolumeX size={16} /> : <Volume2 size={16} />}
          </button>
          <input
            type="range"
            min={0} max={1} step={0.05}
            value={muted ? 0 : volume}
            onChange={handleVolume}
            onClick={(e) => e.stopPropagation()}
            className="w-16 cursor-pointer accent-blue-500"
            title="Volume"
          />

          <button
            onClick={() => toggleFs()}
            className="text-white hover:text-blue-400 transition-colors p-1.5 rounded-lg ml-1"
            title="Tela cheia"
          >
            {isFs ? <Minimize size={16} /> : <Maximize size={16} />}
          </button>
        </div>
      </div>
    </div>
  )
}
