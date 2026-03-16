import { useEffect, useState } from 'react'
import { Plus, Search, Trash2, Edit2, Shield } from 'lucide-react'
import { clsx } from 'clsx'
import { format } from 'date-fns'
import { userService } from '@/services/api'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { usePermission } from '@/hooks/usePermission'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'
import type { User } from '@/types'

const ROLE_OPTIONS = [
  { value: 'operator',       label: 'Operador',         level: 1 },
  { value: 'supervisor',     label: 'Supervisor',       level: 2 },
  { value: 'city_admin',     label: 'Admin da Cidade',  level: 3 },
  { value: 'reseller_admin', label: 'Admin Revendedor', level: 4 },
  { value: 'super_admin',    label: 'Super Admin',      level: 5 },
]

const ROLE_VARIANT: Record<string, 'info' | 'success' | 'warning' | 'danger'> = {
  operator:       'info',
  supervisor:     'info',
  city_admin:     'warning',
  reseller_admin: 'danger',
  super_admin:    'danger',
}

const ROLE_LABEL: Record<string, string> = {
  operator: 'Operador', supervisor: 'Supervisor', city_admin: 'Admin Cidade',
  reseller_admin: 'Admin Revendedor', super_admin: 'Super Admin',
}

export function UsersPage() {
  const { user: me } = useAuthStore()
  const { isSuperAdmin, isCityAdmin, hasRole } = usePermission()
  const [users, setUsers]       = useState<User[]>([])
  const [loading, setLoading]   = useState(true)
  const [search, setSearch]     = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [addModal, setAddModal] = useState(false)
  const [editUser, setEditUser] = useState<User | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [saving, setSaving]     = useState(false)

  const [formName, setFormName]       = useState('')
  const [formEmail, setFormEmail]     = useState('')
  const [formRole, setFormRole]       = useState('operator')
  const [formPassword, setFormPassword] = useState('')
  const [formActive, setFormActive]   = useState(true)

  const load = () => {
    setLoading(true)
    userService.list().then(r => setUsers(r.results)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const openAdd = () => {
    setFormName(''); setFormEmail(''); setFormRole('operator'); setFormPassword(''); setFormActive(true)
    setEditUser(null); setAddModal(true)
  }

  const openEdit = (u: User) => {
    setFormName(u.name); setFormEmail(u.email); setFormRole(u.role); setFormPassword(''); setFormActive(u.is_active)
    setEditUser(u); setAddModal(true)
  }

  const canManage = (u: User) => {
    if (u.id === me?.id) return false
    const myLevel = ROLE_OPTIONS.find(r => r.value === me?.role)?.level ?? 0
    const theirLevel = ROLE_OPTIONS.find(r => r.value === u.role)?.level ?? 0
    return myLevel > theirLevel
  }

  const availableRoles = () => ROLE_OPTIONS.filter(r => {
    const myLevel = ROLE_OPTIONS.find(o => o.value === me?.role)?.level ?? 0
    return r.level < myLevel
  })

  const handleSave = async () => {
    if (!formName.trim() || !formEmail.trim()) { toast.error('Nome e email obrigatórios'); return }
    if (!editUser && !formPassword) { toast.error('Senha obrigatória para novo usuário'); return }
    setSaving(true)
    try {
      const payload: any = { name: formName, email: formEmail, role: formRole, is_active: formActive }
      if (formPassword) payload.password = formPassword
      if (editUser) {
        await userService.update(editUser.id, payload)
        toast.success('Usuário atualizado')
      } else {
        await userService.create(payload)
        toast.success('Usuário criado')
      }
      setAddModal(false)
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Erro ao salvar usuário')
    } finally { setSaving(false) }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await userService.delete(deleteId)
      toast.success('Usuário removido')
      setDeleteId(null)
      load()
    } catch { toast.error('Erro ao remover') }
  }

  const filtered = users.filter(u => {
    if (roleFilter && u.role !== roleFilter) return false
    if (search && !u.name.toLowerCase().includes(search.toLowerCase()) &&
        !u.email.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  if (!hasRole('city_admin')) {
    return (
      <div className="card p-16 text-center">
        <Shield size={40} className="text-t3 mx-auto mb-4" />
        <p className="text-t2 font-medium">Acesso Restrito</p>
        <p className="text-xs text-t3 mt-1">Você não tem permissão para gerenciar usuários</p>
      </div>
    )
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-t3" />
          <input className="input pl-9" placeholder="Buscar usuários..."
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>

        <select className="input max-w-[180px]" value={roleFilter} onChange={e => setRoleFilter(e.target.value)}>
          <option value="">Todos os perfis</option>
          {ROLE_OPTIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>

        <button className="btn btn-primary gap-2" onClick={openAdd}>
          <Plus size={16} />Novo Usuário
        </button>
      </div>

      <p className="text-xs text-t3">{filtered.length} usuário(s)</p>

      {loading ? <PageSpinner /> : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
                {['Usuário', 'Email', 'Perfil', 'Status', 'Criado em', ''].map(h => (
                  <th key={h} className="px-4 py-3 text-xs font-medium text-t3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(u => (
                <tr key={u.id} className="border-b hover:bg-elevated transition"
                  style={{ borderColor: 'var(--border)' }}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                        style={{ background: 'var(--elevated)', color: 'var(--text-1)' }}>
                        {u.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-t1">{u.name}</p>
                        {u.id === me?.id && <p className="text-xs text-accent">Você</p>}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-t2 text-xs">{u.email}</td>
                  <td className="px-4 py-3">
                    <Badge variant={ROLE_VARIANT[u.role] ?? 'info'}>
                      <Shield size={10} />{ROLE_LABEL[u.role] ?? u.role}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={u.is_active ? 'success' : 'warning'} dot>
                      {u.is_active ? 'Ativo' : 'Inativo'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-t3 text-xs">
                    {u.created_at ? format(new Date(u.created_at), 'dd/MM/yyyy') : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {canManage(u) && (
                      <div className="flex items-center gap-1">
                        <button className="btn btn-ghost w-7 h-7 p-0 rounded-md" onClick={() => openEdit(u)}>
                          <Edit2 size={14} />
                        </button>
                        <button className="btn btn-ghost w-7 h-7 p-0 rounded-md text-danger hover:text-danger"
                          onClick={() => setDeleteId(u.id)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-t3 text-sm">Nenhum usuário encontrado</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Add/Edit Modal */}
      <Modal
        open={addModal}
        onClose={() => setAddModal(false)}
        title={editUser ? 'Editar Usuário' : 'Novo Usuário'}
        size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setAddModal(false)}>Cancelar</button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Salvando...' : editUser ? 'Salvar' : 'Criar'}
            </button>
          </>
        }>
        <div className="space-y-4">
          <div>
            <label className="label">Nome completo</label>
            <input className="input" placeholder="João da Silva"
              value={formName} onChange={e => setFormName(e.target.value)} />
          </div>
          <div>
            <label className="label">E-mail</label>
            <input className="input" type="email" placeholder="joao@empresa.com"
              value={formEmail} onChange={e => setFormEmail(e.target.value)} />
          </div>
          <div>
            <label className="label">Perfil de Acesso</label>
            <select className="input" value={formRole} onChange={e => setFormRole(e.target.value)}>
              {availableRoles().map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">
              Senha {editUser && <span className="text-t3">(deixe em branco para manter)</span>}
            </label>
            <input className="input" type="password" placeholder="••••••••"
              value={formPassword} onChange={e => setFormPassword(e.target.value)} />
          </div>
          <div className="flex items-center gap-3">
            <label className="label mb-0 flex-1">Usuário ativo</label>
            <button
              className="relative w-10 h-6 rounded-full transition-colors shrink-0"
              style={{ background: formActive ? 'var(--accent)' : 'var(--elevated)' }}
              onClick={() => setFormActive(!formActive)}>
              <div className={clsx('absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                formActive ? 'translate-x-5' : 'translate-x-1')} />
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete confirm */}
      <Modal open={!!deleteId} onClose={() => setDeleteId(null)} title="Remover Usuário" size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setDeleteId(null)}>Cancelar</button>
            <button className="btn btn-danger" onClick={handleDelete}>
              <Trash2 size={15} />Remover
            </button>
          </>
        }>
        <p className="text-sm text-t2">
          Tem certeza? O usuário perderá acesso ao sistema imediatamente.
        </p>
      </Modal>
    </div>
  )
}
