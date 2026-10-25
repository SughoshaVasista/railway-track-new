import React from 'react'
import Header from '../components/Header'
import Panel from '../components/Panel'
import Lamp from '../components/Lamp'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { useAIDetection } from '../hooks/useData'

const display = (value) => value === undefined || value === null || value === '' ? 'NO DATA' : value

function Fusion({ value }) {
  const items = Array.isArray(value) ? value : value && typeof value === 'object' ? Object.entries(value).map(([name, result]) => ({ name, ...(typeof result === 'object' ? result : { passed: result }) })) : []
  return items.length ? <div className="fusion-list">{items.map((item, index) => <div key={item.name || index}><Lamp severity={item.passed ? 'clear' : 'critical'} label={item.passed ? 'PASS' : 'FAIL'} /><span>{item.name || 'NO DATA'}</span></div>)}</div> : <EmptyState>No sensor-fusion data</EmptyState>
}

function LiveFrame({ detection }) {
  const image = detection.frame_url || detection.image_url || detection.frame || detection.image; const boxes = detection.boxes || detection.bounding_boxes || []; const width = Number(detection.image_width || detection.width); const height = Number(detection.image_height || detection.height)
  if (!image) return <div className="ai-frame"><EmptyState>Image unavailable</EmptyState></div>
  return <div className="ai-frame" style={width && height ? { aspectRatio: `${width} / ${height}` } : undefined}><img src={image} alt="Live detection frame" />{boxes.map((box, index) => { const x = Number(box.x ?? box.left); const y = Number(box.y ?? box.top); const w = Number(box.width ?? box.w); const h = Number(box.height ?? box.h); if (![x, y, w, h].every(Number.isFinite) || !width || !height) return null; return <div className="ai-box" key={box.id || index} style={{ left: `${x / width * 100}%`, top: `${y / height * 100}%`, width: `${w / width * 100}%`, height: `${h / height * 100}%` }}><span>{display(box.class || box.label)} · {display(box.confidence)} · {display(box.severity)}</span></div> })}</div>
}

export default function AI() {
  const state = useAIDetection(); const detection = state.data || {}
  return <><Header title="AI Detection" text="Live camera frame and sensor-fusion classification." />{state.loading ? <LoadingState>Loading detection frame...</LoadingState> : state.error ? <ErrorState /> : <div className="ai-detection-grid"><Panel title="Live frame" status={detection.updated_at || 'Live data'}><LiveFrame detection={detection} /></Panel><Panel title="Detection" status={detection.status || 'NO DATA'}><div className="ai-details"><dl className="detail-list"><dt>Class</dt><dd>{display(detection.class || detection.label || detection.defect)}</dd><dt>Confidence</dt><dd className="mono">{display(detection.confidence)}</dd><dt>Severity</dt><dd>{display(detection.severity)}</dd><dt>Final confidence</dt><dd className="mono">{display(detection.final_confidence ?? detection.finalConfidence)}</dd></dl><h3>Sensor fusion</h3><Fusion value={detection.sensor_fusion || detection.fusion} /></div></Panel></div>}</>
}
