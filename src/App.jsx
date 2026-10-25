import React, { Component, lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import './App.css'
import Login from './pages/Login'
import Shell from './components/Shell'
import ProtectedRoute from './components/ProtectedRoute'
import { LoadingState } from './components/StateMessage'
import { AuthProvider, useAuth } from './context/AuthContext'
import { AppModeProvider } from './context/AppModeContext'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Alerts = lazy(() => import('./pages/Alerts'))
const MapPage = lazy(() => import('./pages/MapPage'))
const AI = lazy(() => import('./pages/AI'))
const Hardware = lazy(() => import('./pages/Hardware'))
const Worker = lazy(() => import('./pages/Worker'))
const Switching = lazy(() => import('./pages/Switching'))
const Tasks = lazy(() => import('./pages/Tasks'))
const Workers = lazy(() => import('./pages/Workers'))
const RepairHistory = lazy(() => import('./pages/RepairHistory'))
const SensorHistory = lazy(() => import('./pages/SensorHistory'))
const Simulation = lazy(() => import('./pages/Simulation'))
const Model = lazy(() => import('./pages/Model'))
const Settings = lazy(() => import('./pages/Settings'))

class AppErrorBoundary extends Component {
  state = { error: false }

  static getDerivedStateFromError() { return { error: true } }

  render() {
    if (this.state.error) return <main className="app-error"><div><p className="eyebrow">RailSafe could not open this view</p><h1>Something went wrong</h1><p className="muted">Reload the page to recover. If this keeps happening, sign out and sign in again.</p><button className="primary" onClick={() => window.location.reload()}>Reload RailSafe</button></div></main>
    return this.props.children
  }
}

function HomeRedirect() {
  const { user } = useAuth()
  return <Navigate to={user?.role === 'admin' ? '/admin' : '/worker'} replace />
}

const admin = (Page) => <ProtectedRoute allowedRoles={['admin']}><Page /></ProtectedRoute>

export default function App() {
  return <AppErrorBoundary><BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AuthProvider><AppModeProvider><Suspense fallback={<LoadingState>Loading RailSafe...</LoadingState>}><Routes>
    <Route path="/login" element={<Login />} />
    <Route element={<ProtectedRoute allowedRoles={['admin', 'worker']} />}>
      <Route element={<Shell />}>
        <Route index element={<HomeRedirect />} />
        <Route path="admin" element={admin(Dashboard)} />
        <Route path="alerts" element={admin(Alerts)} />
        <Route path="hardware" element={admin(Hardware)} />
        <Route path="switching" element={admin(Switching)} />
        <Route path="tasks" element={admin(Tasks)} />
        <Route path="workers" element={admin(Workers)} />
        <Route path="repair-history" element={admin(RepairHistory)} />
        <Route path="sensor-history" element={admin(SensorHistory)} />
        <Route path="simulation" element={admin(Simulation)} />
        <Route path="model" element={admin(Model)} />
        <Route path="settings" element={admin(Settings)} />
        <Route path="map" element={<MapPage />} />
        <Route path="ai-detection" element={admin(AI)} />
        <Route path="ai" element={admin(AI)} />
        <Route path="worker" element={<Worker />} />
        <Route path="worker/:taskId" element={<Worker />} />
        <Route path="*" element={<Navigate to="/worker" replace />} />
      </Route>
    </Route>
  </Routes></Suspense></AppModeProvider></AuthProvider></BrowserRouter></AppErrorBoundary>
}
