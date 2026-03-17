import axios from 'axios'
import type {
  User, Camera, ROI, VMSEvent, RecordingSegment, Clip, Agent,
  NotificationRule, StreamInfo, PushConfig, PaginatedResponse,
  DwellEvent, FaceDetectionEvent,
} from '@/types'

// ─── Axios instance ───────────────────────────────────────────────────────────

const api = axios.create({ baseURL: '/api/v1' })

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
  // SimpleJWT accepts username or email depending on backend config
  // Current VMS uses email as username field
  login: (data: { email: string; password: string }) =>
    api.post<{ access: string; refresh: string }>('/auth/token/', {
      username: data.email,
      password: data.password,
    }).then(r => r.data),

  me: (token?: string) =>
    api.get<User>('/auth/me/', token ? { headers: { Authorization: `Bearer ${token}` } } : undefined).then(r => r.data),

  refreshToken: (refresh: string) =>
    api.post<{ access: string }>('/auth/token/refresh/', { refresh }).then(r => r.data),
}

// ─── Theme ────────────────────────────────────────────────────────────────────
// No theme endpoint in current VMS — return null gracefully

export const themeService = {
  get: () => Promise.resolve(null),
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

  live: (id: string) =>
    api.get<StreamInfo>(`/cameras/${id}/live/`).then(r => r.data),

  pushConfig: (id: string) =>
    api.get<PushConfig>(`/cameras/${id}/push-config/`).then(r => r.data),

  snapshot: (id: string) =>
    `/api/v1/cameras/${id}/snapshot/`,

  // Alias for legacy compatibility
  streamUrl: (id: string) =>
    api.get<StreamInfo>(`/cameras/${id}/live/`).then(r => ({
      hls: r.data.hls_url,
      webrtc_whep: r.data.webrtc_url,
    })),
}

// ─── ROI ─────────────────────────────────────────────────────────────────────
// Not yet implemented in backend — will return empty list gracefully

export const roiService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<ROI>>('/analytics/rois/', { params })
      .then(r => r.data)
      .catch(() => ({ count: 0, results: [], next: null, previous: null })),

  create: (data: {
    camera: string
    name: string
    ia_type: string
    polygon_points: number[][]
    is_active?: boolean
    config?: Record<string, unknown>
  }) =>
    api.post<ROI>('/analytics/rois/', data).then(r => r.data),

  update: (id: string, data: Partial<ROI> & { polygon_points?: number[][] }) =>
    api.patch<ROI>(`/analytics/rois/${id}/`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/analytics/rois/${id}/`),
}

// ─── Events ──────────────────────────────────────────────────────────────────

export const eventService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<VMSEvent>>('/events/', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<VMSEvent>(`/events/${id}/`).then(r => r.data),
}

// Alias for legacy DetectionsPage compatibility
export const detectionService = eventService

// ─── Recordings ──────────────────────────────────────────────────────────────

export const recordingService = {
  clips: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Clip>>('/recordings/clips/', { params }).then(r => r.data),

  timeline: (cameraId: string, params?: Record<string, unknown>) =>
    api.get<RecordingSegment[]>(`/cameras/${cameraId}/timeline/`, { params }).then(r => r.data),

  createClip: (eventId: string) =>
    api.post<Clip>(`/events/${eventId}/clip/`).then(r => r.data),

  getClip: (clipId: string) =>
    api.get<Clip>(`/clips/${clipId}/`).then(r => r.data),

  downloadClip: (clipId: string) =>
    `/api/v1/clips/${clipId}/download/`,
}

// Legacy compatibility aliases
export const clipService = {
  list: (params?: Record<string, unknown>) => recordingService.clips(params),
  delete: (id: string) => api.delete(`/clips/${id}/`),
}

export const segmentService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<RecordingSegment>>('/recordings/clips/', { params }).then(r => r.data),
}

// ─── Agents ──────────────────────────────────────────────────────────────────

export const agentService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<Agent>>('/agents/', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<Agent>(`/agents/${id}/`).then(r => r.data),

  create: (data: Partial<Agent>) =>
    api.post<Agent>('/agents/', data).then(r => r.data),

  update: (id: string, data: Partial<Agent>) =>
    api.patch<Agent>(`/agents/${id}/`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/agents/${id}/`),
}

// ─── Notifications ───────────────────────────────────────────────────────────

export const notificationService = {
  listRules: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<NotificationRule>>('/notifications/rules/', { params }).then(r => r.data),

  createRule: (data: Partial<NotificationRule>) =>
    api.post<NotificationRule>('/notifications/rules/', data).then(r => r.data),

  updateRule: (id: string, data: Partial<NotificationRule>) =>
    api.patch<NotificationRule>(`/notifications/rules/${id}/`, data).then(r => r.data),

  deleteRule: (id: string) =>
    api.delete(`/notifications/rules/${id}/`),

  listLogs: (params?: Record<string, unknown>) =>
    api.get('/notifications/logs/', { params }).then(r => r.data),
}

// ─── Users ───────────────────────────────────────────────────────────────────
// Limited API — only me/ available currently

export const userService = {
  me: () =>
    api.get<User>('/auth/me/').then(r => r.data),

  // Stub list — returns current user only until user management API is built
  list: (_params?: Record<string, unknown>) =>
    api.get<User>('/auth/me/').then(r => ({
      count: 1,
      results: [r.data],
      next: null,
      previous: null,
    })),
}

// ─── Analytics (dwell, face events) ─────────────────────────────────────────

export const analyticsDwellService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<DwellEvent>>('/analytics/dwell-events/', { params }).then(r => r.data),
}

export const analyticsFaceService = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<FaceDetectionEvent>>('/analytics/face-events/', { params }).then(r => r.data),
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export const dashboardService = {
  stats: () =>
    api.get('/dashboard/stats/').then(r => r.data),

  eventsByHour: () =>
    api.get('/dashboard/events-by-hour/').then(r => r.data),
}
