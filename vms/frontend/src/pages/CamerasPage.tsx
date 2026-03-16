import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Camera, Trash2, Pencil } from 'lucide-react'
import Modal from '../components/Modal'
import api from '../lib/api'
import { useCameraStore } from '../stores/cameraStore'
import { formatDate } from '../lib/utils'

const MANUFACTURERS = [
  { value: 'hikvision', label: 'Hikvision' },
  { value: 'intelbras', label: 'Intelbras' },
  { value: 'dahua', label: 'Dahua' },
  { value: 'other', label: 'Outro' },
]

const RETENTION_OPTIONS = [
  { value: 7, label: '7 dias' },
  { value: 15, label: '15 dias' },
  { value: 30, label: '30 dias' },
]

export default function CamerasPage() {
  const { cameras, fetchCameras, loading } = useCameraStore()
  const [showModal, setShowModal] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [form, setForm] = useState({
    name: '',
    location: '',
    rtsp_url: '',
    manufacturer: 'other',
    retention_days: 7,
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchCameras()
  }, [])

  const resetForm = () => {
    setForm({ name: '', location: '', rtsp_url: '', manufacturer: 'other', retention_days: 7 })
    setEditId(null)
    setError('')
  }

  const openCreate = () => {
    resetForm()
    setShowModal(true)
  }

  const openEdit = (cam: typeof cameras[0]) => {
    setForm({
      name: cam.name,
      location: cam.location,
      rtsp_url: cam.rtsp_url,
      manufacturer: cam.manufacturer,
      retention_days: cam.retention_days,
    })
    setEditId(cam.id)
    setShowModal(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      if (editId) {
        await api.patch(`/cameras/${editId}/`, form)
      } else {
        await api.post('/cameras/', form)
      }
      setShowModal(false)
      resetForm()
      fetchCameras()
    } catch (err: any) {
      setError(err.response?.data?.error || err.response?.data?.rtsp_url?.[0] || 'Erro ao salvar câmera')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Tem certeza que deseja remover esta câmera?')) return
    try {
      await api.delete(`/cameras/${id}/`)
      fetchCameras()
    } catch {
      alert('Erro ao remover câmera')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Câmeras</h1>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 bg-vms-accent hover:bg-vms-accent-hover rounded-lg px-4 py-2 text-sm font-medium transition-colors"
        >
          <Plus size={16} /> Adicionar Câmera
        </button>
      </div>

      {loading && cameras.length === 0 ? (
        <p className="text-vms-muted">Carregando...</p>
      ) : cameras.length === 0 ? (
        <div className="text-center py-16 text-vms-muted">
          <Camera size={48} className="mx-auto mb-3 opacity-40" />
          <p>Nenhuma câmera cadastrada</p>
          <button onClick={openCreate} className="text-vms-accent mt-2 text-sm hover:underline">
            Adicionar primeira câmera
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cameras.map((cam) => (
            <div key={cam.id} className="bg-vms-card rounded-xl p-4 border border-vms-border hover:border-vms-accent/30 transition-colors">
              <div className="flex items-start justify-between mb-3">
                <Link to={`/cameras/${cam.id}`} className="flex-1">
                  <h3 className="font-semibold text-sm hover:text-vms-accent transition-colors">{cam.name}</h3>
                  <p className="text-vms-muted text-xs">{cam.location}</p>
                </Link>
                <div className="flex gap-1">
                  <button onClick={() => openEdit(cam)} className="p-1.5 text-vms-muted hover:text-white rounded-lg hover:bg-vms-card-hover">
                    <Pencil size={14} />
                  </button>
                  <button onClick={() => handleDelete(cam.id)} className="p-1.5 text-vms-muted hover:text-red-400 rounded-lg hover:bg-vms-card-hover">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              <div className="space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-vms-muted">Status</span>
                  <span className={cam.is_online ? 'text-vms-success' : 'text-vms-danger'}>
                    ● {cam.is_online ? 'Online' : 'Offline'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-vms-muted">Fabricante</span>
                  <span className="capitalize">{cam.manufacturer}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-vms-muted">Retenção</span>
                  <span>{cam.retention_days} dias</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-vms-muted">Criada</span>
                  <span>{formatDate(cam.created_at)}</span>
                </div>
              </div>

              <Link
                to={`/cameras/${cam.id}`}
                className="mt-3 block text-center text-xs bg-vms-card-hover hover:bg-vms-border rounded-lg py-2 transition-colors"
              >
                Abrir ao vivo
              </Link>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      <Modal
        open={showModal}
        onClose={() => { setShowModal(false); resetForm() }}
        title={editId ? 'Editar Câmera' : 'Adicionar Câmera'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-vms-muted mb-1">Nome</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-vms-accent"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-vms-muted mb-1">Localização</label>
            <input
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-vms-accent"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-vms-muted mb-1">URL RTSP</label>
            <input
              value={form.rtsp_url}
              onChange={(e) => setForm({ ...form, rtsp_url: e.target.value })}
              placeholder="rtsp://user:pass@ip:porta/path"
              className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-vms-accent font-mono"
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-vms-muted mb-1">Fabricante</label>
              <select
                value={form.manufacturer}
                onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
                className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-vms-accent"
              >
                {MANUFACTURERS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-vms-muted mb-1">Retenção</label>
              <select
                value={form.retention_days}
                onChange={(e) => setForm({ ...form, retention_days: Number(e.target.value) })}
                className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-vms-accent"
              >
                {RETENTION_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">{error}</div>
          )}

          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={() => { setShowModal(false); resetForm() }}
              className="px-4 py-2 text-sm rounded-lg bg-vms-card-hover hover:bg-vms-border transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm rounded-lg bg-vms-accent hover:bg-vms-accent-hover disabled:opacity-60 font-medium transition-colors"
            >
              {saving ? 'Salvando...' : editId ? 'Salvar' : 'Adicionar'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
