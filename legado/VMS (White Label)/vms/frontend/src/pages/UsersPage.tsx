import { useAuthStore } from '../stores/authStore'
import { User } from 'lucide-react'

export default function UsersPage() {
  const user = useAuthStore((s) => s.user)

  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Usuários</h1>

      <div className="bg-vms-card rounded-xl p-6 max-w-md">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-full bg-vms-accent flex items-center justify-center">
            <User size={28} />
          </div>
          <div>
            <p className="text-lg font-semibold">{user?.username ?? '—'}</p>
            <p className="text-vms-muted text-sm">{user?.email ?? '—'}</p>
          </div>
        </div>

        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-vms-muted">ID</span>
            <span>{user?.id ?? '—'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-vms-muted">Tenant</span>
            <span>{user?.tenant?.name ?? '—'} #{user?.tenant?.id ?? ''}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
