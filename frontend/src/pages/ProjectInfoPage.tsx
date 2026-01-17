import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  FileText, Bug, Lightbulb, MessageSquare, HelpCircle, 
  Send, Plus, Edit2, Trash2, Save
} from 'lucide-react'
import { useNotificationStore } from '../stores/notificationStore'
import { useAuthStore } from '../stores/authStore'
import { useToast } from '../components/ui/Toast'
import { useConfirm } from '../components/ui/ConfirmDialog'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Textarea from '../components/ui/Textarea'
import Select from '../components/ui/Select'
import apiClient from '../api/client'

type TabType = 'changelog' | 'feedback'

interface Changelog {
  id: number
  version: string
  title: string
  content: string
  type: string
  is_published: boolean
  publish_date: string | null
  created_at: string
  author_name: string
}

interface Feedback {
  id: number
  user_id: number
  type: string
  title: string
  content: string
  status: string
  priority: number
  admin_reply: string | null
  admin_id: number | null
  author_name: string
  admin_name: string | null
  created_at: string
  updated_at: string
}

const CHANGELOG_TYPES = [
  { value: 'feature', label: '✨ 新功能', color: 'bg-green-100 text-green-800' },
  { value: 'bugfix', label: '🐛 修复', color: 'bg-red-100 text-red-800' },
  { value: 'improvement', label: '⚡ 优化', color: 'bg-blue-100 text-blue-800' },
  { value: 'breaking', label: '💥 重大更新', color: 'bg-orange-100 text-orange-800' },
]

const FEEDBACK_TYPES = [
  { value: 'feature', label: '功能建议', icon: Lightbulb },
  { value: 'bug', label: 'Bug 报告', icon: Bug },
  { value: 'question', label: '问题咨询', icon: HelpCircle },
  { value: 'other', label: '其他', icon: MessageSquare },
]

const FEEDBACK_STATUSES = [
  { value: 'pending', label: '待处理', color: 'bg-slate-100 text-slate-600' },
  { value: 'reviewing', label: '审核中', color: 'bg-yellow-100 text-yellow-700' },
  { value: 'planned', label: '已规划', color: 'bg-blue-100 text-blue-700' },
  { value: 'completed', label: '已完成', color: 'bg-green-100 text-green-700' },
  { value: 'rejected', label: '已拒绝', color: 'bg-red-100 text-red-700' },
]

export default function ProjectInfoPage() {
  const [activeTab, setActiveTab] = useState<TabType>('changelog')
  const { isAdmin } = useAuthStore()
  const { markAsRead, latestChangelogId } = useNotificationStore()

  // 页面加载时标记为已读
  useEffect(() => {
    if (latestChangelogId) {
      markAsRead(latestChangelogId)
    }
  }, [latestChangelogId, markAsRead])

  return (
    <div className="space-y-6">
      {/* 页头 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">项目信息</h1>
          <p className="text-sm text-slate-500 mt-1">查看更新日志，提交功能建议或报告问题</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={activeTab === 'changelog' ? 'primary' : 'secondary'}
            onClick={() => setActiveTab('changelog')}
            icon={FileText}
          >
            更新日志
          </Button>
          <Button
            variant={activeTab === 'feedback' ? 'primary' : 'secondary'}
            onClick={() => setActiveTab('feedback')}
            icon={MessageSquare}
          >
            反馈建议
          </Button>
        </div>
      </div>

      {/* 内容区 */}
      {activeTab === 'changelog' && <ChangelogSection isAdmin={isAdmin} />}
      {activeTab === 'feedback' && <FeedbackSection isAdmin={isAdmin} />}
    </div>
  )
}

// ==================== 更新日志组件 ====================

