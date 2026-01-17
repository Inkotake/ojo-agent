import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Plus, Trash2, BookOpen, Users, Calendar, 
  ChevronRight, Search, Loader2, Edit, Save, X
} from 'lucide-react'
import apiClient from '../api/client'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { useToast } from '../components/ui/Toast'
import { useConfirm } from '../components/ui/ConfirmDialog'

interface Training {
  id: string
  title: string
  description: string
  author: string
  problem_count: number
  created_at?: string
}

interface CreateTrainingForm {
  title: string
  description: string
  problemIds: string
}

export default function TrainingPage() {
  const toast = useToast()
  const confirm = useConfirm()
  const queryClient = useQueryClient()
  
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [form, setForm] = useState<CreateTrainingForm>({
    title: '',
    description: '',
    problemIds: ''
  })
  const [selectedTraining, setSelectedTraining] = useState<Training | null>(null)
  const [addProblemsInput, setAddProblemsInput] = useState('')
  
  // 获取题单列表
  const { data: trainingsData, isLoading } = useQuery({
    queryKey: ['trainings'],
    queryFn: async () => {
      const response = await apiClient.get('/api/training/list')
      return response.data
    }
  })
  
  const trainings: Training[] = trainingsData?.trainings || []
  
  // 创建题单
  const createMutation = useMutation({
    mutationFn: async (data: CreateTrainingForm) => {
      const problemIds = data.problemIds
        .split(/[\n,]/)
        .map(s => s.trim())
        .filter(s => s)
      
      const response = await apiClient.post('/api/training/create', {
        title: data.title,
        description: data.description,
        problem_ids: problemIds
      })
      return response.data
    },
    onSuccess: () => {
      toast.success('题单创建成功')
      queryClient.invalidateQueries({ queryKey: ['trainings'] })
      setShowCreateForm(false)
      setForm({ title: '', description: '', problemIds: '' })
    },
    onError: (error: Error) => {
      toast.error(`创建失败: ${error.message}`)
    }
  })
  
  // 添加题目到题单
  const addProblemsMutation = useMutation({
    mutationFn: async ({ trainingId, problemIds }: { trainingId: string, problemIds: string[] }) => {
      const response = await apiClient.post(`/api/training/${trainingId}/add`, {
        problem_ids: problemIds
      })
      return response.data
    },
    onSuccess: () => {
      toast.success('题目添加成功')
      queryClient.invalidateQueries({ queryKey: ['trainings'] })
      setAddProblemsInput('')
    },
    onError: (error: Error) => {
      toast.error(`添加失败: ${error.message}`)
    }
  })
  
  // 删除题单
  const deleteMutation = useMutation({
    mutationFn: async (trainingId: string) => {
      const response = await apiClient.delete(`/api/training/${trainingId}`)
      return response.data
    },
    onSuccess: () => {
      toast.success('题单已删除')
      queryClient.invalidateQueries({ queryKey: ['trainings'] })
      setSelectedTraining(null)
    },
    onError: (error: Error) => {
      toast.error(`删除失败: ${error.message}`)
    }
  })
  
  const handleCreate = () => {
    if (!form.title.trim()) {
      toast.error('请输入题单标题')
      return
    }
    createMutation.mutate(form)
  }
  
  const handleAddProblems = () => {
    if (!selectedTraining || !addProblemsInput.trim()) return
    
    const problemIds = addProblemsInput
      .split(/[\n,]/)
      .map(s => s.trim())
      .filter(s => s)
    
    if (problemIds.length === 0) {
      toast.error('请输入题目ID')
      return
    }
    
    addProblemsMutation.mutate({
      trainingId: selectedTraining.id,
      problemIds
    })
  }
  
  const filteredTrainings = trainings.filter(t => 
    t.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.description?.toLowerCase().includes(searchTerm.toLowerCase())
  )
  
  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* 头部 */}
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">题单管理</h2>
          <p className="text-slate-500">创建和管理OJ平台题单</p>
        </div>
        <Button onClick={() => setShowCreateForm(true)} icon={Plus}>
          创建题单
        </Button>
      </div>
      
      {/* 创建表单 */}
      {showCreateForm && (
        <Card className="p-6 border-2 border-indigo-200 bg-indigo-50/30">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-bold text-slate-800">创建新题单</h3>
            <button onClick={() => setShowCreateForm(false)} className="text-slate-400 hover:text-slate-600">
              <X size={20} />
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <Input
              label="题单标题"
              placeholder="输入题单标题"
              value={form.title}
              onChange={(e) => setForm(prev => ({ ...prev, title: e.target.value }))}
            />
            <Input
              label="描述"
              placeholder="可选的题单描述"
              value={form.description}
              onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
            />
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-1">
              初始题目 (可选，每行一个ID)
            </label>
            <textarea
              className="w-full h-24 p-3 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="1001&#10;1002&#10;1003"
              value={form.problemIds}
              onChange={(e) => setForm(prev => ({ ...prev, problemIds: e.target.value }))}
            />
          </div>
          
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowCreateForm(false)}>
              取消
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              创建
            </Button>
          </div>
        </Card>
      )}
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 题单列表 */}
        <div className="lg:col-span-2 space-y-4">
          {/* 搜索 */}
          <div className="relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="搜索题单..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          
          {/* 列表 */}
          {isLoading ? (
            <div className="text-center py-12">
              <Loader2 size={32} className="animate-spin mx-auto text-indigo-600" />
              <p className="mt-2 text-slate-500">加载中...</p>
            </div>
          ) : filteredTrainings.length === 0 ? (
            <Card className="p-12 text-center">
              <BookOpen size={48} className="mx-auto text-slate-300 mb-3" />
              <p className="text-slate-500">暂无题单</p>
              <p className="text-sm text-slate-400 mt-1">点击上方按钮创建第一个题单</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {filteredTrainings.map((training) => (
                <div 
                  key={training.id}
                  className={`p-4 cursor-pointer transition-all hover:shadow-md bg-white rounded-xl border border-slate-100 shadow-sm ${
                    selectedTraining?.id === training.id 
                      ? 'ring-2 ring-indigo-500 bg-indigo-50/50' 
                      : ''
                  }`}
                  onClick={() => setSelectedTraining(training)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <h4 className="font-bold text-slate-800">{training.title}</h4>
                      {training.description && (
                        <p className="text-sm text-slate-500 mt-1 line-clamp-1">{training.description}</p>
                      )}
                      <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                        <span className="flex items-center gap-1">
                          <BookOpen size={12} />
                          {training.problem_count || 0} 题
                        </span>
                        <span className="flex items-center gap-1">
                          <Users size={12} />
                          {training.author}
                        </span>
                        {training.created_at && (
                          <span className="flex items-center gap-1">
                            <Calendar size={12} />
                            {new Date(training.created_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <ChevronRight size={20} className="text-slate-300" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* 右侧详情 */}
        <div className="lg:col-span-1">
          {selectedTraining ? (
            <Card className="p-6 sticky top-4">
              <h3 className="font-bold text-slate-800 mb-4">{selectedTraining.title}</h3>
              
              {selectedTraining.description && (
                <p className="text-sm text-slate-500 mb-4">{selectedTraining.description}</p>
              )}
              
              <div className="space-y-3 mb-6">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">题目数量</span>
                  <span className="font-medium">{selectedTraining.problem_count || 0}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">作者</span>
                  <span className="font-medium">{selectedTraining.author}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">题单ID</span>
                  <span className="font-mono text-xs">{selectedTraining.id}</span>
                </div>
              </div>
              
              {/* 添加题目 */}
              <div className="border-t border-slate-100 pt-4 mb-4">
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  添加题目
                </label>
                <textarea
                  className="w-full h-20 p-2 text-sm border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="每行一个题目ID"
                  value={addProblemsInput}
                  onChange={(e) => setAddProblemsInput(e.target.value)}
                />
                <Button 
                  className="w-full mt-2" 
                  onClick={handleAddProblems}
                  disabled={!addProblemsInput.trim() || addProblemsMutation.isPending}
                >
                  {addProblemsMutation.isPending ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Plus size={16} />
                  )}
                  添加题目
                </Button>
              </div>
              
              {/* 删除按钮 */}
              <Button 
                variant="ghost" 
                className="w-full text-red-500 hover:bg-red-50 hover:text-red-600"
                onClick={async () => {
                  const ok = await confirm({
                    title: '删除题单',
                    message: `确定删除题单 "${selectedTraining.title}" 吗？`,
                    confirmText: '删除',
                    variant: 'danger'
                  })
                  if (ok) deleteMutation.mutate(selectedTraining.id)
                }}
                disabled={deleteMutation.isPending}
              >
                <Trash2 size={16} />
                删除题单
              </Button>
            </Card>
          ) : (
            <Card className="p-6 text-center text-slate-400">
              <Edit size={32} className="mx-auto mb-2 opacity-50" />
              <p>选择一个题单查看详情</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
