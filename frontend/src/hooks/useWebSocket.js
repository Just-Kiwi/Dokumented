import { useState, useEffect } from 'react'
import { connectWebSocket } from '../api'

export const useWebSocket = (onMessage) => {
  const [isConnected, setIsConnected] = useState(false)
  const [ws, setWs] = useState(null)

  useEffect(() => {
    const socket = connectWebSocket(
      (data) => {
        setIsConnected(true)
        onMessage(data)
      },
      (error) => {
        setIsConnected(false)
      },
      () => {
        setIsConnected(false)
      }
    )

    setWs(socket)

    return () => {
      if (socket) {
        socket.close()
      }
    }
  }, [onMessage])

  const send = (message) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
    }
  }

  return { isConnected, send }
}

export default useWebSocket
