import React, { useState } from 'react'
import './ConfigPanel.css'
import { setConfig, getConfig } from '../api'

export const ConfigPanel = ({ isOpen, onClose }) => {
  const [llmKey, setLlmKey] = useState('')
  const [dllmKey, setDllmKey] = useState('')
  const [dllmUrl, setDllmUrl] = useState('https://api.inceptionlabs.ai/v1')
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [keyStatus, setKeyStatus] = useState({
    llm: false,
    dllm: false
  })

  const handleSaveConfig = async () => {
    setIsLoading(true)
    setMessage('')

    try {
      if (llmKey) {
        await setConfig('ANTHROPIC_API_KEY', llmKey)
      }
      if (dllmKey) {
        await setConfig('MERCURY_API_KEY', dllmKey)
      }
      if (dllmUrl) {
        await setConfig('MERCURY_BASE_URL', dllmUrl)
      }

      setMessage('Configuration saved successfully!')
      setTimeout(() => {
        setLlmKey('')
        setDllmKey('')
        setMessage('')
      }, 2000)
    } catch (error) {
      setMessage(`Error saving configuration: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleCheckConfig = async () => {
    setIsLoading(true)
    setKeyStatus({ llm: false, dllm: false })

    try {
      const checkLlm = await getConfig('ANTHROPIC_API_KEY').catch(() => null)
      const checkDllm = await getConfig('MERCURY_API_KEY').catch(() => null)

      setKeyStatus({
        llm: !!checkLlm?.data?.value,
        dllm: !!checkDllm?.data?.value
      })

      setMessage('Configuration check complete')
      setTimeout(() => setMessage(''), 2000)
    } catch (error) {
      setMessage(`Error checking configuration: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
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
          <div className="config-section">
            <label>LLM API Key (Claude Sonnet)</label>
            <input
              type="password"
              value={llmKey}
              onChange={(e) => setLlmKey(e.target.value)}
              placeholder="sk-ant-..."
              disabled={isLoading}
            />
            <p className="hint">Leave empty to keep existing key</p>
            {keyStatus.llm && <p className="status-text">Key configured</p>}
          </div>

          <div className="config-section">
            <label>dLLM API Key (Mercury 2)</label>
            <input
              type="password"
              value={dllmKey}
              onChange={(e) => setDllmKey(e.target.value)}
              placeholder="your-mercury-key..."
              disabled={isLoading}
            />
            <p className="hint">Leave empty to keep existing key</p>
            {keyStatus.dllm && <p className="status-text">Key configured</p>}
          </div>

          <div className="config-section">
            <label>dLLM Base URL (Mercury 2)</label>
            <input
              type="text"
              value={dllmUrl}
              onChange={(e) => setDllmUrl(e.target.value)}
              placeholder="https://api.inceptionlabs.ai/v1"
              disabled={isLoading}
            />
            <p className="hint">Default: https://api.inceptionlabs.ai/v1</p>
          </div>

          {message && (
            <div className={`message ${message.includes('Error') ? 'error' : 'success'}`}>
              {message}
            </div>
          )}

          <div className="config-actions">
            <button
              onClick={handleCheckConfig}
              className="check-btn"
              disabled={isLoading}
            >
              {isLoading ? 'Checking...' : 'Check Configuration'}
            </button>
            <button
              onClick={handleSaveConfig}
              className="save-btn"
              disabled={isLoading || (!llmKey && !dllmKey)}
            >
              {isLoading ? 'Saving...' : 'Save Configuration'}
            </button>
            <button
              onClick={onClose}
              className="cancel-btn"
              disabled={isLoading}
            >
              Cancel
            </button>
          </div>

          <div className="config-info">
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
