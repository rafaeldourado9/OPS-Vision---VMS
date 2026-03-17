import { useAuthStore } from '@/store/authStore'
import type { Role } from '@/types'

const ROLE_HIERARCHY: Record<Role, number> = {
  operator:       1,
  supervisor:     2,
  city_admin:     3,
  reseller_admin: 4,
  super_admin:    5,
}

export function usePermission() {
  const user = useAuthStore(s => s.user)

  const hasRole = (minRole: Role): boolean => {
    if (!user) return false
    return ROLE_HIERARCHY[user.role] >= ROLE_HIERARCHY[minRole]
  }

  const isCityAdmin    = hasRole('city_admin')
  const isSuperAdmin   = hasRole('super_admin')
  const isResellerAdmin = hasRole('reseller_admin')

  return { hasRole, isCityAdmin, isSuperAdmin, isResellerAdmin, user }
}
