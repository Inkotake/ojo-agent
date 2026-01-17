import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Gauge, Save, Zap, Users, Server, 
  Brain, Upload, Download, AlertTriangle,
  Loader2, Trash2, RotateCcw
} from 'lucide-react'
import apiClient from '../api/client'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { useToast } from '../components/ui/Toast'

interface ConcurrencyConfig {
  max_global_tasks: number
  max_tasks_per_user: number
  max_fetch_concurrent: number
  max_upload_concurrent: number
  max_solve_concurrent: number
  max_llm_concurrent: number
  max_llm_per_provider: number
  max_queue_size: number
  task_timeout_seconds: number
}

interface SemaphoreStats {
  [key: string]: {
    max: number
    current: number
    waiting: number
    total_acquired: number
  }
}

interface Preset {
  name: string
  description: string
  config: Partial<ConcurrencyConfig>
}

const configLabels: Record<keyof ConcurrencyConfig, { label: string, icon: typeof Gauge, description: string }> = {
  max_global_tasks: { label: '全局任务并发', icon: Server, description: '整个系统同时运行的最大任务数' },
  max_tasks_per_user: { label: '每用户任务数', icon: Users, description: '单个用户同时运行的最大任务数' },
  max_fetch_concurrent: { label: '拉取并发数', icon: Download, description: '同时从OJ平台拉取题目的并发数' },
  max_upload_concurrent: { label: '上传并发数', icon: Upload, description: '同时上传到OJ平台的并发数' },
  max_solve_concurrent: { label: '求解并发数', icon: Zap, description: '同时进行代码求解的并发数' },
  max_llm_concurrent: { label: 'LLM总并发', icon: Brain, description: 'LLM请求的总并发数' },
  max_llm_per_provider: { label: '每Provider并发', icon: Brain, description: '每个LLM提供商的并发数' },
  max_queue_size: { label: '最大队列长度', icon: Gauge, description: '待处理任务的最大队列长度' },
  task_timeout_seconds: { label: '任务超时(秒)', icon: AlertTriangle, description: '单个任务的超时时间' },
}

