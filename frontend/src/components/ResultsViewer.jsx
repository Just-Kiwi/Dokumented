import React, { useState } from 'react'
import { applyOverrides } from '../api'
import './ResultsViewer.css'

export const ResultsViewer = ({ result, onOverridesApplied, onError }) => {
  const [overrides, setOverrides] = useState({})
  const [isApplying, setIsApplying] = useState(false)

  if (!result) {
    return <div className="results-empty">No extraction results yet</div>
  }

  const handleOverrideChange = (fieldName, value) => {
    setOverrides({
      ...overrides,
      [fieldName]: value === '' ? null : value
    })
  }

  const handleApplyOverrides = async () => {
    setIsApplying(true)
    try {
      const overridesList = Object.entries(overrides).map(([field_name, value]) => ({
        field_name,
        value
      }))

      await applyOverrides(result.result_id, overridesList)
      onOverridesApplied()
      setOverrides({})
    } catch (error) {
      onError(`Failed to apply overrides: ${error.message}`)
    } finally {
      setIsApplying(false)
    }
  }

  return (
    <div className="results-viewer">
      <h2>Extraction Results</h2>

      <div className="result-header">
        <p><strong>Filename:</strong> {result.filename}</p>
        <p><strong>Script:</strong> v{result.script_version} {result.script_id ? `(ID: ${result.script_id})` : ''}</p>
        <p><strong>Status:</strong> <span className={`status ${result.status}`}>{result.status}</span></p>
      </div>

      <div className="results-table">
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>Extracted Value</th>
              <th>Override</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(result.extracted_json || {}).map(([field, value]) => (
              <tr key={field}>
                <td className="field-name">{field}</td>
                <td className="field-value">
                  {value !== null && value !== undefined ? String(value) : <em className="null">null</em>}
                </td>
                <td className="field-override">
                  <input
                    type="text"
                    placeholder="Set value or clear..."
                    value={overrides[field] !== undefined ? overrides[field] : ''}
                    onChange={(e) => handleOverrideChange(field, e.target.value)}
                    className="override-input"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {Object.keys(overrides).length > 0 && (
        <div className="override-actions">
          <button
            onClick={handleApplyOverrides}
            className="apply-btn"
            disabled={isApplying}
          >
            {isApplying ? 'Applying...' : 'Apply Overrides'}
          </button>
          <button
            onClick={() => setOverrides({})}
            className="cancel-btn"
            disabled={isApplying}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}

export default ResultsViewer
