import React from 'react'
import './BatchResultsTab.css'

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

export const BatchResultsTab = ({
  files,
  results,
  selectedIndex,
  onSelectTab,
  onDownloadSingle,
  onDownloadAll,
  hasResults
}) => {
  if (!hasResults) {
    return (
      <div className="batch-results-empty">
        No results to display. Process files to see extraction results.
      </div>
    )
  }

  const processedFiles = files.filter(f => f.status === 'processed')
  const currentFile = processedFiles[selectedIndex]
  const currentResult = results[currentFile?.filename]

  const getAllFields = (result) => {
    if (!result) return []
    
    const fields = []
    
    if (result.schema && result.schema.length > 0) {
      result.schema.forEach(fieldInfo => {
        const fieldName = fieldInfo.name
        const extractedValue = result.extracted_json?.[fieldName]
        fields.push({
          name: fieldName,
          value: extractedValue,
          status: fieldInfo.status || 'unknown',
          confidence: fieldInfo.confidence || 0
        })
      })
    } else if (result.extracted_json) {
      Object.entries(result.extracted_json).forEach(([fieldName, value]) => {
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

  const allFields = currentResult ? getAllFields(currentResult) : []

  return (
    <div className="batch-results-tab">
      <div className="tabs-header">
        <div className="tabs-list">
          {processedFiles.map((file, index) => (
            <button
              key={index}
              className={`tab-btn ${selectedIndex === index ? 'active' : ''}`}
              onClick={() => onSelectTab(index)}
            >
              {file.filename}
            </button>
          ))}
        </div>
        <div className="download-actions">
          <button
            className="download-btn"
            onClick={() => onDownloadSingle(selectedIndex)}
            disabled={!currentResult}
          >
            Download
          </button>
          <button
            className="download-btn download-all"
            onClick={onDownloadAll}
            disabled={processedFiles.length === 0}
          >
            Download All
          </button>
        </div>
      </div>

      <div className="tab-content">
        {currentResult ? (
          <>
            <div className="result-header">
              <p><strong>Filename:</strong> {currentResult.filename}</p>
              <p><strong>Script:</strong> v{currentResult.script_version}</p>
              <p><strong>Status:</strong> <span className={`status ${currentResult.status}`}>{currentResult.status}</span></p>
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
                    </tr>
                  </thead>
                  <tbody>
                    {allFields.map((field) => (
                      <tr key={field.name} className={getStatusClass(field.status)}>
                        <td className="field-name">{field.name}</td>
                        <td className="field-value">
                          {field.value !== null && field.value !== undefined 
                            ? String(field.value) 
                            : <em className="null">null</em>
                          }
                        </td>
                        <td className="field-status">
                          <span className={`status-badge ${getStatusClass(field.status)}`}>
                            {getStatusIcon(field.status)} {field.status || 'unknown'}
                          </span>
                        </td>
                        <td className="field-confidence">
                          {field.confidence > 0 ? `${(field.confidence * 100).toFixed(0)}%` : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
          <div className="no-result-selected">
            Select a file to view its results
          </div>
        )}
      </div>
    </div>
  )
}

export default BatchResultsTab
