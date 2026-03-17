// ─── Auth ────────────────────────────────────────────────────────────────────

export type Role = 'operator' | 'supervisor' | 'admin' | 'super_admin'

export interface User {
  id: string
  email: string
  name: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface AuthTokens {
  access: string
  refresh: string
}

// ─── Theme ───────────────────────────────────────────────────────────────────

export interface Theme {
  name?: string
  company_name?: string
  primary_color?: string
  logo_url?: string
  favicon_url?: string
}

// ─── Camera ──────────────────────────────────────────────────────────────────

export type Manufacturer = 'hikvision' | 'intelbras' | 'dahua' | 'other'

export interface Camera {
  id: string
  name: string
  location: string
  rtsp_url: string
  manufacturer: Manufacturer
  retention_days: number
  is_online: boolean
  agent?: string | null
  tenant?: string
  created_at: string
  updated_at: string
}

export interface StreamInfo {
  camera_id: string
  is_online: boolean
  hls_url: string
  webrtc_url: string
  token: string
  expires_at: string | null
}

export interface PushConfig {
  rtmp_url: string    // ex: rtmp://cameras.suaempresa.com:1935
  stream_key: string  // ex: tenant-1/cam-5
  username: string    // ex: cam-5
  password: string    // token HMAC-SHA256
  full_url: string    // rtmp://user:pass@host:1935/path
}

// ─── ROI ─────────────────────────────────────────────────────────────────────

export type ROIType =
  | 'vehicle_dwell'
  | 'intrusion'
  | 'object_detected'
  | 'crowd'
  | 'vehicle_traffic'
  | 'human_traffic'
  | 'line_crossing'
  | 'loitering'
  | 'abandoned_object'
  | 'queue'
  | 'heatmap'
  | 'lpr'
  | 'facial'

export interface ROI {
  id: string
  camera: string
  name: string
  polygon_points: number[][]
  ia_type: ROIType
  config?: Record<string, unknown>
  is_active: boolean
  created_at: string
}

// ─── Event ───────────────────────────────────────────────────────────────────

export type EventType =
  | 'camera.online'
  | 'camera.offline'
  | 'motion.detected'
  | 'alpr.detected'
  | 'intrusion.detected'
  | 'fire.detected'
  | 'video.loss'
  | 'tampering.detected'
  | 'line_crossing.detected'
  | 'face.detected'

export interface VMSEvent {
  id: string
  event_type: EventType
  payload: Record<string, unknown>
  camera: string
  camera_name?: string
  plate?: string | null
  confidence?: number | null
  created_at: string
}

// ─── Recording / Segment ─────────────────────────────────────────────────────

export interface RecordingSegment {
  id: string
  camera: string
  start_time: string
  end_time: string
  duration_seconds: number
  file_path: string
}

// ─── Clip ────────────────────────────────────────────────────────────────────

export type ClipStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface Clip {
  id: string
  camera: string
  camera_name?: string
  event?: string | null
  start_time: string
  end_time: string
  file_path?: string
  status: ClipStatus
  created_at: string
}

// ─── Agent ───────────────────────────────────────────────────────────────────

export type AgentStatus = 'pending' | 'online' | 'offline'

export interface Agent {
  id: string
  name: string
  status: AgentStatus
  last_heartbeat?: string | null
  version?: string | null
  tenant?: string
  created_at: string
}

// ─── Notification Rule ───────────────────────────────────────────────────────

export interface NotificationRule {
  id: string
  name: string
  event_type_pattern: string
  channel: string
  destination: string
  is_active: boolean
  created_at: string
}

// ─── Dashboard Stats ─────────────────────────────────────────────────────────

export interface DashboardStats {
  total_cameras: number
  online_cameras: number
  offline_cameras: number
  total_events_today: number
  total_clips: number
  events_by_type_today: Record<string, number>
}

export interface EventsByHour {
  hour: string
  events: number
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export interface DwellEvent {
  id: string
  camera: string
  camera_name?: string
  tenant: string
  roi?: string | null
  roi_name?: string | null
  track_id: number
  entered_at: string
  exited_at?: string | null
  dwell_seconds?: number | null
  frame_path: string
  is_valid?: boolean | null
  created_at: string
}

export interface FaceDetectionEvent {
  id: string
  camera: string
  camera_name?: string
  roi?: string | null
  roi_name?: string | null
  face_profile?: string | null
  profile_name?: string | null
  confidence: number
  is_unknown: boolean
  frame_path: string
  created_at: string
}

// ─── Pagination ──────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  count: number
  next?: string | null
  previous?: string | null
  results: T[]
}
