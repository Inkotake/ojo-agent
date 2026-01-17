import { useState, useEffect } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { Activity, Globe, Users, List, LucideIcon, Inbox, FileText, DownloadCloud, ExternalLink, Trash2, Shield, UserPlus, Ticket, Copy, Check, Plus, Key, X, RefreshCw } from 'lucide-react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Select from '../components/ui/Select'
import ProgressBar from '../components/ui/ProgressBar'
import { useWebSocket } from '../hooks/useWebSocket'
import { useDownload } from '../hooks/useDownload'
import { useToast } from '../components/ui/Toast'
import { useConfirm } from '../components/ui/ConfirmDialog'
import apiClient from '../api/client'
import OJIcon, { identifyOJ } from '../components/OJIcon'
import StageProgress, { StageDetail } from '../components/StageProgress'
import LogDialog from '../components/LogDialog'

// Types
interface TabButtonProps {
  id: string
  label: string
  icon: LucideIcon
}

interface AdminTask {
  id?: string | number
  task_id: string
  problem_id: string
  task?: string
  status: number
  progress: number
  stage: string
  user_id?: number
  username?: string
  user?: string
  oj_platform?: string
  source_oj?: string
  uploaded_url?: string
  error_message?: string
  created_at?: string
  updated_at?: string
  completed_at?: string
  oj?: string
}

interface AdminUser {
  id: number
  username: string
  name?: string
  role: string
  status: string
  last_login?: string
  lastActive?: string
  task_count?: number
}

