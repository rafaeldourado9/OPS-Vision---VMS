import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import { useEffect, type ReactNode } from 'react'
import DashboardLayout from './layouts/DashboardLayout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import CamerasPage from './pages/CamerasPage'
import CameraDetailPage from './pages/CameraDetailPage'
import MosaicPage from './pages/MosaicPage'
import RecordingsPage from './pages/RecordingsPage'
import PlaybackPage from './pages/PlaybackPage'
import EventsPage from './pages/EventsPage'
import NotificationsPage from './pages/NotificationsPage'
import AgentsPage from './pages/AgentsPage'
import ClipsPage from './pages/ClipsPage'
import UsersPage from './pages/UsersPage'
import SettingsPage from './pages/SettingsPage'
import AnalyticsPage from './pages/AnalyticsPage'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const fetchUser = useAuthStore((s) => s.fetchUser)

  useEffect(() => {
    if (isAuthenticated) fetchUser()
  }, [isAuthenticated, fetchUser])

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="cameras" element={<CamerasPage />} />
        <Route path="cameras/:id" element={<CameraDetailPage />} />
        <Route path="mosaic" element={<MosaicPage />} />
        <Route path="recordings" element={<RecordingsPage />} />
        <Route path="recordings/:cameraId/playback" element={<PlaybackPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="detections" element={<EventsPage />} />
        <Route path="clips" element={<ClipsPage />} />
        <Route path="people" element={<SettingsPage />} />
        <Route path="tactical-map" element={<SettingsPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="agents" element={<AgentsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
