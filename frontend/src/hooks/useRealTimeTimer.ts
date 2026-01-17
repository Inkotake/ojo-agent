import { useState, useEffect, useRef } from 'react'

/**
 * 格式化耗时显示
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`
  }
  
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) {
    return `${seconds}s`
  }
  
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes < 60) {
    return `${minutes}m ${remainingSeconds}s`
  }
  
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return `${hours}h ${remainingMinutes}m`
}

/**
 * 实时计时器Hook
 * 用于显示运行中任务的实时耗时
 */
export function useRealTimeTimer(
  startTime: Date | string | number | null,
  isRunning: boolean = true,
  intervalMs: number = 1000
) {
  const [elapsed, setElapsed] = useState(0)
  const [formattedTime, setFormattedTime] = useState('0s')
  const intervalRef = useRef<number | null>(null)
  
  useEffect(() => {
    if (!startTime || !isRunning) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      return
    }
    
    const start = typeof startTime === 'string' || typeof startTime === 'number'
      ? new Date(startTime).getTime()
      : startTime.getTime()
    
    const updateElapsed = () => {
      const now = Date.now()
      const ms = now - start
      setElapsed(ms)
      setFormattedTime(formatDuration(ms))
    }
    
    // 立即更新一次
    updateElapsed()
    
    // 设置定时更新
    intervalRef.current = window.setInterval(updateElapsed, intervalMs)
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [startTime, isRunning, intervalMs])
  
  return { elapsed, formattedTime }
}

/**
 * 批量任务计时器
 * 用于跟踪多个任务的耗时
 */
interface TaskTimer {
  id: string
  startTime: Date
  endTime?: Date
  status: 'running' | 'completed' | 'failed'
}

export function useTaskTimers() {
  const [timers, setTimers] = useState<Map<string, TaskTimer>>(new Map())
  const [now, setNow] = useState(Date.now())
  
  // 每秒更新当前时间
  useEffect(() => {
    const interval = setInterval(() => {
      setNow(Date.now())
    }, 1000)
    
    return () => clearInterval(interval)
  }, [])
  
  const startTimer = (taskId: string) => {
    setTimers(prev => {
      const newTimers = new Map(prev)
      newTimers.set(taskId, {
        id: taskId,
        startTime: new Date(),
        status: 'running'
      })
      return newTimers
    })
  }
  
  const stopTimer = (taskId: string, status: 'completed' | 'failed' = 'completed') => {
    setTimers(prev => {
      const newTimers = new Map(prev)
      const timer = newTimers.get(taskId)
      if (timer) {
        newTimers.set(taskId, {
          ...timer,
          endTime: new Date(),
          status
        })
      }
      return newTimers
    })
  }
  
  const getElapsed = (taskId: string): number => {
    const timer = timers.get(taskId)
    if (!timer) return 0
    
    const endTime = timer.endTime ? timer.endTime.getTime() : now
    return endTime - timer.startTime.getTime()
  }
  
  const getFormattedElapsed = (taskId: string): string => {
    return formatDuration(getElapsed(taskId))
  }
  
  const clearTimer = (taskId: string) => {
    setTimers(prev => {
      const newTimers = new Map(prev)
      newTimers.delete(taskId)
      return newTimers
    })
  }
  
  const clearAllTimers = () => {
    setTimers(new Map())
  }
  
  return {
    timers,
    startTimer,
    stopTimer,
    getElapsed,
    getFormattedElapsed,
    clearTimer,
    clearAllTimers
  }
}

export default useRealTimeTimer
