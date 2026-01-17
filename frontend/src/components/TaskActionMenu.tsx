import { useState, useRef, useEffect } from 'react'
import { MoreVertical, RefreshCw, Download, Eye, Copy, XCircle, ExternalLink } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '../api/client'
import { useToast } from './ui/Toast'

interface TaskActionMenuProps {
  taskId: string
  problemId: string
  status: number
  uploadedUrl?: string  // 上传后的题目链接
  onViewLogs: () => void
  onDownload: () => void
}

type RetryModule = 'fetch' | 'gen' | 'upload' | 'solve' | 'all'

export default function TaskActionMenu({
  taskId,
  problemId,
  status,
  uploadedUrl,
  onViewLogs,
  onDownload
}: TaskActionMenuProps) {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const toast = useToast()
  const queryClient = useQueryClient()
  
  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])
  
  // 重试模块
  const retryMutation = useMutation({
    mutationFn: async (module: RetryModule) => {
      const response = await apiClient.post(`/api/tasks/${taskId}/retry`, { module })
      return response.data
    },
    onSuccess: (_, module) => {
      toast.success(`正在重试 ${module} 模块`)
      queryClient.invalidateQueries({ queryKey: ['user-tasks'] })
      setIsOpen(false)
    },
    onError: (error: Error) => {
      toast.error(`重试失败: ${error.message}`)
    }
  })
  
  // 取消任务
  const cancelMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.delete(`/api/tasks/${taskId}`)
      return response.data
    },
    onSuccess: () => {
      toast.success('任务已取消')
      queryClient.invalidateQueries({ queryKey: ['user-tasks'] })
      setIsOpen(false)
    },
    onError: (error: Error) => {
      toast.error(`取消失败: ${error.message}`)
    }
  })
  
  // 复制题目ID
  const handleCopyId = async () => {
    try {
      await navigator.clipboard.writeText(problemId)
      toast.success('已复制题目ID')
      setIsOpen(false)
    } catch {
      toast.error('复制失败')
    }
  }
  
  const isRunning = status === 1 // 运行中
  
  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
        title="更多操作"
      >
        <MoreVertical size={16} className="text-slate-500" />
      </button>
      
      {isOpen && (
        <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-slate-200 rounded-lg shadow-lg z-50 py-1 animate-in fade-in slide-in-from-top-2 duration-150">
          {/* 查看日志 */}
          <button
            onClick={() => {
              onViewLogs()
              setIsOpen(false)
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            <Eye size={16} className="text-slate-500" />
            查看详细日志
          </button>
          
          {/* 下载数据 */}
          <button
            onClick={() => {
              onDownload()
              setIsOpen(false)
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            <Download size={16} className="text-slate-500" />
            下载工作目录
          </button>
          
          {/* 打开上传链接 */}
          {uploadedUrl && uploadedUrl.trim() && (
            <button
              onClick={() => {
                const url = uploadedUrl.trim()
                if (url.startsWith('http://') || url.startsWith('https://')) {
                  window.open(url, '_blank', 'noopener,noreferrer')
                  setIsOpen(false)
                } else {
                  console.warn('uploadedUrl is invalid:', url)
                  toast.error('链接地址无效')
                }
              }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-green-600 hover:bg-green-50"
              title={uploadedUrl}
            >
              <ExternalLink size={16} />
              打开上传链接
            </button>
          )}
          
          {/* 复制ID */}
          <button
            onClick={handleCopyId}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            <Copy size={16} className="text-slate-500" />
            复制题目ID
          </button>
          
          <div className="border-t border-slate-100 my-1" />
          
          {/* 全部重试（失败时显示，状态码: -1=失败, 3=编译错误） */}
          {(status === -1 || status === 3) && (
            <button
              onClick={() => retryMutation.mutate('all' as RetryModule)}
              disabled={retryMutation.isPending}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 disabled:opacity-50"
            >
              <RefreshCw size={16} />
              重新执行任务
            </button>
          )}
          
          {/* 重试选项 */}
          <div className="px-3 py-1 text-xs text-slate-400 font-medium">重试单个模块</div>
          
          <button
            onClick={() => retryMutation.mutate('fetch')}
            disabled={retryMutation.isPending}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            <RefreshCw size={16} className="text-blue-500" />
            重试拉取
          </button>
          
          <button
            onClick={() => retryMutation.mutate('gen')}
            disabled={retryMutation.isPending}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            <RefreshCw size={16} className="text-purple-500" />
            重试生成
          </button>
          
          <button
            onClick={() => retryMutation.mutate('upload')}
            disabled={retryMutation.isPending}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            <RefreshCw size={16} className="text-green-500" />
            重试上传
          </button>
          
          <button
            onClick={() => retryMutation.mutate('solve')}
            disabled={retryMutation.isPending}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            <RefreshCw size={16} className="text-orange-500" />
            重试求解
          </button>
          
          {/* 取消任务 */}
          {isRunning && (
            <>
              <div className="border-t border-slate-100 my-1" />
              <button
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                <XCircle size={16} />
                取消任务
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
