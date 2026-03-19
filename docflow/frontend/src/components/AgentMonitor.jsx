import React, { useState, useEffect, useCallback } from 'react'
import useWebSocket from '../hooks/useWebSocket'
import './AgentMonitor.css'

export const AgentMonitor = ({ resultId }) => {
  const [events, setEvents] = useState([])
  const [isExpanded, setIsExpanded] = useState(true)

  const handleMessage = useCallback((message) => {
    if (message.event) {
      setEvents(prev => [...prev, { ...message, timestamp: new Date().toLocaleTimeString() }])
    }
  }, [])

  const { isConnected } = useWebSocket(handleMessage)

  const getEventIcon = (event) => {
    const icons = {
      'fingerprint_assigned': '🔍',
      'script_found': '📦',
      'script_written': '✍️',
      'script_executed': '▶️',
      'dllm_check_complete': '✅',
      'retry': '🔄',
      'escalated_to_human': '⚠️',
      'complete': '🎉'
    }
    return icons[event] || '📝'
  }

  const getEventColor = (event) => {
    const colors = {
      'fingerprint_assigned': '#2196F3',
      'script_found': '#4CAF50',
      'script_written': '#FF9800',
      'script_executed': '#9C27B0',
      'dllm_check_complete': '#00BCD4',
      'retry': '#FF9800',
      'escalated_to_human': '#f44336',
      'complete': '#4CAF50'
    }
    return colors[event] || '#666'
  }

  return (
    <div className={`agent-monitor ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <div className="monitor-header" onClick={() => setIsExpanded(!isExpanded)}>
        <h3>
          🤖 Agent Monitor
          <span className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '●' : '○'}
          </span>
        </h3>
        <button className="toggle-btn">{isExpanded ? '▼' : '▶'}</button>
      </div>

      {isExpanded && (
        <div className="monitor-content">
          {events.length === 0 ? (
            <p className="no-events">Waiting for extraction events...</p>
          ) : (
            <div className="events-list">
              {events.map((event, index) => (
                <div key={index} className="event-item">
                  <span className="event-icon">{getEventIcon(event.event)}</span>
                  <div className="event-details">
                    <p className="event-name" style={{ color: getEventColor(event.event) }}>
                      {event.event.replace(/_/g, ' ').toUpperCase()}
                    </p>
                    <p className="event-time">{event.timestamp}</p>
                    {event.data && Object.keys(event.data).length > 0 && (
                      <p className="event-data">{JSON.stringify(event.data, null, 2).substring(0, 200)}...</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AgentMonitor
