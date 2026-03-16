import { create } from 'zustand'
import api from '../lib/api'

export interface Camera {
  id: number
  name: string
  location: string
  rtsp_url: string
  manufacturer: string
  retention_days: number
  is_online: boolean
  agent: number | null
  tenant: number
  created_at: string
  updated_at: string
}

interface CameraState {
  cameras: Camera[]
  loading: boolean
  fetchCameras: () => Promise<void>
}

export const useCameraStore = create<CameraState>((set) => ({
  cameras: [],
  loading: false,
  fetchCameras: async () => {
    set({ loading: true })
    try {
      const { data } = await api.get('/cameras/', { params: { page_size: 100 } })
      set({ cameras: data.results ?? data })
    } catch {
      // handled by interceptor
    } finally {
      set({ loading: false })
    }
  },
}))
