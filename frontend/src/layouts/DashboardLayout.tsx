import { Outlet } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import { useAuthStore } from '../stores/authStore'
import { Bell, User } from 'lucide-react'

export default function DashboardLayout() {
  const user = useAuthStore((s) => s.user)

  return (
    <div className="flex min-h-screen bg-vms-bg">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-14 border-b border-vms-border flex items-center justify-end px-6 gap-4 bg-vms-bg shrink-0">
          <button className="text-vms-muted hover:text-white transition-colors">
            <Bell size={18} />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-vms-accent flex items-center justify-center text-sm font-bold">
              {user?.username?.[0]?.toUpperCase() ?? 'A'}
            </div>
            <div className="text-sm">
              <p className="font-medium">{user?.username ?? 'Admin'}</p>
              <p className="text-vms-muted text-xs">{user?.email ?? ''}</p>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
