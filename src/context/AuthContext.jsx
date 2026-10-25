import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { loginRequest, registerUnauthorizedHandler } from '../services/api'

const AUTH_KEY = 'amrin_auth'
const DEMO_AUTH_ENABLED = import.meta.env.DEV && import.meta.env.VITE_DEMO_AUTH !== 'false'
const AuthContext = createContext(null)

const readStoredAuth = () => {
  for (const storage of [window.localStorage, window.sessionStorage]) {
    try {
      const raw = storage.getItem(AUTH_KEY)
      if (!raw) continue
      const value = JSON.parse(raw)
      if (value && typeof value === 'object' && value.token && ['admin', 'worker'].includes(value.role)) return value
      storage.removeItem(AUTH_KEY)
    } catch {
      try { storage.removeItem(AUTH_KEY) } catch { /* Storage may be unavailable in private contexts. */ }
    }
  }
  return null
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => readStoredAuth())
  const [ready] = useState(true)

  const logout = () => {
    window.localStorage.removeItem(AUTH_KEY)
    window.sessionStorage.removeItem(AUTH_KEY)
    setAuth(null)
  }

  useEffect(() => {
    registerUnauthorizedHandler(logout)
    return () => registerUnauthorizedHandler(undefined)
  }, [])

  const login = async (credentials, remember) => {
    let result
    try {
      result = await loginRequest(credentials)
    } catch (error) {
      const demoUsers = { admin: { password: 'admin', role: 'admin', name: 'Admin User' }, worker: { password: 'worker', role: 'worker', name: 'Maintenance Worker', worker_id: 'worker-01' } }
      const demoUser = demoUsers[credentials.username]
      if (!DEMO_AUTH_ENABLED || !demoUser || demoUser.password !== credentials.password) throw error
      result = { token: `demo-${credentials.username}-token`, ...demoUser }
    }
    const nextAuth = { token: result.token, role: result.role, name: result.name, worker_id: result.worker_id }
    const storage = remember ? window.localStorage : window.sessionStorage
    window.localStorage.removeItem(AUTH_KEY)
    window.sessionStorage.removeItem(AUTH_KEY)
    storage.setItem(AUTH_KEY, JSON.stringify(nextAuth))
    setAuth(nextAuth)
    return nextAuth
  }

  const value = useMemo(() => ({ auth, user: auth, ready, login, logout }), [auth, ready])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
