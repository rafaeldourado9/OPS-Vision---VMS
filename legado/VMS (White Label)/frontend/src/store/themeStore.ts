import { create } from 'zustand'
import type { Theme } from '@/types'

interface ThemeState {
  theme: Theme | null
  loading: boolean
  setTheme: (theme: Theme) => void
  setLoading: (v: boolean) => void
  primaryColor: () => string
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme:   null,
  loading: true,

  setTheme: (theme) => {
    set({ theme })
    // Aplica cor primária como CSS var global
    document.documentElement.style.setProperty('--accent', theme.primary_color ?? null)
    // Favicon dinâmico
    if (theme.favicon_url) {
      const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
      if (link) link.href = theme.favicon_url
    }
    // Título dinâmico
    document.title = theme.name || 'VMS'
  },

  setLoading: (v) => set({ loading: v }),

  primaryColor: () => get().theme?.primary_color || '#3B82F6',
}))
