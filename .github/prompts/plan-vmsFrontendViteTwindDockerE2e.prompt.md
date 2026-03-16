# Plan: VMS Frontend with Vite + Twind + Docker Integration & E2E Testing

Build the complete VMS frontend SPA using React + Vite + Twind (dark theme matching screenshots), Dockerize it behind nginx, spin up the full stack, add 7 real cameras from urls.txt, and integration-test every endpoint including live streams, events, webhooks, and notifications.

---

## Phase A — Frontend Scaffold & Core Infrastructure

### A1. Initialize Vite + React + TypeScript project in `frontend/`
- Deps: `twind`, `@twind/preset-tailwind`, `react-router-dom@6`, `zustand`, `axios`, `hls.js`, `chart.js`, `react-chartjs-2`, `lucide-react` (icons)
- Twind theme tokens extracted from screenshots:
  - Backgrounds: `#0f1117` (main), `#1a1d27` (sidebar), `#1e2130` (cards)
  - Accent: `#3b82f6` (blue), `#22c55e` (green/online), `#ef4444` (red/offline)
  - Text: `#ffffff` (primary), `#9ca3af` (muted)

### A2. API client + auth layer
- Axios instance with baseURL `/api/v1/`, Bearer token interceptor, 401 → auto-refresh
- Zustand auth store: `login()`, `logout()`, token persistence in localStorage, user info
- SSE client connecting to `/sse/?token=<jwt>` for realtime events

### A3. App layout + routing — Protected routes with sidebar layout matching screenshot
- `/login`, `/`, `/cameras`, `/cameras/:id`, `/mosaic`, `/recordings`, `/recordings/:cameraId/playback`, `/analytics`, `/detections`, `/clips`, `/people`, `/tactical-map`, `/users`, `/settings`, `/notifications`

---

## Phase B — Pages & Components (matching screenshot design)

### B1. Login Page
- Split layout: left = blue gradient + camera pattern SVG + VMS branding + feature badges (IA Embarcada, Multi-Câmera, Analíticos, Dark Mode); right = dark form (email, senha, "Entrar" button, "VMS © 2026")

### B2. Dashboard
- Top 5 stat cards (Total Câmeras, Online, Offline, Detecções Hoje, Clips)
- 2 charts (Detecções por Hora bar chart, Eventos Hoje pie chart)
- Camera status list with online/offline badges

### B3. Cameras Page
- Card list with CRUD, "Adicionar Câmera" modal with RTSP URL validation
- Click → detail with HLS.js live player

### B4. Mosaic Page
- 2x2 / 3x3 grid of live HLS feeds, camera selector

### B5. Recordings & Playback
- Timeline per camera, segment list, HLS.js playback
- Clip creation form, clip list + download

### B6. Events/Detections
- Filterable table (event_type, camera, plate, confidence, date range)
- Pagination, ALPR events with plate badge

### B7. Notifications
- Rule CRUD (name, pattern, channel, destination, secret, active toggle)
- Log list (status, response_code, timestamp)

### B8. Agents, Clips, Users, Settings
- Agent CRUD (API key shown once), clip download, user profile, placeholder settings

---

## Phase C — Docker Integration

### C1. Frontend Dockerfile
- Multi-stage: `node:20-alpine` build → `nginx:alpine` serve static files

### C2. Update `docker-compose.yml`
- Add `frontend` service, depends_on django + fastapi

### C3. Update `infra/nginx/nginx.conf`
- Add `location /` → frontend proxy
- Add `/hls/` and `/webrtc/` → MediaMTX proxy
- Update CSP for connect-src to allow HLS/WebRTC origins

### C4. Update `.env.example`
- Add `VITE_API_BASE_URL`, `VITE_SSE_URL`, `VITE_HLS_BASE_URL`, `VITE_WEBRTC_BASE_URL`

### C5. Update `Makefile`
- Fix frontend targets to reference Docker

---

## Phase D — Stack Startup & Camera Registration

### D1. Build and start full stack
- `docker compose build && docker compose up -d`
- Verify all 10 services healthy

### D2. Create superuser & tenant
- Via Django management command, verify login via frontend

### D3. Add 7 cameras from `urls.txt`
- cam-port-6045 through cam-port-6050 (7 Intelbras/Dahua cameras on IPs 45.236.226.70-74):
  1. `cam-port-6045` — `rtsp://admin:Camerite123@45.236.226.70:6045/cam/realmonitor?channel=1&subtype=0`
  2. `cam-port-6044` — `rtsp://admin:Camerite123@45.236.226.70:6044/cam/realmonitor?channel=1&subtype=0`
  3. `cam-port-6046` — `rtsp://admin:Camerite123@45.236.226.71:6046/cam/realmonitor?channel=1&subtype=0`
  4. `cam-port-6047` — `rtsp://admin:Camerite123@45.236.226.71:6047/cam/realmonitor?channel=1&subtype=0`
  5. `cam-port-6048` — `rtsp://admin:Camerite123@45.236.226.72:6048/cam/realmonitor?channel=1&subtype=0`
  6. `cam-port-6049` — `rtsp://admin:Camerite123@45.236.226.72:6049/cam/realmonitor?channel=1&subtype=0`
  7. `cam-port-6050` — `rtsp://admin:Camerite123@45.236.226.74:6050/cam/realmonitor?channel=1&subtype=0`

