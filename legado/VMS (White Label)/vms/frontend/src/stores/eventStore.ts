import { create } from 'zustand'
import api from '../lib/api'

export interface VmsEvent {
  id: number
  event_type: string
  payload: Record<string, unknown>
  camera: number | null
  tenant: number
  plate: string | null
  confidence: number | null
  created_at: string
}

interface EventState {
  events: VmsEvent[]
  count: number
  loading: boolean
  fetchEvents: (params?: Record<string, string>) => Promise<void>
}

export const useEventStore = create<EventState>((set) => ({
  events: [],
  count: 0,
  loading: false,
  fetchEvents: async (params = {}) => {
    set({ loading: true })
    try {
      const { data } = await api.get('/events/', { params: { page_size: 50, ...params } })
      set({ events: data.results ?? data, count: data.count ?? 0 })
    } catch {
      // handled by interceptor
    } finally {
      set({ loading: false })
    }
  },
}))