export default function ConcurrencyPage() {
  const toast = useToast()
  const queryClient = useQueryClient()
  
  const [config, setConfig] = useState<ConcurrencyConfig>({
    max_global_tasks: 50,
    max_tasks_per_user: 10,
    max_fetch_concurrent: 10,
    max_upload_concurrent: 5,
    max_solve_concurrent: 5,
    max_llm_concurrent: 8,
    max_llm_per_provider: 4,
    max_queue_size: 500,
    task_timeout_seconds: 600
  })
  
  // 获取配置
  const { data: configData, isLoading } = useQuery({
    queryKey: ['concurrency-config'],
    queryFn: async () => {
      const response = await apiClient.get('/api/concurrency/config')
      return response.data
    },
    refetchInterval: 5000 // 5秒刷新
  })
  
  // 获取预设
  const { data: presetsData } = useQuery({
    queryKey: ['concurrency-presets'],
    queryFn: async () => {
      const response = await apiClient.get('/api/concurrency/presets')
      return response.data.presets as Record<string, Preset>
    }
  })
  
  // 获取队列统计
  const { data: queueData } = useQuery({
    queryKey: ['queue-stats'],
    queryFn: async () => {
      const response = await apiClient.get('/api/concurrency/queue')
      return response.data
    },
    refetchInterval: 3000
  })
  
  useEffect(() => {
    if (configData?.config) {
      setConfig(configData.config)
    }
  }, [configData])
  
  // 保存配置
  const saveMutation = useMutation({
    mutationFn: async (cfg: Partial<ConcurrencyConfig>) => {
      const response = await apiClient.post('/api/concurrency/config', cfg)
      return response.data
    },
    onSuccess: () => {
      toast.success('并发配置已保存')
      queryClient.invalidateQueries({ queryKey: ['concurrency-config'] })
    },
    onError: (error: Error) => {
      toast.error(`保存失败: ${error.message}`)
    }
  })
  
  // 应用预设
  const presetMutation = useMutation({
    mutationFn: async (presetName: string) => {
      const response = await apiClient.post(`/api/concurrency/presets/${presetName}`)
      return response.data
    },
    onSuccess: (data) => {
      toast.success(`已应用预设: ${data.preset}`)
      queryClient.invalidateQueries({ queryKey: ['concurrency-config'] })
    },
    onError: (error: Error) => {
      toast.error(`应用预设失败: ${error.message}`)
    }
  })
  
  // 清理超时任务
  const cleanupMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/api/concurrency/queue/cleanup')
      return response.data
    },
    onSuccess: (data) => {
      toast.success(data.message)
      queryClient.invalidateQueries({ queryKey: ['queue-stats'] })
    }
  })
  
  // 恢复中断任务
  const recoverMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/api/concurrency/queue/recover')
      return response.data
    },
    onSuccess: (data) => {
      toast.success(data.message)
      queryClient.invalidateQueries({ queryKey: ['queue-stats'] })
    }
  })
  
  const handleSave = () => {
    saveMutation.mutate(config)
  }
  
  const stats: SemaphoreStats = configData?.stats || {}
  const presets = presetsData || {}
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-indigo-600" />
      </div>
    )
  }
  
  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* 头部 */}
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">并发管理</h2>
          <p className="text-slate-500">配置系统各环节的并发限制</p>
        </div>
        <Button onClick={handleSave} icon={Save} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? '保存中...' : '保存配置'}
        </Button>
      </div>
      
      {/* 实时状态 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {Object.entries(stats).map(([key, stat]) => (
          <Card key={key} className="p-4 text-center">
            <div className="text-xs text-slate-400 mb-1">{key}</div>
            <div className="text-2xl font-bold text-slate-800">
              {stat.current}<span className="text-slate-400">/{stat.max}</span>
            </div>
            {stat.waiting > 0 && (
              <div className="text-xs text-amber-500 mt-1">
                等待: {stat.waiting}
              </div>
            )}
          </Card>
        ))}
      </div>
      
      {/* 队列状态 */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-slate-700 flex items-center gap-2">
            <Gauge size={18} />
            任务队列状态
          </h3>
          <div className="flex gap-2">
            <Button 
              variant="secondary" 
              onClick={() => cleanupMutation.mutate()}
              disabled={cleanupMutation.isPending}
            >
              <Trash2 size={16} />
              清理超时
            </Button>
            <Button 
              variant="secondary" 
              onClick={() => recoverMutation.mutate()}
              disabled={recoverMutation.isPending}
            >
              <RotateCcw size={16} />
              恢复中断
            </Button>
          </div>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center p-3 bg-slate-50 rounded-lg">
            <div className="text-2xl font-bold text-slate-700">{queueData?.pending || 0}</div>
            <div className="text-xs text-slate-500">等待中</div>
          </div>
          <div className="text-center p-3 bg-blue-50 rounded-lg">
            <div className="text-2xl font-bold text-blue-600">{queueData?.running || 0}</div>
            <div className="text-xs text-blue-500">执行中</div>
          </div>
          <div className="text-center p-3 bg-green-50 rounded-lg">
            <div className="text-2xl font-bold text-green-600">{queueData?.completed || 0}</div>
            <div className="text-xs text-green-500">已完成</div>
          </div>
          <div className="text-center p-3 bg-red-50 rounded-lg">
            <div className="text-2xl font-bold text-red-600">{queueData?.failed || 0}</div>
            <div className="text-xs text-red-500">失败</div>
          </div>
          <div className="text-center p-3 bg-indigo-50 rounded-lg">
            <div className="text-2xl font-bold text-indigo-600">{queueData?.total || 0}</div>
            <div className="text-xs text-indigo-500">总计</div>
          </div>
        </div>
      </Card>
      
      {/* 快速预设 */}
      <Card className="p-4">
        <h3 className="font-bold text-slate-700 mb-4 flex items-center gap-2">
          <Zap size={18} />
          快速预设
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(presets).map(([key, preset]) => (
            <button
              key={key}
              onClick={() => presetMutation.mutate(key)}
              disabled={presetMutation.isPending}
              className="p-4 border border-slate-200 rounded-lg text-left hover:border-indigo-500 hover:bg-indigo-50/50 transition-all"
            >
              <div className="font-medium text-slate-700">{preset.name}</div>
              <div className="text-sm text-slate-500 mt-1">{preset.description}</div>
              <div className="text-xs text-slate-400 mt-2">
                全局: {preset.config.max_global_tasks} | 
                每用户: {preset.config.max_tasks_per_user} | 
                LLM: {preset.config.max_llm_concurrent}
              </div>
            </button>
          ))}
        </div>
      </Card>
      
      {/* 详细配置 */}
      <Card className="p-6">
        <h3 className="font-bold text-slate-700 mb-6 flex items-center gap-2">
          <Server size={18} />
          详细配置
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {(Object.keys(configLabels) as Array<keyof ConcurrencyConfig>).map((key) => {
            const { label, icon: Icon, description } = configLabels[key]
            return (
              <div key={key} className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <Icon size={16} className="text-slate-400" />
                  {label}
                </label>
                <input
                  type="number"
                  value={config[key]}
                  onChange={(e) => setConfig(prev => ({ ...prev, [key]: parseInt(e.target.value) || 0 }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  min={1}
                />
                <p className="text-xs text-slate-400">{description}</p>
              </div>
            )
          })}
        </div>
      </Card>
      
      {/* 使用提示 */}
      <Card className="p-4 bg-amber-50 border-amber-200">
        <div className="flex items-start gap-3">
          <AlertTriangle size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-amber-800">配置建议</h4>
            <ul className="text-sm text-amber-700 mt-2 space-y-1">
              <li>• <strong>10人同时使用</strong>: 建议使用"标准模式"预设</li>
              <li>• <strong>全局任务数</strong>: 建议设为用户数 × 每用户任务数</li>
              <li>• <strong>上传并发</strong>: 过高可能触发OJ平台限流</li>
              <li>• <strong>LLM并发</strong>: 根据API配额调整，避免触发限流</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  )
}
