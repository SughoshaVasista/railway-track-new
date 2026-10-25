import React, { createContext, useContext, useMemo, useState } from 'react'
const AppModeContext = createContext(null)
export function AppModeProvider({ children }) {
  const [mode, setModeState] = useState('live')
  const [refreshKey, setRefreshKey] = useState(0)
  const setMode = (next) => { setModeState(next); setRefreshKey((value) => value + 1) }
  const value = useMemo(() => ({ mode, setMode, refreshKey }), [mode, refreshKey])
  return <AppModeContext.Provider value={value}>{children}</AppModeContext.Provider>
}
export const useAppMode = () => useContext(AppModeContext) || { mode: 'live', refreshKey: 0, setMode: () => {} }
