import React from 'react'
import Lamp from './Lamp'

export default function AlertRow({ alert, onClick }) {
  return <article className={`alert-row ${onClick ? 'interactive' : ''}`} onClick={onClick} onKeyDown={(event) => event.key === 'Enter' && onClick?.()} tabIndex={onClick ? 0 : undefined}><div><Lamp severity={String(alert.severity || 'offline').toLowerCase()} /><code>{alert.id || 'NO DATA'}</code></div><b>{alert.defect || alert.type || 'NO DATA'}</b><small className="data-line">{alert.track || 'NO DATA'} · {alert.chainage || 'NO DATA'} · {alert.confidence ?? 'NO DATA'}%</small><label>{alert.status || 'NO DATA'}</label></article>
}
