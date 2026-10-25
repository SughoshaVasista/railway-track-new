import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { loginRequest, registerUnauthorizedHandler } from '../services/api'

const AUTH_KEY = 'amrin_auth'
const AuthContext = createContext(null)

const readStoredAuth = () => {
  const raw = window.localStorage.getItem(AUTH_KEY) || window.sessionStorage.getItem(AUTH_KEY)
  return raw ? JSON.parse(raw) : null
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
      const demoEnabled = import.meta.env.VITE_DEMO_AUTH === 'true'
      const demoUsers = { admin: { password: 'admin', role: 'admin', name: 'Admin User' }, worker: { password: 'worker', role: 'worker', name: 'Maintenance Worker', worker_id: 'worker-01' } }
      const demoUser = demoUsers[credentials.username]
      if (!demoEnabled || !demoUser || demoUser.password !== credentials.password) throw error
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
