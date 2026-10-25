import React, { useState } from 'react'
import Header from '../components/Header'
import Panel from '../components/Panel'
import AlertRow from '../components/AlertRow'
import MapView from '../components/MapView'
import StatusStrip from '../components/StatusStrip'
import EventLog from '../components/EventLog'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { useAlerts, useDashboardSummary } from '../hooks/useData'
import { useCity } from '../context/CityContext'
import { cities } from '../config/cities'

export default function Dashboard() {
  const [tab, setTab] = useState('map')
  const summary = useDashboardSummary(); const alertsState = useAlerts()
  const metrics = summary.data || {}; const alerts = Array.isArray(alertsState.data) ? alertsState.data : []
  const { city } = useCity(); const cityName = cities.find((item) => item.id === city)?.name || 'all cities'; const s3Count = Number(metrics.s3_alerts || 0)
  const tabs = [['map', 'Map'], ['alerts', 'Alerts'], ['kpis', 'KPIs']]
  const kpis = [['Active', metrics.active_alerts, 'critical'], ['S3', metrics.s3_alerts, 'critical'], ['S2', metrics.s2_alerts, 'warning'], ['S1', metrics.s1_alerts, 'minor'], ['Pending Repairs', metrics.pending_tasks, 'warning']]
  return <><Header title="Command Center" text="Live railway condition and maintenance overview." /><StatusStrip summaryState={summary} alertsState={alertsState} />{s3Count > 0 && <div className="s3-banner">△ {s3Count} active S3 defects in {cityName}. <a href="/alerts?severity=S3">Acknowledge</a> <a href="/tasks">Assign worker</a></div>}<div className="dashboard-tabs">{tabs.map(([key, label]) => <button key={key} className={tab === key ? 'selected' : ''} onClick={() => setTab(key)}>{label}</button>)}</div><div className="command-grid"><Panel title="Live track overview" status="Live view" className={`command-map dashboard-tab-panel ${tab === 'map' ? 'is-active' : ''}`}><MapView /></Panel><Panel title="Alert feed" status={alertsState.loading ? 'Loading' : `${alerts.length} received`} className={`command-alerts dashboard-tab-panel ${tab === 'alerts' ? 'is-active' : ''}`}>{alertsState.loading ? <LoadingState>Loading alerts...</LoadingState> : alertsState.error ? <ErrorState /> : alerts.length ? alerts.map((alert) => <AlertRow key={alert.id} alert={alert} />) : <EmptyState>No alerts</EmptyState>}</Panel><section className={`command-kpis dashboard-tab-panel ${tab === 'kpis' ? 'is-active' : ''}`}><div className="readout-strip">{kpis.map(([label, data]) => <div className="readout" key={label}><span>{label}</span><strong>{data ?? 'NO DATA'}</strong></div>)}</div></section></div><div className="event-log-mobile-panel"><EventLog /></div><footer className="dashboard-status">{metrics.online_devices ?? 'NO DATA'} devices online · {summary.error || alertsState.error ? 'OFFLINE' : 'LIVE'} · <time>{summary.updatedAt ? new Date(summary.updatedAt).toISOString() : 'NO DATA'}</time></footer></>
}
