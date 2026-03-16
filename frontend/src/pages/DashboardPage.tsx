import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cctv, Wifi, WifiOff, ShieldAlert, Film, TrendingUp, ArrowRight } from 'lucide-react'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { dashboardService, cameraService } from '@/services/api'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import type { DashboardStats, DetectionByHour, Camera } from '@/types'

const EVENT_LABELS: Record<string, string> = {
  lpr: 'Placa', crowd: 'Multidão', intrusion: 'Intrusão',
  object_detected: 'Objeto', vehicle_traffic: 'Veículo', human_traffic: 'Pessoa',
  line_crossing: 'Cruzamento', loitering: 'Perambulação', abandoned_object: 'Abandonado',
  queue_alert: 'Fila', facial_match: 'Facial', facial_unknown: 'Desconhecido',
}

export function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats]     = useState<DashboardStats | null>(null)
  const [hours, setHours]     = useState<DetectionByHour[]>([])
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      dashboardService.stats(),
      dashboardService.detectionsByHour(),
      cameraService.list({ page_size: 6 }),
    ]).then(([s, h, c]) => {
      setStats(s); setHours(h); setCameras(c.results)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <PageSpinner />

  const statCards = [
    { label: 'Total de Câmeras',  value: stats?.total_cameras ?? 0,          icon: Cctv,        color: '#3B82F6' },
    { label: 'Online',            value: stats?.online_cameras ?? 0,          icon: Wifi,        color: '#22C55E' },
    { label: 'Offline',           value: stats?.offline_cameras ?? 0,         icon: WifiOff,     color: '#EF4444' },
    { label: 'Detecções Hoje',    value: stats?.total_detections_today ?? 0,  icon: ShieldAlert, color: '#F59E0B' },
    { label: 'Clips',             value: stats?.total_clips ?? 0,             icon: Film,        color: '#8B5CF6' },
  ]

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {statCards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card px-4 py-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-t2 font-medium">{label}</p>
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: color + '18' }}>
                <Icon size={16} style={{ color }} />
              </div>
            </div>
            <p className="text-2xl font-bold text-t1">{value.toLocaleString()}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Detections chart */}
        <div className="card p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-semibold text-t1">Detecções por Hora</p>
              <p className="text-xs text-t3">Últimas 24 horas</p>
            </div>
            <TrendingUp size={16} className="text-t3" />
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={hours} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="hour" tick={{ fontSize: 11, fill: 'var(--text-3)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-3)' }} />
              <Tooltip
                contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: 'var(--text-2)' }}
                itemStyle={{ color: 'var(--accent)' }}
              />
              <Area type="monotone" dataKey="detections" stroke="var(--accent)" fill="url(#grad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Events by type */}
        <div className="card p-4">
          <p className="text-sm font-semibold text-t1 mb-1">Eventos Hoje</p>
          <p className="text-xs text-t3 mb-4">Por tipo de analítico</p>
          {Object.entries(stats?.events_by_type_today ?? {}).length === 0 ? (
            <div className="flex-1 flex items-center justify-center py-8">
              <p className="text-xs text-t3">Nenhum evento hoje</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {Object.entries(stats?.events_by_type_today ?? {})
                .sort(([, a], [, b]) => b - a)
                .slice(0, 8)
                .map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between gap-3">
                    <p className="text-xs text-t2 truncate">{EVENT_LABELS[type] ?? type}</p>
                    <div className="flex items-center gap-2 shrink-0">
                      <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--elevated)' }}>
                        <div className="h-full rounded-full" style={{
                          background: 'var(--accent)',
                          width: `${Math.min(100, (count / Math.max(...Object.values(stats!.events_by_type_today))) * 100)}%`,
                        }} />
                      </div>
                      <span className="text-xs font-semibold text-t1 w-6 text-right">{count}</span>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent cameras */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm font-semibold text-t1">Câmeras</p>
            <p className="text-xs text-t3">Status em tempo real</p>
          </div>
          <button onClick={() => navigate('/cameras')} className="btn btn-ghost text-xs gap-1">
            Ver todas <ArrowRight size={14} />
          </button>
        </div>
        <div className="space-y-2">
          {cameras.map(cam => (
            <div key={cam.id}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-elevated transition cursor-pointer"
              onClick={() => navigate(`/cameras/${cam.id}`)}>
              <div className={`w-2 h-2 rounded-full shrink-0 ${cam.online ? 'bg-green-500' : 'bg-red-500'}`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-t1 truncate">{cam.name}</p>
                <p className="text-xs text-t3 truncate">{cam.address}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge variant={cam.online ? 'success' : 'danger'} dot>
                  {cam.online ? 'Online' : 'Offline'}
                </Badge>
                <span className="text-xs text-t3 uppercase">{cam.stream_protocol}</span>
              </div>
            </div>
          ))}
          {cameras.length === 0 && (
            <p className="text-sm text-t3 text-center py-4">Nenhuma câmera cadastrada</p>
          )}
        </div>
      </div>
    </div>
  )
}
