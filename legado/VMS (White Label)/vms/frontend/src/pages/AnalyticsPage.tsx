import { useEffect, useState } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js'
import { Bar, Doughnut, Line } from 'react-chartjs-2'
import api from '../lib/api'
import { todayISO } from '../lib/utils'

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, PointElement, LineElement, Tooltip, Legend)

export default function AnalyticsPage() {
  const [hourly, setHourly] = useState<Record<string, number>>({})
  const [byType, setByType] = useState<Record<string, number>>({})
  const [byCamera, setByCamera] = useState<Record<string, number>>({})

  useEffect(() => {
    loadAnalytics()
  }, [])

  const loadAnalytics = async () => {
    try {
      const { data } = await api.get('/events/', { params: { created_at__gte: todayISO(), page_size: 100 } })
      const events = data.results ?? data

      const h: Record<string, number> = {}
      const t: Record<string, number> = {}
      const c: Record<string, number> = {}
      for (const ev of events) {
        const hour = new Date(ev.created_at).getHours().toString().padStart(2, '0') + ':00'
        h[hour] = (h[hour] || 0) + 1
        t[ev.event_type] = (t[ev.event_type] || 0) + 1
        const camLabel = ev.camera ? `Cam #${ev.camera}` : 'Sistema'
        c[camLabel] = (c[camLabel] || 0) + 1
      }
      setHourly(h)
      setByType(t)
      setByCamera(c)
    } catch {}
  }

  const hours = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0') + ':00')
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: '#6b7280' }, grid: { display: false } },
      y: { ticks: { color: '#6b7280' }, grid: { color: '#1e2130' } },
    },
  }

  const colors = ['#3b82f6', '#22c55e', '#ef4444', '#f59e0b', '#6366f1', '#ec4899', '#14b8a6', '#8b5cf6']

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Analíticos</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Hourly trend */}
        <div className="bg-vms-card rounded-xl p-4">
          <h3 className="font-semibold text-sm mb-3">Eventos por Hora (Hoje)</h3>
          <div className="h-64">
            <Line
              data={{
                labels: hours,
                datasets: [{
                  label: 'Eventos',
                  data: hours.map((h) => hourly[h] || 0),
                  borderColor: '#3b82f6',
                  backgroundColor: 'rgba(59, 130, 246, 0.1)',
                  fill: true,
                  tension: 0.3,
                }],
              }}
              options={chartOptions}
            />
          </div>
        </div>

        {/* By type */}
        <div className="bg-vms-card rounded-xl p-4">
          <h3 className="font-semibold text-sm mb-3">Por Tipo de Evento</h3>
          <div className="h-64">
            {Object.keys(byType).length > 0 ? (
              <Doughnut
                data={{
                  labels: Object.keys(byType),
                  datasets: [{
                    data: Object.values(byType),
                    backgroundColor: colors.slice(0, Object.keys(byType).length),
                    borderWidth: 0,
                  }],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { position: 'bottom', labels: { color: '#9ca3af', font: { size: 11 } } } },
                }}
              />
            ) : (
              <div className="h-full flex items-center justify-center text-vms-muted text-sm">Sem dados</div>
            )}
          </div>
        </div>

        {/* By camera */}
        <div className="bg-vms-card rounded-xl p-4 lg:col-span-2">
          <h3 className="font-semibold text-sm mb-3">Eventos por Câmera (Hoje)</h3>
          <div className="h-64">
            <Bar
              data={{
                labels: Object.keys(byCamera),
                datasets: [{
                  label: 'Eventos',
                  data: Object.values(byCamera),
                  backgroundColor: '#3b82f6',
                  borderRadius: 4,
                }],
              }}
              options={chartOptions}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
