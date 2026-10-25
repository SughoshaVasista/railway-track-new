import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiErrorMessage, getDeviceSensors, getDevices } from '../services/api'
import { decide } from '../sim/decision'
import SeverityBadge from '../components/ui/SeverityBadge'

const scenarios = { clear_clear: { label: 'Clear / Clear', state: {} }, s3_on_A: { label: 'S3 on A', state: { track_A_defect: 'S3' } }, s2_on_A_B_occupied: { label: 'S2 on A + B occupied', state: { track_A_defect: 'S2', track_B_occupied: true } }, both_s3: { label: 'Both S3', state: { track_A_defect: 'S3', track_B_defect: 'S3' } }, too_close: { label: 'Too close', state: { distance_to_switch_A: 10 } } }
const requiredInputs = ['track_A_defect', 'track_B_defect', 'track_A_occupied', 'track_B_occupied', 'switch_A_available', 'switch_B_available', 'distance_to_switch_A', 'distance_to_switch_B']
const inputNames = Object.fromEntries(requiredInputs.map((key) => [key.toLowerCase(), key]))

function parseBoolean(value, key) {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number' && (value === 0 || value === 1)) return value === 1
  const text = String(value ?? '').trim().toLowerCase()
  const positive = key.endsWith('_occupied') ? ['occupied', 'yes', 'true', 'detected', '1'] : ['available', 'online', 'ok', 'yes', 'true', '1']
  const negative = key.endsWith('_occupied') ? ['clear', 'unoccupied', 'no', 'false', '0'] : ['unavailable', 'offline', 'fault', 'no', 'false', '0']
  if (positive.includes(text)) return true
  if (negative.includes(text)) return false
  return undefined
}

function parseInput(key, value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) value = value.value ?? value.severity ?? value.defect ?? value.state ?? value.occupied ?? value.available
  if (key.endsWith('_defect')) {
    const text = String(value ?? '').trim().toUpperCase()
    if (['S1', 'S2', 'S3'].includes(text)) return text
    if (['NONE', 'CLEAR', 'OK', 'NO DEFECT', 'NO_DEFECT'].includes(text)) return 'NONE'
    return undefined
  }
  if (key.endsWith('_occupied') || key.endsWith('_available')) return parseBoolean(value, key)
  if (key.startsWith('distance_to_switch')) {
    const number = Number(value)
    return Number.isFinite(number) && number >= 0 ? number : undefined
  }
  if (key === 'delay_score') {
    const number = Number(value)
    return Number.isFinite(number) ? Math.max(0, Math.min(1, number)) : undefined
  }
  return undefined
}

function decisionInput(readings) {
  const state = {}
  const timestamps = []
  const now = Date.now()
  for (const reading of readings) {
    const recorded = Date.parse(reading.timestamp || reading.updated_at || '')
    if (!Number.isFinite(recorded) || now - recorded > 90_000 || recorded > now + 60_000) continue
    if (['OFFLINE', 'ERROR', 'INVALID', 'STALE'].includes(String(reading.status || '').toUpperCase())) continue
    const name = String(reading.name || '').trim().toLowerCase()
    if (name === 'simulation_state' && reading.value && typeof reading.value === 'object' && !Array.isArray(reading.value)) {
      for (const [field, value] of Object.entries(reading.value)) {
        const key = inputNames[field.toLowerCase()]
        const parsed = key ? parseInput(key, value) : field.toLowerCase() === 'delay_score' ? parseInput('delay_score', value) : undefined
        if (parsed !== undefined) state[key || 'delay_score'] = parsed
      }
    } else {
      const key = inputNames[name] || (name === 'delay_score' ? name : null)
      const parsed = key ? parseInput(key, reading.value) : undefined
      if (parsed !== undefined) state[key] = parsed
    }
    timestamps.push(recorded)
  }
  const missing = requiredInputs.filter((key) => state[key] === undefined)
  if (state.delay_score === undefined) state.delay_score = 1
  return { state, missing, lastReadingAt: timestamps.length ? new Date(Math.max(...timestamps)).toISOString() : null }
}

