import React, { useState, useCallback, useEffect } from 'react'
import useWebSocket from '../hooks/useWebSocket'
import { getValidationLog } from '../api'
import './AgentMonitor.css'

export const AgentMonitor = ({ resultId }) => {
  const [events, setEvents] = useState([])
  const [isExpanded, setIsExpanded] = useState(true)
  const [activeTab, setActiveTab] = useState('events')
  const [validationLog, setValidationLog] = useState(null)
  const [loadingLog, setLoadingLog] = useState(false)

  const handleMessage = useCallback((message) => {
    if (message.event) {
      setEvents(prev => [...prev, { ...message, timestamp: new Date().toLocaleTimeString() }])
    }
  }, [])

  const { isConnected } = useWebSocket(handleMessage)

  useEffect(() => {
    if (resultId && activeTab === 'validation') {
      setLoadingLog(true)
      getValidationLog(resultId)
        .then(res => setValidationLog(res.data))
        .catch(err => console.error('Failed to load validation log:', err))
        .finally(() => setLoadingLog(false))
    }
  }, [resultId, activeTab])

  const getEventIcon = (event) => {
    const icons = {
      'fingerprint_assigned': '\uD83D\uDD0D',
      'script_found': '\uD83D\uDCE6',
      'script_written': '\u270F\uFE0F',
      'script_executed': '\u25B6\uFE0F',
      'dllm_check_complete': '\u2705',
      'retry': '\uD83D\uDD04',
      'escalated_to_human': '\u26A0\uFE0F',
      'complete': '\uD83C\uDF89',
      'processing': '\u23F3'
    }
    return icons[event] || '\uD83D\uDCDD'
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
      'complete': '#4CAF50',
      'processing': '#9C27B0'
    }
    return colors[event] || '#666'
  }

  const getStatusColor = (status) => {
    const colors = {
      'filled': '#4CAF50',
      'missing': '#f44336',
      'uncertain': '#FF9800'
    }
    return colors[status] || '#666'
  }

  const getConfidenceBar = (confidence) => {
    const percentage = Math.round(confidence * 100)
    const color = confidence > 0.75 ? '#4CAF50' : confidence > 0.5 ? '#FF9800' : '#f44336'
    return (
      <div className="confidence-bar-container">
        <div className="confidence-bar" style={{ width: `${percentage}%`, backgroundColor: color }} />
        <span className="confidence-text">{percentage}%</span>
      </div>
    )
  }

  return (
    <div className={`agent-monitor ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <div className="monitor-header" onClick={() => setIsExpanded(!isExpanded)}>
        <h3>
          Agent Monitor
          <span className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '\u25CF' : '\u25CB'}
          </span>
        </h3>
        <button className="toggle-btn">{isExpanded ? '\u25BC' : '\u25B6'}</button>
      </div>

      {isExpanded && (
        <div className="monitor-content">
          {resultId && (
            <div className="monitor-tabs">
              <button 
                className={`tab-btn ${activeTab === 'events' ? 'active' : ''}`}
                onClick={() => setActiveTab('events')}
              >
                Events
              </button>
              <button 
                className={`tab-btn ${activeTab === 'validation' ? 'active' : ''}`}
                onClick={() => setActiveTab('validation')}
              >
                dLLM Validation
              </button>
            </div>
          )}

          {activeTab === 'events' && (
            events.length === 0 ? (
              <p className="no-events">
                {resultId ? 'Waiting for extraction events...' : 'Upload and extract a document to see events'}
              </p>
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
            )
          )}

          {activeTab === 'validation' && (
            <div className="validation-panel">
              {loadingLog ? (
                <p className="loading">Loading validation log...</p>
              ) : validationLog ? (
                <>
                  <div className="validation-summary">
                    <span className="summary-item filled">
                      {validationLog.filled} Filled
                    </span>
                    <span className="summary-item missing">
                      {validationLog.missing} Missing
                    </span>
                    <span className="summary-item uncertain">
                      {validationLog.uncertain} Uncertain
                    </span>
                  </div>
                  <div className="validation-table">
                    <div className="validation-table-header">
                      <span>Field</span>
                      <span>Status</span>
                      <span>Value</span>
                      <span>Confidence</span>
                    </div>
                    {validationLog.fields.map((field, index) => (
                      <div key={index} className="validation-row">
                        <span className="field-name">{field.field}</span>
                        <span className="field-status" style={{ color: getStatusColor(field.status) }}>
                          {field.status.toUpperCase()}
                        </span>
                        <span className="field-value">
                          {field.value !== null ? String(field.value).substring(0, 50) : '-'}
                        </span>
                        <span className="field-confidence">
                          {getConfidenceBar(field.confidence)}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="no-data">No validation data available</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AgentMonitor
