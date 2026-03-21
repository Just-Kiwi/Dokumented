import React, { useState } from 'react'
import './ConfigPanel.css'
import { listConfig } from '../api'

export const ConfigPanel = ({ isOpen, onClose }) => {
  const [config, setConfig] = useState({})
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [creditStatus, setCreditStatus] = useState(null)
  const [hasLoaded, setHasLoaded] = useState(false)

  const loadConfig = async () => {
    setIsLoading(true)
    setMessage('')
    try {
      const response = await listConfig()
      setConfig(response.data)
      setHasLoaded(true)
    } catch (error) {
      setMessage('Error loading configuration')
    } finally {
      setIsLoading(false)
    }
  }

  const handleCheckCredits = async () => {
    if (!hasLoaded) {
      await loadConfig()
    }
    
    setIsLoading(true)
    setCreditStatus(null)
    setMessage('')

    try {
      const response = await listConfig()
      const anthropicConfigured = response.data?.ANTHROPIC_API_KEY?.configured
      const mercuryConfigured = response.data?.MERCURY_API_KEY?.configured
      
      if (!anthropicConfigured) {
        setMessage('ANTHROPIC_API_KEY not configured.')
        setIsLoading(false)
        return
      }
      
      if (!mercuryConfigured) {
        setCreditStatus({ anthropic: 'configured' })
        setMessage('Anthropic key configured. MERCURY_API_KEY not configured.')
        setIsLoading(false)
        return
      }
      
      setCreditStatus({
        anthropic: 'configured',
        mercury: 'configured'
      })
      setMessage('API keys are configured. Credits will be verified when you run an extraction.')
    } catch (error) {
      setMessage(`Error checking configuration: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleRefresh = async () => {
    await loadConfig()
  }

  if (!isOpen) return null

  return (
    <div className="config-panel-backdrop">
      <div className="config-panel">
        <div className="config-header">
          <h2>Configuration</h2>
          <button className="close-btn" onClick={onClose}>Close</button>
        </div>

        <div className="config-content">
          {!hasLoaded && !isLoading && (
            <div className="load-prompt">
              <p>Click "Load" or "Check Configuration" to view current settings.</p>
            </div>
          )}

          {hasLoaded && (
            <>
              <div className="config-section">
                <label>Anthropic API Key (Claude Sonnet)</label>
                <div className="config-value">
                  {config.ANTHROPIC_API_KEY?.configured ? (
                    <span className="key-configured">
                      <span className="check-icon">✓</span>
                      {config.ANTHROPIC_API_KEY.value}
                    </span>
                  ) : (
                    <span className="key-not-configured">
                      <span className="x-icon">✗</span>
                      Not configured
                    </span>
                  )}
                </div>
                <p className="hint">Set <code>ANTHROPIC_API_KEY</code> in <code>backend/.env</code></p>
              </div>

              <div className="config-section">
                <label>Mercury API Key (Mercury 2)</label>
                <div className="config-value">
                  {config.MERCURY_API_KEY?.configured ? (
                    <span className="key-configured">
                      <span className="check-icon">✓</span>
                      {config.MERCURY_API_KEY.value}
                    </span>
                  ) : (
                    <span className="key-not-configured">
                      <span className="x-icon">✗</span>
                      Not configured
                    </span>
                  )}
                </div>
                <p className="hint">Set <code>MERCURY_API_KEY</code> in <code>backend/.env</code></p>
              </div>

              <div className="config-section">
                <label>Mercury Base URL</label>
                <div className="config-value">
                  {config.MERCURY_BASE_URL?.value || 'https://api.inceptionlabs.ai/v1'}
                </div>
                <p className="hint">Set <code>MERCURY_BASE_URL</code> in <code>backend/.env</code> to override</p>
              </div>

              <div className="config-section">
                <label>Application Settings</label>
                <div className="settings-list">
                  <div className="setting-item">
                    <span className="setting-name">Max Retries:</span>
                    <span className="setting-value">{config.MAX_RETRIES?.value || '3'}</span>
                  </div>
                  <div className="setting-item">
                    <span className="setting-name">Confidence Threshold:</span>
                    <span className="setting-value">{config.CONFIDENCE_THRESHOLD?.value || '0.75'}</span>
                  </div>
                  <div className="setting-item">
                    <span className="setting-name">Database:</span>
                    <span className="setting-value db-path">{config.DATABASE_URL?.value || 'sqlite:///./dokumented.db'}</span>
                  </div>
                </div>
                <p className="hint">Edit these values in <code>backend/.env</code></p>
              </div>
            </>
          )}

          {message && (
            <div className={`message ${message.includes('Error') || message.includes('Not configured') || message.includes('not configured') ? 'error' : 'success'}`}>
              {message}
            </div>
          )}

          <div className="config-actions">
            <button
              onClick={handleCheckCredits}
              className="check-btn"
              disabled={isLoading}
            >
              {isLoading ? 'Checking...' : 'Check Configuration'}
            </button>
            <button
              onClick={handleRefresh}
              className="refresh-btn"
              disabled={isLoading}
            >
              Load
            </button>
            <button
              onClick={onClose}
              className="cancel-btn"
              disabled={isLoading}
            >
              Done
            </button>
          </div>

          <div className="config-info">
            <h3>How to Configure</h3>
            <ol>
              <li>Edit the <code>backend/.env</code> file</li>
              <li>Add your API keys:
                <pre>
{`ANTHROPIC_API_KEY=sk-ant-your-key
MERCURY_API_KEY=your-mercury-key`}
                </pre>
              </li>
              <li>Restart the backend server</li>
              <li>Click "Check Configuration" to verify</li>
            </ol>
            <h3>API Documentation</h3>
            <ul>
              <li>
                <strong>Claude Sonnet:</strong>
                <a href="https://docs.anthropic.com" target="_blank" rel="noopener noreferrer">
                  Anthropic Docs
                </a>
              </li>
              <li>
                <strong>Mercury 2:</strong>
                <a href="https://docs.inceptionlabs.ai" target="_blank" rel="noopener noreferrer">
                  Inception Labs Docs
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ConfigPanel
