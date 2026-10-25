import React from 'react'

export default function StatusPill({ children, tone = 'neutral' }) {
  return <span className={`status-pill status-${tone}`}>{children}</span>
}
