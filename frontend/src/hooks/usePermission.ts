import { useAuthStore } from '@/store/authStore'
import type { Role } from '@/types'

const ROLE_HIERARCHY: Record<string, number> = {
  operator:   1,
  supervisor: 2,
  admin:      3,
  super_admin: 4,
}

export function usePermission() {
  const user = useAuthStore(s => s.user)

  const hasRole = (minRole: Role): boolean => {
    if (!user) return false
    return (ROLE_HIERARCHY[user.role] ?? 0) >= (ROLE_HIERARCHY[minRole] ?? 0)
  }

  const isCityAdmin    = hasRole('admin')
  const isSuperAdmin   = hasRole('super_admin')
  const isResellerAdmin = hasRole('admin')

  return { hasRole, isCityAdmin, isSuperAdmin, isResellerAdmin, user }
}
