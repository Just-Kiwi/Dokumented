import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Config endpoints
export const getConfig = (key) => api.get(`/config/${key}`)
export const setConfig = (key, value) => api.post('/config', { key, value })
export const listConfig = () => api.get('/config')

// Extraction endpoints
export const uploadDocument = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const extractFields = (filename, rawText, schema) => 
  api.post('/extract', { filename, raw_text: rawText, schema })

export const getExtraction = (resultId) => api.get(`/extraction/${resultId}`)

export const getValidationLog = (resultId) => api.get(`/extraction/${resultId}/validation-log`)

export const applyOverrides = (resultId, overrides) =>
  api.post(`/extraction/${resultId}/overrides`, { result_id: resultId, overrides })

export const getConfigList = () => api.get('/config')

export const startBatch = (files, field_definitions) =>
  api.post('/batch/start', { files, field_definitions: field_definitions || [] })

export const getBatch = (batchId) => api.get(`/batch/${batchId}`)

export const listBatches = () => api.get('/batch')

export const pauseBatch = (batchId) => api.post(`/batch/${batchId}/pause`)

export const resumeBatch = (batchId) => api.post(`/batch/${batchId}/resume`)

export const cancelBatch = (batchId) => api.post(`/batch/${batchId}/cancel`)

export const clearBatch = (batchId) => api.post(`/batch/${batchId}/clear`)

export const processBatch = (batchId) => api.post(`/batch/${batchId}/process`)

export const downloadBatch = (batchId) => api.get(`/batch/${batchId}/download`)

export const downloadSingleResult = (resultId) => api.get(`/extraction/${resultId}`)

export const listScripts = () => api.get('/scripts')
export const getScript = (scriptId) => api.get(`/scripts/${scriptId}`)

// WebSocket
export const connectWebSocket = (onMessage, onError, onClose) => {
  const ws = new WebSocket('ws://localhost:8000/ws/status')
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onMessage(data)
    } catch (e) {
      console.error('WebSocket message parse error:', e)
    }
  }
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
    onError(error)
  }
  
  ws.onclose = () => {
    console.log('WebSocket closed')
    onClose()
  }
  
  return ws
}

export default api
