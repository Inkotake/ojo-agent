import { useState, useEffect, useRef } from 'react'
import { X, Search, Download, Copy, Check, RefreshCw } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import Button from './ui/Button'
import apiClient from '../api/client'

interface LogEntry {
  time: string
  message: string
  level?: 'info' | 'warning' | 'error' | 'success'
}

interface LogDialogProps {
  isOpen: boolean
  onClose: () => void
  taskId: string
  problemId: string
  logs?: string[]  // 可选，如果不提供则从后端获取
  onRefresh?: () => void
}

export default function LogDialog({
  isOpen,
  onClose,
  taskId,
  problemId,
  logs: propLogs,
  onRefresh
}: LogDialogProps) {
  // 从后端获取日志
  const { data: fetchedLogs, isLoading, refetch } = useQuery({
    queryKey: ['task-logs', taskId, problemId],
    queryFn: async () => {
      if (!taskId) return []
      try {
        const response = await apiClient.get(`/api/tasks/${taskId}/logs`, {
          params: { problem_id: problemId }
        })
        return response.data.logs || []
      } catch (err) {
        console.error('获取日志失败:', err)
        return []
      }
    },
    enabled: isOpen && !!taskId,
    refetchInterval: isOpen ? 2000 : false,  // 打开时每2秒刷新一次
  })
  
  // 合并后端日志和实时日志（实时日志可能有后端还没保存的新内容）
  const logs = [...(fetchedLogs || []), ...(propLogs || []).filter(
    log => !(fetchedLogs || []).includes(log)  // 去重
  )]
  const [searchTerm, setSearchTerm] = useState('')
  const [copied, setCopied] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const logContainerRef = useRef<HTMLDivElement>(null)
  
  // 解析日志条目
  const parseLogEntries = (rawLogs: string[]): LogEntry[] => {
    return rawLogs.map(log => {
      // 尝试解析时间戳 [HH:MM:SS]
      const timeMatch = log.match(/^\[(\d{2}:\d{2}:\d{2})\]/)
      const time = timeMatch ? timeMatch[1] : ''
      const message = timeMatch ? log.substring(timeMatch[0].length).trim() : log
      
      // 判断日志级别
      let level: LogEntry['level'] = 'info'
      if (log.includes('✓') || log.includes('成功')) {
        level = 'success'
      } else if (log.includes('✗') || log.includes('失败') || log.includes('错误')) {
        level = 'error'
      } else if (log.includes('⚠') || log.includes('警告')) {
        level = 'warning'
      }
      
      return { time, message, level }
    })
  }
  
  const logEntries = parseLogEntries(logs)
  
  // 过滤日志
  const filteredLogs = searchTerm
    ? logEntries.filter(entry => 
        entry.message.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : logEntries
  
  // 自动滚动到底部
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs, autoScroll])
  
  // 复制日志
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(logs.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('复制失败:', err)
    }
  }
  
  // 下载日志
  const handleDownload = () => {
    const content = logs.join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${problemId}_log.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }
  
  // 获取日志级别样式
  const getLevelStyle = (level?: LogEntry['level']) => {
    switch (level) {
      case 'success':
        return 'text-green-400'
      case 'error':
        return 'text-red-400'
      case 'warning':
        return 'text-amber-400'
      default:
        return 'text-slate-300'
    }
  }
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/95 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="h-full flex flex-col">
        {/* 头部 */}
        <div className="flex items-center justify-between p-4 bg-slate-800 border-b border-slate-700">
          <div>
            <h3 className="text-lg font-bold text-white">任务日志</h3>
            <p className="text-sm text-slate-400">
              题目: {problemId} | 任务ID: {taskId.slice(0, 8)}...
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors text-slate-300 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>
        
        {/* 工具栏 */}
        <div className="flex items-center gap-3 p-3 border-b border-slate-700 bg-slate-800">
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="搜索日志..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm bg-slate-700 border border-slate-600 text-white placeholder-slate-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>
          
          <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-slate-600 bg-slate-700 text-indigo-600 focus:ring-indigo-500"
            />
            自动滚动
          </label>
          
          <Button variant="ghost" onClick={() => { refetch(); onRefresh?.() }}>
            <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
          </Button>
          
          <Button variant="ghost" onClick={handleCopy}>
            {copied ? <Check size={16} className="text-green-500" /> : <Copy size={16} />}
          </Button>
          
          <Button variant="ghost" onClick={handleDownload}>
            <Download size={16} />
          </Button>
        </div>
        
        {/* 日志内容 */}
        <div
          ref={logContainerRef}
          className="flex-1 overflow-y-auto p-4 font-mono text-sm bg-slate-950"
          onScroll={(e) => {
            const target = e.currentTarget
            const isAtBottom = Math.abs(target.scrollHeight - target.scrollTop - target.clientHeight) < 10
            if (!isAtBottom && autoScroll) {
              setAutoScroll(false)
            }
          }}
        >
          {isLoading && logs.length === 0 ? (
            <div className="text-center text-slate-400 py-8">
              <RefreshCw size={24} className="animate-spin mx-auto mb-2" />
              加载日志中...
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="text-center text-slate-400 py-8">
              {searchTerm ? '未找到匹配的日志' : '暂无日志'}
            </div>
          ) : (
            <div className="space-y-1">
              {filteredLogs.map((entry, index) => (
                <div key={index} className="flex gap-2 hover:bg-slate-900/70 rounded px-2 py-1">
                  {entry.time && (
                    <span className="text-slate-600 flex-shrink-0">[{entry.time}]</span>
                  )}
                  <span className={getLevelStyle(entry.level)}>
                    {entry.message}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* 底部统计 */}
        <div className="flex items-center justify-between p-3 border-t border-slate-700 bg-slate-800">
          <span className="text-sm text-slate-400">
            共 {logs.length} 条日志
            {searchTerm && ` | 匹配 ${filteredLogs.length} 条`}
          </span>
          <div className="flex gap-2">
            <Button 
              variant="secondary" 
              onClick={() => {
                setAutoScroll(true)
                if (logContainerRef.current) {
                  logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
                }
              }}
              className="bg-slate-700 hover:bg-slate-600 text-white border-slate-600"
            >
              滚动到底部
            </Button>
            <Button variant="primary" onClick={onClose}>
              关闭
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
