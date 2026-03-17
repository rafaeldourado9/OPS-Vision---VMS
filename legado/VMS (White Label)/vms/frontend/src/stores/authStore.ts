import { create } from 'zustand'
import api from '../lib/api'

interface User {
  id: number
  username: string
  email: string
  tenant: { id: number; name: string; slug: string }
}

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  setTokens: (access: string, refresh: string) => void
  fetchUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: localStorage.getItem('vms_access'),
  refreshToken: localStorage.getItem('vms_refresh'),
  user: null,
  isAuthenticated: !!localStorage.getItem('vms_access'),

  setTokens: (access: string, refresh: string) => {
    localStorage.setItem('vms_access', access)
    localStorage.setItem('vms_refresh', refresh)
    set({ accessToken: access, refreshToken: refresh, isAuthenticated: true })
  },

  login: async (username: string, password: string) => {
    const { data } = await api.post('/auth/token/', { username, password })
    get().setTokens(data.access, data.refresh)
    await get().fetchUser()
  },

  logout: () => {
    localStorage.removeItem('vms_access')
    localStorage.removeItem('vms_refresh')
    set({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false })
  },

  fetchUser: async () => {
    try {
      const { data } = await api.get('/auth/me/')
      set({ user: data })
    } catch {
      // token invalid
    }
  },
}))
