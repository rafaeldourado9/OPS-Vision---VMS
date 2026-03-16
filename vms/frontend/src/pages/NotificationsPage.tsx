import { useEffect, useState } from 'react'
import { Plus, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'
import api from '../lib/api'
import { formatDate } from '../lib/utils'
import Modal from '../components/Modal'
import Pagination from '../components/Pagination'

interface NotificationRule {
  id: number
  name: string
  event_type_pattern: string
  channel: string
  destination: string
  is_active: boolean
  webhook_secret: string
  created_at: string
}

interface NotificationLog {
  id: number
  rule: number
  event_type: string
  status: string
  response_code: number | null
  response_body: string
  created_at: string
}

export default function NotificationsPage() {
  const [rules, setRules] = useState<NotificationRule[]>([])
  const [logs, setLogs] = useState<NotificationLog[]>([])
  const [logCount, setLogCount] = useState(0)
  const [logPage, setLogPage] = useState(1)
  const [showModal, setShowModal] = useState(false)
  const [tab, setTab] = useState<'rules' | 'logs'>('rules')
  const [form, setForm] = useState({
    name: '',
    event_type_pattern: '*',
    channel: 'webhook',
    destination: '',
    webhook_secret: '',
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadRules()
  }, [])

  useEffect(() => {
    if (tab === 'logs') loadLogs()
  }, [tab, logPage])

  const loadRules = async () => {
    try {
      const { data } = await api.get('/notifications/rules/', { params: { page_size: 100 } })
      setRules(data.results ?? data)
    } catch {}
  }

  const loadLogs = async () => {
    try {
      const { data } = await api.get('/notifications/logs/', { params: { page: logPage, page_size: 20 } })
      setLogs(data.results ?? data)
      setLogCount(data.count ?? 0)
    } catch {}
  }

  const createRule = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api.post('/notifications/rules/', form)
      setShowModal(false)
      setForm({ name: '', event_type_pattern: '*', channel: 'webhook', destination: '', webhook_secret: '' })
      loadRules()
    } catch {}
    setSaving(false)
  }

  const toggleRule = async (rule: NotificationRule) => {
    try {
      await api.patch(`/notifications/rules/${rule.id}/`, { is_active: !rule.is_active })
      loadRules()
    } catch {}
  }

  const deleteRule = async (id: number) => {
    if (!confirm('Remover esta regra?')) return
    try {
      await api.delete(`/notifications/rules/${id}/`)
      loadRules()
    } catch {}
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Notificações</h1>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-vms-accent hover:bg-vms-accent-hover rounded-lg px-4 py-2 text-sm font-medium transition-colors"
        >
          <Plus size={16} /> Nova Regra
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-vms-card rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab('rules')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${tab === 'rules' ? 'bg-vms-accent text-white' : 'text-vms-muted hover:text-white'}`}
        >
          Regras
        </button>
        <button
          onClick={() => setTab('logs')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${tab === 'logs' ? 'bg-vms-accent text-white' : 'text-vms-muted hover:text-white'}`}
        >
          Logs
        </button>
      </div>

      {tab === 'rules' && (
        <div className="space-y-2">
          {rules.map((rule) => (
            <div key={rule.id} className="bg-vms-card rounded-lg p-4 flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">{rule.name}</p>
                <p className="text-xs text-vms-muted mt-0.5">
                  Padrão: <code className="bg-vms-bg px-1 rounded">{rule.event_type_pattern}</code> → {rule.destination}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => toggleRule(rule)} className="text-vms-muted hover:text-white">
                  {rule.is_active ? <ToggleRight size={20} className="text-vms-success" /> : <ToggleLeft size={20} />}
                </button>
                <button onClick={() => deleteRule(rule.id)} className="text-vms-muted hover:text-red-400">
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
          {rules.length === 0 && (
            <p className="text-vms-muted text-sm text-center py-8">Nenhuma regra de notificação</p>
          )}
        </div>
      )}

      {tab === 'logs' && (
        <>
          <div className="bg-vms-card rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-vms-border text-vms-muted text-xs">
                  <th className="text-left px-4 py-3">Regra</th>
                  <th className="text-left px-4 py-3">Evento</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">HTTP</th>
                  <th className="text-left px-4 py-3">Data</th>
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 ? (
                  <tr><td colSpan={5} className="text-center py-8 text-vms-muted">Nenhum log</td></tr>
                ) : logs.map((log) => (
                  <tr key={log.id} className="border-b border-vms-border/50 hover:bg-vms-card-hover">
                    <td className="px-4 py-3">#{log.rule}</td>
                    <td className="px-4 py-3 text-vms-muted">{log.event_type}</td>
                    <td className="px-4 py-3">
                      <span className={log.status === 'success' ? 'text-vms-success' : 'text-vms-danger'}>
                        {log.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-vms-muted">{log.response_code ?? '—'}</td>
                    <td className="px-4 py-3 text-vms-muted">{formatDate(log.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination currentPage={logPage} totalCount={logCount} pageSize={20} onPageChange={setLogPage} />
        </>
      )}

      {/* Create Rule Modal */}
      <Modal open={showModal} onClose={() => setShowModal(false)} title="Nova Regra de Notificação">
        <form onSubmit={createRule} className="space-y-4">
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
            <label className="block text-sm text-vms-muted mb-1">Padrão de Evento</label>
            <input
              value={form.event_type_pattern}
              onChange={(e) => setForm({ ...form, event_type_pattern: e.target.value })}
              placeholder="detection.alpr, camera.*, *"
              className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm font-mono"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-vms-muted mb-1">URL Webhook</label>
            <input
              value={form.destination}
              onChange={(e) => setForm({ ...form, destination: e.target.value })}
              placeholder="https://example.com/webhook"
              className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-vms-muted mb-1">Secret (HMAC)</label>
            <input
              value={form.webhook_secret}
              onChange={(e) => setForm({ ...form, webhook_secret: e.target.value })}
              placeholder="Opcional"
              className="w-full bg-vms-bg border border-vms-border rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 text-sm rounded-lg bg-vms-card-hover">Cancelar</button>
            <button type="submit" disabled={saving} className="px-4 py-2 text-sm rounded-lg bg-vms-accent hover:bg-vms-accent-hover font-medium disabled:opacity-60">
              {saving ? 'Salvando...' : 'Criar Regra'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
