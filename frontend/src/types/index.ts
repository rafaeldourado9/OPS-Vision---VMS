// ─── Auth ────────────────────────────────────────────────────────────────────

export type Role =
  | 'operator'
  | 'supervisor'
  | 'city_admin'
  | 'reseller_admin'
  | 'super_admin'

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
  terms_url?: string
  privacy_url?: string
}

// ─── Camera ──────────────────────────────────────────────────────────────────

export type StreamProtocol = 'rtsp' | 'rtmp' | 'hls'

export interface Camera {
  id: string
  name: string
  address: string
  lat?: number | null
  lng?: number | null
  stream_protocol: StreamProtocol
  stream_url?: string
  stream_key?: string
  retention_days: number
  ia_enabled: boolean
  online: boolean
  last_seen?: string
  resolution?: string
  fps?: number
  created_at: string
}

export interface StreamUrl {
  hls?: string
  webrtc_whep?: string
}

// ─── ROI ─────────────────────────────────────────────────────────────────────

export type ROIType =
  | 'lpr'
  | 'crowd'
  | 'intrusion'
  | 'object_detected'
  | 'vehicle_traffic'
  | 'human_traffic'
  | 'line_crossing'
  | 'loitering'
  | 'abandoned_object'
  | 'queue'
  | 'facial'
  | 'heatmap'

export interface ROI {
  id: string
  camera: string
  name: string
  polygon_points: number[][]  // normalizado [0-1], array de [x, y]
  ia_type: ROIType
  config?: Record<string, unknown>
  enabled: boolean
  created_at: string
}

// ─── Detection / Event ───────────────────────────────────────────────────────

export type EventType =
  | 'lpr'
  | 'crowd'
  | 'intrusion'
  | 'object_detected'
  | 'vehicle_traffic'
  | 'human_traffic'
  | 'line_crossing'
  | 'loitering'
  | 'abandoned_object'
  | 'queue_alert'
  | 'facial_match'
  | 'facial_unknown'

export interface Detection {
  id: string
  camera_id: string
  roi_id?: string
  event_type: EventType
  confidence: number
  thumbnail_url?: string
  metadata: Record<string, any>
  detected_at: string
  created_at: string
}

// ─── Segments / Recordings ───────────────────────────────────────────────────

export interface Segment {
  id: string
  camera: string
  file_path: string
  started_at: string
  ended_at: string
  duration_seconds: number
  file_size_bytes: number
}

// ─── Clips ───────────────────────────────────────────────────────────────────

export type ClipStatus = 'pending' | 'processing' | 'ready' | 'error'

export interface Clip {
  id: string
  camera: string
  camera_name?: string
  name: string
  started_at: string
  ended_at: string
  duration_seconds?: number
  file_url?: string
  thumbnail_url?: string
  status: ClipStatus
  created_at: string
}

// ─── Person (Facial) ─────────────────────────────────────────────────────────

export interface Person {
  id: string
  name: string
  photo_url?: string
  notes?: string
  active: boolean
  created_at: string
  updated_at: string
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export interface DashboardStats {
  total_cameras: number
  online_cameras: number
  offline_cameras: number
  total_detections_today: number
  total_clips: number
  storage_used_gb?: number
  events_by_type_today: Record<string, number>
}

export interface DetectionByHour {
  hour: string
  detections: number
}

export interface TrafficDataPoint {
  hour?: string
  day?: string
  events: number
}

export interface EventByType {
  event_type: string
  count: number
}

// ─── Pagination ──────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  count: number
  next?: string
  previous?: string
  results: T[]
}
