import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { loginRequest, registerRequest, registerUnauthorizedHandler } from '../services/api'
import { loginDemo, registerDemo } from '../services/auth'

const AUTH_KEY = 'amrin_auth'
const AuthContext = createContext(null)

const readStoredAuth = () => {
  for (const storage of [window.localStorage, window.sessionStorage]) {
    const raw = storage.getItem(AUTH_KEY)
    if (!raw) continue
    try {
      const value = JSON.parse(raw)
      if (value && typeof value.token === 'string' && ['admin', 'worker'].includes(value.role)) return value
    } catch {
      // Discard malformed persisted auth and continue checking the other store.
    }
    storage.removeItem(AUTH_KEY)
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
      if (import.meta.env.VITE_DEMO_AUTH !== 'true') throw error
      result = await loginDemo(credentials.username, credentials.password)
    }
    const nextAuth = { token: result.token, role: result.role, name: result.name, worker_id: result.worker_id, city: result.city }
    const storage = remember ? window.localStorage : window.sessionStorage
    window.localStorage.removeItem(AUTH_KEY)
    window.sessionStorage.removeItem(AUTH_KEY)
    storage.setItem(AUTH_KEY, JSON.stringify(nextAuth))
    setAuth(nextAuth)
    return nextAuth
  }

  const register = async (details) => {
    try { return await registerRequest(details) } catch (error) { if (import.meta.env.VITE_DEMO_AUTH !== 'true') throw error; return registerDemo(details) }
  }

  const value = useMemo(() => ({ auth, user: auth, ready, login, register, logout }), [auth, ready])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
