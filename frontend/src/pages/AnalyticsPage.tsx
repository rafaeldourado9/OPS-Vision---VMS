import { useEffect, useState } from 'react'
import { BarChart3, TrendingUp, Users, Car, Clock, Image as ImageIcon } from 'lucide-react'
import { clsx } from 'clsx'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  LineChart, Line, PieChart, Pie, Cell, Legend,
} from 'recharts'
import { analyticsService, cameraService } from '@/services/api'
import { PageSpinner } from '@/components/ui/Spinner'
import type { Camera } from '@/types'

type Tab = 'overview' | 'traffic' | 'events' | 'heatmap' | 'queue'

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Visão Geral', icon: BarChart3 },
  { id: 'traffic',  label: 'Tráfego',     icon: TrendingUp },
  { id: 'events',   label: 'Eventos',     icon: Users },
  { id: 'heatmap',  label: 'Mapa de Calor', icon: ImageIcon },
  { id: 'queue',    label: 'Filas',       icon: Clock },
]

const PIE_COLORS = ['#3B82F6','#22C55E','#F59E0B','#EF4444','#8B5CF6','#EC4899','#06B6D4','#84CC16']

export function AnalyticsPage() {
  const [tab, setTab]             = useState<Tab>('overview')
  const [cameras, setCameras]     = useState<Camera[]>([])
  const [selCam, setSelCam]       = useState('')
  const [loading, setLoading]     = useState(false)
  const [trafficData, setTraffic] = useState<any[]>([])
  const [eventsData, setEvents]   = useState<any[]>([])
  const [queueData, setQueue]     = useState<any[]>([])
  const [heatmapUrl, setHeatmap]  = useState<string>('')

  useEffect(() => {
    cameraService.list({ page_size: 100 }).then(r => setCameras(r.results))
  }, [])

  useEffect(() => {
    setLoading(true)
    const params = selCam ? { camera_id: selCam } : {}

    Promise.all([
      analyticsService.trafficByHour({ ...params, event_type: 'human_traffic' }),
      analyticsService.eventsByType({ ...params, days: 7 }),
      analyticsService.queueStats({ ...params }),
    ]).then(([traffic, events, queue]) => {
      setTraffic(traffic.data ?? [])
      setEvents(events.data ?? [])
      setQueue(queue.data ?? [])
    }).finally(() => setLoading(false))

    if (selCam) setHeatmap(`/api/v1/cameras/${selCam}/heatmap/?t=${Date.now()}`)
  }, [selCam, tab])

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Tab bar + Camera filter */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1 p-1 rounded-xl" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={clsx('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                tab === id ? 'text-white' : 'text-t2 hover:text-t1')}
              style={tab === id ? { background: 'var(--accent)' } : {}}>
              <Icon size={14} />{label}
            </button>
          ))}
        </div>
        <select className="input max-w-[200px]" value={selCam} onChange={e => setSelCam(e.target.value)}>
          <option value="">Todas as câmeras</option>
          {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {loading ? <PageSpinner /> : (
        <>
          {/* Overview */}
          {tab === 'overview' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="card p-4">
                <p className="text-sm font-semibold text-t1 mb-1">Tráfego Humano — Últimas 24h</p>
                <p className="text-xs text-t3 mb-4">Pessoas detectadas por hora</p>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={trafficData} margin={{ left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="hour" tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
                    <YAxis tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
                    <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="events" fill="var(--accent)" radius={[4,4,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="card p-4">
                <p className="text-sm font-semibold text-t1 mb-1">Distribuição de Eventos — 7 dias</p>
                <p className="text-xs text-t3 mb-4">Por tipo de analítico</p>
                {eventsData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie data={eventsData} dataKey="count" nameKey="event_type" cx="50%" cy="50%" outerRadius={80}>
                        {eventsData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                      <Legend wrapperStyle={{ fontSize: 11, color: 'var(--text-2)' }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[200px] flex items-center justify-center text-t3 text-sm">Sem dados</div>
                )}
              </div>
            </div>
          )}

          {/* Traffic */}
          {tab === 'traffic' && (
            <div className="grid grid-cols-1 gap-4">
              {(['human_traffic', 'vehicle_traffic'] as const).map(type => (
                <TrafficChart key={type} eventType={type} cameraId={selCam} />
              ))}
            </div>
          )}

          {/* Events */}
          {tab === 'events' && (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
                    <th className="px-4 py-3 text-xs font-medium text-t3">Tipo de Evento</th>
                    <th className="px-4 py-3 text-xs font-medium text-t3">Total (7 dias)</th>
                    <th className="px-4 py-3 text-xs font-medium text-t3">Barra</th>
                  </tr>
                </thead>
                <tbody>
                  {eventsData.sort((a, b) => b.count - a.count).map((row, i) => (
                    <tr key={i} className="border-b hover:bg-elevated" style={{ borderColor: 'var(--border)' }}>
                      <td className="px-4 py-3 text-t1 font-medium">{row.event_type}</td>
                      <td className="px-4 py-3 text-t2">{row.count}</td>
                      <td className="px-4 py-3 w-48">
                        <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--elevated)' }}>
                          <div className="h-full rounded-full"
                            style={{ background: 'var(--accent)', width: `${(row.count / eventsData[0]?.count) * 100}%` }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                  {eventsData.length === 0 && (
                    <tr><td colSpan={3} className="px-4 py-10 text-center text-t3 text-sm">Sem dados no período</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Heatmap */}
          {tab === 'heatmap' && (
            <div className="card p-6 text-center">
              {!selCam ? (
                <p className="text-t3 text-sm">Selecione uma câmera para ver o mapa de calor</p>
              ) : heatmapUrl ? (
                <img src={heatmapUrl} alt="Heatmap" className="max-w-2xl mx-auto rounded-lg w-full"
                  onError={() => setHeatmap('')} />
              ) : (
                <div className="py-16 space-y-2">
                  <ImageIcon size={32} className="text-t3 mx-auto" />
                  <p className="text-t3 text-sm">Mapa de calor ainda não disponível.<br />Aguarde o processamento de frames da câmera.</p>
                </div>
              )}
            </div>
          )}

          {/* Queue */}
          {tab === 'queue' && (
            <div className="space-y-3">
              {queueData.length === 0 ? (
                <div className="card p-16 text-center">
                  <Clock size={32} className="text-t3 mx-auto mb-3" />
                  <p className="text-t3 text-sm">Nenhum alerta de fila recente</p>
                </div>
              ) : queueData.map((q: any, i: number) => (
                <div key={i} className="card px-4 py-3 flex items-center gap-4">
                  <Clock size={18} className="text-yellow-400 shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-t1">{q.camera}</p>
                    <p className="text-xs text-t3">{q.detected_at}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-t1">{q.count} pessoas</p>
                    <p className="text-xs text-t3">Espera: {Math.round(q.avg_wait_seconds / 60)}min</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function TrafficChart({ eventType, cameraId }: { eventType: string; cameraId: string }) {
  const [data, setData] = useState<any[]>([])
  useEffect(() => {
    analyticsService.trafficByHour({ event_type: eventType, ...(cameraId ? { camera_id: cameraId } : {}) })
      .then(r => setData(r.data ?? []))
  }, [eventType, cameraId])

  const label = eventType === 'human_traffic' ? 'Tráfego Humano' : 'Tráfego de Veículos'
  const color = eventType === 'human_traffic' ? '#3B82F6' : '#F59E0B'

  return (
    <div className="card p-4">
      <p className="text-sm font-semibold text-t1 mb-4">{label} — Últimas 24h</p>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="hour" tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
          <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
          <Line type="monotone" dataKey="events" stroke={color} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
