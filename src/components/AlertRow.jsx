import React from 'react'
import Lamp from './Lamp'
import SeverityBadge from './ui/SeverityBadge'
import ConfidenceChip from './ui/ConfidenceChip'

export default function AlertRow({ alert, onClick }) {
  return <article className={`alert-row ${onClick ? 'interactive' : ''}`} onClick={onClick} onKeyDown={(event) => event.key === 'Enter' && onClick?.()} tabIndex={onClick ? 0 : undefined}><div><SeverityBadge severity={alert.severity} /><code>{alert.id || 'NO DATA'}</code></div><b>{alert.defect || alert.type || 'NO DATA'}</b><small className="data-line">{alert.track || 'NO DATA'} · {alert.chainage || 'NO DATA'}</small><ConfidenceChip value={alert.confidence} /><label>{alert.status || 'NO DATA'}</label></article>
}
