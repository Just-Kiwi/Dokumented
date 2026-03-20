import React, { useState } from 'react'
import Upload from './components/Upload'
import SchemaConfig from './components/SchemaConfig'
import ResultsViewer from './components/ResultsViewer'
import AgentMonitor from './components/AgentMonitor'
import ConfigPanel from './components/ConfigPanel'
import { extractFields } from './api'
import './App.css'

function App() {
  const [uploadedDocument, setUploadedDocument] = useState(null)
  const [extractionResult, setExtractionResult] = useState(null)
  const [isExtracting, setIsExtracting] = useState(false)
  const [error, setError] = useState('')
  const [configOpen, setConfigOpen] = useState(false)

  const handleDocumentParsed = (data) => {
    setUploadedDocument(data)
    setExtractionResult(null)
    setError('')
  }

  const handleExtract = async (schema) => {
    if (!uploadedDocument) {
      setError('Please upload a document first')
      return
    }

    setIsExtracting(true)
    setError('')

    try {
      const response = await extractFields(
        uploadedDocument.filename,
        uploadedDocument.rawText,
        schema
      )

      // In a real scenario, you'd poll for results or use WebSocket
      // For now, just show that extraction started
      setExtractionResult({
        result_id: response.data.result_id,
        filename: uploadedDocument.filename,
        fingerprint: 'pending...',
        status: 'processing',
        extracted_json: {}
      })
    } catch (error) {
      setError(`Extraction failed: ${error.message}`)
    } finally {
      setIsExtracting(false)
    }
  }

  const handleOverridesApplied = () => {
    setError('')
    // Reset or show success message
  }

  const handleError = (errorMessage) => {
    setError(errorMessage)
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>🚀 DocFlow</h1>
          <p>Intelligent Document Extraction System</p>
        </div>
        <button
          className="config-btn"
          onClick={() => setConfigOpen(true)}
          title="Configure API Keys"
        >
          ⚙️ Settings
        </button>
      </header>

      <main className="app-main">
        <div className="container">
          {error && (
            <div className="error-banner">
              <p>{error}</p>
              <button onClick={() => setError('')}>✕</button>
            </div>
          )}

          <div className="panels">
            <div className="left-panel">
              <Upload
                onDocumentParsed={handleDocumentParsed}
                onError={handleError}
              />

              {uploadedDocument && (
                <div className="document-info">
                  <h3>✓ Document Loaded</h3>
                  <p><strong>File:</strong> {uploadedDocument.filename}</p>
                  <p><strong>Size:</strong> {(uploadedDocument.fullTextLength / 1024).toFixed(2)} KB</p>
                  <p><strong>Preview:</strong></p>
                  <div className="text-preview">
                    {uploadedDocument.rawText}
                  </div>
                </div>
              )}
            </div>

            <div className="right-panel">
              <SchemaConfig
                onSchemaChange={() => {}}
                onExtract={handleExtract}
                isLoading={isExtracting}
              />

              <ResultsViewer
                result={extractionResult}
                onOverridesApplied={handleOverridesApplied}
                onError={handleError}
              />
            </div>
          </div>

          <AgentMonitor resultId={extractionResult?.result_id} />
        </div>
      </main>

      <ConfigPanel
        isOpen={configOpen}
        onClose={() => setConfigOpen(false)}
      />

      <footer className="app-footer">
        <p>DocFlow v1.0.0 | Two-Model Agent Architecture | Lucas 2026</p>
      </footer>
    </div>
  )
}

export default App
