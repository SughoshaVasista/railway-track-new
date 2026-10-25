import React, { useEffect, useMemo, useState } from 'react'
import { Cpu } from 'lucide-react'
import { Line, LineChart, ResponsiveContainer } from 'recharts'
import Header from '../components/Header'
import Lamp from '../components/Lamp'
import Panel from '../components/Panel'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { useDeviceDiagnostics, useDevices, useModelStatus, useSensorsLatest } from '../hooks/useData'
import { TEMPERATURE_FLAG_C } from '../config/thresholds'

const sensorTypes = [['Camera', '30 FPS'], ['Ultrasonic', '20 Hz'], ['Accelerometer', '100 Hz'], ['Temperature', '1 Hz'], ['GPS', '1 Hz']]
const explanations = { ONLINE: 'Sensor is reporting within its expected interval.', DEGRADED: 'Sensor is reporting, but quality is reduced.', ERROR: 'Sensor reported an error.', TIMEOUT: 'No response arrived before the timeout.', INVALID_READING: 'The latest value failed validation.', MISSING_DATA: 'No reading has arrived.' }
const noData = (value) => value === undefined || value === null || value === '' ? 'NO DATA' : value
const values = (sensor) => Array.isArray(sensor) ? sensor : sensor && typeof sensor === 'object' ? Object.entries(sensor).map(([name, value]) => ({ name, ...(typeof value === 'object' ? value : { value }) })) : []
const number = (value) => typeof value === 'number' && Number.isFinite(value) ? value : null
const packetTime = (item) => item?.updated_at || item?.last_received_at || item?.timestamp

function Freshness({ updatedAt }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer) }, [])
  const seconds = updatedAt ? Math.max(0, Math.floor((now - new Date(updatedAt).getTime()) / 1000)) : null
  const state = seconds === null ? 'OFFLINE' : seconds < 5 ? 'LIVE' : seconds < 30 ? 'DELAYED' : 'OFFLINE'
  return <span className={`freshness-chip freshness-${state.toLowerCase()}`}><i />{state}{seconds === null ? '' : ` · ${seconds}s ago`}</span>
}

function Sparkline({ points }) {
  if (!points.length) return <span className="sparkline-empty">NO DATA</span>
  return <div className="sparkline"><ResponsiveContainer width="100%" height={46}><LineChart data={points}><Line type="monotone" dataKey="value" stroke="var(--catenary-blue)" strokeWidth={2} dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div>
}

function health(sensor) {
  const raw = String(sensor?.status || '').toUpperCase()
  if (raw) return raw
  return sensor && Object.keys(sensor).some((key) => ['value', 'raw', 'reading', 'x', 'latitude', 'lat'].includes(key)) ? 'ONLINE' : 'MISSING_DATA'
}

function SensorCard({ title, rate, sensor, points }) {
  const status = health(sensor); const raw = sensor || {}; const interpreted = raw.interpreted_value ?? raw.interpreted ?? raw.classification; const temperatureFlag = title === 'Temperature' && typeof raw.value === 'number' && raw.value > TEMPERATURE_FLAG_C
  const latest = packetTime(raw); const age = latest ? Math.max(0, Math.floor((Date.now() - new Date(latest).getTime()) / 1000)) : null
  const rows = title === 'Accelerometer' ? [['X', noData(raw.x)], ['Y', noData(raw.y)], ['Z', noData(raw.z)], ['Vibration', noData(raw.vibration || raw.vibration_state)], ['Anomaly score', noData(raw.anomaly_score)]] : title === 'GPS' ? [['Latitude', noData(raw.lat ?? raw.latitude)], ['Longitude', noData(raw.lng ?? raw.longitude)], ['Accuracy', raw.accuracy === undefined ? 'NO DATA' : `${raw.accuracy} m`], ['Satellites', noData(raw.satellites)], ['Fix type', noData(raw.fix_type ?? raw.fixType)]] : [['Raw value', noData(raw.raw ?? raw.value ?? raw.reading)], ['Interpreted', noData(interpreted)]]
  return <article className="hardware-sensor-card"><div className="hardware-card-head"><div><p className="eyebrow">{rate}</p><h2>{title}</h2></div><Lamp severity={temperatureFlag ? 'warning' : status.toLowerCase()} label={temperatureFlag ? 'DEGRADED' : status} /></div><p className="sensor-explanation">{temperatureFlag ? `Temperature above ${TEMPERATURE_FLAG_C} C.` : explanations[status] || 'Sensor status is not available.'}</p><strong className="hardware-value">{title === 'Accelerometer' ? noData(raw.value) : title === 'GPS' ? `${noData(raw.lat ?? raw.latitude)}, ${noData(raw.lng ?? raw.longitude)}` : noData(raw.value ?? raw.reading ?? raw.raw)}</strong><div className="hardware-age">last received {age === null ? 'NO DATA' : `${age}s ago`}</div><div className="hardware-details">{rows.map(([label, value]) => <div key={label}><span>{label}</span><code>{value}</code></div>)}</div><Sparkline points={points} /></article>
}

