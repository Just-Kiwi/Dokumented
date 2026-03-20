import React, { useState } from 'react'
import { uploadDocument } from '../api'
import './Upload.css'

export const Upload = ({ onDocumentParsed, onError }) => {
  const [isDragging, setIsDragging] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const processFile = async (file) => {
    setIsLoading(true)
    try {
      const response = await uploadDocument(file)
      onDocumentParsed({
        filename: response.data.filename,
        rawText: response.data.raw_text,
        fullTextLength: response.data.full_text_length
      })
    } catch (error) {
      onError(`Upload failed: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) {
      if (['.pdf', '.docx', '.txt'].some(ext => file.name.toLowerCase().endsWith(ext))) {
        processFile(file)
      } else {
        onError('Only PDF, DOCX, and TXT files are supported')
      }
    }
  }

  const handleFileInput = (e) => {
    const file = e.target.files[0]
    if (file) {
      processFile(file)
    }
  }

  return (
    <div className="upload-container">
      <h2>Upload Document</h2>
      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <p>Drag and drop your document here</p>
        <p>or</p>
        <label htmlFor="file-input" className="file-input-label">
          {isLoading ? 'Processing...' : 'Click to browse'}
        </label>
        <input
          id="file-input"
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={handleFileInput}
          disabled={isLoading}
          style={{ display: 'none' }}
        />
      </div>
      <p className="supported-formats">
        Supported: PDF, DOCX, TXT
      </p>
    </div>
  )
}

export default Upload
