import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { useAuthStore } from '@/store/authStore'
import { useThemeStore } from '@/store/themeStore'
import { themeService } from '@/services/api'

import { LoginPage }           from '@/pages/LoginPage'
import { DashboardPage }       from '@/pages/DashboardPage'
import { CamerasPage }         from '@/pages/CamerasPage'
import { CameraDetailPage }    from '@/pages/CameraDetailPage'
import { ROIEditorPage }       from '@/pages/ROIEditorPage'
import { MosaicPage }          from '@/pages/MosaicPage'
import { RecordingsPage }      from '@/pages/RecordingsPage'
import { EventsPage }          from '@/pages/EventsPage'
import { AnalyticsPage }       from '@/pages/AnalyticsPage'
import { ClipsPage }           from '@/pages/ClipsPage'
import { AgentsPage }          from '@/pages/AgentsPage'
import { NotificationsPage }   from '@/pages/NotificationsPage'
import { UsersPage }           from '@/pages/UsersPage'
import { SettingsPage }        from '@/pages/SettingsPage'

function RequireAuth() {
  const { isAuthenticated } = useAuthStore()
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  return <Outlet />
}

function ThemeLoader() {
  const { setTheme, setLoading } = useThemeStore()

  useEffect(() => {
    themeService.get()
      .then(t => { if (t) setTheme(t) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <ThemeLoader />
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<RequireAuth />}>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard"               element={<DashboardPage />} />
            <Route path="/cameras"                 element={<CamerasPage />} />
            <Route path="/cameras/:id"             element={<CameraDetailPage />} />
            <Route path="/cameras/:id/roi"         element={<ROIEditorPage />} />
            <Route path="/mosaic"                  element={<MosaicPage />} />
            <Route path="/recordings"              element={<RecordingsPage />} />
            <Route path="/events"                  element={<EventsPage />} />
            <Route path="/analytics"               element={<AnalyticsPage />} />
            <Route path="/clips"                   element={<ClipsPage />} />
            <Route path="/agents"                  element={<AgentsPage />} />
            <Route path="/notifications"           element={<NotificationsPage />} />
            <Route path="/users"                   element={<UsersPage />} />
            <Route path="/settings"                element={<SettingsPage />} />
            <Route path="*"                        element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
