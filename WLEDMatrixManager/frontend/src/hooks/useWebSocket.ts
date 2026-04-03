/**
 * Custom hook for WebSocket connection
 */

import { useEffect, useCallback } from 'react'
import haClient from '@/api/client'
import { useHAStore } from '@/store/ha'

export function useWebSocket() {
  const setConnected = useHAStore((state) => state.setConnected)
  const setError = useHAStore((state) => state.setError)
  const updateEntity = useHAStore((state) => state.updateEntity)

  useEffect(() => {
    const handleMessage = (data: any) => {
      // Handle different message types from server
      if (data.entity) {
        updateEntity(data.entity)
      }
    }

    const handleError = () => {
      setConnected(false)
      setError('WebSocket connection failed')
    }

    haClient.connect(handleMessage, handleError)
    setConnected(true)

    return () => {
      haClient.disconnect()
      setConnected(false)
    }
  }, [setConnected, setError, updateEntity])

  const sendMessage = useCallback((data: any) => {
    haClient.send(data)
  }, [])

  return { sendMessage }
}
