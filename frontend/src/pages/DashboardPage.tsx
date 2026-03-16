import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Camera,
  Wifi,
  WifiOff,
  AlertTriangle,
  Scissors,
  ArrowUpRight,
} from 'lucide-react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js'
import { Bar, Doughnut } from 'react-chartjs-2'
import StatsCard from '../components/StatsCard'
import api from '../lib/api'
import { useCameraStore, type Camera as CameraType } from '../stores/cameraStore'
import { todayISO } from '../lib/utils'

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend)

interface HourlyData {
  [hour: string]: number
}

interface EventTypeCounts {
  [type: string]: number
}

export default function DashboardPage() {
  const { cameras, fetchCameras } = useCameraStore()
  const [todayEvents, setTodayEvents] = useState(0)
  const [clipCount, setClipCount] = useState(0)
  const [hourlyDetections, setHourlyDetections] = useState<HourlyData>({})
  const [eventTypes, setEventTypes] = useState<EventTypeCounts>({})

  useEffect(() => {
    fetchCameras()
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      const [eventsRes, clipsRes] = await Promise.all([
        api.get('/events/', { params: { created_at__gte: todayISO(), page_size: 100 } }),
        api.get('/recordings/clips/', { params: { page_size: 1 } }),
      ])

      const events = eventsRes.data.results ?? eventsRes.data
      setTodayEvents(eventsRes.data.count ?? events.length)
      setClipCount(clipsRes.data.count ?? 0)

      // Aggregate hourly
      const hourly: HourlyData = {}
      const types: EventTypeCounts = {}
      for (const ev of events) {
        const hour = new Date(ev.created_at).getHours().toString().padStart(2, '0') + ':00'
        hourly[hour] = (hourly[hour] || 0) + 1
        const t = ev.event_type ?? 'unknown'
        types[t] = (types[t] || 0) + 1
      }
      setHourlyDetections(hourly)
      setEventTypes(types)
    } catch {
      // silent
    }
  }

  const online = cameras.filter((c) => c.is_online).length
  const offline = cameras.filter((c) => !c.is_online).length

  // Chart data
  const hours = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0') + ':00')
  const barData = {
    labels: hours,
    datasets: [
      {
        label: 'Detecções',
        data: hours.map((h) => hourlyDetections[h] || 0),
        backgroundColor: '#3b82f6',
        borderRadius: 4,
      },
    ],
  }

  const barOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: '#6b7280', font: { size: 10 } }, grid: { display: false } },
      y: { ticks: { color: '#6b7280' }, grid: { color: '#1e2130' } },
    },
  }

  const typeLabels = Object.keys(eventTypes)
  const typeColors = ['#3b82f6', '#22c55e', '#ef4444', '#f59e0b', '#6366f1', '#ec4899', '#14b8a6', '#8b5cf6']
  const doughnutData = {
    labels: typeLabels.map((t) => t.replace('.', ' ')),
    datasets: [
      {
        data: typeLabels.map((t) => eventTypes[t]),
        backgroundColor: typeColors.slice(0, typeLabels.length),
        borderWidth: 0,
      },
    ],
  }

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom' as const, labels: { color: '#9ca3af', padding: 12, font: { size: 11 } } } },
  }

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <StatsCard
          label="Total de Câmeras"
          value={cameras.length}
          icon={<Camera size={20} className="text-white" />}
          color="bg-vms-accent"
        />
        <StatsCard
          label="Online"
          value={online}
          icon={<Wifi size={20} className="text-white" />}
          color="bg-vms-success"
        />
        <StatsCard
          label="Offline"
          value={offline}
          icon={<WifiOff size={20} className="text-white" />}
          color="bg-red-600"
        />
        <StatsCard
          label="Detecções Hoje"
          value={todayEvents}
          icon={<AlertTriangle size={20} className="text-white" />}
          color="bg-vms-info"
        />
        <StatsCard
          label="Clips"
          value={clipCount}
          icon={<Scissors size={20} className="text-white" />}
          color="bg-purple-600"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 mb-6">
        <div className="lg:col-span-3 bg-vms-card rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-semibold text-sm">Detecções por Hora</h3>
              <p className="text-vms-muted text-xs">Últimas 24 horas</p>
            </div>
            <ArrowUpRight size={16} className="text-vms-muted" />
          </div>
          <div className="h-48">
            <Bar data={barData} options={barOptions} />
          </div>
        </div>

        <div className="lg:col-span-2 bg-vms-card rounded-xl p-4">
          <div className="mb-3">
            <h3 className="font-semibold text-sm">Eventos Hoje</h3>
            <p className="text-vms-muted text-xs">Por tipo de analítico</p>
          </div>
          {typeLabels.length > 0 ? (
            <div className="h-48">
              <Doughnut data={doughnutData} options={doughnutOptions} />
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-vms-muted text-sm">
              Nenhum evento hoje
            </div>
          )}
        </div>
      </div>

      {/* Camera list */}
      <div className="bg-vms-card rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-sm">Câmeras</h3>
            <p className="text-vms-muted text-xs">Status em tempo real</p>
          </div>
          <Link to="/cameras" className="text-vms-accent text-sm hover:underline flex items-center gap-1">
            Ver todas <ArrowUpRight size={14} />
          </Link>
        </div>
        <div className="space-y-2">
          {cameras.slice(0, 10).map((cam) => (
            <CameraStatusRow key={cam.id} camera={cam} />
          ))}
          {cameras.length === 0 && (
            <p className="text-vms-muted text-sm py-4 text-center">Nenhuma câmera cadastrada</p>
          )}
        </div>
      </div>
    </div>
  )
}

function CameraStatusRow({ camera }: { camera: CameraType }) {
  return (
    <Link
      to={`/cameras/${camera.id}`}
      className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-vms-card-hover transition-colors"
    >
      <div className="flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full ${camera.is_online ? 'bg-vms-success' : 'bg-vms-danger'}`} />
        <div>
          <p className="text-sm font-medium">{camera.name}</p>
          <p className="text-xs text-vms-muted">{camera.location}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className={`text-xs ${camera.is_online ? 'text-vms-success' : 'text-vms-danger'}`}>
          ● {camera.is_online ? 'Online' : 'Offline'}
        </span>
        <span className="text-xs text-vms-muted uppercase">{camera.manufacturer}</span>
      </div>
    </Link>
  )
}
