import { useEffect, useState } from 'react'
import { onValue, ref } from 'firebase/database'
import { firebaseEnabled, realtimeDb } from '../firebase'
import { useAppMode } from '../context/AppModeContext'
import { getAlerts, getDashboardEventLog, getDashboardSummary, getDevices, getDeviceDiagnostics, getDeviceSensors, getModelStatus, getSimulationState, getSwitchStatus, getTasks, getTracks, getTrains, getWorkers } from '../services/api'

const unwrap = (value) => value?.items ?? value?.data ?? value ?? []

function useLiveResource({ path, fetcher, deps = [], transform = unwrap }) {
  const { mode, refreshKey } = useAppMode()
  const [refreshToken, setRefreshToken] = useState(0)
  const [state, setState] = useState({ data: null, loading: true, error: null, updatedAt: null })
  useEffect(() => {
    let cancelled = false
    let timer
    const success = (value) => !cancelled && setState({ data: transform(value), loading: false, error: null, updatedAt: Date.now() })
    const failure = (error) => !cancelled && setState({ data: null, loading: false, error, updatedAt: null })
    setState({ data: null, loading: true, error: null, updatedAt: null })
    if (firebaseEnabled && realtimeDb && path) {
      const unsubscribe = onValue(ref(realtimeDb, path), (snapshot) => success(snapshot.val()), failure)
      return () => { cancelled = true; unsubscribe() }
    }
    const poll = () => fetcher(mode).then(success).catch(failure)
    poll()
    timer = window.setInterval(poll, 3000)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [...deps, mode, refreshKey, refreshToken])
  return { ...state, refresh: () => setRefreshToken((value) => value + 1) }
}

export const useAlerts = (filters = {}) => useLiveResource({ path: 'alerts', fetcher: (mode) => getAlerts({ ...filters, mode }), deps: [JSON.stringify(filters)], transform: (value) => unwrap(value).filter((item) => Object.entries(filters).every(([key, expected]) => { if (!expected) return true; if (key === 'type') return (item.type || item.defect || item.class) === expected; return item[key] === expected })) })
export const useDashboardSummary = () => useLiveResource({ path: 'dashboard/summary', fetcher: (mode) => getDashboardSummary({ mode }), deps: [], transform: (value) => value?.summary ?? value })
export const useSwitchStatus = () => useLiveResource({ path: 'switch/status', fetcher: (mode) => getSwitchStatus({ mode }), deps: [] })
export const useSensorsLatest = (deviceId) => useLiveResource({ path: deviceId ? `devices/${deviceId}/sensors` : null, fetcher: () => getDeviceSensors(deviceId), deps: [deviceId] })
export const useSensorHistory = (deviceId, windowName = '24h') => useLiveResource({ path: null, fetcher: () => getDeviceSensors(deviceId, { history: true, window: windowName }), deps: [deviceId, windowName] })
export const useDeviceDiagnostics = (deviceId) => useLiveResource({ path: deviceId ? `devices/${deviceId}/diagnostics` : null, fetcher: () => getDeviceDiagnostics(deviceId), deps: [deviceId], transform: (value) => value })
export const useModelStatus = () => useLiveResource({ path: null, fetcher: getModelStatus, deps: [], transform: (value) => value?.model ?? value })
export const useSimulationState = () => useLiveResource({ path: null, fetcher: getSimulationState, deps: [] })
export const useWorkers = () => useLiveResource({ path: null, fetcher: getWorkers, deps: [] })
export const useDevices = () => useLiveResource({ path: 'devices', fetcher: getDevices, deps: [] })
export const useTasks = (workerId) => useLiveResource({ path: workerId ? `tasks/${workerId}` : null, fetcher: () => getTasks(workerId ? { worker_id: workerId } : {}), deps: [workerId] })
export const useMapData = () => useLiveResource({ path: null, fetcher: (mode) => Promise.all([getTracks({ mode }), getTrains({ mode })]).then(([tracks, trains]) => ({ tracks: unwrap(tracks), trains: unwrap(trains) })), deps: [], transform: (value) => value })
export const useEventLog = (since = '') => useLiveResource({ path: null, fetcher: (mode) => getDashboardEventLog({ since, mode }), deps: [since], transform: (value) => unwrap(value).sort((a, b) => new Date(b.timestamp || b.created_at || 0) - new Date(a.timestamp || a.created_at || 0)) })
