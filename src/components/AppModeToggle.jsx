import React from 'react'
import { useAppMode } from '../context/AppModeContext'

export default function AppModeToggle() {
  const { mode, setMode } = useAppMode()
  return <div className="mode-toggle" role="group" aria-label="Application mode">{['live', 'simulation'].map((item) => <button key={item} className={mode === item ? 'selected' : ''} aria-pressed={mode === item} onClick={() => setMode(item)}>{item === 'live' ? 'Live' : 'Simulation'}</button>)}</div>
}
