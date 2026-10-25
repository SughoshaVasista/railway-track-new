import React, { useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import Header from '../components/Header'
import Panel from '../components/Panel'
import Lamp from '../components/Lamp'
import AlertRow from '../components/AlertRow'
import MapView from '../components/MapView'
import StatusStrip from '../components/StatusStrip'
import EventLog from '../components/EventLog'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { useAlerts, useDashboardSummary, useSwitchStatus } from '../hooks/useData'

export default function Dashboard() {
  const [tab, setTab] = useState('map')
  const summary = useDashboardSummary(); const alertsState = useAlerts(); const switchState = useSwitchStatus()
  const metrics = summary.data || {}; const alerts = Array.isArray(alertsState.data) ? alertsState.data : []
  const tabs = [['map', 'Map'], ['alerts', 'Alerts'], ['kpis', 'KPIs'], ['switching', 'Switching']]
  const kpis = [['Active', metrics.active_alerts, 'critical'], ['S3', metrics.s3_alerts, 'critical'], ['S2', metrics.s2_alerts, 'warning'], ['S1', metrics.s1_alerts, 'minor'], ['Pending Repairs', metrics.pending_tasks, 'warning']]
  return <><Header title="Command Center" text="Live railway condition and maintenance overview." /><StatusStrip summaryState={summary} alertsState={alertsState} /><div className="banner"><ShieldCheck size={19} />Simulation and decision-support mode. This is not live railway signalling control.</div><div className="dashboard-tabs">{tabs.map(([key, label]) => <button key={key} className={tab === key ? 'selected' : ''} onClick={() => setTab(key)}>{label}</button>)}</div><div className="command-grid"><Panel title="Live track overview" status="Live view" className={`command-map dashboard-tab-panel ${tab === 'map' ? 'is-active' : ''}`}><MapView /></Panel><Panel title="Alert feed" status={alertsState.loading ? 'Loading' : `${alerts.length} received`} className={`command-alerts dashboard-tab-panel ${tab === 'alerts' ? 'is-active' : ''}`}>{alertsState.loading ? <LoadingState>Loading alerts...</LoadingState> : alertsState.error ? <ErrorState /> : alerts.length ? alerts.map((alert) => <AlertRow key={alert.id} alert={alert} />) : <EmptyState>No alerts</EmptyState>}</Panel><section className={`command-kpis dashboard-tab-panel ${tab === 'kpis' ? 'is-active' : ''}`}><div className="kpis">{kpis.map(([label, data, tone]) => <article className={`kpi ${tone}`} key={label}><span>{label}</span><strong>{data ?? 'NO DATA'}</strong></article>)}</div></section><Panel title="Track switching" status={switchState.loading ? 'Loading' : 'Live data'} className={`command-switching dashboard-tab-panel ${tab === 'switching' ? 'is-active' : ''}`}>{switchState.loading ? <LoadingState>Loading switch status...</LoadingState> : switchState.error ? <ErrorState /> : switchState.data ? <div className="decision"><div><h3>Safety rules</h3>{(switchState.data.rules_checked || []).map((rule) => <p className="rule" key={rule.rule}><Lamp severity={rule.passed ? 'clear' : 'critical'} />{rule.rule}</p>)}</div><div className="recommend"><p className="eyebrow">Recommended route</p><h2>{switchState.data.target_track || 'NO DATA'}</h2><b className="confidence">{switchState.data.confidence ?? 'NO DATA'} confidence</b><p className="muted">{switchState.data.reason || 'NO DATA'}</p></div></div> : <EmptyState>Switch decision unavailable</EmptyState>}</Panel></div><div className={`event-log-mobile-panel dashboard-tab-panel ${tab === 'switching' ? 'is-active' : ''}`}><EventLog /></div></>
}
