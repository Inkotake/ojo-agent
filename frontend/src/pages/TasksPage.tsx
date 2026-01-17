import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Play, Trash2, Pause, FileJson, DownloadCloud, ArrowRight, Cpu, UploadCloud, ListPlus, FileText } from 'lucide-react'
import apiClient from '../api/client'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Select from '../components/ui/Select'
import Textarea from '../components/ui/Textarea'
import ModuleSelector, { type ModuleConfig } from '../components/ModuleSelector'
import BatchAddDialog from '../components/BatchAddDialog'
import LogDialog from '../components/LogDialog'
import TaskActionMenu from '../components/TaskActionMenu'
import PasteProblemDialog from '../components/PasteProblemDialog'
import StageProgress, { StageDetail } from '../components/StageProgress'
import OJIcon, { identifyOJ, OJ_PLATFORMS, formatDisplayId } from '../components/OJIcon'
import { useWebSocket } from '../hooks/useWebSocket'
import { useDownload } from '../hooks/useDownload'
import { useToast } from '../components/ui/Toast'

interface QueueTask {
  id: string
  displayId: string
  status: number
  progress: number
  currentStage: string
  logs: string[]
  task_id?: string
  source?: string  // 来源OJ (用于显示图标)
  adapter?: string  // 拉取适配器名称 (用于后端)
  llmProvider?: string  // LLM 提供商（生成+求解）
  error_message?: string
  created_at?: string
  updated_at?: string
  uploaded_url?: string  // 上传后的题目链接
}


interface Adapter {
  name: string
  display_name: string
  capabilities: string[]
  has_config: boolean
}

