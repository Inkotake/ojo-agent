import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Globe, AlertCircle, Settings, X, Save, CheckCircle } from 'lucide-react'
import apiClient from '../api/client'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../components/ui/Toast'

interface ConfigSchema {
  [key: string]: {
    type: string
    label: string
    default?: string
    required?: boolean
    tooltip?: string
  }
}

interface Adapter {
  name: string
  display_name: string
  capabilities: string[]
  version: string
  status: string
  config_schema: ConfigSchema
  config_values: Record<string, any>
  has_config: boolean
}

// 能力值到中文标签的映射（使用小写枚举名）
const CAPABILITY_LABELS: Record<string, string> = {
  // 标准能力名称（与后端 OJCapability 枚举对应）
  'fetch_problem': '拉取题目',
  'upload_data': '上传数据',
  'submit_solution': '提交代码',
  'manage_training': '题单管理',
  'judge_status': '判题状态',
  'batch_fetch': '批量拉取',
  'provide_solution': '获取题解',
}

function getCapabilityLabel(cap: string): string {
  return CAPABILITY_LABELS[cap] || CAPABILITY_LABELS[cap.toLowerCase()] || cap
}

export default function AdaptersPage() {
  const { connected } = useWebSocket()
  const queryClient = useQueryClient()
  const toast = useToast()
  
  const [editingAdapter, setEditingAdapter] = useState<Adapter | null>(null)
  const [configForm, setConfigForm] = useState<Record<string, string>>({})
  const [saveSuccess, setSaveSuccess] = useState(false)
  
  const { data: adaptersData, isLoading, refetch } = useQuery({
    queryKey: ['adapters'],
    queryFn: async () => {
      const response = await apiClient.get('/api/adapters')
      return response.data.adapters || []
    },
  })

  const saveConfigMutation = useMutation({
    mutationFn: async ({ adapterName, config }: { adapterName: string, config: Record<string, string> }) => {
      const response = await apiClient.post(`/api/adapters/${adapterName}/config`, { config })
      return response.data
    },
    onSuccess: () => {
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
      queryClient.invalidateQueries({ queryKey: ['adapters'] })
      toast.success('配置已保存')
    },
    onError: () => {
      toast.error('保存失败，请重试')
    },
  })

  const adapters: Adapter[] = adaptersData || []

  const openConfigModal = (adapter: Adapter) => {
    setEditingAdapter(adapter)
    // 初始化表单值
    const initialValues: Record<string, string> = {}
    if (adapter.config_schema) {
      Object.keys(adapter.config_schema).forEach(key => {
        const value = adapter.config_values?.[key]
        // 如果是掩码密码，显示为空让用户重新输入
        initialValues[key] = value === '********' ? '' : (value || adapter.config_schema[key].default || '')
      })
    }
    setConfigForm(initialValues)
    setSaveSuccess(false)
  }

  const closeConfigModal = () => {
    setEditingAdapter(null)
    setConfigForm({})
  }

  const handleSaveConfig = () => {
    if (!editingAdapter) return
    saveConfigMutation.mutate({
      adapterName: editingAdapter.name,
      config: configForm
    })
  }

  const getConfiguredCount = (adapter: Adapter) => {
    if (!adapter.config_schema || !adapter.config_values) return 0
    let count = 0
    Object.keys(adapter.config_schema).forEach(key => {
      const value = adapter.config_values[key]
      const isConfigured = adapter.config_values[`_${key}_configured`]
      if (value && value !== '' || isConfigured) count++
    })
    return count
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">OJ 适配器注册表</h2>
          <p className="text-slate-500">查看和配置 OJ 平台适配器</p>
        </div>
        <Button
          onClick={() => refetch()}
          disabled={isLoading}
          icon={RefreshCw}
          variant="secondary"
        >
          刷新
        </Button>
      </div>

      {/* System Status Banner */}
      <div className={`border rounded-xl p-4 ${
        adapters.length > 0 
          ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200' 
          : 'bg-gradient-to-r from-slate-50 to-gray-50 border-slate-200'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${adapters.length > 0 ? 'bg-green-500 animate-pulse' : 'bg-slate-400'}`}></div>
            <div>
              <p className="font-bold text-slate-800">
                {isLoading ? '加载中...' : adapters.length > 0 ? '所有系统运行正常' : '未找到适配器'}
              </p>
              <p className="text-xs text-slate-600">
                已注册 {adapters.length} 个适配器
              </p>
            </div>
          </div>
          <span className={`text-xs px-2 py-1 rounded font-medium ${
            adapters.length > 0 ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'
          }`}>
            {adapters.length} 个活跃
          </span>
        </div>
      </div>

      {/* Adapters List */}
      <div className="space-y-4">
        <h3 className="font-bold text-slate-800">已注册适配器</h3>
        
        {isLoading ? (
          <Card className="p-12 text-center text-slate-400">
            加载适配器中...
          </Card>
        ) : adapters.length === 0 ? (
          <Card className="p-12 text-center text-slate-400">
            <AlertCircle size={32} className="mx-auto mb-2 opacity-50" />
            <p>无已注册的适配器</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {adapters.map((adapter) => {
              const status = adapter.status || 'unknown'
              const isOnline = status === 'online' || status === 'ready'
              const hasConfig = adapter.has_config
              const configuredCount = getConfiguredCount(adapter)
              const totalFields = Object.keys(adapter.config_schema || {}).length
              
              return (
                <Card key={adapter.name} className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-3 h-3 rounded-full ${isOnline ? 'bg-green-500' : 'bg-slate-400'}`} />
                      <div>
                        <h4 className="font-bold text-slate-700">
                          {adapter.display_name || adapter.name}
                        </h4>
                        <p className="text-xs text-slate-400">
                          {adapter.version ? `v${adapter.version}` : adapter.name}
                        </p>
                      </div>
                    </div>
                    {hasConfig && (
                      <button
                        onClick={() => openConfigModal(adapter)}
                        className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                        title="配置"
                      >
                        <Settings size={18} />
                      </button>
                    )}
                  </div>
                  
                  {/* Capabilities */}
                  {adapter.capabilities && adapter.capabilities.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {adapter.capabilities.map((cap: string) => (
                        <span
                          key={cap}
                          className="px-2 py-0.5 text-xs bg-indigo-50 text-indigo-600 rounded"
                        >
                          {getCapabilityLabel(cap)}
                        </span>
                      ))}
                    </div>
                  )}
                  
                  {/* Config Status */}
                  {hasConfig && (
                    <div className="mt-3 pt-3 border-t border-slate-100">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500">配置状态</span>
                        <span className={`px-2 py-0.5 rounded ${
                          configuredCount === totalFields 
                            ? 'bg-green-100 text-green-700' 
                            : configuredCount > 0 
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-slate-100 text-slate-600'
                        }`}>
                          {configuredCount}/{totalFields} 已配置
                        </span>
                      </div>
                    </div>
                  )}
                </Card>
              )
            })}
          </div>
        )}
      </div>

      {/* Network Status */}
      <Card className="p-6">
        <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
          <Globe size={18} className="text-cyan-600" />
          连接状态
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
            <span className="text-sm text-slate-600">API 端点</span>
            <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded font-medium">
              在线
            </span>
          </div>
          <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
            <span className="text-sm text-slate-600">WebSocket</span>
            <span className={`text-xs px-2 py-1 rounded font-medium ${
              connected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
            }`}>
              {connected ? '已连接' : '未连接'}
            </span>
          </div>
          <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
            <span className="text-sm text-slate-600">已加载适配器</span>
            <span className="text-xs px-2 py-1 bg-indigo-100 text-indigo-700 rounded font-medium">
              {adapters.length}
            </span>
          </div>
        </div>
      </Card>

      {/* Config Modal */}
      {editingAdapter && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-bold text-slate-800">
                配置 {editingAdapter.display_name || editingAdapter.name}
              </h3>
              <button
                onClick={closeConfigModal}
                className="p-1 text-slate-400 hover:text-slate-600 rounded"
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="p-4 space-y-4 overflow-y-auto max-h-[60vh]">
              {Object.entries(editingAdapter.config_schema || {}).map(([key, schema]) => {
                const isConfigured = editingAdapter.config_values?.[`_${key}_configured`]
                
                return (
                  <Input
                    key={key}
                    label={schema.label}
                    type={schema.type === 'password' ? 'password' : 'text'}
                    placeholder={isConfigured ? '(已配置，留空保持不变)' : schema.tooltip || `输入 ${schema.label}`}
                    value={configForm[key] || ''}
                    onChange={(e) => setConfigForm({ ...configForm, [key]: e.target.value })}
                    required={schema.required}
                    helperText={schema.tooltip}
                  />
                )
              })}
            </div>
            
            <div className="p-4 border-t border-slate-100 flex items-center justify-between">
              {saveSuccess ? (
                <span className="flex items-center gap-1 text-green-600 text-sm">
                  <CheckCircle size={16} /> 保存成功
                </span>
              ) : (
                <span className="text-xs text-slate-400">
                  配置将保存到本地
                </span>
              )}
              <div className="flex gap-2">
                <Button variant="secondary" onClick={closeConfigModal}>
                  取消
                </Button>
                <Button 
                  icon={Save} 
                  onClick={handleSaveConfig}
                  disabled={saveConfigMutation.isPending}
                >
                  {saveConfigMutation.isPending ? '保存中...' : '保存'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
