import React, { useState } from 'react'
import { uploadDocument } from '../api'
import './UploadPanel.css'

export const UploadPanel = ({ onFilesAdded, maxFiles, disabled }) => {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const processFile = async (file) => {
    setIsLoading(true)
    setError('')
    try {
      const response = await uploadDocument(file)
      return {
        filename: response.data.filename,
        rawText: response.data.raw_text,
        fullTextLength: response.data.full_text_length,
        status: 'unprocessed',
        result_id: null,
        error: null
      }
    } catch (err) {
      throw new Error(`Failed to upload ${file.name}: ${err.message}`)
    }
  }

  const handleDrop = async (e) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files)
    await processFiles(files)
  }

  const handleFileInput = async (e) => {
    const files = Array.from(e.target.files)
    await processFiles(files)
    e.target.value = ''
  }

  const processFiles = async (files) => {
    const validFiles = files.filter(f => 
      ['.pdf', '.docx', '.txt'].some(ext => f.name.toLowerCase().endsWith(ext))
    )
    
    if (validFiles.length === 0) {
      setError('Only PDF, DOCX, and TXT files are supported')
      return
    }

    setIsLoading(true)
    const results = []
    
    for (const file of validFiles) {
      try {
        const processed = await processFile(file)
        results.push(processed)
      } catch (err) {
        setError(err.message)
      }
    }
    
    if (results.length > 0) {
      onFilesAdded(results)
    }
    
    setIsLoading(false)
  }

  return (
    <div className="upload-panel">
      <h2>Upload Documents</h2>
      <p>Upload multiple files for batch processing</p>
      
      <div
        className={`drop-zone ${isLoading ? 'loading' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
        }}
        onDrop={handleDrop}
        onClick={() => document.getElementById('multi-file-input').click()}
      >
        <p>{isLoading ? 'Processing files...' : 'Drag and drop files here'}</p>
        <p>or</p>
        <label htmlFor="multi-file-input" className="file-input-label">
          {isLoading ? 'Processing...' : 'Click to browse'}
        </label>
        <input
          id="multi-file-input"
          type="file"
          accept=".pdf,.docx,.txt"
          multiple
          onChange={handleFileInput}
          disabled={disabled || isLoading}
          style={{ display: 'none' }}
        />
      </div>
      
      {error && <div className="upload-error">{error}</div>}
      
      <p className="supported-formats">
        Supported: PDF, DOCX, TXT (max {maxFiles} files)
      </p>
    </div>
  )
}

export default UploadPanel
