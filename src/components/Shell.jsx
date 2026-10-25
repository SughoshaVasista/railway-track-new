import React from 'react'
import { LogOut, TrainFront, UserRound } from 'lucide-react'
import { Outlet } from 'react-router-dom'
import Nav from './Nav'
import AppModeToggle from './AppModeToggle'
import { useAuth } from '../context/AuthContext'

export default function Shell() {
  const { user, logout } = useAuth()
  return <div className="shell"><Nav /><main className="content"><header className="topbar"><div className="topbar-brand"><TrainFront size={22} /><b>RailSafe</b></div><AppModeToggle /><div className="topbar-user"><UserRound size={16} /><span>{user?.name || 'RailSafe user'}</span><button className="icon" onClick={logout} aria-label="Log out"><LogOut size={17} /></button></div></header><div className="page"><Outlet /></div></main></div>
}
