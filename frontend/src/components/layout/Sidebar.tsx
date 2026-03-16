import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Cctv, LayoutGrid, PlaySquare, BarChart3,
  ShieldAlert, MapPin, UserCheck, Film, Users, Settings,
  ChevronLeft, ChevronRight, LogOut,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useAuthStore } from '@/store/authStore'
import { useThemeStore } from '@/store/themeStore'
import { usePermission } from '@/hooks/usePermission'
import { authService } from '@/services/api'
import toast from 'react-hot-toast'

interface NavItem {
  to: string
  icon: React.ElementType
  label: string
  adminOnly?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/cameras',    icon: Cctv,            label: 'Câmeras' },
  { to: '/mosaic',     icon: LayoutGrid,      label: 'Mosaico' },
  { to: '/recordings', icon: PlaySquare,      label: 'Gravações' },
  { to: '/analytics',  icon: BarChart3,       label: 'Analíticos' },
  { to: '/detections', icon: ShieldAlert,     label: 'Detecções' },
  { to: '/map',        icon: MapPin,          label: 'Mapa Tático' },
  { to: '/persons',    icon: UserCheck,       label: 'Pessoas',    adminOnly: true },
  { to: '/clips',      icon: Film,            label: 'Clips' },
  { to: '/users',      icon: Users,           label: 'Usuários',   adminOnly: true },
  { to: '/settings',   icon: Settings,        label: 'Configurações', adminOnly: true },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const { theme } = useThemeStore()
  const { logout, refreshToken } = useAuthStore()
  const { isCityAdmin } = usePermission()
  const navigate = useNavigate()

  const handleLogout = async () => {
    try {
      if (refreshToken) await authService.logout(refreshToken)
    } catch { /* ignore */ }
    logout()
    navigate('/login')
    toast.success('Sessão encerrada')
  }

  const visibleItems = NAV_ITEMS.filter(item => !item.adminOnly || isCityAdmin)

  return (
    <aside
      className={clsx(
        'flex flex-col h-full transition-all duration-200 border-r',
        collapsed ? 'w-16' : 'w-56',
      )}
      style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}
    >
      {/* Logo */}
      <div className={clsx('flex items-center h-14 px-3 border-b shrink-0', collapsed && 'justify-center')}
        style={{ borderColor: 'var(--border)' }}>
        {!collapsed && (
          <div className="flex items-center gap-2 min-w-0">
            {theme?.logo_url
              ? <img src={theme.logo_url} alt={theme.company_name ?? theme.name} className="h-7 w-auto object-contain" />
              : <div className="w-7 h-7 rounded-md flex items-center justify-center text-white text-xs font-bold"
                  style={{ background: 'var(--accent)' }}>V</div>
            }
            <span className="text-sm font-semibold text-t1 truncate">{theme?.company_name ?? theme?.name ?? 'VMS'}</span>
          </div>
        )}
        {collapsed && (
          <div className="w-7 h-7 rounded-md flex items-center justify-center text-white text-xs font-bold"
            style={{ background: 'var(--accent)' }}>V</div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {visibleItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/dashboard'}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-all duration-100 group',
                collapsed ? 'justify-center' : '',
                isActive
                  ? 'text-white'
                  : 'text-t2 hover:text-t1 hover:bg-elevated',
              )
            }
            style={({ isActive }) =>
              isActive ? { background: 'var(--accent)', color: '#fff' } : {}
            }
          >
            <Icon size={18} className="shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t px-2 py-2 space-y-0.5 shrink-0" style={{ borderColor: 'var(--border)' }}>
        <button
          onClick={handleLogout}
          title={collapsed ? 'Sair' : undefined}
          className={clsx(
            'flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium text-t2 hover:text-danger hover:bg-elevated transition-all w-full',
            collapsed && 'justify-center',
          )}
        >
          <LogOut size={18} className="shrink-0" />
          {!collapsed && <span>Sair</span>}
        </button>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(c => !c)}
          title={collapsed ? 'Expandir' : 'Recolher'}
          className={clsx(
            'flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium text-t3 hover:text-t1 hover:bg-elevated transition-all w-full',
            collapsed && 'justify-center',
          )}
        >
          {collapsed ? <ChevronRight size={16} /> : <><ChevronLeft size={16} /><span>Recolher</span></>}
        </button>
      </div>
    </aside>
  )
}