export default function SimulationStandalone() {
  const [scenario, setScenario] = useState('clear_clear')
  const [mode, setMode] = useState('live')
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [position, setPosition] = useState(0)
  const [devices, setDevices] = useState([])
  const [deviceId, setDeviceId] = useState('')
  const [readings, setReadings] = useState([])
  const [sensorError, setSensorError] = useState('')
  const [deviceError, setDeviceError] = useState('')
  const selected = scenarios[scenario]
  const device = devices.find((item) => item.id === deviceId)
  const live = useMemo(() => decisionInput(readings), [readings])
  const decisionState = mode === 'scenario' ? { distance_to_switch: 80, delay_score: 1, ...selected.state } : live.state
  const readyForDecision = mode === 'scenario' || (!!deviceId && live.missing.length === 0)
  const decision = useMemo(() => readyForDecision ? decide(decisionState, { trainId: deviceId || 'demo-train', switchId: 'demo-switch', position }) : null, [readyForDecision, decisionState, deviceId, position])

  useEffect(() => {
    let active = true
    const loadDevices = async () => {
      try {
        const response = await getDevices()
        if (!active) return
        const items = Array.isArray(response?.items) ? response.items : []
        setDevices(items)
        setDeviceError('')
        setDeviceId((current) => items.some((item) => item.id === current) ? current : items.find((item) => item.status === 'ONLINE')?.id || items[0]?.id || '')
      } catch (error) {
        if (active) setDeviceError(apiErrorMessage(error, 'Could not load registered Raspberry Pi devices.'))
      }
    }
    loadDevices()
    const timer = window.setInterval(loadDevices, 10_000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  useEffect(() => {
    if (!deviceId) { setReadings([]); return undefined }
    let active = true
    const loadReadings = async () => {
      try {
        const response = await getDeviceSensors(deviceId)
        if (active) { setReadings(Array.isArray(response?.items) ? response.items : []); setSensorError('') }
      } catch (error) {
        if (active) { setReadings([]); setSensorError(apiErrorMessage(error, 'Could not read this device’s sensors.')) }
      }
    }
    loadReadings()
    const timer = window.setInterval(loadReadings, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [deviceId])

  useEffect(() => {
    if (!playing) return undefined
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const timer = window.setInterval(() => {
      setPosition((current) => {
        if (current >= 600) { setPlaying(false); return 0 }
        return Math.min(600, current + (reducedMotion ? 60 : speed * 6))
      })
    }, reducedMotion ? 500 : 100)
    return () => window.clearInterval(timer)
  }, [playing, speed])

  const step = () => setPosition((current) => current >= 600 ? 0 : Math.min(600, current + 60))
  const reset = () => { setPlaying(false); setPosition(0); setScenario('clear_clear') }
  const isLiveReady = mode === 'live' && decision !== null
  return <main className="simulator"><div className="simulation-warning">{mode === 'scenario' ? 'SIMULATION: SCENARIO DATA' : isLiveReady ? 'LIVE SENSOR INPUT · DECISION SUPPORT ONLY' : 'SIMULATION: WAITING FOR LIVE SENSOR DATA'}</div><header className="simulator-head"><div><p className="eyebrow">AMRIN decision support</p><h1>Track simulator</h1></div><Link to="/login">Back to dashboard</Link></header><div className="simulator-layout"><section className="schematic" aria-label="Track schematic"><svg viewBox="0 0 760 300" role="img"><text x="20" y="32">START</text><text x="660" y="32">END</text><text x="230" y="103">TRACK A</text><text x="230" y="215">TRACK B</text><path d="M70 90H690M70 200H690M300 90L430 200" /><circle cx="300" cy="90" r="5" /><circle cx="430" cy="200" r="5" /><rect x={70 + position} y="78" width="30" height="18" /></svg><div className="sim-controls"><button className="button-secondary" onClick={() => setPlaying(true)} disabled={playing}>Play</button><button className="button-secondary" onClick={() => setPlaying(false)} disabled={!playing}>Pause</button><button className="button-secondary" onClick={step}>Step</button><button className="button-secondary" onClick={reset}>Reset</button><span className="speed-label">Playback speed</span><div className="speed-control" role="group" aria-label="Playback speed">{[1, 2, 4].map((value) => <button key={value} type="button" className={speed === value ? 'selected' : ''} aria-pressed={speed === value} onClick={() => setSpeed(value)}>{value}×</button>)}</div><span className="sim-position">{position} m · {playing ? 'VISUAL PLAYBACK' : 'STOPPED'}</span></div><p className="sim-data-note">Train playback is visual only. Raspberry Pi readings drive the decision panel.</p></section><section className="sim-panel"><h2>Input source</h2><div className="sim-source-controls"><button type="button" className="button-secondary" aria-pressed={mode === 'live'} onClick={() => setMode('live')}>Raspberry Pi sensors</button><button type="button" className="button-secondary" aria-pressed={mode === 'scenario'} onClick={() => setMode('scenario')}>Scenarios</button></div>{mode === 'live' ? <><label className="sim-device-select">Registered device<select value={deviceId} onChange={(event) => setDeviceId(event.target.value)}><option value="">Select a device</option>{devices.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.id}</option>)}</select></label><p className="sim-device-status" role="status">{deviceError || sensorError || (device ? `${device.status} · ${live.lastReadingAt ? `latest input ${new Date(live.lastReadingAt).toLocaleTimeString()}` : 'waiting for sensor readings'}` : 'No registered device found. Register a Raspberry Pi and send telemetry to the backend.')}</p>{live.missing.length > 0 && <p className="sim-missing-data">Waiting for current inputs: {live.missing.join(', ')}</p>}</> : <div>{Object.entries(scenarios).map(([key, item]) => <label className="scenario-option" key={key}><input type="radio" checked={scenario === key} onChange={() => setScenario(key)} />{item.label}</label>)}</div>}<h2>Decision</h2>{decision ? <><dl className="detail-list"><dt>Action</dt><dd>{decision.action}</dd><dt>Target</dt><dd>{decision.target_track || 'NONE'}</dd><dt>Confidence</dt><dd className="mono">{decision.confidence}</dd><dt>Reason</dt><dd>{decision.reason}</dd></dl><div className="sim-rules">{decision.rules_checked.map((rule) => <p key={rule.rule}><span className={rule.passed ? 'pass' : 'fail'}>{rule.passed ? 'PASS' : 'FAIL'}</span>{rule.rule}</p>)}</div><div className="sim-scores"><div>Track A <strong>{decision.raw_scores.A ?? 'BLOCKED'}</strong></div><div>Track B <strong>{decision.raw_scores.B ?? 'BLOCKED'}</strong></div></div><SeverityBadge severity={decision.action === 'EMERGENCY_STOP' ? 'S3' : decision.action_level === 'WARNING' ? 'S2' : 'S1'} /></> : <p className="sim-missing-data" role="status">No decision is shown until all required live inputs are fresh. This avoids treating missing sensor data as a safe condition.</p>}</section></div></main>
}
