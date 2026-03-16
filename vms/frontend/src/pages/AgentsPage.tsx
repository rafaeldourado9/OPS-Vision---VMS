import { useEffect, useState } from 'react'
import { Plus, Trash2, Key, Copy } from 'lucide-react'
import api from '../lib/api'
import { formatDate } from '../lib/utils'
import Modal from '../components/Modal'

interface Agent {
  id: number
  name: string
  location: string
  is_active: boolean
  last_heartbeat: string | null
  created_at: string
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [showModal, setShowModal] = useState(false)
  const [newApiKey, setNewApiKey] = useState('')
  const [form, setForm] = useState({ name: '', location: '' })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadAgents()
  }, [])

  const loadAgents = async () => {
    try {
      const { data } = await api.get('/agents/', { params: { page_size: 100 } })
      setAgents(data.results ?? data)
    } catch {}
  }

  const createAgent = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await api.post('/agents/', form)
      setNewApiKey(data.api_key || '')
      setForm({ name: '', location: '' })
      loadAgents()
    } catch {}
    setSaving(false)
  }

  const revokeAgent = async (id: number) => {
    if (!confirm('Revogar este agente? A chave API será invalidada.')) return
    try {
      await api.delete(`/agents/${id}/`)
      loadAgents()
    } catch {}
  }

  const copyKey = () => {
    navigator.clipboard.writeText(newApiKey)
  }

  const isOnline = (agent: Agent) => {
    if (!agent.last_heartbeat) return false
    const diff = Date.now() - new Date(agent.last_heartbeat).getTime()
    return diff < 5 * 60 * 1000 // 5 min
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Agentes</h1>
        <button
          onClick={() => { setShowModal(true); setNewApiKey('') }}
          className="flex items-center gap-2 bg-vms-accent hover:bg-vms-accent-hover rounded-lg px-4 py-2 text-sm font-medium transition-colors"
        >
          <Plus size={16} /> Novo Agente
        </button>
      </div>

      <div className="space-y-2">
        {agents.map((agent) => (
          <div key={agent.id} className="bg-vms-card rounded-lg p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full ${agent.is_active && isOnline(agent) ? 'bg-vms-success' : 'bg-vms-danger'}`} />
              <div>
                <p className="font-medium text-sm">{agent.name}</p>
                <p className="text-xs text-vms-muted">
                  {agent.location} · {agent.last_heartbeat ? `Heartbeat: ${formatDate(agent.last_heartbeat)}` : 'Sem heartbeat'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xs ${agent.is_active ? 'text-vms-success' : 'text-vms-danger'}`}>
                {agent.is_active ? 'Ativo' : 'Revogado'}
              </span>
              {agent.is_active && (
                <button onClick={() => revokeAgent(agent.id)} className="text-vms-muted hover:text-red-400">
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          </div>
        ))}
        {agents.length === 0 && (
          <p className="text-vms-muted text-sm text-center py-8">Nenhum agente registrado</p>
        )}
      </div>

      {/* Create Agent Modal */}
      <Modal open={showModal} onClose={() => setShowModal(false)} title={newApiKey ? 'Agente Criado' : 'Novo Agente'}>
        {newApiKey ? (
          <div className="space-y-4">
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 text-yellow-400 text-sm">
              <Key size={16} className="inline mr-2" />
              Copie a chave API agora. Ela não será exibida novamente!
            </div>
            <div className="bg-vms-bg rounded-lg p-3 font-mono text-sm break-all flex items-start gap-2">
              <span className="flex-1">{newApiKey}</span>
              <button onClick={copyKey} className="text-vms-accent shrink-0"><Copy size={16} /></button>
            </div>
            <button
              onClick={() => setShowModal(false)}
              className="w-full py-2 bg-vms-accent hover:bg-vms-accent-hover rounded-lg text-sm font-medium transition-colors"
            >
              Fechar
            </button>
          </div>
        ) : (
          <form onSubmit={createAgent} className="space-y-4">
            <div>
              <label className="block text-sm text-vms-muted mb-1">Nome</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-vms-muted mb-1">Localização</label>
              <input
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
                className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
                required
              />
            </div>
            <div className="flex gap-3 justify-end">
              <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 text-sm rounded-lg bg-vms-card-hover">Cancelar</button>
              <button type="submit" disabled={saving} className="px-4 py-2 text-sm rounded-lg bg-vms-accent hover:bg-vms-accent-hover font-medium disabled:opacity-60">
                {saving ? 'Criando...' : 'Criar Agente'}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
