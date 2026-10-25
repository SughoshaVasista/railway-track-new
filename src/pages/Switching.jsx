import React, { useState } from 'react'
import Header from '../components/Header'
import Panel from '../components/Panel'
import Lamp from '../components/Lamp'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { useAuth } from '../context/AuthContext'
import { postSwitchDecision } from '../services/api'
import { useSwitchStatus } from '../hooks/useData'

export default function Switching() {
  const state = useSwitchStatus(); const { user } = useAuth(); const [message, setMessage] = useState('')
  const decision = state.data || {}; const emergency = decision.action === 'EMERGENCY_STOP'; const rules = Array.isArray(decision.rules_checked) ? decision.rules_checked : []
  const override = async () => { setMessage(''); try { await postSwitchDecision({ override: true, train_id: decision.train_id, switch_id: decision.switch_id, target_track: decision.target_track }); setMessage('Override submitted to server.') } catch { setMessage('Override rejected or unavailable.') } }
  return <><Header title="Track Switching" text="Decision support for controlled route selection." /><div className="banner"><strong>SIMULATION / DECISION-SUPPORT MODE, not live railway control.</strong></div>{state.loading ? <LoadingState>Loading switch status...</LoadingState> : state.error ? <ErrorState /> : !state.data ? <EmptyState>Switch decision unavailable</EmptyState> : <div className="switching-grid"><Panel title="Hard safety rules" status={`${rules.length} rules`}><div className="checks">{rules.map((rule, index) => <p key={`${rule.rule}-${index}`}><Lamp severity={rule.passed ? 'clear' : 'critical'} label={rule.passed ? 'PASS' : 'FAIL'} /><span>{rule.rule || 'NO DATA'}</span></p>)}</div></Panel><Panel title="Decision" status={decision.action_level || 'NO DATA'}><div className={`switch-decision ${emergency ? 'emergency-stop' : ''}`}><p className="eyebrow">Action</p><h2>{decision.action || 'NO DATA'}</h2>{emergency ? <><Lamp severity="critical" label="EMERGENCY STOP" /><p className="muted">No recommended track.</p></> : <><p className="eyebrow">Selected track</p><h2>{decision.target_track || 'NO DATA'}</h2><strong className="confidence">{decision.confidence ?? 'NO DATA'}%</strong></>}<p className="muted">{decision.reason || 'NO DATA'}</p></div></Panel><Panel title="Track scores" status="Higher is better"><div className="track-scores">{Object.entries(decision.raw_scores || {}).map(([track, score]) => <div className="track-score" key={track}><span>Track {track}</span><strong>{score ?? 'BLOCKED'}</strong></div>)}</div></Panel></div>}{user.role === 'admin' && state.data && !emergency && <div className="override-row"><button className="primary" onClick={override}>Override decision</button>{message && <span className="muted">{message}</span>}</div>}</>
}