function ChangelogSection({ isAdmin }: { isAdmin: boolean }) {
  const [showEditor, setShowEditor] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState({
    version: '',
    title: '',
    content: '',
    type: 'feature',
    is_published: false
  })
  const queryClient = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()

  // 获取更新日志
  const { data, isLoading } = useQuery({
    queryKey: ['changelogs', isAdmin],
    queryFn: async () => {
      const res = await apiClient.get('/api/project/changelogs', {
        params: { include_drafts: isAdmin, limit: 50 }
      })
      return res.data
    }
  })

  // 创建/更新日志
  const saveMutation = useMutation({
    mutationFn: async (data: typeof form) => {
      if (editingId) {
        return apiClient.put(`/api/project/changelogs/${editingId}`, data)
      }
      return apiClient.post('/api/project/changelogs', data)
    },
    onSuccess: () => {
      toast.success(editingId ? '更新成功' : '创建成功')
      queryClient.invalidateQueries({ queryKey: ['changelogs'] })
      resetForm()
    },
    onError: () => toast.error('操作失败')
  })

  // 发布日志
  const publishMutation = useMutation({
    mutationFn: (id: number) => apiClient.post(`/api/project/changelogs/${id}/publish`),
    onSuccess: () => {
      toast.success('已发布')
      queryClient.invalidateQueries({ queryKey: ['changelogs'] })
    },
    onError: () => toast.error('发布失败')
  })

  // 删除日志
  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/api/project/changelogs/${id}`),
    onSuccess: () => {
      toast.success('已删除')
      queryClient.invalidateQueries({ queryKey: ['changelogs'] })
    },
    onError: () => toast.error('删除失败')
  })

  const resetForm = () => {
    setForm({ version: '', title: '', content: '', type: 'feature', is_published: false })
    setEditingId(null)
    setShowEditor(false)
  }

  const handleEdit = (changelog: Changelog) => {
    setForm({
      version: changelog.version,
      title: changelog.title,
      content: changelog.content,
      type: changelog.type,
      is_published: changelog.is_published
    })
    setEditingId(changelog.id)
    setShowEditor(true)
  }

  const handleDelete = async (id: number) => {
    const ok = await confirm({
      title: '删除更新日志',
      message: '确定要删除这条更新日志吗？此操作不可撤销。',
      confirmText: '删除',
      variant: 'danger'
    })
    if (ok) deleteMutation.mutate(id)
  }

  const changelogs: Changelog[] = data?.changelogs || []

  return (
    <div className="space-y-4">
      {/* 管理员：创建按钮 */}
      {isAdmin && !showEditor && (
        <Button onClick={() => setShowEditor(true)} icon={Plus}>
          新建更新日志
        </Button>
      )}

      {/* 管理员：编辑器 */}
      {isAdmin && showEditor && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-slate-800 mb-4">
            {editingId ? '编辑更新日志' : '新建更新日志'}
          </h3>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="版本号"
                placeholder="如: v9.1.0"
                value={form.version}
                onChange={(e) => setForm({ ...form, version: e.target.value })}
              />
              <Select
                label="类型"
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
                options={CHANGELOG_TYPES.map(t => ({ value: t.value, label: t.label }))}
              />
            </div>
            <Input
              label="标题"
              placeholder="更新标题"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <Textarea
              label="内容"
              placeholder="更新内容（支持 Markdown）"
              rows={6}
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
            />
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={form.is_published}
                  onChange={(e) => setForm({ ...form, is_published: e.target.checked })}
                  className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                立即发布
              </label>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => saveMutation.mutate(form)}
                disabled={!form.version || !form.title || !form.content || saveMutation.isPending}
                icon={Save}
              >
                {saveMutation.isPending ? '保存中...' : (editingId ? '更新' : '保存')}
              </Button>
              <Button variant="secondary" onClick={resetForm}>
                取消
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 更新日志列表 */}
      {isLoading ? (
        <div className="text-center py-12 text-slate-500">加载中...</div>
      ) : changelogs.length === 0 ? (
        <Card className="p-12 text-center">
          <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-500">暂无更新日志</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {changelogs.map((log) => {
            const typeInfo = CHANGELOG_TYPES.find(t => t.value === log.type) || CHANGELOG_TYPES[0]
            return (
              <Card key={log.id} className="p-6">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${typeInfo.color}`}>
                      {typeInfo.label}
                    </span>
                    <span className="text-sm font-mono text-slate-500">{log.version}</span>
                    {!log.is_published && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                        草稿
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {log.publish_date && (
                      <span className="text-xs text-slate-400">
                        {new Date(log.publish_date).toLocaleDateString('zh-CN')}
                      </span>
                    )}
                    {isAdmin && (
                      <div className="flex gap-1">
                        {!log.is_published && (
                          <button
                            onClick={() => publishMutation.mutate(log.id)}
                            className="p-1.5 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                            title="发布"
                          >
                            <Send size={16} />
                          </button>
                        )}
                        <button
                          onClick={() => handleEdit(log)}
                          className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                          title="编辑"
                        >
                          <Edit2 size={16} />
                        </button>
                        <button
                          onClick={() => handleDelete(log.id)}
                          className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="删除"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                <h3 className="text-lg font-semibold text-slate-800 mb-2">{log.title}</h3>
                <div className="prose prose-sm prose-slate max-w-none">
                  <p className="text-slate-600 whitespace-pre-wrap">{log.content}</p>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ==================== 用户反馈组件 ====================

function FeedbackSection({ isAdmin }: { isAdmin: boolean }) {
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    type: 'feature',
    title: '',
    content: ''
  })
  const [replyingId, setReplyingId] = useState<number | null>(null)
  const [replyForm, setReplyForm] = useState({
    status: '',
    admin_reply: ''
  })
  const queryClient = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()

  // 获取反馈列表
  const { data, isLoading } = useQuery({
    queryKey: ['feedbacks'],
    queryFn: async () => {
      const res = await apiClient.get('/api/project/feedbacks')
      return res.data
    }
  })

  // 提交反馈
  const submitMutation = useMutation({
    mutationFn: (data: typeof form) => apiClient.post('/api/project/feedbacks', data),
    onSuccess: () => {
      toast.success('反馈已提交，感谢您的反馈！')
      queryClient.invalidateQueries({ queryKey: ['feedbacks'] })
      setForm({ type: 'feature', title: '', content: '' })
      setShowForm(false)
    },
    onError: () => toast.error('提交失败')
  })

  // 管理员回复
  const replyMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: typeof replyForm }) =>
      apiClient.put(`/api/project/feedbacks/${id}/reply`, data),
    onSuccess: () => {
      toast.success('回复成功')
      queryClient.invalidateQueries({ queryKey: ['feedbacks'] })
      setReplyingId(null)
      setReplyForm({ status: '', admin_reply: '' })
    },
    onError: () => toast.error('回复失败')
  })

  // 删除反馈
  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/api/project/feedbacks/${id}`),
    onSuccess: () => {
      toast.success('已删除')
      queryClient.invalidateQueries({ queryKey: ['feedbacks'] })
    },
    onError: () => toast.error('删除失败')
  })

  const handleDelete = async (id: number) => {
    const ok = await confirm({
      title: '删除反馈',
      message: '确定要删除这条反馈吗？',
      confirmText: '删除',
      variant: 'danger'
    })
    if (ok) deleteMutation.mutate(id)
  }

  const handleStartReply = (feedback: Feedback) => {
    setReplyingId(feedback.id)
    setReplyForm({
      status: feedback.status,
      admin_reply: feedback.admin_reply || ''
    })
  }

  const feedbacks: Feedback[] = data?.feedbacks || []

  return (
    <div className="space-y-4">
      {/* 提交反馈按钮 */}
      {!showForm && (
        <Button onClick={() => setShowForm(true)} icon={Plus}>
          提交反馈
        </Button>
      )}

      {/* 反馈表单 */}
      {showForm && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-slate-800 mb-4">提交反馈</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">反馈类型</label>
              <div className="flex flex-wrap gap-2">
                {FEEDBACK_TYPES.map((type) => {
                  const Icon = type.icon
                  return (
                    <button
                      key={type.value}
                      onClick={() => setForm({ ...form, type: type.value })}
                      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        form.type === type.value
                          ? 'bg-indigo-600 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      <Icon size={16} />
                      {type.label}
                    </button>
                  )
                })}
              </div>
            </div>
            <Input
              label="标题"
              placeholder="简要描述您的反馈"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <Textarea
              label="详细描述"
              placeholder="请详细描述您的建议或问题..."
              rows={5}
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
            />
            <div className="flex gap-2">
              <Button
                onClick={() => submitMutation.mutate(form)}
                disabled={!form.title || !form.content || submitMutation.isPending}
                icon={Send}
              >
                {submitMutation.isPending ? '提交中...' : '提交反馈'}
              </Button>
              <Button variant="secondary" onClick={() => setShowForm(false)}>
                取消
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 反馈列表 */}
      {isLoading ? (
        <div className="text-center py-12 text-slate-500">加载中...</div>
      ) : feedbacks.length === 0 ? (
        <Card className="p-12 text-center">
          <MessageSquare className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-500">暂无反馈</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {feedbacks.map((feedback) => {
            const typeInfo = FEEDBACK_TYPES.find(t => t.value === feedback.type) || FEEDBACK_TYPES[0]
            const statusInfo = FEEDBACK_STATUSES.find(s => s.value === feedback.status) || FEEDBACK_STATUSES[0]
            const TypeIcon = typeInfo.icon
            const isReplying = replyingId === feedback.id

            return (
              <Card key={feedback.id} className="p-6">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
                      <TypeIcon size={12} />
                      {typeInfo.label}
                    </span>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusInfo.color}`}>
                      {statusInfo.label}
                    </span>
                    {isAdmin && (
                      <span className="text-xs text-slate-400">
                        来自 {feedback.author_name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">
                      {new Date(feedback.created_at).toLocaleDateString('zh-CN')}
                    </span>
                    {isAdmin && (
                      <button
                        onClick={() => handleStartReply(feedback)}
                        className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                        title="回复"
                      >
                        <MessageSquare size={16} />
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(feedback.id)}
                      className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      title="删除"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                <h3 className="text-lg font-semibold text-slate-800 mb-2">{feedback.title}</h3>
                <p className="text-slate-600 whitespace-pre-wrap mb-4">{feedback.content}</p>

                {/* 管理员回复区域 */}
                {feedback.admin_reply && !isReplying && (
                  <div className="mt-4 p-4 bg-indigo-50 rounded-lg border border-indigo-100">
                    <div className="flex items-center gap-2 text-sm text-indigo-600 font-medium mb-2">
                      <MessageSquare size={14} />
                      管理员回复 {feedback.admin_name && `(${feedback.admin_name})`}
                    </div>
                    <p className="text-slate-700 whitespace-pre-wrap">{feedback.admin_reply}</p>
                  </div>
                )}

                {/* 管理员回复表单 */}
                {isReplying && (
                  <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="space-y-4">
                      <Select
                        label="状态"
                        value={replyForm.status}
                        onChange={(e) => setReplyForm({ ...replyForm, status: e.target.value })}
                        options={FEEDBACK_STATUSES.map(s => ({ value: s.value, label: s.label }))}
                      />
                      <Textarea
                        label="回复内容"
                        placeholder="输入回复..."
                        rows={3}
                        value={replyForm.admin_reply}
                        onChange={(e) => setReplyForm({ ...replyForm, admin_reply: e.target.value })}
                      />
                      <div className="flex gap-2">
                        <Button
                          onClick={() => replyMutation.mutate({ id: feedback.id, data: replyForm })}
                          disabled={replyMutation.isPending}
                          icon={Send}
                        >
                          {replyMutation.isPending ? '提交中...' : '提交回复'}
                        </Button>
                        <Button variant="secondary" onClick={() => setReplyingId(null)}>
                          取消
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

