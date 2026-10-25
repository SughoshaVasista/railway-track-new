import React, { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Header from '../components/Header'
import AlertRow from '../components/AlertRow'
import AlertDrawer from '../components/AlertDrawer'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { useAlerts } from '../hooks/useData'

export default function Alerts() {
  const [params, setParams] = useSearchParams(); const [selected, setSelected] = useState(null)
  const filters = useMemo(() => Object.fromEntries(['severity', 'type', 'status', 'track', 'time'].map((key) => [key, params.get(key) || ''])), [params])
  const state = useAlerts(filters); const shown = Array.isArray(state.data) ? state.data : []
  const setFilter = (key, value) => { const next = new URLSearchParams(params); value ? next.set(key, value) : next.delete(key); setParams(next) }
  const options = (key, fallback) => { const values = [...new Set(shown.map((item) => key === 'type' ? (item.type || item.defect || item.class) : item[key]).filter(Boolean))].sort(); return values.length ? values : fallback }
  return <><Header title="Alerts" text="Review, acknowledge and assign detected defects." /><div className="alert-filters">{[['severity', ['S3', 'S2', 'S1']], ['type', options('type', ['NO DATA'])], ['status', options('status', ['ACTIVE', 'ACKNOWLEDGED', 'RESOLVED'])], ['track', options('track', ['A', 'B'])], ['time', ['1h', '24h', '7d']]].map(([key, values]) => <label key={key}>{key}<select value={filters[key]} onChange={(event) => setFilter(key, event.target.value)}><option value="">ALL</option>{values.map((value) => <option value={value} key={value}>{value}</option>)}</select></label>)}</div><div className="cards">{state.loading ? <LoadingState>Loading alerts...</LoadingState> : state.error ? <ErrorState /> : shown.length ? shown.map((alert) => <AlertRow key={alert.id} alert={alert} onClick={() => setSelected(alert)} />) : <EmptyState>No alerts</EmptyState>}</div><AlertDrawer alert={selected} onClose={() => setSelected(null)} onChanged={state.refresh} /></>
}
