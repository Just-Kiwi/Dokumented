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
  const [theme, setTheme] = useState('day')

  React.useEffect(() => {
    try {
      const saved = localStorage.getItem('docflow-theme')
      if (saved === 'day' || saved === 'night') {
        setTheme(saved)
      }
    } catch {
    }
  }, [])

  React.useEffect(() => {
    try {
      localStorage.setItem('docflow-theme', theme)
    } catch {
    }
  }, [theme])

  const toggleTheme = () => {
    const next = theme === 'day' ? 'night' : 'day'
    setTheme(next)
  }

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
  }

  const handleError = (errorMessage) => {
    setError(errorMessage)
  }

  return (
    <div className="app" data-theme={theme}>
      <header className="app-header">
        <div className="header-content">
          <h1>Dokument</h1>
          <p>Intelligent Document Extraction System</p>
        </div>
        <div className="header-actions">
          <button
            className="config-btn"
            onClick={() => setConfigOpen(true)}
            title="Configure API Keys"
          >
            Settings
          </button>
          <button
            className="config-btn"
            onClick={toggleTheme}
            title="Toggle Day/Night Mode"
          >
            {theme === 'day' ? '\u2600' : '\u263D'}
          </button>
        </div>
      </header>

      <main className="app-main">
        <div className="container">
          {error && (
            <div className="error-banner">
              <p>{error}</p>
              <button onClick={() => setError('')}>Close</button>
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
                  <h3>Document Loaded</h3>
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
        <p>Dokument v1.0.0 | Two-Model Agent Architecture | Lucas 2026</p>
      </footer>
    </div>
  )
}

export default App
