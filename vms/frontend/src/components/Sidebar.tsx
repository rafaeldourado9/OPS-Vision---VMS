import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Camera,
  Grid3X3,
  Film,
  BarChart3,
  Search,
  MapPin,
  Users,
  Scissors,
  Bell,
  Settings,
  LogOut,
  ChevronLeft,
} from 'lucide-react'
import { useState } from 'react'
import { useAuthStore } from '../stores/authStore'
import { cn } from '../lib/utils'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/cameras', icon: Camera, label: 'Câmeras' },
  { to: '/mosaic', icon: Grid3X3, label: 'Mosaico' },
  { to: '/recordings', icon: Film, label: 'Gravações' },
  { to: '/analytics', icon: BarChart3, label: 'Analíticos' },
  { to: '/detections', icon: Search, label: 'Detecções' },
  { to: '/tactical-map', icon: MapPin, label: 'Mapa Tático' },
  { to: '/people', icon: Users, label: 'Pessoas' },
  { to: '/clips', icon: Scissors, label: 'Clips' },
  { to: '/users', icon: Users, label: 'Usuários' },
  { to: '/notifications', icon: Bell, label: 'Configurações' },
]

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <aside
      className={cn(
        'flex flex-col bg-vms-sidebar border-r border-vms-border h-screen sticky top-0 transition-all duration-200',
        collapsed ? 'w-16' : 'w-56',
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 h-14 border-b border-vms-border">
        <div className="w-8 h-8 rounded-lg bg-vms-accent flex items-center justify-center text-white font-bold text-sm shrink-0">
          V
        </div>
        {!collapsed && <span className="font-semibold text-lg">VMS</span>}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-vms-accent text-white'
                  : 'text-vms-muted hover:text-white hover:bg-vms-card',
              )
            }
          >
            <item.icon size={18} className="shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Bottom */}
      <div className="border-t border-vms-border p-2 space-y-1">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-4 py-2.5 mx-0 rounded-lg text-sm text-vms-muted hover:text-white hover:bg-vms-card w-full transition-colors"
        >
          <LogOut size={18} className="shrink-0" />
          {!collapsed && <span>Sair</span>}
        </button>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-3 px-4 py-2 mx-0 rounded-lg text-sm text-vms-muted hover:text-white hover:bg-vms-card w-full transition-colors"
        >
          <ChevronLeft
            size={18}
            className={cn('shrink-0 transition-transform', collapsed && 'rotate-180')}
          />
          {!collapsed && <span>Recolher</span>}
        </button>
      </div>
    </aside>
  )
}
