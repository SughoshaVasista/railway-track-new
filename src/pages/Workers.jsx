import React from 'react'
import Header from '../components/Header'
import Lamp from '../components/Lamp'
import { EmptyState, ErrorState, LoadingState } from '../components/StateMessage'
import { useTasks, useWorkers } from '../hooks/useData'

export default function Workers() { const workersState = useWorkers(); const tasksState = useTasks(); const workers = Array.isArray(workersState.data) ? workersState.data : []; const tasks = Array.isArray(tasksState.data) ? tasksState.data : []; return <><Header title="Workers" text="Field workforce and active assignments." />{workersState.loading ? <LoadingState>Loading workers...</LoadingState> : workersState.error ? <ErrorState /> : workers.length ? <div className="admin-list">{workers.map((worker) => { const id = worker.id || worker.worker_id; const count = tasks.filter((task) => task.worker_id === id && task.status !== 'COMPLETED').length; return <article className="admin-row" key={id}><Lamp severity={String(worker.status || 'missing_data').toLowerCase()} label={worker.status || 'NO DATA'} /><div><b>{worker.name || id || 'NO DATA'}</b><small>{worker.role || 'NO DATA'}</small></div><strong className="mono">{count}</strong><span>active tasks</span></article> })}</div> : <EmptyState>No workers</EmptyState>}</> }
