import React, { useState, useEffect, useCallback } from 'react'
import UploadPanel from './components/UploadPanel'
import FileQueuePanel from './components/FileQueuePanel'
import BatchResultsTab from './components/BatchResultsTab'
import SchemaConfig from './components/SchemaConfig'
import { 
  startBatch, getBatch, listBatches,
  pauseBatch, resumeBatch, cancelBatch, clearBatch, processBatch,
  downloadBatch, getExtraction
} from './api'
import './App.css'

const POLL_INTERVAL = 2000

function App() {
  const [batchId, setBatchId] = useState(null)
  const [files, setFiles] = useState([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [batchStatus, setBatchStatus] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [schema, setSchema] = useState([
    { name: 'vendor_name', description: 'Name of the vendor/company', required: true },
    { name: 'invoice_date', description: 'Date of the invoice', required: true },
    { name: 'invoice_total', description: 'Total amount due', required: true },
    { name: 'invoice_number', description: 'Invoice reference number', required: true }
  ])
  const [error, setError] = useState('')
  const [results, setResults] = useState({})
  const [theme, setTheme] = useState('day')

  const loadBatch = useCallback(async (id) => {
    try {
      const response = await getBatch(id)
      setFiles(response.data.files)
      setBatchStatus(response.data.status)
      setIsProcessing(response.data.status === 'processing')
      
      const processedFiles = response.data.files.filter(f => f.status === 'processed')
      const newResults = {}
      
      for (let i = 0; i < processedFiles.length; i++) {
        const file = processedFiles[i]
        if (file.result_id) {
          try {
            const resultRes = await getExtraction(file.result_id)
            newResults[file.filename] = resultRes.data
          } catch (e) {
            console.error('Failed to load result for', file.filename, e)
          }
        }
      }
      
      if (Object.keys(newResults).length > 0) {
        setResults(newResults)
      }
      
    } catch (e) {
      console.error('Failed to load batch:', e)
    }
  }, [])

  useEffect(() => {
    try {
      const saved = localStorage.getItem('dokumented-theme')
      if (saved === 'day' || saved === 'night') {
        setTheme(saved)
      }
    } catch {}
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem('dokumented-theme', theme)
    } catch {}
  }, [theme])

  useEffect(() => {
    let interval
    if (batchId && isProcessing) {
      interval = setInterval(() => {
        loadBatch(batchId)
      }, POLL_INTERVAL)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [batchId, isProcessing, loadBatch])

  useEffect(() => {
    const loadLastBatch = async () => {
      try {
        const res = await listBatches()
        if (res.data.length > 0) {
          const lastBatch = res.data[0]
          if (lastBatch.status !== 'completed' && lastBatch.status !== 'cancelled') {
            setBatchId(lastBatch.batch_id)
            loadBatch(lastBatch.batch_id)
          }
        }
      } catch (e) {
        console.error('Failed to load batches:', e)
      }
    }
    loadLastBatch()
  }, [loadBatch])

  const toggleTheme = () => {
    const next = theme === 'day' ? 'night' : 'day'
    setTheme(next)
  }

  const handleFilesAdded = async (newFiles) => {
    setError('')
    try {
      const filesForApi = newFiles.map(f => ({
        filename: f.filename,
        raw_text: f.rawText
      }))
      
      const filesWithStatus = newFiles.map(f => ({
        filename: f.filename,
        rawText: f.rawText,
        status: 'unprocessed',
        resultId: null,
        error: null
      }))
      
      const schemaForApi = schema.map(f => ({
        name: f.name,
        description: f.description || '',
        required: f.required
      }))
      
      const res = await startBatch(filesForApi, schemaForApi)
      setBatchId(res.data.batch_id)
      setFiles(filesWithStatus)
      setBatchStatus('pending')
      
      await loadBatch(res.data.batch_id)
      
    } catch (e) {
      setError(`Failed to start batch: ${e.message}`)
    }
  }

  const handleStartExtraction = async () => {
    if (!batchId) return
    setIsProcessing(true)
    try {
      await processBatch(batchId)
      loadBatch(batchId)
    } catch (e) {
      setIsProcessing(false)
      setError(`Processing failed: ${e.message}`)
    }
  }

  const handleSelectFile = (index) => {
    setSelectedIndex(index)
  }

  const handlePause = async () => {
    if (!batchId) return
    try {
      await pauseBatch(batchId)
      setBatchStatus('paused')
      loadBatch(batchId)
    } catch (e) {
      setError(`Failed to pause: ${e.message}`)
    }
  }

  const handleResume = async () => {
    if (!batchId) return
    try {
      await resumeBatch(batchId)
      setBatchStatus('processing')
      setIsProcessing(true)
      loadBatch(batchId)
    } catch (e) {
      setError(`Failed to resume: ${e.message}`)
    }
  }

  const handleCancel = async () => {
    if (!batchId) return
    try {
      await cancelBatch(batchId)
      setBatchStatus('cancelled')
      setIsProcessing(false)
      loadBatch(batchId)
    } catch (e) {
      setError(`Failed to cancel: ${e.message}`)
    }
  }

  const handleClear = async () => {
    if (!batchId) return
    try {
      await clearBatch(batchId)
      setBatchId(null)
      setFiles([])
      setBatchStatus(null)
      setResults({})
      setSelectedIndex(0)
    } catch (e) {
      setError(`Failed to clear: ${e.message}`)
    }
  }

  const handleDownloadSingle = async (index) => {
    const processedFiles = files.filter(f => f.status === 'processed')
    const file = processedFiles[index]
    if (!file || !file.resultId) return
    
    try {
      const res = await getExtraction(file.resultId)
      const dataStr = JSON.stringify(res.data, null, 2)
      const blob = new Blob([dataStr], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${file.filename.replace(/\.[^/.]+$/, '')}_result.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(`Failed to download: ${e.message}`)
    }
  }

  const handleDownloadAll = async () => {
    if (!batchId) return
    try {
      const res = await downloadBatch(batchId)
      const dataStr = JSON.stringify(res.data, null, 2)
      const blob = new Blob([dataStr], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `batch_${batchId}_results.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(`Failed to download: ${e.message}`)
    }
  }

  const processedFiles = files.filter(f => f.status === 'processed')
  const selectedResult = processedFiles[selectedIndex] ? results[processedFiles[selectedIndex].filename] : null
  const isPaused = batchStatus === 'paused'

  return (
    <div className="app" data-theme={theme}>
      <header className="app-header">
        <div className="header-content">
          <h1>Dokument</h1>
          <p>Intelligent Document Extraction System</p>
        </div>
        <div className="header-actions">
          <button className="config-btn" onClick={toggleTheme}>
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

          <div className="panels batch-mode">
            <div className="left-panel">
              <UploadPanel
                onFilesAdded={handleFilesAdded}
                maxFiles={25}
                disabled={isProcessing}
              />
              
              <FileQueuePanel
                files={files}
                selectedIndex={selectedIndex}
                onSelectFile={handleSelectFile}
                onPause={handlePause}
                onResume={handleResume}
                onCancel={handleCancel}
                onClear={handleClear}
                isProcessing={isProcessing}
                isPaused={isPaused}
                disabled={!batchId}
              />
            </div>

            <div className="right-panel">
              <SchemaConfig
                onSchemaChange={setSchema}
                onExtract={handleStartExtraction}
                isLoading={isProcessing}
                disabled={files.length === 0}
              />
              
              <BatchResultsTab
                files={files}
                results={results}
                selectedIndex={selectedIndex}
                onSelectTab={setSelectedIndex}
                onDownloadSingle={handleDownloadSingle}
                onDownloadAll={handleDownloadAll}
                hasResults={processedFiles.length > 0}
              />
            </div>
          </div>
        </div>
      </main>

      <footer className="app-footer">
        <p>Dokument v1.0.0 | Two-Model Agent Architecture | Lucas 2026</p>
      </footer>
    </div>
  )
}

export default App
