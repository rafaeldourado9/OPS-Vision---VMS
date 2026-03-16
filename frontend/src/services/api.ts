import axios from 'axios'
import type {
  User, Camera, ROI, Detection, Segment, Clip, Person,
  DashboardStats, DetectionByHour, TrafficDataPoint, EventByType,
  Theme, StreamUrl, PaginatedResponse,
} from '@/types'

// ─── Axios instance ───────────────────────────────────────────────────────────

const api = axios.create({ baseURL: '/api/v1' })

// Injeta access token em toda request
api.interceptors.request.use((config) => {
  const raw = localStorage.getItem('auth-storage')
  if (raw) {
    try {
      const state = JSON.parse(raw)?.state
      if (state?.accessToken) {
        config.headers.Authorization = `Bearer ${state.accessToken}`
      }
    } catch { /* ignore */ }
  }
  return config
})

// Refresh automático em 401
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        const raw = localStorage.getItem('auth-storage')
        const state = JSON.parse(raw || '{}')?.state
        if (state?.refreshToken) {
          const { data } = await axios.post('/api/v1/auth/token/refresh/', {
            refresh: state.refreshToken,
          })
          state.accessToken = data.access
          localStorage.setItem('auth-storage', JSON.stringify({ state }))
          original.headers.Authorization = `Bearer ${data.access}`
          return api(original)
        }
      } catch {
        localStorage.removeItem('auth-storage')
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  },
)

export default api

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const authService = {
  login: (data: { email: string; password: string }) =>
    api.post<{ access: string; refresh: string; user: User }>('/auth/login/', data).then(r => r.data),

  logout: (refresh: string) =>
    api.post('/auth/logout/', { refresh }),

  me: () =>
    api.get<User>('/auth/me/').then(r => r.data),

  refreshToken: (refresh: string) =>
    api.post<{ access: string }>('/auth/token/refresh/', { refresh }).then(r => r.data),
}

// ─── Theme ────────────────────────────────────────────────────────────────────

export const themeService = {
  get: () =>
    api.get<Theme>('/theme/').then(r => r.data),

  update: (data: FormData | Partial<Theme>) => {
    const isFormData = data instanceof FormData
    return api.patch<Theme>('/theme/', data, {
      headers: isFormData ? { 'Content-Type': 'multipart/form-data' } : {},
    }).then(r => r.data)
  },
}

// ─── Cameras ─────────────────────────────────────────────────────────────────

export const cameraService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Camera>>('/cameras/', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<Camera>(`/cameras/${id}/`).then(r => r.data),

  create: (data: Partial<Camera> | FormData) =>
    api.post<Camera>('/cameras/', data).then(r => r.data),

  update: (id: string, data: Partial<Camera>) =>
    api.patch<Camera>(`/cameras/${id}/`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/cameras/${id}/`),

  snapshot: (id: string) =>
    `/api/v1/cameras/${id}/snapshot/`,

  streamUrl: (id: string) =>
    api.get<StreamUrl>(`/cameras/${id}/stream-url/`).then(r => r.data),

  heatmap: (id: string) =>
    `/api/v1/cameras/${id}/heatmap/`,
}

// ─── ROI ─────────────────────────────────────────────────────────────────────

export const roiService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<ROI>>('/roi/', { params }).then(r => r.data),

  create: (data: {
    camera: string
    name: string
    ia_type: string
    polygon_points: number[][]
    enabled?: boolean
    config?: Record<string, unknown>
  }) =>
    api.post<ROI>('/roi/', data).then(r => r.data),

  update: (id: string, data: Partial<ROI> & { polygon_points?: number[][] }) =>
    api.patch<ROI>(`/roi/${id}/`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/roi/${id}/`),
}

// ─── Detection Masks ─────────────────────────────────────────────────────────

export const maskService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<{ id: string; camera: string; name: string; polygon_points: number[][]; enabled: boolean; created_at: string }>>('/detection-masks/', { params }).then(r => r.data),

  create: (data: { camera: string; name: string; polygon_points: number[][]; enabled?: boolean }) =>
    api.post('/detection-masks/', data).then(r => r.data),

  update: (id: string, data: Partial<{ name: string; polygon_points: number[][]; enabled: boolean }>) =>
    api.patch(`/detection-masks/${id}/`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/detection-masks/${id}/`),
}

// ─── Detections ───────────────────────────────────────────────────────────────

export const detectionService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Detection>>('/detections/', { params }).then(r => r.data),

  exportCsv: (params?: Record<string, unknown>) => {
    const p = new URLSearchParams(params as Record<string, string>)
    return `/api/v1/detections/export/?file_format=csv&${p.toString()}`
  },
}

// ─── Segments (Recordings) ───────────────────────────────────────────────────

export const segmentService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Segment>>('/segments/', { params }).then(r => r.data),
}

// ─── Clips ───────────────────────────────────────────────────────────────────

export const clipService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Clip>>('/clips/', { params }).then(r => r.data),

  create: (data: { camera: string; name: string; started_at: string; ended_at: string }) =>
    api.post<Clip>('/clips/', data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/clips/${id}/`),
}

// ─── Persons ─────────────────────────────────────────────────────────────────

export const personService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Person>>('/persons/', { params }).then(r => r.data),

  create: (data: FormData) =>
    api.post<Person>('/persons/', data, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data),

  update: (id: string, data: FormData | Partial<Person>) => {
    const isFormData = data instanceof FormData
    return api.patch<Person>(`/persons/${id}/`, data, {
      headers: isFormData ? { 'Content-Type': 'multipart/form-data' } : {},
    }).then(r => r.data)
  },

  delete: (id: string) =>
    api.delete(`/persons/${id}/`),
}

// ─── Users ───────────────────────────────────────────────────────────────────

export const userService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<User>>('/auth/users/', { params }).then(r => r.data),

  create: (data: Partial<User> & { password: string }) =>
    api.post<User>('/auth/users/create/', data).then(r => r.data),

  update: (id: string, data: Partial<User> & { password?: string }) =>
    api.patch<User>(`/auth/users/${id}/update/`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/auth/users/${id}/delete/`),

  updateMe: (data: Partial<User> & { password?: string }) =>
    api.patch<User>('/auth/users/me/update/', data).then(r => r.data),
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export const dashboardService = {
  stats: () =>
    api.get<DashboardStats>('/dashboard/stats/').then(r => r.data),

  detectionsByHour: () =>
    api.get<DetectionByHour[]>('/dashboard/detections-by-hour/').then(r => r.data),
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export const analyticsService = {
  trafficByHour: (params?: Record<string, unknown>) =>
    api.get<{ event_type: string; data: TrafficDataPoint[] }>('/analytics/traffic-by-hour/', { params }).then(r => r.data),

  trafficByDay: (params?: Record<string, unknown>) =>
    api.get<{ event_type: string; data: TrafficDataPoint[] }>('/analytics/traffic-by-day/', { params }).then(r => r.data),

  eventsByType: (params?: Record<string, unknown>) =>
    api.get<{ period_days: number; data: EventByType[] }>('/analytics/events-by-type/', { params }).then(r => r.data),

  queueStats: (params?: Record<string, unknown>) =>
    api.get<{ data: any[] }>('/analytics/queue-stats/', { params }).then(r => r.data),
}
