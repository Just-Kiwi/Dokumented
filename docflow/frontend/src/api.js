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

export const applyOverrides = (resultId, overrides) =>
  api.post(`/extraction/${resultId}/overrides`, { result_id: resultId, overrides })

// Script library endpoints
export const listScripts = () => api.get('/scripts')
export const getScript = (fingerprint) => api.get(`/scripts/${fingerprint}`)

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
