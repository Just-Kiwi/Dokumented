import React from 'react'
import './FileQueuePanel.css'

const statusColors = {
  unprocessed: '#9e9e9e',
  processing: '#ff9800',
  processed: '#4caf50',
  paused: '#9c27b0',
  cancelled: '#f44336'
}

const getStatusClass = (status) => {
  return `file-item file-${status}`
}

export const FileQueuePanel = ({
  files,
  selectedIndex,
  onSelectFile,
  onPause,
  onResume,
  onCancel,
  onClear,
  isProcessing,
  isPaused,
  disabled
}) => {
  const processedCount = files.filter(f => f.status === 'processed').length

  return (
    <div className="file-queue-panel">
      <div className="queue-header">
        <h2>File Queue</h2>
        <span className="queue-count">
          {processedCount} / {files.length} processed
        </span>
      </div>

      <div className="file-list">
        {files.map((file, index) => (
          <div
            key={index}
            className={getStatusClass(file.status) + (selectedIndex === index ? ' selected' : '')}
            onClick={() => onSelectFile(index)}
          >
            <div 
              className="status-indicator"
              style={{ backgroundColor: statusColors[file.status] || statusColors.unprocessed }}
            />
            <div className="file-info">
              <span className={file.status === 'cancelled' ? 'file-name cancelled' : 'file-name'}>
                {file.filename}
              </span>
              {file.error && <span className="file-error">{file.error}</span>}
            </div>
            <span className="status-label">{file.status}</span>
          </div>
        ))}
      </div>

      <div className="queue-actions">
        {isProcessing && !isPaused ? (
          <button 
            className="action-btn pause-btn"
            onClick={onPause}
            disabled={disabled}
          >
            Pause
          </button>
        ) : isPaused ? (
          <button 
            className="action-btn resume-btn"
            onClick={onResume}
            disabled={disabled}
          >
            Resume
          </button>
        ) : null}
        <button 
          className="action-btn cancel-btn"
          onClick={onCancel}
          disabled={disabled || (files.length === 0)}
        >
          Cancel
        </button>
        <button 
          className="action-btn clear-btn"
          onClick={onClear}
          disabled={disabled || (files.length === 0)}
        >
          Clear
        </button>
      </div>
    </div>
  )
}

export default FileQueuePanel
