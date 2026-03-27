import React, { useState, useEffect } from 'react'
import { applyOverrides, getExtraction } from '../api'
import './ResultsViewer.css'

const getStatusIcon = (status) => {
  switch (status) {
    case 'filled': return '\u2705'
    case 'missing': return '\u274C'
    case 'uncertain': return '\u26A0\uFE0F'
    default: return '\u2753'
  }
}

const getStatusClass = (status) => {
  switch (status) {
    case 'filled': return 'status-filled'
    case 'missing': return 'status-missing'
    case 'uncertain': return 'status-uncertain'
    default: return 'status-unknown'
  }
}

export const ResultsViewer = ({ result, onOverridesApplied, onError }) => {
  const [overrides, setOverrides] = useState({})
  const [isApplying, setIsApplying] = useState(false)
  const [fullResult, setFullResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (result && result.result_id && !result.schema) {
      setIsLoading(true)
      getExtraction(result.result_id)
        .then(res => {
          setFullResult(res.data)
        })
        .catch(err => {
          console.error('Failed to load full result:', err)
          setFullResult(result)
        })
        .finally(() => {
          setIsLoading(false)
        })
    } else if (result) {
      setFullResult(result)
    }
  }, [result])

  if (!result) {
    return <div className="results-empty">No extraction results yet</div>
  }

  const currentResult = fullResult || result

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

      await applyOverrides(currentResult.result_id, overridesList)
      onOverridesApplied()
      setOverrides({})
      setFullResult(null)
    } catch (error) {
      onError(`Failed to apply overrides: ${error.message}`)
    } finally {
      setIsApplying(false)
    }
  }

  const getAllFields = () => {
    const fields = []
    
    if (currentResult.schema && currentResult.schema.length > 0) {
      currentResult.schema.forEach(fieldInfo => {
        const fieldName = fieldInfo.name
        const extractedValue = currentResult.extracted_json?.[fieldName]
        fields.push({
          name: fieldName,
          value: extractedValue,
          status: fieldInfo.status || 'unknown',
          confidence: fieldInfo.confidence || 0
        })
      })
    } else if (currentResult.extracted_json) {
      Object.entries(currentResult.extracted_json).forEach(([fieldName, value]) => {
        fields.push({
          name: fieldName,
          value: value,
          status: value !== null && value !== undefined ? 'filled' : 'missing',
          confidence: value !== null && value !== undefined ? 1 : 0
        })
      })
    }
    
    return fields
  }

  const allFields = getAllFields()

  if (isLoading) {
    return <div className="results-empty">Loading results...</div>
  }

  return (
    <div className="results-viewer">
      <h2>Extraction Results</h2>

      <div className="result-header">
        <p><strong>Filename:</strong> {currentResult.filename}</p>
        <p><strong>Script:</strong> v{currentResult.script_version} {currentResult.script_id ? `(ID: ${currentResult.script_id})` : ''}</p>
        <p><strong>Status:</strong> <span className={`status ${currentResult.status}`}>{currentResult.status}</span></p>
        {currentResult.missing_fields && currentResult.missing_fields.length > 0 && (
          <p className="missing-count">
            <strong>Missing/Uncertain:</strong> {currentResult.missing_fields.length} field(s)
          </p>
        )}
      </div>

      {allFields.length === 0 ? (
        <div className="no-fields">No fields to display</div>
      ) : (
        <div className="results-table">
          <table>
            <thead>
              <tr>
                <th>Field</th>
                <th>Extracted Value</th>
                <th>Status</th>
                <th>Confidence</th>
                <th>Override</th>
              </tr>
            </thead>
            <tbody>
              {allFields.map((field) => {
                const displayValue = overrides[field.name] !== undefined 
                  ? overrides[field.name] 
                  : field.value
                const isOverridden = overrides[field.name] !== undefined
                
                return (
                  <tr key={field.name} className={getStatusClass(field.status)}>
                    <td className="field-name">{field.name}</td>
                    <td className="field-value">
                      {displayValue !== null && displayValue !== undefined 
                        ? String(displayValue) 
                        : <em className="null">null</em>
                      }
                      {isOverridden && field.value !== overrides[field.name] && (
                        <span className="overridden-badge">edited</span>
                      )}
                    </td>
                    <td className="field-status">
                      <span className={`status-badge ${getStatusClass(field.status)}`}>
                        {getStatusIcon(field.status)} {field.status || 'unknown'}
                      </span>
                    </td>
                    <td className="field-confidence">
                      {field.confidence > 0 ? `${(field.confidence * 100).toFixed(0)}%` : '-'}
                    </td>
                    <td className="field-override">
                      <input
                        type="text"
                        placeholder={field.status === 'missing' ? 'Enter value...' : 'Override...'}
                        value={overrides[field.name] !== undefined ? overrides[field.name] : ''}
                        onChange={(e) => handleOverrideChange(field.name, e.target.value)}
                        className="override-input"
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

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