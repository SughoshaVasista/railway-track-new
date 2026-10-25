import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 8000,
})

let unauthorizedHandler
export const registerUnauthorizedHandler = (handler) => { unauthorizedHandler = handler }

const storedAuth = () => {
  for (const storage of [window.localStorage, window.sessionStorage]) {
    const raw = storage.getItem('amrin_auth')
    if (!raw) continue
    try {
      const auth = JSON.parse(raw)
      if (auth && typeof auth === 'object') return auth
    } catch {
      storage.removeItem('amrin_auth')
    }
  }
  return null
}

api.interceptors.request.use((config) => {
  const auth = storedAuth()
  if (auth?.token) config.headers.Authorization = `Bearer ${auth.token}`
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) config.headers.delete?.('Content-Type')
  return config
})

api.interceptors.response.use((response) => response, (error) => {
  const requestPath = String(error.config?.url || '')
  const isPublicAuthRequest = /\/auth\/(login|register)\/?$/.test(requestPath)
  const apiError = error.response?.data?.error
  if (apiError?.code) error.code = apiError.code
  if (apiError?.message) error.message = apiError.message
  if (error.response?.status === 401 && !isPublicAuthRequest) unauthorizedHandler?.()
  return Promise.reject(error)
})

export const apiErrorMessage = (error, fallback = 'The server did not accept this request.') => error?.response?.data?.error?.message || error?.message || fallback

const get = (path, params) => api.get(path, { params }).then(({ data }) => data)
const post = (path, body) => api.post(path, body).then(({ data }) => data)

export const loginRequest = (credentials) => post('/auth/login', credentials)
export const registerRequest = (body) => post('/auth/register', body)
export const getCurrentUser = () => get('/auth/me')
export const getAlerts = (filters = {}) => get('/alerts', filters)
export const getAlert = (id) => get(`/alerts/${id}`)
export const acknowledgeAlert = (id, body) => post(`/alerts/${id}/acknowledge`, body)
export const resolveAlert = (id, body) => post(`/alerts/${id}/resolve`, body)
export const markFalsePositive = (id, body) => post(`/alerts/${id}/false-positive`, body)
export const assignAlert = (id, body) => post(`/alerts/${id}/assign`, body)
export const changeAlertPriority = (id, body) => post(`/alerts/${id}/priority`, body)
export const getAlertHistory = (id) => get(`/alerts/${id}/history`)
export const getDevices = () => get('/devices')
export const getDeviceSensors = (id, params = {}) => get(`/devices/${id}/sensors`, params)
export const getDeviceDiagnostics = (id) => get(`/devices/${id}/diagnostics`)
export const getTasks = (params = {}) => get('/tasks', params)
export const createTask = (body) => post('/tasks', body)
export const assignTask = (id, body) => post(`/tasks/${encodeURIComponent(id)}/assignment`, body)
export const unassignTask = (id) => api.delete(`/tasks/${encodeURIComponent(id)}/assignment`).then(({ data }) => data)
export const getWorkers = () => get('/workers')
export const getPendingUsers = () => get('/users/pending')
export const approveUser = (id) => post(`/users/${encodeURIComponent(id)}/approve`)
export const rejectUser = (id) => post(`/users/${encodeURIComponent(id)}/reject`)
export const updateTaskStatus = (id, body) => api.put(`/tasks/${id}/status`, body).then(({ data }) => data)
export const submitTaskForReview = (id, body = {}) => post(`/tasks/${encodeURIComponent(id)}/submit`, body)
export const reviewTask = (id, body) => post(`/tasks/${encodeURIComponent(id)}/review`, body)
export const uploadTaskEvidence = (id, body) => api.post(`/tasks/${encodeURIComponent(id)}/evidence`, body).then(({ data }) => data)
export const getTaskEvidenceImage = (url) => {
  const path = url.startsWith('/api/') ? url.slice(4) : url
  return api.get(path, { responseType: 'blob' }).then(({ data }) => data)
}
export const getTracks = (params = {}) => get('/tracks', params)
export const getTrains = (params = {}) => get('/trains', params)
export const getSwitchStatus = (params = {}) => get('/switch/status', params)
export const getDashboardSummary = (params = {}) => get('/dashboard/summary', params)
export const getDashboardEventLog = (params = {}) => get('/dashboard/event-log', params)
export const getModelStatus = () => get('/model/status')
export const getAIDetection = () => get('/ai/detection')
