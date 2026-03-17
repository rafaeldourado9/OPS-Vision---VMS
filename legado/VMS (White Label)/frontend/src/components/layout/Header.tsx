import { useLocation } from 'react-router-dom'
import { Bell, User } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'

const TITLES: Record<string, string> = {
  '/':           'Dashboard',
  '/cameras':    'Câmeras',
  '/mosaic':     'Mosaico',
  '/recordings': 'Gravações',
  '/analytics':  'Analíticos',
  '/detections': 'Detecções',
  '/map':        'Mapa Tático',
  '/persons':    'Pessoas',
  '/clips':      'Clips',
  '/users':      'Usuários',
  '/settings':   'Configurações',
}

export function Header() {
  const { pathname } = useLocation()
  const user = useAuthStore(s => s.user)

  const title = Object.entries(TITLES)
    .sort((a, b) => b[0].length - a[0].length)
    .find(([key]) => pathname.startsWith(key))?.[1] ?? 'VMS'

  return (
    <header
      className="h-14 flex items-center justify-between px-4 shrink-0 border-b"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      <h1 className="text-sm font-semibold text-t1">{title}</h1>

      <div className="flex items-center gap-2">
        <button className="btn btn-ghost w-8 h-8 p-0 rounded-lg relative">
          <Bell size={16} />
        </button>

        <div className="flex items-center gap-2 pl-2 border-l" style={{ borderColor: 'var(--border)' }}>
          <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-semibold"
            style={{ background: 'var(--accent)' }}>
            {user?.name?.charAt(0).toUpperCase() ?? <User size={14} />}
          </div>
          {user && (
            <div className="hidden sm:block">
              <p className="text-xs font-medium text-t1 leading-none">{user.name}</p>
              <p className="text-xs text-t3 leading-none mt-0.5">{user.role}</p>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
