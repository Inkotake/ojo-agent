import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { CheckCircle2, Cpu, Play, DownloadCloud, Inbox, Search, ExternalLink, ArrowUpDown, Clock, FileText, TrendingUp, Hash, Trash2, AlertCircle, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useEffect, useState, useMemo } from 'react'
import apiClient from '../api/client'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Select from '../components/ui/Select'
import OJIcon, { identifyOJ, OJ_PLATFORMS, formatDisplayId } from '../components/OJIcon'
import StageProgress, { StageDetail } from '../components/StageProgress'
import LogDialog from '../components/LogDialog'
import { useWebSocket } from '../hooks/useWebSocket'
import { useDownload } from '../hooks/useDownload'
import { useToast } from '../components/ui/Toast'
import { useConfirm } from '../components/ui/ConfirmDialog'
import { useAuthStore } from '../stores/authStore'

interface TaskItem {
  id: number
  problem_id: string
  status: number
  progress: number
  stage: string
  source_oj?: string
  target_oj?: string
  uploaded_url?: string
  created_at: string
  updated_at?: string
  error_message?: string
}

// 格式化时间
function formatTime(dateStr: string | undefined): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  // 今天
  if (diff < 24 * 60 * 60 * 1000 && date.getDate() === now.getDate()) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  // 昨天
  if (diff < 48 * 60 * 60 * 1000) {
    return '昨天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  // 更早
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function Dashboard() {
  const queryClient = useQueryClient()
  const { messages, connected } = useWebSocket()
  const { downloadWorkspace } = useDownload()
  const toast = useToast()
  const { isAdmin } = useAuthStore()
  
  // 搜索和筛选状态
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [sourceOjFilter, setSourceOjFilter] = useState<string>('')
  const [targetOjFilter, setTargetOjFilter] = useState<string>('')
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')
  
  // 日志对话框状态
  const [showLogDialog, setShowLogDialog] = useState(false)
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null)
  
  // 批次报告弹窗状态
  const [showListDialog, setShowListDialog] = useState<'completed' | 'incomplete' | null>(null)
  
  // Fetch system stats
  const { data: stats } = useQuery({
    queryKey: ['system-stats'],
    queryFn: async () => {
      const response = await apiClient.get('/api/system/stats')
      return response.data
    },
    refetchInterval: 5000,
  })
  
  // Fetch all tasks with filters
  const { data: tasksData, isLoading: tasksLoading } = useQuery({
    queryKey: ['all-tasks', searchQuery, statusFilter, sourceOjFilter, targetOjFilter],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('limit', '200')
      if (searchQuery) params.append('search', searchQuery)
      if (statusFilter) params.append('status_filter', statusFilter)
      if (sourceOjFilter) params.append('source_oj', sourceOjFilter)
      if (targetOjFilter) params.append('target_oj', targetOjFilter)
      
      const response = await apiClient.get(`/api/tasks?${params.toString()}`)
      return response.data.tasks as TaskItem[]
    },
    refetchInterval: 5000,
  })
  
  // 排序任务
  const sortedTasks = useMemo(() => {
    const tasks = tasksData || []
    return [...tasks].sort((a, b) => {
      const dateA = new Date(a.created_at || 0).getTime()
      const dateB = new Date(b.created_at || 0).getTime()
      return sortOrder === 'desc' ? dateB - dateA : dateA - dateB
    })
  }, [tasksData, sortOrder])
  
  // 获取最近一批任务（5分钟内创建的视为同一批）
  const latestBatch = useMemo(() => {
    if (!sortedTasks.length) return { tasks: [], completed: [], incomplete: [], startTime: null, endTime: null }
    
    const latest = sortedTasks[0]
    const latestTime = new Date(latest.created_at || 0).getTime()
    const BATCH_WINDOW = 5 * 60 * 1000 // 5分钟
    
    const batchTasks = sortedTasks.filter(task => {
      const taskTime = new Date(task.created_at || 0).getTime()
      return latestTime - taskTime < BATCH_WINDOW
    })
    
    // 计算批次时间
    const times = batchTasks.map(t => new Date(t.created_at || 0).getTime())
    const startTime = times.length ? new Date(Math.min(...times)) : null
    const endTime = times.length ? new Date(Math.max(...times)) : null
    
    return {
      tasks: batchTasks,
      completed: batchTasks.filter(t => t.status === 4),
      incomplete: batchTasks.filter(t => t.status !== 4),
      startTime,
      endTime
    }
  }, [sortedTasks])
  
  // WebSocket real-time updates
  useEffect(() => {
    if (!connected || messages.length === 0) return
    
    const lastMessage = messages[messages.length - 1]
    
    // Refresh stats and task list when task completes
    if (lastMessage?.type === 'task.completed' || lastMessage?.type === 'task.started' || lastMessage?.type === 'task.progress') {
      queryClient.invalidateQueries({ queryKey: ['system-stats'] })
      queryClient.invalidateQueries({ queryKey: ['all-tasks'] })
    }
  }, [messages, connected, queryClient])
  
  const handleDownload = async (taskId: string) => {
    const success = await downloadWorkspace(taskId)
    if (success) {
      toast.success('下载已开始')
    } else {
      toast.error('下载失败，请重试')
    }
  }
  
  const handleOpenUrl = (url: string) => {
    window.open(url, '_blank')
  }
  
  const handleViewLogs = (task: TaskItem) => {
    setSelectedTask(task)
    setShowLogDialog(true)
  }
  
  const confirm = useConfirm()
  
  const handleDeleteTask = async (taskId: number) => {
    const ok = await confirm({
      title: '删除任务',
      message: '确定要删除这个任务吗？此操作不可撤销。',
      confirmText: '删除',
      variant: 'danger'
    })
    if (!ok) return
    try {
      await apiClient.delete(`/api/tasks/${taskId}`)
      toast.success('任务已删除')
      queryClient.invalidateQueries({ queryKey: ['all-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['system-stats'] })
    } catch {
      toast.error('删除失败')
    }
  }
  
  // 重试任务 mutation
  const retryMutation = useMutation({
    mutationFn: async (taskId: number) => {
      const response = await apiClient.post(`/api/tasks/${taskId}/retry`, { module: 'all' })
      return response.data
    },
    onSuccess: () => {
      toast.success('任务已重新提交')
      queryClient.invalidateQueries({ queryKey: ['all-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['system-stats'] })
    },
    onError: () => {
      toast.error('重试失败')
    }
  })
  
  const handleRetryTask = async (taskId: number) => {
    const ok = await confirm({
      title: '重试任务',
      message: '确定要重新执行这个任务吗？将重置状态并重新执行所有步骤。',
      confirmText: '重试',
      variant: 'info'
    })
    if (!ok) return
    retryMutation.mutate(taskId)
  }
  
  // OJ选项列表
  const ojOptions = Object.entries(OJ_PLATFORMS)
    .filter(([key]) => key !== 'unknown')
    .map(([key, val]) => ({ value: key, label: val.name }))
  
  return (
    <div className="space-y-6">
      {/* Stats Grid & Task Report */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: 2x2 Stats Grid */}
        <div className="lg:col-span-1 grid grid-cols-2 gap-3">
          <Card className="p-3 bg-gradient-to-br from-green-500 to-emerald-600 text-white border-none">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={18} className="text-white/80" />
              <span className="text-xs text-white/80">已完成</span>
            </div>
            <p className="text-2xl font-bold mt-1">{stats?.success || 0}</p>
          </Card>
          
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <Cpu size={18} className="text-blue-500" />
              <span className="text-xs text-slate-500">运行中</span>
            </div>
            <p className="text-2xl font-bold mt-1 text-slate-800">{stats?.running || 0}</p>
          </Card>
          
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <Hash size={18} className="text-slate-400" />
              <span className="text-xs text-slate-500">总任务</span>
            </div>
            <p className="text-2xl font-bold mt-1 text-slate-800">{stats?.total || 0}</p>
          </Card>
          
          <Card className="p-3">
            <div className="flex items-center gap-2">
              <TrendingUp size={18} className="text-amber-500" />
              <span className="text-xs text-slate-500">成功率</span>
            </div>
            <p className="text-2xl font-bold mt-1 text-slate-800">
              {stats?.total > 0 ? ((stats.success / stats.total) * 100).toFixed(0) : 0}%
            </p>
          </Card>
        </div>
        
        {/* Right: Task Report - Combined Card */}
        <Card className="lg:col-span-2 p-4">
          <div className="flex items-stretch gap-4 h-full">
            {/* 左侧：两个小方块 */}
            <div className="flex gap-3 flex-1">
              {/* 已完成块 */}
              <button 
                className="flex-1 p-3 rounded-xl border-2 border-green-100 hover:border-green-300 hover:shadow-md transition-all text-center bg-green-50/50"
                onClick={() => latestBatch.completed.length > 0 && setShowListDialog('completed')}
              >
                <div className="p-2 bg-green-100 rounded-lg w-fit mx-auto mb-2">
                  <CheckCircle2 size={24} className="text-green-600" />
                </div>
                <p className="text-3xl font-bold text-green-600">{latestBatch.completed.length}</p>
                <p className="text-xs text-slate-500 mt-1">已完成</p>
              </button>
              
              {/* 未完成块 */}
              <button 
                className="flex-1 p-3 rounded-xl border-2 border-amber-100 hover:border-amber-300 hover:shadow-md transition-all text-center bg-amber-50/50"
                onClick={() => latestBatch.incomplete.length > 0 && setShowListDialog('incomplete')}
              >
                <div className="p-2 bg-amber-100 rounded-lg w-fit mx-auto mb-2">
                  <AlertCircle size={24} className="text-amber-600" />
                </div>
                <p className="text-3xl font-bold text-amber-600">{latestBatch.incomplete.length}</p>
                <p className="text-xs text-slate-500 mt-1">进行中</p>
              </button>
            </div>
            
            {/* 右侧：批次时间 */}
            <div className="border-l border-slate-200 pl-4 flex flex-col justify-center min-w-[120px]">
              <p className="text-xs text-slate-400 mb-1">本批次时间</p>
              {latestBatch.startTime ? (
                <>
                  <p className="text-sm font-medium text-slate-700">
                    {latestBatch.startTime.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                  </p>
                  <p className="text-xs text-slate-400 mt-2">共 {latestBatch.tasks.length} 个任务</p>
                </>
              ) : (
                <p className="text-sm text-slate-300">暂无任务</p>
              )}
            </div>
          </div>
        </Card>
      </div>
      
      {/* 题目列表弹窗 */}
      {showListDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowListDialog(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-semibold text-slate-800 flex items-center gap-2">
                {showListDialog === 'completed' ? (
                  <>
                    <CheckCircle2 size={18} className="text-green-600" />
                    已完成任务 ({latestBatch.completed.length})
                  </>
                ) : (
                  <>
                    <AlertCircle size={18} className="text-amber-600" />
                    进行中/未完成 ({latestBatch.incomplete.length})
                  </>
                )}
              </h3>
              <button 
                onClick={() => setShowListDialog(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>
            
            <div className="p-4 flex-1 overflow-y-auto">
              <textarea
                readOnly
                className="w-full h-64 p-3 bg-slate-50 rounded-lg text-sm font-mono border border-slate-200 focus:outline-none resize-none"
                value={
                  showListDialog === 'completed'
                    ? latestBatch.completed.map(t => t.uploaded_url || t.problem_id).join('\n')
                    : latestBatch.incomplete.map(t => t.problem_id).join('\n')
                }
              />
            </div>
            
            <div className="p-4 border-t border-slate-100 flex gap-2">
              <Button
                variant="primary"
                className="flex-1"
                onClick={() => {
                  const text = showListDialog === 'completed'
                    ? latestBatch.completed.map(t => t.uploaded_url || t.problem_id).join('\n')
                    : latestBatch.incomplete.map(t => t.problem_id).join('\n')
                  navigator.clipboard.writeText(text)
                  toast.success('已复制到剪贴板')
                }}
              >
                复制全部
              </Button>
              <Button variant="secondary" onClick={() => setShowListDialog(null)}>
                关闭
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Task List with Search & Filter */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-800">所有任务</h2>
          <Link to="/tasks">
            <Button variant="secondary" className="text-xs h-8" icon={Play}>
              新建批处理
            </Button>
          </Link>
        </div>
        
        {/* Search and Filter Bar */}
        <Card className="p-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-slate-500 mb-1">搜索</label>
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="搜索题目ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>
            
            <div className="w-32">
              <label className="block text-xs font-medium text-slate-500 mb-1">状态</label>
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                options={[
                  { value: '', label: '全部' },
                  { value: 'completed', label: '已完成' },
                  { value: 'running', label: '运行中' },
                  { value: 'failed', label: '失败' },
                  { value: 'pending', label: '等待中' },
                ]}
              />
            </div>
            
            <div className="w-32">
              <label className="block text-xs font-medium text-slate-500 mb-1">来源OJ</label>
              <Select
                value={sourceOjFilter}
                onChange={(e) => setSourceOjFilter(e.target.value)}
                options={[{ value: '', label: '全部' }, ...ojOptions]}
              />
            </div>
            
            <div className="w-32">
              <label className="block text-xs font-medium text-slate-500 mb-1">目标OJ</label>
              <Select
                value={targetOjFilter}
                onChange={(e) => setTargetOjFilter(e.target.value)}
                options={[{ value: '', label: '全部' }, ...ojOptions]}
              />
            </div>
            
            <button
              onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
              className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
              title={sortOrder === 'desc' ? '最新优先' : '最早优先'}
            >
              <ArrowUpDown size={18} />
            </button>
          </div>
        </Card>
        
        {/* Tasks Table */}
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr>
                  <th className="px-4 py-3 font-medium text-slate-500 w-20">来源</th>
                  <th className="px-4 py-3 font-medium text-slate-500 w-20">目标</th>
                  <th className="px-4 py-3 font-medium text-slate-500 w-36">题目ID</th>
                  <th className="px-4 py-3 font-medium text-slate-500 w-32">开始时间</th>
                  <th className="px-4 py-3 font-medium text-slate-500">进度</th>
                  <th className="px-4 py-3 font-medium text-slate-500 w-36">当前状态</th>
                  <th className="px-4 py-3 font-medium text-slate-500 text-right w-28">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tasksLoading ? (
                  // 加载骨架屏
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={`skeleton-${i}`}>
                      <td className="px-4 py-3"><div className="h-6 w-6 bg-slate-100 rounded animate-pulse" /></td>
                      <td className="px-4 py-3"><div className="h-6 w-6 bg-slate-100 rounded animate-pulse" /></td>
                      <td className="px-4 py-3"><div className="h-4 w-24 bg-slate-100 rounded animate-pulse" /></td>
                      <td className="px-4 py-3"><div className="h-4 w-20 bg-slate-100 rounded animate-pulse" /></td>
                      <td className="px-4 py-3"><div className="h-6 w-40 bg-slate-100 rounded animate-pulse" /></td>
                      <td className="px-4 py-3"><div className="h-4 w-24 bg-slate-100 rounded animate-pulse" /></td>
                      <td className="px-4 py-3"><div className="h-6 w-20 bg-slate-100 rounded animate-pulse ml-auto" /></td>
                    </tr>
                  ))
                ) : sortedTasks.length === 0 ? (
                  // 空状态
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center">
                      <div className="flex flex-col items-center gap-3 text-slate-400">
                        <Inbox size={40} strokeWidth={1.5} />
                        <p className="text-sm">暂无任务记录</p>
                        <Link to="/tasks">
                          <Button variant="secondary" className="text-xs" icon={Play}>
                            创建第一个任务
                          </Button>
                        </Link>
                      </div>
                    </td>
                  </tr>
                ) : (
                  sortedTasks.map((task) => {
                    const sourceOj = task.source_oj || identifyOJ(task.problem_id)
                    const targetOj = task.target_oj || 'unknown'
                    const hasUploadedUrl = !!task.uploaded_url
                    
                    return (
                      <tr key={task.id} className="hover:bg-slate-50/50 transition-colors">
                        <td className="px-4 py-3">
                          <OJIcon oj={sourceOj} size="sm" />
                        </td>
                        <td className="px-4 py-3">
                          <OJIcon oj={targetOj} size="sm" />
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono font-medium text-slate-700 text-xs" title={task.problem_id}>
                            {formatDisplayId(task.problem_id, sourceOj)}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1 text-slate-500 text-xs">
                            <Clock size={12} />
                            {formatTime(task.created_at)}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <StageProgress stage={task.stage} status={task.status} />
                        </td>
                        <td className="px-4 py-3">
                          <StageDetail 
                            stage={task.stage} 
                            status={task.status} 
                            errorMessage={task.error_message}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            {/* 查看日志按钮 */}
                            <button
                              onClick={() => handleViewLogs(task)}
                              className="p-1.5 rounded-lg transition-colors text-slate-500 hover:text-slate-700 hover:bg-slate-100"
                              title="查看日志"
                            >
                              <FileText size={16} />
                            </button>
                            
                            {/* 下载按钮 - 已完成才能下载 */}
                            <button
                              onClick={() => handleDownload(String(task.id))}
                              disabled={task.status !== 4}
                              className={`p-1.5 rounded-lg transition-colors ${
                                task.status === 4
                                  ? 'text-indigo-600 hover:bg-indigo-50'
                                  : 'text-slate-300 cursor-not-allowed'
                              }`}
                              title={task.status === 4 ? '下载工作区' : '任务未完成'}
                            >
                              <DownloadCloud size={16} />
                            </button>
                            
                            {/* 打开链接按钮 - 有上传URL才能打开 */}
                            <button
                              onClick={() => task.uploaded_url && handleOpenUrl(task.uploaded_url)}
                              disabled={!hasUploadedUrl}
                              className={`p-1.5 rounded-lg transition-colors ${
                                hasUploadedUrl
                                  ? 'text-green-600 hover:bg-green-50'
                                  : 'text-slate-300 cursor-not-allowed'
                              }`}
                              title={hasUploadedUrl ? '打开上传链接' : '暂无上传链接'}
                            >
                              <ExternalLink size={16} />
                            </button>
                            
                            {/* 重试按钮 - 失败任务显示（-1=失败, 3=编译错误），管理员可重试任意非运行中的任务 */}
                            {(task.status === -1 || task.status === 3 || (isAdmin && task.status !== 1)) && (
                              <button
                                onClick={() => handleRetryTask(task.id)}
                                disabled={retryMutation.isPending}
                                className="p-1.5 rounded-lg transition-colors text-blue-500 hover:text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                                title="重试任务"
                              >
                                <RefreshCw size={16} className={retryMutation.isPending ? 'animate-spin' : ''} />
                              </button>
                            )}
                            
                            {/* 删除按钮 */}
                            <button
                              onClick={() => handleDeleteTask(task.id)}
                              className="p-1.5 rounded-lg transition-colors text-slate-400 hover:text-red-600 hover:bg-red-50"
                              title="删除任务"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
          
          {/* 任务数量统计 */}
          {!tasksLoading && sortedTasks.length > 0 && (
            <div className="px-4 py-2 bg-slate-50 border-t border-slate-100 text-xs text-slate-500">
              共 {sortedTasks.length} 条记录
            </div>
          )}
        </Card>
      </div>
      
      {/* 日志对话框 */}
      <LogDialog
        isOpen={showLogDialog}
        onClose={() => setShowLogDialog(false)}
        taskId={String(selectedTask?.id || '')}
        problemId={selectedTask?.problem_id || ''}
      />
    </div>
  )
}
