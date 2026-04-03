/**
 * Dashboard Component
 */

import { useEffect } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useHAStore } from '@/store/ha'
import haClient from '@/api/client'
import './Dashboard.css'

export function Dashboard() {
  const { sendMessage } = useWebSocket()
  const connected = useHAStore((state) => state.connected)
  const status = useHAStore((state) => state.status)
  const entities = useHAStore((state) => state.entities)
  const error = useHAStore((state) => state.error)
  const setStatus = useHAStore((state) => state.setStatus)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const data = await haClient.getStatus()
        setStatus(data.status)
      } catch (err) {
        setStatus('error')
      }
    }

    fetchStatus()
  }, [setStatus])

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>🏠 Home Assistant</h1>
        <div className="status-indicator">
          <span className={`status ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '● Connected' : '○ Disconnected'}
          </span>
        </div>
      </header>

      <main className="dashboard-main">
        {error && (
          <div className="error-banner">
            <p>⚠️ {error}</p>
          </div>
        )}

        <section className="status-section">
          <h2>Status: {status}</h2>
        </section>

        <section className="entities-section">
          <h2>Entities ({entities.length})</h2>
          {entities.length === 0 ? (
            <p className="empty-state">No entities available</p>
          ) : (
            <div className="entities-grid">
              {entities.map((entity) => (
                <div key={entity.entity_id} className="entity-card">
                  <div className="entity-id">{entity.entity_id}</div>
                  <div className="entity-state">{entity.state}</div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="actions-section">
          <button
            onClick={() => sendMessage({ action: 'get_entities' })}
            className="btn btn-primary"
          >
            Refresh Entities
          </button>
        </section>
      </main>
    </div>
  )
}