export default function TasksPage() {
  const queryClient = useQueryClient()
  const { messages, connected } = useWebSocket()
  const { downloadWorkspace } = useDownload()
  const toast = useToast()
  
  // Config States
  const [fetchAdapter, setFetchAdapter] = useState('auto')
  const [llmProvider, setLlmProvider] = useState('deepseek')  // 统一LLM选择（生成+求解）
  const [submitAdapter, setSubmitAdapter] = useState('shsoj')
  const [batchInput, setBatchInput] = useState('')
  
  // Module config (upload 和 solve 联动：开启 upload 时自动开启 solve)
  const [moduleConfig, setModuleConfig] = useState<ModuleConfig>({
    fetch: true,
    gen: true,
    upload: true,
    solve: true  // upload 和 solve 联动
  })
  
  // Dialog states
  const [showBatchDialog, setShowBatchDialog] = useState(false)
  const [showLogDialog, setShowLogDialog] = useState(false)
  const [showPasteDialog, setShowPasteDialog] = useState(false)
  const [selectedTask, setSelectedTask] = useState<QueueTask | null>(null)
  
  // 获取可用适配器列表
  const { data: adaptersData } = useQuery({
    queryKey: ['adapters'],
    queryFn: async () => {
      const response = await apiClient.get('/api/adapters')
      return response.data.adapters || []
    },
  })
  
  const adapters: Adapter[] = adaptersData || []
  
  // 分类适配器：可拉取和可上传（能力名称为小写）
  const fetchAdapters = adapters.filter(a => 
    a.capabilities.includes('fetch_problem')
  )
  const uploadAdapters = adapters.filter(a => 
    a.capabilities.includes('upload_data')
  )
  
  // 获取已保存的模块适配器设置
  const { data: moduleSettings } = useQuery({
    queryKey: ['module-adapters'],
    queryFn: async () => {
      const response = await apiClient.get('/api/module-adapters')
      return response.data.module_adapter_settings
    },
  })
  
  // 加载保存的设置
  useEffect(() => {
    if (moduleSettings) {
      if (moduleSettings.fetch?.adapter) setFetchAdapter(moduleSettings.fetch.adapter)
      if (moduleSettings.upload?.adapter) setSubmitAdapter(moduleSettings.upload.adapter)
    }
  }, [moduleSettings])
  
  // 待提交队列（用户添加的，还没点开始）
  const [pendingQueue, setPendingQueue] = useState<QueueTask[]>([])
  const [isRunning, setIsRunning] = useState(false)
  
  // 已提交任务（从后端获取）
  const { data: submittedTasks } = useQuery({
    queryKey: ['user-tasks'],
    queryFn: async () => {
      const response = await apiClient.get('/api/tasks')
      return (response.data.tasks || []).map((task: { id: number; problem_id: string; status?: number; progress?: number; stage?: string; error_message?: string; created_at?: string; updated_at?: string; uploaded_url?: string }) => ({
        id: String(task.id),
        displayId: task.problem_id,
        status: task.status || 0,
        progress: task.progress || 0,
        currentStage: task.stage || 'pending',
        logs: [],
        task_id: String(task.id),
        error_message: task.error_message,
        created_at: task.created_at,
        updated_at: task.updated_at,
        uploaded_url: task.uploaded_url,
      }))
    },
    refetchInterval: isRunning ? 3000 : 10000,  // 运行时3秒轮询，否则10秒
  })
  
  // 过滤：只显示正在处理的任务（排除已完成status=4、已取消status=-2）
  const activeTasks = (submittedTasks || []).filter((task: QueueTask) => 
    task.status !== 4 && task.status !== -2
  )
  
  // 队列只显示待提交的任务（已提交的任务在仪表盘查看）
  const queue: QueueTask[] = [...pendingQueue]
  
  // 正在运行的任务数量（用于显示状态）
  const runningCount = activeTasks.filter((t: QueueTask) => t.status === 1).length
  const waitingCount = activeTasks.filter((t: QueueTask) => t.status === 0).length

  interface CreateTaskRequest {
    problem_ids: string[]
    problems?: { id: string; adapter: string }[]  // 新格式：每个题目带适配器
    enable_fetch: boolean
    enable_generation: boolean
    enable_upload: boolean
    enable_solve: boolean
    source_adapter?: string
    target_adapter?: string
    llm_provider?: string  // 统一LLM提供商（生成+求解）
  }

  const createTaskMutation = useMutation({
    mutationFn: async (data: CreateTaskRequest) => {
      const response = await apiClient.post('/api/tasks', data)
      return response.data
    },
    onSuccess: (data) => {
      console.log('Task created:', data)
      // Refresh task list
      queryClient.invalidateQueries({ queryKey: ['user-tasks'] })
      toast.success(data.message || `已创建 ${data.tasks?.length || 0} 个任务`)
      // 任务已提交，允许用户继续添加新任务
      setIsRunning(false)
    },
    onError: (error: any) => {
      // 显示服务器返回的具体错误信息
      const message = error?.response?.data?.detail || '任务创建失败，请重试'
      toast.error(message)
      setIsRunning(false)
    },
  })
  
  // 实时日志状态
  const [realtimeLogs, setRealtimeLogs] = useState<Record<string, string[]>>({})
  // 已处理的消息ID（避免重复处理）
  const [lastProcessedMsgIdx, setLastProcessedMsgIdx] = useState(0)
  
  // WebSocket real-time task progress updates
  useEffect(() => {
    if (!connected || messages.length === 0) return
    
    // 只处理新消息
    const newMessages = messages.slice(lastProcessedMsgIdx)
    if (newMessages.length === 0) return
    
    setLastProcessedMsgIdx(messages.length)
    
    for (const msg of newMessages) {
      // 处理进度更新 - 包含日志消息
      if (msg?.type === 'task.progress' && msg?.data?.log) {
        const problemId = msg?.problem_id || msg?.data?.problem_id
        if (problemId) {
          setRealtimeLogs(prev => ({
            ...prev,
            [problemId]: [...(prev[problemId] || []), msg.data.log].slice(-100)
          }))
        }
      }
      
      // 任何任务状态变化都触发 refetch
      if (msg?.type === 'task.progress' || 
          msg?.type === 'task.completed' || 
          msg?.type === 'task.failed' ||
          msg?.type === 'task.started' ||
          msg?.type === 'task.problem_completed') {
        queryClient.invalidateQueries({ queryKey: ['user-tasks'] })
        
        // 显示 Toast 通知（只对特定事件）
        if (msg?.type === 'task.problem_completed') {
          const pid = msg?.problem_id
          const status = msg?.status
          if (status === 'success') {
            toast.success(`题目 ${pid} 处理完成`)
          }
        }
        
        // 任务完成时停止运行状态
        if (msg?.type === 'task.completed' || msg?.type === 'task.failed') {
          setIsRunning(false)
          if (msg?.type === 'task.completed') {
            toast.success('批处理任务完成!')
          }
        }
      }
    }
  }, [messages, connected, queryClient, toast, lastProcessedMsgIdx])

  const parseBatchInput = () => {
    if (!batchInput.trim()) return
    
    const newItems: QueueTask[] = []
    // 支持换行和逗号分隔
    const parts = batchInput.split(/[\n,]/).map(s => s.trim()).filter(s => s)
    
    // 使用当前选择的适配器（非 auto 时固定使用选择的适配器）
    const useSelectedAdapter = fetchAdapter !== 'auto'
    const selectedPlatform = useSelectedAdapter 
      ? Object.entries(OJ_PLATFORMS).find(([_, p]) => p.adapter === fetchAdapter)?.[0] || fetchAdapter
      : null
    
    parts.forEach(part => {
      // Support range input (1001-1010) - only for pure numeric ranges
      if (/^\d+-\d+$/.test(part)) {
        const [start, end] = part.split('-').map(Number)
        if (!isNaN(start) && !isNaN(end)) {
          for (let i = start; i <= end; i++) {
            const displayId = `${i}`
            // 非 auto 时使用选择的适配器，auto 时自动识别
            const ojType = useSelectedAdapter ? selectedPlatform! : identifyOJ(displayId)
            newItems.push({
              id: `task-${Date.now()}-${i}`,
              displayId,
              status: -3,  // 待提交
              progress: 0,
              currentStage: '待提交',
              logs: [],
              source: ojType,
              adapter: useSelectedAdapter ? fetchAdapter : (OJ_PLATFORMS[ojType] || OJ_PLATFORMS.unknown).adapter,
              llmProvider: llmProvider,  // 绑定当时的 LLM 选择
            })
          }
        }
      } else {
        // 非 auto 时使用选择的适配器，auto 时自动识别
        const ojType = useSelectedAdapter ? selectedPlatform! : identifyOJ(part)
        newItems.push({
          id: `task-${Date.now()}-${part}`,
          displayId: part,
          status: -3,  // 待提交
          progress: 0,
          currentStage: '待提交',
          logs: [],
          source: ojType,
          adapter: useSelectedAdapter ? fetchAdapter : (OJ_PLATFORMS[ojType] || OJ_PLATFORMS.unknown).adapter,
          llmProvider: llmProvider,  // 绑定当时的 LLM 选择
        })
      }
    })
    
    setPendingQueue(prev => [...prev, ...newItems])
    setBatchInput('')
  }

  const clearQueue = () => setPendingQueue([])

  // Start batch task - call backend API
  const startBatch = async () => {
    if (pendingQueue.length === 0) {
      toast.error('队列为空，请先添加任务')
      return
    }
    
    setIsRunning(true)
    
    // 构建每个任务的信息（包含独立的适配器）
    const problems = pendingQueue.map(t => ({
      id: t.displayId,
      adapter: t.adapter || 'auto'  // 使用队列中识别好的适配器
    }))
    
    // 检查是否所有任务使用同一个 LLM（目前后端只支持批量统一 LLM）
    const llmProviders = new Set(pendingQueue.map(t => t.llmProvider || 'deepseek'))
    if (llmProviders.size > 1) {
      toast.warning('注意：队列中任务使用不同 LLM，将统一使用当前选择的 LLM')
    }
    
    // 使用当前选择的 LLM（后端目前只支持批量统一 LLM）
    // 如果队列中所有任务使用同一个 LLM，优先使用该 LLM
    const effectiveLlmProvider = llmProviders.size === 1 
      ? Array.from(llmProviders)[0] 
      : llmProvider
    
    // Call backend API to create task
    createTaskMutation.mutate({
      problems,  // 新格式：每个题目带适配器
      problem_ids: pendingQueue.map(t => t.displayId),  // 兼容旧格式
      enable_fetch: moduleConfig.fetch,
      enable_generation: moduleConfig.gen,
      enable_upload: moduleConfig.upload,
      enable_solve: moduleConfig.solve,
      target_adapter: submitAdapter,
      llm_provider: effectiveLlmProvider,  // 使用有效的 LLM
    })
    
    // 清空待提交队列（任务已提交到后端）
    setPendingQueue([])
  }

  const pauseBatch = () => setIsRunning(false)
  
  const handleDownload = async (taskId: string) => {
    const success = await downloadWorkspace(taskId)
    if (success) {
      toast.success('下载已开始')
    } else {
      toast.error('下载失败，请重试')
    }
  }
  
  const handleViewLogs = (task: QueueTask) => {
    setSelectedTask(task)
    setShowLogDialog(true)
  }
  
  const handleBatchAdd = (urls: string[]) => {
    // 批量添加（从标签选择器）默认使用 aicoders 适配器
    const newItems: QueueTask[] = urls.map((url, i) => ({
      id: `task-${Date.now()}-${i}`,
      displayId: url,
      status: -3,  // 待提交
      progress: 0,
      currentStage: '待提交',
      logs: [],
      source: 'aicoders',
      adapter: 'aicoders',
      llmProvider: llmProvider,  // 绑定当时的 LLM 选择
    }))
    setPendingQueue(prev => [...prev, ...newItems])
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">批处理控制台</h2>
          <p className="text-slate-500">配置流水线适配器并处理多个任务</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setShowPasteDialog(true)} icon={FileText}>
            粘贴题面
          </Button>
          <Button variant="secondary" onClick={() => setShowBatchDialog(true)} icon={ListPlus}>
            批量添加
          </Button>
          {!isRunning ? (
            <Button onClick={startBatch} icon={Play} disabled={pendingQueue.length === 0} variant="success">
              开始批处理
            </Button>
          ) : (
            <Button onClick={pauseBatch} icon={Pause} variant="secondary">
              暂停
            </Button>
          )}
        </div>
      </div>

      {/* 1. Pipeline Configuration (The Flow) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Source */}
        <Card className="p-4 border-t-4 border-t-purple-500 relative">
          <div className="absolute top-1/2 -right-3 z-10 hidden md:block text-slate-300 bg-slate-50 rounded-full p-1 border border-slate-200">
            <ArrowRight size={16} />
          </div>
          <div className="flex items-center gap-2 mb-3">
            <DownloadCloud size={18} className="text-purple-600" />
            <h3 className="font-bold text-slate-700">1. 数据源 (获取)</h3>
          </div>
          <Select
            value={fetchAdapter}
            onChange={(e) => setFetchAdapter(e.target.value)}
          >
            <option value="auto">自动识别</option>
            {fetchAdapters.map(a => (
              <option key={a.name} value={a.name}>{a.display_name}</option>
            ))}
          </Select>
        </Card>
        
        {/* LLM Provider - 统一用于生成和求解 */}
        <Card className="p-4 border-t-4 border-t-indigo-500 relative">
          <div className="absolute top-1/2 -right-3 z-10 hidden md:block text-slate-300 bg-slate-50 rounded-full p-1 border border-slate-200">
            <ArrowRight size={16} />
          </div>
          <div className="flex items-center gap-2 mb-3">
            <Cpu size={18} className="text-indigo-600" />
            <h3 className="font-bold text-slate-700">2. LLM (生成+求解)</h3>
          </div>
          <Select
            value={llmProvider}
            onChange={(e) => setLlmProvider(e.target.value)}
            options={[
              { value: 'deepseek', label: 'DeepSeek Reasoner' },
              { value: 'openai', label: 'OpenAI 兼容' },
            ]}
          />
          <p className="text-xs text-slate-400 mt-2">生成和求解统一使用此LLM，OCR自动使用硅基流动</p>
        </Card>
        
        {/* Target */}
        <Card className="p-4 border-t-4 border-t-cyan-500">
          <div className="flex items-center gap-2 mb-3">
            <UploadCloud size={18} className="text-cyan-600" />
            <h3 className="font-bold text-slate-700">3. 目标 (上传)</h3>
          </div>
          <Select
            value={submitAdapter}
            onChange={(e) => setSubmitAdapter(e.target.value)}
          >
            {uploadAdapters.length === 0 ? (
              <option value="">无可用适配器</option>
            ) : (
              uploadAdapters.map(a => (
                <option key={a.name} value={a.name}>{a.display_name}</option>
              ))
            )}
          </Select>
        </Card>
      </div>
      
      {/* Module Selector */}
      <Card className="p-4">
        <ModuleSelector
          value={moduleConfig}
          onChange={setModuleConfig}
        />
        
      </Card>

      {/* 2. Batch Input */}
      <Card className="p-4">
        <div className="flex gap-4">
          {fetchAdapter === 'manual' ? (
            /* 手动题面模式 */
            <div className="flex-1 space-y-3">
              <div className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded-lg">
                <FileText size={16} />
                <span>手动题面模式：请粘贴完整的题目内容，系统将自动格式化</span>
              </div>
              <Textarea
                label="粘贴题面内容"
                className="min-h-[200px]"
                placeholder="请粘贴完整的题目内容，包括：
- 题目标题
- 题目描述
- 输入格式
- 输出格式
- 样例输入输出
- 数据范围/提示

系统将使用 AI 自动格式化题面..."
                value={batchInput}
                onChange={(e) => setBatchInput(e.target.value)}
              />
            </div>
          ) : (
            /* 标准模式 */
            <Textarea
              label="批量输入 (每行一个题目ID或URL)"
              className="flex-1 min-h-[160px]"
              placeholder="每行输入一个题目ID或URL，例如：
1001
1002
2000-2005
https://oj.aicoders.cn/problem/2772
https://www.luogu.com.cn/problem/P1001"
              value={batchInput}
              onChange={(e) => setBatchInput(e.target.value)}
            />
          )}
          <div className="flex flex-col gap-2 justify-center min-w-[100px]">
            <Button onClick={parseBatchInput} disabled={!batchInput.trim()} className="whitespace-nowrap">
              <Plus size={16} className="mr-1" /> 添加
            </Button>
            <Button variant="ghost" onClick={clearQueue} className="text-red-500 hover:text-red-600 hover:bg-red-50 whitespace-nowrap">
              <Trash2 size={16} className="mr-1" /> 清空
            </Button>
          </div>
        </div>
      </Card>

      {/* 3. Queue - 待提交任务 */}
      <div className="space-y-4">
        <h3 className="font-bold text-slate-800 flex items-center gap-2">
          <FileJson size={18} /> 待提交队列{' '}
          <span className="text-slate-400 font-normal">({queue.length} 个任务)</span>
          {(runningCount > 0 || waitingCount > 0) && (
            <span className="ml-2 text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">
              后台: {runningCount} 运行中, {waitingCount} 等待中
            </span>
          )}
          {isRunning && <span className="ml-2 text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full animate-pulse">运行中</span>}
        </h3>
        
        {queue.length === 0 ? (
          <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-xl text-slate-400">
            <FileJson size={48} className="mx-auto mb-3 opacity-50" />
            <p>队列为空，请在上方输入题目ID后点击添加</p>
            {(runningCount > 0 || waitingCount > 0) && (
              <p className="mt-2 text-sm">已提交的任务请在「仪表盘」查看进度</p>
            )}
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden flex flex-col h-[600px]">
            <div className="bg-slate-50 px-6 py-3 flex items-center text-xs font-medium text-slate-500 uppercase sticky top-0 z-10 border-b border-slate-100">
              <div className="w-16 flex-shrink-0">来源</div>
              <div className="w-28 flex-shrink-0">ID</div>
              <div className="flex-1 min-w-[180px] px-2">进度</div>
              <div className="w-36 flex-shrink-0 px-2">当前状态</div>
              <div className="w-16 flex-shrink-0 text-right">操作</div>
            </div>
            <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
              {queue.map((task) => {
                const source = task.source || identifyOJ(task.displayId)
                return (
                  <div key={task.id} className="px-6 py-3 flex items-center hover:bg-slate-50/50">
                    <div className="w-16 flex-shrink-0">
                      <OJIcon oj={source} size="sm" />
                    </div>
                    <div className="w-28 flex-shrink-0 font-mono font-medium text-slate-700 truncate text-xs" title={task.displayId}>
                      {formatDisplayId(task.displayId, source)}
                    </div>
                    <div className="flex-1 min-w-[180px] px-2">
                      <StageProgress stage={task.currentStage} status={task.status} />
                    </div>
                    <div className="w-36 flex-shrink-0 px-2">
                      <StageDetail 
                        stage={task.currentStage} 
                        status={task.status}
                        errorMessage={task.error_message}
                      />
                    </div>
                    <div className="w-16 flex-shrink-0 flex justify-end">
                      <TaskActionMenu
                        taskId={task.task_id || task.id}
                        problemId={task.displayId}
                        status={task.status}
                        uploadedUrl={task.uploaded_url}
                        onViewLogs={() => handleViewLogs(task)}
                        onDownload={() => task.task_id && handleDownload(task.task_id)}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
      
      
      {/* Dialogs */}
      <BatchAddDialog
        isOpen={showBatchDialog}
        onClose={() => setShowBatchDialog(false)}
        onAdd={handleBatchAdd}
      />
      
      <LogDialog
        isOpen={showLogDialog}
        onClose={() => setShowLogDialog(false)}
        taskId={selectedTask?.task_id || selectedTask?.id || ''}
        problemId={selectedTask?.displayId || ''}
        logs={realtimeLogs[selectedTask?.displayId || ''] || selectedTask?.logs || []}
      />
      
      <PasteProblemDialog
        isOpen={showPasteDialog}
        onClose={() => setShowPasteDialog(false)}
        onCreated={(problemId) => {
          setPendingQueue(prev => [...prev, {
            id: `task-${Date.now()}-paste`,
            displayId: problemId,
            status: -3,  // 待提交
            progress: 0,
            currentStage: '待提交',
            logs: [],
            source: 'manual',
            adapter: 'manual',
            llmProvider: llmProvider,  // 绑定当时的 LLM 选择
          }])
        }}
      />
    </div>
  )
}