function ModelStatus() {
  const state = useModelStatus(); const model = state.data || {}; const lamp = (value, label) => <Lamp severity={value === true || value === 'LOADED' || value === 'ACTIVE' ? 'clear' : 'offline'} label={label || (value === undefined ? 'MISSING_DATA' : value ? 'ONLINE' : 'OFFLINE')} />
  return <Panel title="Model status" status={state.loading ? 'Loading' : state.error ? 'Unavailable' : 'Measured data'}>{state.loading ? <LoadingState>Loading model status...</LoadingState> : state.error ? <ErrorState /> : <div className="model-status"><div>{lamp(model.loaded, 'Loaded')}{lamp(model.inference_active ?? model.inferenceActive, 'Inference active')}</div><dl className="detail-list"><dt>Name / version</dt><dd>{noData(model.name)} / {noData(model.version)}</dd><dt>Class count</dt><dd className="mono">{noData(model.class_count ?? model.classCount)}</dd><dt>Input size</dt><dd className="mono">{noData(model.input_size ?? model.inputSize)}</dd><dt>Inference</dt><dd className="mono">{model.inference_ms === undefined ? 'NO DATA' : `${model.inference_ms} ms`}</dd><dt>Device</dt><dd>{noData(model.device)}</dd></dl></div>}</Panel>
}

export default function Hardware() {
  const devicesState = useDevices(); const device = (Array.isArray(devicesState.data) ? devicesState.data : [])[0]; const sensorsState = useSensorsLatest(device?.id); const diagnosticsState = useDeviceDiagnostics(device?.id); const list = values(sensorsState.data); const byName = useMemo(() => Object.fromEntries(list.map((sensor) => [String(sensor.name || sensor.type || '').toLowerCase(), sensor])), [sensorsState.data])
  const [history, setHistory] = useState({})
  useEffect(() => { if (!list.length) return; setHistory((old) => { const next = { ...old }; list.forEach((sensor) => { const name = String(sensor.name || sensor.type || '').toLowerCase(); const measured = number(sensor.value ?? sensor.reading ?? sensor.raw); if (measured !== null) next[name] = [...(next[name] || []), { value: measured }].slice(-32) }); return next }) }, [sensorsState.data])
  const diagnostics = diagnosticsState.data || {}; const updatedAt = diagnostics.updated_at || list.map(packetTime).find(Boolean); const piStatus = diagnostics.pi_status ?? diagnostics.pi?.status; const networkStatus = diagnostics.network_status ?? diagnostics.network?.status; const uptime = diagnostics.uptime ?? diagnostics.pi?.uptime
  if (devicesState.loading) return <><Header title="Hardware Monitor" text="Measured device and sensor health." /><LoadingState>Loading devices...</LoadingState></>
  if (devicesState.error) return <><Header title="Hardware Monitor" text="Measured device and sensor health." /><ErrorState /></>
  return <><Header title="Hardware Monitor" text="Measured device and sensor health." /><div className="hardware-banner"><div><span>Pi status</span><Lamp severity={String(piStatus || 'missing_data').toLowerCase()} label={piStatus || 'MISSING_DATA'} /></div><div><span>Network</span><Lamp severity={String(networkStatus || 'missing_data').toLowerCase()} label={networkStatus || 'MISSING_DATA'} /></div><div><span>Uptime</span><b className="mono">{noData(uptime)}</b></div><Freshness updatedAt={updatedAt} /></div>{!device ? <EmptyState>Device offline</EmptyState> : <><div className="device"><Cpu size={25} /><b>{noData(device.name || device.id)} <small>{noData(device.platform)}</small></b><Lamp severity={String(device.status || 'missing_data').toLowerCase()} label={device.status || 'MISSING_DATA'} /></div><div className="hardware-grid">{sensorTypes.map(([title, rate]) => <SensorCard title={title} rate={rate} sensor={byName[title.toLowerCase()]} points={history[title.toLowerCase()] || []} key={title} />)}</div><ModelStatus /></>}</>
}
