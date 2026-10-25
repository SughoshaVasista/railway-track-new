import React, { useState } from 'react'
import { AlertTriangle, BarChart3, Bot, ClipboardList, Cpu, Gauge, LayoutDashboard, ListTodo, Map, Settings, Shield, Users, Wrench, X } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const groups = [
  { title: 'Operations', items: [['/admin', 'Command Center', LayoutDashboard], ['/map', 'Live Map', Map], ['/alerts', 'Alerts', AlertTriangle], ['/tasks', 'Tasks', ListTodo]] },
  { title: 'Inspection', items: [['/ai-detection', 'AI Detection', Bot], ['/sensor-history', 'Sensor History', BarChart3]] },
  { title: 'Maintenance', items: [['/hardware', 'Hardware', Cpu], ['/workers', 'Workers', Users], ['/repair-history', 'Repair History', ClipboardList]] },
  { title: 'System', items: [['/switching', 'Track Switching', Gauge], ['/simulation', 'Simulation', Wrench], ['/model', 'Model', Shield], ['/settings', 'Settings', Settings]] },
]

const mobileItems = [['/admin', 'Command Center', LayoutDashboard], ['/map', 'Map', Map], ['/alerts', 'Alerts', AlertTriangle], ['/tasks', 'Tasks', ListTodo]]
const moreItems = groups.flatMap((group) => group.items).filter(([to]) => !mobileItems.some(([mobileTo]) => mobileTo === to))

function LinkItem({ to, label, Icon, onClick }) {
  return <NavLink to={to} onClick={onClick} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}><Icon size={18} /><span>{label}</span></NavLink>
}

export default function Nav() {
  const { user } = useAuth()
  const [moreOpen, setMoreOpen] = useState(false)
  const visibleGroups = user.role === 'admin' ? groups : [{ title: 'Operations', items: [['/worker', 'Tasks', ListTodo], ['/map', 'Map', Map]] }]
  const visibleMobileItems = user.role === 'admin' ? mobileItems : [['/worker', 'Tasks', ListTodo], ['/map', 'Map', Map]]
  const visibleMoreItems = user.role === 'admin' ? moreItems : []
  return <>
    <aside className="sidebar" aria-label="Primary navigation">{visibleGroups.map((group) => <section className="nav-group" key={group.title}><h2>{group.title}</h2>{group.items.map(([to, label, Icon]) => <LinkItem key={to} to={to} label={label} Icon={Icon} />)}</section>)}</aside>
    <nav className="mobile-nav" aria-label="Mobile navigation">{visibleMobileItems.map(([to, label, Icon]) => <LinkItem key={to} to={to} label={label} Icon={Icon} />)}{visibleMoreItems.length > 0 && <button className="nav-link more-button" onClick={() => setMoreOpen(true)} aria-label="Open more navigation"><Settings size={18} /><span>More</span></button>}</nav>
    {moreOpen && visibleMoreItems.length > 0 && <div className="sheet-backdrop" role="presentation" onClick={() => setMoreOpen(false)}><section className="more-sheet" role="dialog" aria-modal="true" aria-label="More navigation" onClick={(event) => event.stopPropagation()}><div className="sheet-head"><h2>More</h2><button className="icon" onClick={() => setMoreOpen(false)} aria-label="Close more navigation"><X size={19} /></button></div>{visibleMoreItems.map(([to, label, Icon]) => <LinkItem key={to} to={to} label={label} Icon={Icon} onClick={() => setMoreOpen(false)} />)}</section></div>}
  </>
}