interface GlobalTasksData {
  tasks: AdminTask[]
}

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('monitor')
  const { connected, messages } = useWebSocket()
  const queryClient = useQueryClient()
  const { downloadWorkspace } = useDownload()
  const toast = useToast()
  
  // Log dialog state
  const [showLogDialog, setShowLogDialog] = useState(false)
  const [selectedTask, setSelectedTask] = useState<AdminTask | null>(null)
  
  // User creation dialog state
  const [showCreateUser, setShowCreateUser] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState('user')
  
  // Invite code state
  const [inviteNote, setInviteNote] = useState('')
  const [copiedCode, setCopiedCode] = useState<string | null>(null)
  
  // Reset password state
  const [resetPasswordUserId, setResetPasswordUserId] = useState<number | null>(null)
  const [resetPasswordValue, setResetPasswordValue] = useState('')

  // Fetch global tasks
  const { data: globalTasksData, isLoading: tasksLoading } = useQuery({
    queryKey: ['admin', 'global-tasks'],
    queryFn: async () => {
      const response = await apiClient.get('/api/admin/tasks/global')
      return response.data
    },
    refetchInterval: 2000,
    enabled: activeTab === 'monitor'
  })

  // Fetch users list
  const { data: usersData, isLoading: usersLoading } = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: async () => {
      const response = await apiClient.get('/api/admin/users')
      return response.data
    },
    enabled: activeTab === 'users'
  })

  // Fetch system stats (including activity logs)
  const { data: statsData } = useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: async () => {
      const response = await apiClient.get('/api/admin/system/stats')
      return response.data
    },
    refetchInterval: 5000,
    enabled: activeTab === 'overview' || activeTab === 'activity'
  })

  // WebSocket real-time updates - listen for messages
  useEffect(() => {
    if (!connected || messages.length === 0) return

    // Get last message
    const lastMessage = messages[messages.length - 1]
    
    // Handle task progress update
    if (lastMessage.type === 'task.progress' || lastMessage.type === 'task:progress') {
      queryClient.setQueryData<GlobalTasksData>(['admin', 'global-tasks'], (old) => {
        if (!old) return old
        return {
          ...old,
          tasks: old.tasks.map((t) => 
            t.task_id === lastMessage.task_id || t.task_id === lastMessage.taskId
              ? { ...t, progress: lastMessage.progress || lastMessage.data?.progress, stage: lastMessage.stage || lastMessage.data?.stage }
              : t
          )
        }
      })
    }
  }, [messages, connected, queryClient])

  const globalTasks: AdminTask[] = globalTasksData?.tasks || []
  const users: AdminUser[] = usersData?.users || []
  const stats = statsData || { tasks: { total: 0, success: 0, running: 0, failed: 0, pending: 0 }, users: { total: 0, active: 0, inactive: 0 }, recent_activities: [] }

  // Delete task mutation
  const deleteTaskMutation = useMutation({
    mutationFn: async (taskId: string) => {
      await apiClient.delete(`/api/admin/tasks/${taskId}`)
    },
    onSuccess: () => {
      toast.success('任务已删除')
      queryClient.invalidateQueries({ queryKey: ['admin', 'global-tasks'] })
    },
    onError: () => toast.error('删除任务失败')
  })

  // Retry task mutation (admin can retry any task)
  const retryTaskMutation = useMutation({
    mutationFn: async (taskId: string) => {
      const response = await apiClient.post(`/api/tasks/${taskId}/retry`, { module: 'all' })
      return response.data
    },
    onSuccess: () => {
      toast.success('任务已重新提交')
      queryClient.invalidateQueries({ queryKey: ['admin', 'global-tasks'] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '重试失败')
    }
  })

  // Create user mutation
  const createUserMutation = useMutation({
    mutationFn: async (data: { username: string; password: string; role: string }) => {
      await apiClient.post('/api/admin/users', data)
    },
    onSuccess: () => {
      toast.success('用户已创建')
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      setShowCreateUser(false)
      setNewUsername('')
      setNewPassword('')
      setNewRole('user')
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || '创建用户失败')
  })

  // Delete user mutation
  const deleteUserMutation = useMutation({
    mutationFn: async (userId: number) => {
      await apiClient.delete(`/api/admin/users/${userId}`)
    },
    onSuccess: () => {
      toast.success('用户已删除')
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || '删除用户失败')
  })

  // Update user role mutation
  const updateRoleMutation = useMutation({
    mutationFn: async ({ userId, role }: { userId: number; role: string }) => {
      await apiClient.put(`/api/admin/users/${userId}/role`, { role })
    },
    onSuccess: () => {
      toast.success('用户角色已更新')
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    onError: () => toast.error('更新角色失败')
  })

  // Fetch invite codes
  const { data: inviteCodesData, isLoading: inviteCodesLoading } = useQuery({
    queryKey: ['invite-codes'],
    queryFn: async () => {
      const response = await apiClient.get('/api/invite-codes')
      return response.data
    },
    enabled: activeTab === 'invites'
  })

  const inviteCodes = inviteCodesData || []

  // Create invite code mutation
  const createInviteCodeMutation = useMutation({
    mutationFn: async (data: { note?: string; expires_days?: number }) => {
      const response = await apiClient.post('/api/invite-codes', data)
      return response.data
    },
    onSuccess: (data) => {
      toast.success(`邀请码已生成: ${data.code}`)
      queryClient.invalidateQueries({ queryKey: ['invite-codes'] })
      setInviteNote('')
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || '生成邀请码失败')
  })

  // Delete invite code mutation
  const deleteInviteCodeMutation = useMutation({
    mutationFn: async (codeId: number) => {
      await apiClient.delete(`/api/invite-codes/${codeId}`)
    },
    onSuccess: () => {
      toast.success('邀请码已删除')
      queryClient.invalidateQueries({ queryKey: ['invite-codes'] })
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || '删除邀请码失败')
  })

  // Reset password mutation
  const resetPasswordMutation = useMutation({
    mutationFn: async ({ userId, newPassword }: { userId: number; newPassword: string }) => {
      await apiClient.post(`/api/admin/users/${userId}/reset-password`, { new_password: newPassword })
    },
    onSuccess: () => {
      toast.success('密码已重置')
      setResetPasswordUserId(null)
      setResetPasswordValue('')
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || '重置密码失败')
  })

  // Handle reset password
  const handleResetPassword = (userId: number) => {
    if (!resetPasswordValue || resetPasswordValue.length < 6) {
      toast.error('密码长度至少6个字符')
      return
    }
    resetPasswordMutation.mutate({ userId, newPassword: resetPasswordValue })
  }

  // Copy to clipboard
  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code)
    setCopiedCode(code)
    setTimeout(() => setCopiedCode(null), 2000)
  }

  // Handlers
  const handleViewLogs = (task: AdminTask) => {
    setSelectedTask(task)
    setShowLogDialog(true)
  }

  const handleDownload = async (taskId: string) => {
    const success = await downloadWorkspace(taskId)
    if (success) toast.success('下载已开始')
    else toast.error('下载失败')
  }

  const handleOpenUrl = (url: string) => {
    window.open(url, '_blank')
  }

  const confirm = useConfirm()

  const handleDeleteTask = async (taskId: string) => {
    const ok = await confirm({
      title: '删除任务',
      message: '确定要删除这个任务吗？',
      confirmText: '删除',
      variant: 'danger'
    })
    if (ok) deleteTaskMutation.mutate(taskId)
  }

  const handleRetryTask = async (taskId: string) => {
    const ok = await confirm({
      title: '重试任务',
      message: '确定要重新执行这个任务吗？将重置状态并重新执行所有步骤。',
      confirmText: '重试',
      variant: 'info'
    })
    if (ok) retryTaskMutation.mutate(taskId)
  }

  const handleCreateUser = () => {
    if (!newUsername || !newPassword) {
      toast.error('请填写用户名和密码')
      return
    }
    createUserMutation.mutate({ username: newUsername, password: newPassword, role: newRole })
  }

  const handleDeleteUser = async (userId: number, username: string) => {
    const ok = await confirm({
      title: '删除用户',
      message: `确定要删除用户 "${username}" 吗？其所有任务也将被删除。`,
      confirmText: '删除',
      variant: 'danger'
    })
    if (ok) deleteUserMutation.mutate(userId)
  }

  const handleToggleRole = (userId: number, currentRole: string) => {
    const newRole = currentRole === 'admin' ? 'user' : 'admin'
    updateRoleMutation.mutate({ userId, role: newRole })
  }

  const TabButton = ({ id, label, icon: Icon }: TabButtonProps) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
        activeTab === id
          ? 'bg-indigo-600 text-white shadow-sm'
          : 'text-slate-600 hover:bg-slate-100'
      }`}
    >
      <Icon size={16} />
      {label}
    </button>
  )

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col md:flex-row justify-between items-end gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">系统管理</h2>
          <p className="text-slate-500">系统健康状态与全局监控</p>
        </div>
        <div className="flex bg-white p-1 rounded-xl border border-slate-200 shadow-sm overflow-x-auto">
          <TabButton id="monitor" label="全局任务" icon={Globe} />
          <TabButton id="overview" label="系统健康" icon={Activity} />
          <TabButton id="users" label="用户管理" icon={Users} />
          <TabButton id="invites" label="邀请码" icon={Ticket} />
          <TabButton id="activity" label="活动日志" icon={List} />
        </div>
      </div>

      {/* Tab: Global Tasks Monitor */}
      {activeTab === 'monitor' && (
        <div className="animate-in fade-in duration-300 space-y-4">
          <div className="flex justify-between items-center bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center gap-2">
              <Globe className="text-indigo-600" />
              <h3 className="font-bold text-slate-800">实时全局任务监控</h3>
              <span className="text-sm text-slate-500">({globalTasks.length} 条记录)</span>
            </div>
            <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full animate-pulse">
              实时更新中
            </span>
          </div>
          
          <Card className="overflow-hidden flex flex-col h-[600px]">
            <div className="overflow-auto flex-1">
              <table className="w-full text-left text-sm border-separate border-spacing-0">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-4 py-3 font-medium text-slate-500 w-16">来源</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-4 py-3 font-medium text-slate-500 w-16">目标</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-4 py-3 font-medium text-slate-500">题目</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-4 py-3 font-medium text-slate-500 w-24">用户</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-4 py-3 font-medium text-slate-500 w-40">进度</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-4 py-3 font-medium text-slate-500 w-32">状态</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-4 py-3 font-medium text-slate-500 text-right w-32">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {tasksLoading ? (
                    Array.from({ length: 5 }).map((_, i) => (
                      <tr key={`skeleton-${i}`}>
                        <td className="px-4 py-3"><div className="h-6 w-6 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-4 py-3"><div className="h-6 w-6 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-4 py-3"><div className="h-4 w-24 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-4 py-3"><div className="h-4 w-16 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-4 py-3"><div className="h-6 w-32 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-4 py-3"><div className="h-4 w-20 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-4 py-3"><div className="h-6 w-24 bg-slate-100 rounded animate-pulse ml-auto" /></td>
                      </tr>
                    ))
                  ) : globalTasks.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-12 text-center">
                        <div className="flex flex-col items-center gap-3 text-slate-400">
                          <Inbox size={40} strokeWidth={1.5} />
                          <p className="text-sm">暂无任务记录</p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    globalTasks.map((task) => {
                      const sourceOj = task.source_oj ? identifyOJ(task.source_oj) : identifyOJ(task.problem_id)
                      const targetOj = task.oj_platform ? identifyOJ(task.oj_platform) : 'unknown'
                      const hasUploadedUrl = !!task.uploaded_url
                      
                      return (
                        <tr key={task.id || task.task_id} className="hover:bg-slate-50/50">
                          <td className="px-4 py-3">
                            <OJIcon oj={sourceOj} size="sm" />
                          </td>
                          <td className="px-4 py-3">
                            <OJIcon oj={targetOj} size="sm" />
                          </td>
                          <td className="px-4 py-3">
                            <div className="font-medium text-slate-800">{task.problem_id}</div>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-sm text-indigo-600 font-medium">{task.username || task.user}</span>
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
                              <button
                                onClick={() => handleViewLogs(task)}
                                className="p-1.5 rounded-lg transition-colors text-slate-500 hover:text-slate-700 hover:bg-slate-100"
                                title="查看日志"
                              >
                                <FileText size={16} />
                              </button>
                              <button
                                onClick={() => (task.id || task.task_id) && handleDownload(String(task.id || task.task_id))}
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
                              {/* 重试按钮 - 非运行中的任务都可重试 */}
                              {task.status !== 1 && (
                                <button
                                  onClick={() => (task.id || task.task_id) && handleRetryTask(String(task.id || task.task_id))}
                                  disabled={retryTaskMutation.isPending}
                                  className="p-1.5 rounded-lg transition-colors text-blue-500 hover:text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                                  title="重试任务"
                                >
                                  <RefreshCw size={16} className={retryTaskMutation.isPending ? 'animate-spin' : ''} />
                                </button>
                              )}
                              <button
                                onClick={() => (task.id || task.task_id) && handleDeleteTask(String(task.id || task.task_id))}
                                className="p-1.5 rounded-lg transition-colors text-red-500 hover:bg-red-50"
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
          </Card>
        </div>
      )}

      {/* Tab: System Health */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 animate-in fade-in duration-300">
          {/* Task Statistics */}
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-green-100 rounded-lg">
                <Activity size={20} className="text-green-600" />
              </div>
              <h3 className="font-bold text-slate-800">已完成任务</h3>
            </div>
            <p className="text-3xl font-bold text-green-600">{stats.tasks?.success || 0}</p>
            <p className="text-sm text-slate-500 mt-1">完成总数</p>
          </Card>
          
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Activity size={20} className="text-blue-600" />
              </div>
              <h3 className="font-bold text-slate-800">运行中任务</h3>
            </div>
            <p className="text-3xl font-bold text-blue-600">{stats.tasks?.running || 0}</p>
            <p className="text-sm text-slate-500 mt-1">正在处理中</p>
          </Card>
          
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-100 rounded-lg">
                <Activity size={20} className="text-red-600" />
              </div>
              <h3 className="font-bold text-slate-800">失败任务</h3>
            </div>
            <p className="text-3xl font-bold text-red-600">{stats.tasks?.failed || 0}</p>
            <p className="text-sm text-slate-500 mt-1">发生错误</p>
          </Card>
          
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-slate-100 rounded-lg">
                <Users size={20} className="text-slate-600" />
              </div>
              <h3 className="font-bold text-slate-800">活跃用户</h3>
            </div>
            <p className="text-3xl font-bold text-slate-700">{stats.users?.active || 0}</p>
            <p className="text-sm text-slate-500 mt-1">共 {stats.users?.total || 0} 个用户</p>
          </Card>
          
          {/* Overview Summary */}
          <Card className="p-6 col-span-1 md:col-span-2 lg:col-span-4">
            <h3 className="font-bold text-slate-800 mb-4">任务概览</h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600">成功率</span>
                  <span className="font-bold text-slate-800">
                    {stats.tasks?.total > 0 ? ((stats.tasks.success / stats.tasks.total) * 100).toFixed(1) : 0}%
                  </span>
                </div>
                <ProgressBar 
                  value={stats.tasks?.total > 0 ? (stats.tasks.success / stats.tasks.total) * 100 : 0} 
                  max={100} 
                  color="bg-green-500" 
                />
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600">等待中任务</span>
                  <span className="font-bold text-slate-800">{stats.tasks?.pending || 0}</span>
                </div>
                <ProgressBar 
                  value={stats.tasks?.pending || 0} 
                  max={Math.max(stats.tasks?.total || 1, stats.tasks?.pending || 1)} 
                  color="bg-slate-400" 
                />
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Tab: Users */}
      {activeTab === 'users' && (
        <div className="animate-in fade-in duration-300 space-y-4">
          {/* Create User Form */}
          <Card className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <Users size={18} className="text-indigo-600" />
                用户管理
                <span className="text-sm font-normal text-slate-500">({users.length} 个用户)</span>
              </h3>
              <Button onClick={() => setShowCreateUser(!showCreateUser)} icon={showCreateUser ? undefined : UserPlus}>
                {showCreateUser ? '取消' : '添加用户'}
              </Button>
            </div>
            
            {showCreateUser && (
              <div className="flex gap-3 items-end border-t pt-4">
                <div className="flex-1">
                  <Input
                    label="用户名"
                    value={newUsername}
                    onChange={(e) => setNewUsername(e.target.value)}
                    placeholder="输入用户名"
                  />
                </div>
                <div className="flex-1">
                  <Input
                    label="密码"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="输入密码"
                  />
                </div>
                <div className="w-32">
                  <label className="text-sm font-medium text-slate-700 mb-1 block">角色</label>
                  <Select value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                    <option value="user">普通用户</option>
                    <option value="admin">管理员</option>
                  </Select>
                </div>
                <Button onClick={handleCreateUser} disabled={createUserMutation.isPending}>
                  {createUserMutation.isPending ? '创建中...' : '创建'}
                </Button>
              </div>
            )}
          </Card>
          
          <Card className="overflow-hidden flex flex-col h-[500px]">
            <div className="overflow-auto flex-1">
              <table className="w-full text-left text-sm border-separate border-spacing-0">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500">ID</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500">用户名</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500">角色</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500">状态</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500">最后活跃</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {usersLoading ? (
                    Array.from({ length: 3 }).map((_, i) => (
                      <tr key={`skeleton-${i}`}>
                        <td className="px-6 py-4"><div className="h-4 w-10 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-6 py-4"><div className="h-4 w-24 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-6 py-4"><div className="h-4 w-16 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-6 py-4"><div className="h-4 w-12 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-6 py-4"><div className="h-4 w-20 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-6 py-4"><div className="h-4 w-16 bg-slate-100 rounded animate-pulse ml-auto" /></td>
                      </tr>
                    ))
                  ) : users.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center">
                        <div className="flex flex-col items-center gap-3 text-slate-400">
                          <Users size={40} strokeWidth={1.5} />
                          <p className="text-sm">暂无用户</p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    users.map((user) => (
                      <tr key={user.id} className="hover:bg-slate-50/50">
                        <td className="px-6 py-4 font-mono text-slate-400">#{user.id}</td>
                        <td className="px-6 py-4 font-bold text-slate-700">{user.username || user.name}</td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            user.role === 'admin' 
                              ? 'bg-indigo-100 text-indigo-700' 
                              : 'bg-slate-100 text-slate-600'
                          }`}>
                            {user.role === 'admin' ? '管理员' : '普通用户'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`text-sm ${user.status === 'active' ? 'text-green-600' : 'text-slate-400'}`}>
                            {user.status === 'active' ? '活跃' : '未激活'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-slate-500 text-sm">
                          {user.last_login || user.lastActive || '从未登录'}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center justify-end gap-1">
                            {resetPasswordUserId === user.id ? (
                              <div className="flex items-center gap-1">
                                <input
                                  type="password"
                                  value={resetPasswordValue}
                                  onChange={(e) => setResetPasswordValue(e.target.value)}
                                  placeholder="新密码"
                                  className="w-24 px-2 py-1 text-xs border rounded"
                                />
                                <button
                                  onClick={() => handleResetPassword(user.id)}
                                  disabled={resetPasswordMutation.isPending}
                                  className="p-1.5 rounded-lg transition-colors text-green-600 hover:bg-green-50"
                                  title="确认"
                                >
                                  <Check size={16} />
                                </button>
                                <button
                                  onClick={() => { setResetPasswordUserId(null); setResetPasswordValue('') }}
                                  className="p-1.5 rounded-lg transition-colors text-slate-500 hover:bg-slate-100"
                                  title="取消"
                                >
                                  <X size={16} />
                                </button>
                              </div>
                            ) : (
                              <>
                                <button
                                  onClick={() => setResetPasswordUserId(user.id)}
                                  className="p-1.5 rounded-lg transition-colors text-slate-500 hover:text-amber-600 hover:bg-amber-50"
                                  title="重置密码"
                                >
                                  <Key size={16} />
                                </button>
                                <button
                                  onClick={() => handleToggleRole(user.id, user.role)}
                                  className="p-1.5 rounded-lg transition-colors text-slate-500 hover:text-indigo-600 hover:bg-indigo-50"
                                  title={user.role === 'admin' ? '降为普通用户' : '升为管理员'}
                                >
                                  <Shield size={16} />
                                </button>
                                <button
                                  onClick={() => handleDeleteUser(user.id, user.username)}
                                  className="p-1.5 rounded-lg transition-colors text-red-500 hover:bg-red-50"
                                  title="删除用户"
                                >
                                  <Trash2 size={16} />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* Tab: Invite Codes */}
      {activeTab === 'invites' && (
        <div className="animate-in fade-in duration-300 space-y-4">
          {/* Create Invite Code */}
          <Card className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <Ticket size={18} className="text-indigo-600" />
                邀请码管理
                <span className="text-sm font-normal text-slate-500">
                  ({inviteCodes.filter((c: any) => c.status === 'available').length} 可用 / {inviteCodes.length} 总计)
                </span>
              </h3>
              <div className="flex gap-2 items-end">
                <Input
                  placeholder="备注（可选）"
                  value={inviteNote}
                  onChange={(e) => setInviteNote(e.target.value)}
                  className="w-40"
                />
                <Button 
                  onClick={() => createInviteCodeMutation.mutate({ note: inviteNote || undefined })}
                  disabled={createInviteCodeMutation.isPending}
                  icon={Plus}
                >
                  {createInviteCodeMutation.isPending ? '生成中...' : '生成邀请码'}
                </Button>
              </div>
            </div>
          </Card>

          {/* Invite Codes List */}
          <Card className="overflow-hidden flex flex-col h-[500px]">
            <div className="overflow-auto flex-1">
              <table className="w-full text-left text-sm border-separate border-spacing-0">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500">邀请码</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500">状态</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500">备注</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500">使用者</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500">创建时间</th>
                    <th className="sticky top-0 z-10 bg-slate-50 border-b border-slate-100 px-6 py-3 font-medium text-slate-500 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {inviteCodesLoading ? (
                    Array.from({ length: 3 }).map((_, i) => (
                      <tr key={`skeleton-${i}`}>
                        <td className="px-6 py-4"><div className="h-4 w-24 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-6 py-4"><div className="h-4 w-16 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-6 py-4"><div className="h-4 w-20 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-6 py-4"><div className="h-4 w-20 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-6 py-4"><div className="h-4 w-28 bg-slate-100 rounded animate-pulse" /></td>
                        <td className="px-6 py-4"><div className="h-4 w-16 bg-slate-100 rounded animate-pulse ml-auto" /></td>
                      </tr>
                    ))
                  ) : inviteCodes.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                        <Ticket size={32} className="mx-auto mb-2 opacity-50" />
                        <p>暂无邀请码</p>
                      </td>
                    </tr>
                  ) : (
                    inviteCodes.map((code: any) => (
                      <tr key={code.id} className="hover:bg-slate-50/50">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <code className="font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-1 rounded">
                              {code.code}
                            </code>
                            <button
                              onClick={() => handleCopyCode(code.code)}
                              className="p-1 hover:bg-slate-100 rounded transition-colors"
                              title="复制"
                            >
                              {copiedCode === code.code ? (
                                <Check size={14} className="text-green-500" />
                              ) : (
                                <Copy size={14} className="text-slate-400" />
                              )}
                            </button>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            code.status === 'available' ? 'bg-green-100 text-green-700' :
                            code.status === 'used' ? 'bg-slate-100 text-slate-600' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {code.status === 'available' ? '可用' :
                             code.status === 'used' ? '已使用' : '已过期'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-slate-600">{code.note || '-'}</td>
                        <td className="px-6 py-4 text-slate-600">{code.used_by_name || '-'}</td>
                        <td className="px-6 py-4 text-slate-500 text-xs">
                          {code.created_at ? new Date(code.created_at).toLocaleString() : '-'}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button
                            onClick={() => deleteInviteCodeMutation.mutate(code.id)}
                            disabled={deleteInviteCodeMutation.isPending}
                            className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                            title="删除邀请码"
                          >
                            <Trash2 size={16} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* Tab: Activity */}
      {activeTab === 'activity' && (
        <div className="animate-in fade-in duration-300">
          <Card className="divide-y divide-slate-100 flex flex-col h-[600px]">
            <div className="overflow-auto flex-1 p-0">
              {(stats.recent_activities || []).length > 0 ? (
                stats.recent_activities.map((act: any) => (
                  <div key={act.id} className="p-4 flex gap-4 hover:bg-slate-50/50 border-b border-slate-100 last:border-0">
                    <div className={`mt-1 w-2 h-2 rounded-full shrink-0 ${
                      act.action === 'login' ? 'bg-green-500' :
                      act.action === 'logout' ? 'bg-gray-500' :
                      act.action === 'create_task' ? 'bg-blue-500' :
                      act.action === 'cancel_task' ? 'bg-orange-500' :
                      'bg-indigo-500'
                    }`} />
                    <div className="flex-1">
                      <div className="flex justify-between">
                        <p className="text-sm font-medium text-slate-800">
                          <span className="font-bold">{act.username || 'System'}</span>
                          {' '}
                          {act.action === 'login' ? '已登录' :
                           act.action === 'logout' ? '已登出' :
                           act.action === 'create_task' ? '创建了任务' :
                           act.action === 'cancel_task' ? '取消了任务' :
                           act.action}
                        </p>
                        <span className="text-xs text-slate-400">
                          {act.created_at ? new Date(act.created_at).toLocaleString() : 'Unknown'}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">{act.target || '-'}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-slate-400">
                  <List size={32} className="mx-auto mb-2 opacity-50" />
                  <p>暂无最近活动</p>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
      
      {/* Log Dialog */}
      <LogDialog
        isOpen={showLogDialog}
        onClose={() => setShowLogDialog(false)}
        taskId={String(selectedTask?.id || selectedTask?.task_id || '')}
        problemId={selectedTask?.problem_id || ''}
      />
    </div>
  )
}