### D4. Verify MediaMTX paths
- `curl http://localhost:9997/v3/paths/list` → all camera paths registered

---

## Phase E — Integration Testing

### E1. Test all API endpoints
- Login, dashboard stats, camera CRUD, live stream HLS, events with filters, recordings timeline, clip create/download, notification rule CRUD, notification logs, agents

### E2. Test camera online/offline
- Health check task marks cameras correctly, UI reflects status

### E3. Test webhook/event pipeline
- Send ALPR webhook → verify event in DB → verify in Events page → verify SSE delivers realtime → verify deduplication (no duplicate < 60s)

### E4. Test notification dispatch
- Create rule matching `detection.alpr` → trigger ALPR event → verify NotificationLog

### E5. Test recordings
- Wait for 60s segments → verify in timeline API → playback via HLS

---

## Relevant Files

### New (frontend/) — ~30 files
- `frontend/package.json` — dependencies and scripts
- `frontend/vite.config.ts` — Vite config with proxy
- `frontend/tsconfig.json` — TypeScript config
- `frontend/index.html` — SPA entry point
- `frontend/Dockerfile` — multi-stage Docker build
- `frontend/src/main.tsx` — React entry
- `frontend/src/App.tsx` — Router + Twind setup
- `frontend/src/twind.config.ts` — Twind theme (colors from screenshot)
- `frontend/src/lib/api.ts` — Axios client + JWT interceptor
- `frontend/src/lib/sse.ts` — SSE realtime client
- `frontend/src/stores/authStore.ts` — Auth state (Zustand)
- `frontend/src/stores/cameraStore.ts` — Camera state
- `frontend/src/stores/eventStore.ts` — Events state
- `frontend/src/layouts/DashboardLayout.tsx` — Main layout with sidebar
- `frontend/src/layouts/AuthLayout.tsx` — Login layout
- `frontend/src/pages/LoginPage.tsx` — Login (matching screenshot)
- `frontend/src/pages/DashboardPage.tsx` — Dashboard (matching screenshot)
- `frontend/src/pages/CamerasPage.tsx` — Camera list + CRUD
- `frontend/src/pages/CameraDetailPage.tsx` — Live view + camera info
- `frontend/src/pages/MosaicPage.tsx` — Multi-camera grid
- `frontend/src/pages/RecordingsPage.tsx` — Recording segments + clips
- `frontend/src/pages/PlaybackPage.tsx` — Video playback
- `frontend/src/pages/EventsPage.tsx` — Events/detections list
- `frontend/src/pages/NotificationsPage.tsx` — Rules + logs
- `frontend/src/pages/AgentsPage.tsx` — Agent management
- `frontend/src/pages/ClipsPage.tsx` — Clip list + download
- `frontend/src/pages/UsersPage.tsx` — User info
- `frontend/src/pages/SettingsPage.tsx` — Settings
- `frontend/src/components/Sidebar.tsx` — Navigation sidebar
- `frontend/src/components/StatsCard.tsx` — Dashboard stat cards
- `frontend/src/components/VideoPlayer.tsx` — HLS.js wrapper
- `frontend/src/components/CameraCard.tsx` — Camera list card
- `frontend/src/components/EventRow.tsx` — Event list item
- `frontend/src/components/Modal.tsx` — Reusable modal
- `frontend/src/components/Pagination.tsx` — Pagination controls

### Modified
- `docker-compose.yml` — Add frontend service
- `infra/nginx/nginx.conf` — Add frontend proxy + MediaMTX proxy routes
- `.env.example` — Add VITE_* variables
- `Makefile` — Update frontend targets

---

## Verification

1. `docker compose build` → all services build OK
2. `docker compose up -d && docker compose ps` → 10 services running
3. `http://localhost` → login page matches screenshot design
4. Login → dashboard loads with real stats from API
5. Add 7 cameras → visible in list, MediaMTX paths confirmed
6. Click camera → HLS live stream plays
7. Mosaic → multi-feed grid works
8. Send ALPR webhook → event appears in UI + SSE delivery
9. Notification rule + trigger → log entry created
10. 60s+ → recording segments in timeline, playback works
11. Clip create + download functional
12. `curl http://localhost/api/v1/health/` → 200 OK

---

## Decisions

- **Twind v1** (stable, Tailwind-in-JS) — no PostCSS build step needed
- **Zustand** state, **HLS.js** video, **Chart.js** charts, **port 3000** dev
- Dark theme only for V1 (matching screenshots), all PT-BR labels
- Frontend served via nginx in Docker, no direct port exposure in prod
- Placeholder pages for People (face_recognition) and Tactical Map (future)
- Camera names: descriptive based on port number
