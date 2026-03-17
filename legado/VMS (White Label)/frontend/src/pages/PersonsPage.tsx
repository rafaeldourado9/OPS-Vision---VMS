import { useEffect, useState, useRef } from 'react'
import { Plus, Trash2, Search, UserCheck, Upload, Edit2 } from 'lucide-react'
import { clsx } from 'clsx'
import { personService } from '@/services/api'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { usePermission } from '@/hooks/usePermission'
import toast from 'react-hot-toast'
import type { Person } from '@/types'

export function PersonsPage() {
  const { isCityAdmin } = usePermission()
  const [persons, setPersons]     = useState<Person[]>([])
  const [loading, setLoading]     = useState(true)
  const [search, setSearch]       = useState('')
  const [addModal, setAddModal]   = useState(false)
  const [editPerson, setEdit]     = useState<Person | null>(null)
  const [deleteId, setDeleteId]   = useState<string | null>(null)
  const [saving, setSaving]       = useState(false)

  const [formName, setFormName]   = useState('')
  const [formNotes, setFormNotes] = useState('')
  const [formActive, setFormActive] = useState(true)
  const [formPhoto, setFormPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string>('')
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => {
    setLoading(true)
    personService.list().then(r => setPersons(r.results)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const openAdd = () => {
    setFormName(''); setFormNotes(''); setFormActive(true); setFormPhoto(null); setPhotoPreview('')
    setEdit(null); setAddModal(true)
  }

  const openEdit = (p: Person) => {
    setFormName(p.name); setFormNotes(p.notes ?? ''); setFormActive(p.active); setFormPhoto(null)
    setPhotoPreview(p.photo_url ?? '')
    setEdit(p); setAddModal(true)
  }

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setFormPhoto(file)
    setPhotoPreview(URL.createObjectURL(file))
  }

  const handleSave = async () => {
    if (!formName.trim()) { toast.error('Nome obrigatório'); return }
    if (!editPerson && !formPhoto) { toast.error('Foto obrigatória para novo cadastro'); return }
    setSaving(true)
    try {
      const data = new FormData()
      data.append('name', formName.trim())
      data.append('notes', formNotes)
      data.append('active', String(formActive))
      if (formPhoto) data.append('photo', formPhoto)

      if (editPerson) {
        await personService.update(editPerson.id, data)
        toast.success('Pessoa atualizada')
      } else {
        await personService.create(data)
        toast.success('Pessoa cadastrada')
      }
      setAddModal(false)
      load()
    } catch { toast.error('Erro ao salvar pessoa') }
    finally { setSaving(false) }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await personService.delete(deleteId)
      toast.success('Pessoa removida')
      setDeleteId(null)
      load()
    } catch { toast.error('Erro ao remover') }
  }

  const filtered = persons.filter(p =>
    !search || p.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-t3" />
          <input className="input pl-9" placeholder="Buscar por nome..."
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        {isCityAdmin && (
          <button className="btn btn-primary gap-2" onClick={openAdd}>
            <Plus size={16} />Cadastrar Pessoa
          </button>
        )}
      </div>

      <p className="text-xs text-t3">{filtered.length} pessoa(s) cadastradas para reconhecimento facial</p>

      {loading ? <PageSpinner /> : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {filtered.map(p => (
            <div key={p.id} className="card overflow-hidden group">
              <div className="aspect-square relative bg-elevated">
                {p.photo_url ? (
                  <img src={p.photo_url} alt={p.name}
                    className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <UserCheck size={36} className="text-t3" />
                  </div>
                )}
                <div className={clsx('absolute top-2 right-2')}>
                  <Badge variant={p.active ? 'success' : 'warning'} dot>
                    {p.active ? 'Ativo' : 'Inativo'}
                  </Badge>
                </div>
                {isCityAdmin && (
                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-2">
                    <button
                      className="w-9 h-9 rounded-lg bg-surface flex items-center justify-center text-t1 hover:bg-elevated transition"
                      onClick={() => openEdit(p)}>
                      <Edit2 size={16} />
                    </button>
                    <button
                      className="w-9 h-9 rounded-lg bg-surface flex items-center justify-center text-danger hover:bg-elevated transition"
                      onClick={() => setDeleteId(p.id)}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                )}
              </div>
              <div className="p-3">
                <p className="text-sm font-medium text-t1 truncate">{p.name}</p>
                {p.notes && <p className="text-xs text-t3 truncate mt-0.5">{p.notes}</p>}
              </div>
            </div>
          ))}

          {filtered.length === 0 && (
            <div className="col-span-full card p-16 text-center">
              <UserCheck size={40} className="text-t3 mx-auto mb-4" />
              <p className="text-t2 font-medium mb-1">Nenhuma pessoa cadastrada</p>
              <p className="text-xs text-t3">Cadastre pessoas para habilitar o reconhecimento facial nas câmeras</p>
              {isCityAdmin && (
                <button className="btn btn-primary mt-4 gap-2" onClick={openAdd}>
                  <Plus size={15} />Cadastrar Pessoa
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Add/Edit Modal */}
      <Modal
        open={addModal}
        onClose={() => setAddModal(false)}
        title={editPerson ? 'Editar Pessoa' : 'Cadastrar Pessoa'}
        size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setAddModal(false)}>Cancelar</button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Salvando...' : editPerson ? 'Salvar' : 'Cadastrar'}
            </button>
          </>
        }>
        <div className="space-y-4">
          {/* Photo */}
          <div className="flex flex-col items-center gap-3">
            <div
              className="w-28 h-28 rounded-full overflow-hidden border-2 flex items-center justify-center cursor-pointer hover:opacity-80 transition"
              style={{ borderColor: 'var(--border)', background: 'var(--elevated)' }}
              onClick={() => fileRef.current?.click()}>
              {photoPreview ? (
                <img src={photoPreview} alt="Preview" className="w-full h-full object-cover" />
              ) : (
                <div className="flex flex-col items-center gap-1">
                  <Upload size={24} className="text-t3" />
                  <span className="text-xs text-t3">Foto</span>
                </div>
              )}
            </div>
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handlePhotoChange} />
            <button className="btn btn-ghost text-xs gap-1" onClick={() => fileRef.current?.click()}>
              <Upload size={12} />{photoPreview ? 'Trocar foto' : 'Selecionar foto'}
            </button>
            <p className="text-xs text-t3 text-center">Use uma foto frontal clara do rosto para melhor precisão</p>
          </div>

          <div>
            <label className="label">Nome completo</label>
            <input className="input" placeholder="Ex: João da Silva"
              value={formName} onChange={e => setFormName(e.target.value)} />
          </div>

          <div>
            <label className="label">Observações <span className="text-t3">(opcional)</span></label>
            <textarea className="input resize-none" rows={2} placeholder="Ex: Funcionário da portaria"
              value={formNotes} onChange={e => setFormNotes(e.target.value)} />
          </div>

          <div className="flex items-center gap-3">
            <label className="label mb-0 flex-1">Ativo</label>
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
      <Modal open={!!deleteId} onClose={() => setDeleteId(null)} title="Remover Pessoa" size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setDeleteId(null)}>Cancelar</button>
            <button className="btn btn-danger" onClick={handleDelete}>
              <Trash2 size={15} />Remover
            </button>
          </>
        }>
        <p className="text-sm text-t2">
          Tem certeza? O reconhecimento facial desta pessoa será desabilitado em todas as câmeras.
        </p>
      </Modal>
    </div>
  )
}
