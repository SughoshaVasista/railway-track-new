import React from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import './App.css'
import Login from './pages/Login'
import Shell from './components/Shell'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './context/AuthContext'
import { AppModeProvider } from './context/AppModeContext'

export default function App() {
  return <BrowserRouter><AuthProvider><AppModeProvider><Routes><Route path="/login" element={<Login />} /><Route element={<ProtectedRoute allowedRoles={['admin', 'worker']} />}><Route path="/*" element={<Shell />} /></Route><Route path="*" element={<Navigate to="/login" replace />} /></Routes></AppModeProvider></AuthProvider></BrowserRouter>
}
