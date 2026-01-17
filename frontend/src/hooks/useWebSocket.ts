import { useEffect, useState, useCallback, useRef } from 'react'

interface WebSocketMessage {
  type: string
  timestamp?: string
  data?: any
  [key: string]: any
}

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting'

// 全局 WebSocket 实例（避免多个组件创建多个连接）
let globalWs: WebSocket | null = null
let globalReconnectTimeout: number | null = null
let globalHeartbeatInterval: number | null = null
let connectionCount = 0
let reconnectAttempts = 0
const MAX_RECONNECT_ATTEMPTS = 10
const HEARTBEAT_INTERVAL = 30000 // 30秒心跳

// 指数退避计算
function getReconnectDelay(attempt: number): number {
  const baseDelay = 1000 // 1秒
  const maxDelay = 30000 // 最大30秒
  const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay)
  // 添加随机抖动
  return delay + Math.random() * 1000
}

export function useWebSocket() {
  const [connected, setConnected] = useState(false)
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [messages, setMessages] = useState<WebSocketMessage[]>([])
  const [lastPong, setLastPong] = useState<Date | null>(null)
  const mountedRef = useRef(true)
  
  useEffect(() => {
    mountedRef.current = true
    connectionCount++
    
    const startHeartbeat = () => {
      if (globalHeartbeatInterval) {
        clearInterval(globalHeartbeatInterval)
      }
      globalHeartbeatInterval = window.setInterval(() => {
        if (globalWs && globalWs.readyState === WebSocket.OPEN) {
          globalWs.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
        }
      }, HEARTBEAT_INTERVAL)
    }
    
    const stopHeartbeat = () => {
      if (globalHeartbeatInterval) {
        clearInterval(globalHeartbeatInterval)
        globalHeartbeatInterval = null
      }
    }
    
    const connect = () => {
      // 如果已经有连接且是打开状态，复用它
      if (globalWs && globalWs.readyState === WebSocket.OPEN) {
        setConnected(true)
        setStatus('connected')
        return
      }
      
      // 如果正在连接中，等待
      if (globalWs && globalWs.readyState === WebSocket.CONNECTING) {
        setStatus('connecting')
        return
      }
      
      // 关闭旧连接
      if (globalWs) {
        globalWs.close()
        globalWs = null
      }
      
      setStatus(reconnectAttempts > 0 ? 'reconnecting' : 'connecting')
      
      // 创建新连接
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${protocol}//${host}/ws`
      
      try {
        const ws = new WebSocket(wsUrl)
        globalWs = ws
        
        ws.onopen = () => {
          reconnectAttempts = 0 // 重置重连计数
          if (mountedRef.current) {
            setConnected(true)
            setStatus('connected')
          }
          console.log('WebSocket connected')
          if (globalReconnectTimeout) {
            clearTimeout(globalReconnectTimeout)
            globalReconnectTimeout = null
          }
          startHeartbeat()
        }
        
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            
            // 处理心跳响应
            if (data.type === 'pong') {
              if (mountedRef.current) {
                setLastPong(new Date())
              }
              return
            }
            
            if (mountedRef.current) {
              setMessages(prev => {
                // 限制消息数量，避免内存泄漏
                const newMessages = [...prev, { ...data, timestamp: new Date().toISOString() }]
                return newMessages.slice(-100)
              })
            }
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }
        
        ws.onerror = (error) => {
          console.error('WebSocket error:', error)
        }
        
        ws.onclose = () => {
          stopHeartbeat()
          if (mountedRef.current) {
            setConnected(false)
            setStatus('disconnected')
          }
          console.log('WebSocket disconnected')
          globalWs = null
          
          // 指数退避重连
          if (connectionCount > 0 && !globalReconnectTimeout && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            const delay = getReconnectDelay(reconnectAttempts)
            reconnectAttempts++
            console.log(`WebSocket reconnecting in ${Math.round(delay/1000)}s (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`)
            
            if (mountedRef.current) {
              setStatus('reconnecting')
            }
            
            globalReconnectTimeout = window.setTimeout(() => {
              globalReconnectTimeout = null
              if (connectionCount > 0) {
                connect()
              }
            }, delay)
          }
        }
      } catch (error) {
        console.error('Failed to create WebSocket:', error)
      }
    }
    
    connect()
    
    // 如果已连接，更新状态
    if (globalWs && globalWs.readyState === WebSocket.OPEN) {
      setConnected(true)
      setStatus('connected')
    }
    
    return () => {
      mountedRef.current = false
      connectionCount--
      
      // 只有当没有 hook 使用时才关闭连接
      if (connectionCount <= 0) {
        stopHeartbeat()
        if (globalReconnectTimeout) {
          clearTimeout(globalReconnectTimeout)
          globalReconnectTimeout = null
        }
        if (globalWs) {
          globalWs.close()
          globalWs = null
        }
        connectionCount = 0
        reconnectAttempts = 0
      }
    }
  }, [])
  
  const sendMessage = useCallback((message: any) => {
    if (globalWs && globalWs.readyState === WebSocket.OPEN) {
      globalWs.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }, [])
  
  return { connected, status, messages, sendMessage, lastPong }
}

