import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Save, Brain, Key, Thermometer, Globe,
  Eye, EyeOff, RefreshCw, CheckCircle, AlertTriangle,
  Shield, Clock, Loader2
} from 'lucide-react'
import apiClient from '../api/client'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { useToast } from '../components/ui/Toast'

// Provider 定义（从后端动态获取）
interface ProviderDefinition {
  id: string
  name: string
  description: string
  api_key_field: string
  api_url_field: string
  model_field: string
  default_api_url: string
  default_model: string
  capabilities: string[]
  user_selectable: boolean
}

interface LLMConfig {
  [key: string]: string | number | boolean | ProviderDefinition[]
  temperature_generation: number
  temperature_solution: number
  request_timeout_minutes: number
  proxy_enabled: boolean
  http_proxy: string
  https_proxy: string
  verify_ssl: boolean
  providers: ProviderDefinition[]
}

// 默认配置
const DEFAULT_CONFIG: Partial<LLMConfig> = {
  temperature_generation: 0.7,
  temperature_solution: 0.7,
  request_timeout_minutes: 5,
  proxy_enabled: false,
  http_proxy: '',
  https_proxy: '',
  verify_ssl: true,
  providers: []
}

// 自动保存防抖延迟
const AUTOSAVE_DELAY = 1500

export default function LLMConfigPage() {
  const toast = useToast()
  const queryClient = useQueryClient()

  const [config, setConfig] = useState<LLMConfig>(DEFAULT_CONFIG as LLMConfig)
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})
  const [testResults, setTestResults] = useState<Record<string, 'success' | 'error' | 'testing' | null>>({})
  const [savingFields, setSavingFields] = useState<Set<string>>(new Set())
  const [savedFields, setSavedFields] = useState<Set<string>>(new Set())
  
  // 防抖保存的定时器
  const saveTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  // 获取配置
  const { data: configData, isLoading } = useQuery({
    queryKey: ['llm-config-admin'],
    queryFn: async () => {
      const response = await apiClient.get('/api/admin/llm-config')
      return response.data.config
    }
  })

  // 从后端数据中提取 providers
  const providers = useMemo<ProviderDefinition[]>(() => {
    return configData?.providers || []
  }, [configData])

  useEffect(() => {
    if (configData) {
      setConfig(prev => ({
        ...prev,
        ...configData,
      }))
      // 管理员默认显示明文 API Key
      const initialShowKeys: Record<string, boolean> = {}
      for (const provider of (configData.providers || [])) {
        initialShowKeys[provider.api_key_field] = true
      }
      setShowKeys(initialShowKeys)
    }
  }, [configData])

  // 单字段保存
  const saveField = useCallback(async (key: string, value: string | number | boolean) => {
    if (key.endsWith('_configured') || key === 'providers') return
    
    setSavingFields(prev => new Set(prev).add(key))
    setSavedFields(prev => {
      const next = new Set(prev)
      next.delete(key)
      return next
    })
    
    try {
      await apiClient.post('/api/config', { scope: 'user', key, value })
      setSavedFields(prev => new Set(prev).add(key))
      
      // 3秒后移除已保存标记
      setTimeout(() => {
        setSavedFields(prev => {
          const next = new Set(prev)
          next.delete(key)
          return next
        })
      }, 3000)
      
      // 刷新配置
      queryClient.invalidateQueries({ queryKey: ['llm-config-admin'] })
      
      // 如果是 API Key，自动进行快速检查（不发送真实请求）
      // 匹配所有包含 "api_key" 的字段
      if (key.includes('api_key') && value) {
        // 根据字段名推断 provider ID
        let providerId = 'deepseek'
        if (key.includes('siliconflow')) {
          providerId = 'siliconflow'
        } else if (key.includes('openai')) {
          providerId = 'openai'
        } else if (key.includes('deepseek') && !key.includes('siliconflow')) {
          providerId = 'deepseek'
        }
        // 延迟一点再测试，快速检查模式（full_test=false）
        setTimeout(() => testConnection(providerId, false), 500)
      }
    } catch (error) {
      toast.error(`保存 ${key} 失败`)
    } finally {
      setSavingFields(prev => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    }
  }, [queryClient, toast])

  // 防抖自动保存
  const debouncedSave = useCallback((key: string, value: string | number | boolean) => {
    // 清除之前的定时器
    if (saveTimersRef.current[key]) {
      clearTimeout(saveTimersRef.current[key])
    }
    
    // 设置新的定时器
    saveTimersRef.current[key] = setTimeout(() => {
      saveField(key, value)
      delete saveTimersRef.current[key]
    }, AUTOSAVE_DELAY)
  }, [saveField])

  // 测试 API 连接
  // fullTest: true = 发送真实请求（手动点击测试按钮）
  // fullTest: false = 快速检查（自动保存后触发）
  const testConnection = async (providerId: string, fullTest: boolean = false) => {
    setTestResults(prev => ({ ...prev, [providerId]: 'testing' }))

    try {
      const response = await apiClient.post('/api/llm/test', { 
        provider: providerId,
        full_test: fullTest
      })
      if (response.data.success) {
        setTestResults(prev => ({ ...prev, [providerId]: 'success' }))
        if (fullTest && response.data.response) {
          toast.success(`${providerId} 连接正常，响应: ${response.data.response.slice(0, 50)}`)
        } else {
          toast.success(`${providerId} 配置有效`)
        }
      } else {
        throw new Error(response.data.error)
      }
    } catch (error) {
      setTestResults(prev => ({ ...prev, [providerId]: 'error' }))
      toast.error(`${providerId} 测试失败: ${(error as Error).message}`)
    }
  }

  const toggleShowKey = (key: string) => {
    setShowKeys(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const updateConfig = (key: string, value: string | number | boolean, autoSave = true) => {
    setConfig(prev => ({ ...prev, [key]: value }))
    if (autoSave) {
      debouncedSave(key, value)
    }
  }

  // 立即保存（用于失焦时）
  const saveImmediately = (key: string, value: string | number | boolean) => {
    // 清除防抖定时器
    if (saveTimersRef.current[key]) {
      clearTimeout(saveTimersRef.current[key])
      delete saveTimersRef.current[key]
    }
    saveField(key, value)
  }

  // 获取字段状态图标
  const getFieldStatus = (key: string) => {
    if (savingFields.has(key)) {
      return <Loader2 size={14} className="animate-spin text-blue-500" />
    }
    if (savedFields.has(key)) {
      return <CheckCircle size={14} className="text-green-500" />
    }
    return null
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw size={32} className="animate-spin text-indigo-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* 说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <Save size={18} className="text-blue-600" />
          <h4 className="font-semibold text-blue-900">自动保存模式</h4>
        </div>
        <p className="text-sm text-blue-700">
          修改配置后会<strong>自动保存</strong>，API Key 保存后会<strong>自动测试连接</strong>。
          所有用户共用此配置，仅管理员可修改。
        </p>
      </div>

      {/* 头部 */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">LLM 全局配置</h2>
          <p className="text-slate-500">配置大语言模型提供商和参数</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {/* 动态渲染每个 Provider 的配置 */}
        {providers.map((provider) => {
          const apiKeyField = provider.api_key_field
          const apiKeyValue = config[apiKeyField] as string || ''
          const isConfigured = config[`${apiKeyField}_configured`] as boolean
          const apiUrlValue = config[provider.api_url_field] as string || provider.default_api_url
          const modelValue = config[provider.model_field] as string || provider.default_model

          return (
            <Card key={provider.id} className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    isConfigured ? 'bg-green-100' : 'bg-slate-100'
                  }`}>
                    <Brain size={20} className={isConfigured ? 'text-green-600' : 'text-slate-400'} />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-800">{provider.name}</h3>
                    <p className="text-xs text-slate-500">{provider.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {testResults[provider.id] === 'testing' && (
                    <span className="flex items-center gap-1 text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded-full">
                      <Loader2 size={12} className="animate-spin" />
                      测试中
                    </span>
                  )}
                  {testResults[provider.id] === 'success' && (
                    <span className="flex items-center gap-1 text-xs px-2 py-1 bg-green-100 text-green-700 rounded-full">
                      <CheckCircle size={12} />
                      连接正常
                    </span>
                  )}
                  {testResults[provider.id] === 'error' && (
                    <span className="flex items-center gap-1 text-xs px-2 py-1 bg-red-100 text-red-700 rounded-full">
                      <AlertTriangle size={12} />
                      连接失败
                    </span>
                  )}
                  {isConfigured && !testResults[provider.id] && (
                    <span className="flex items-center gap-1 text-xs px-2 py-1 bg-green-100 text-green-700 rounded-full">
                      <CheckCircle size={12} />
                      已配置
                    </span>
                  )}
                  {!isConfigured && !testResults[provider.id] && (
                    <span className="text-xs px-2 py-1 bg-slate-100 text-slate-500 rounded-full">
                      未配置
                    </span>
                  )}
                  {!provider.user_selectable && (
                    <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded-full">
                      {provider.capabilities.join(', ').toUpperCase()} 专用
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* API Key */}
                <div className="md:col-span-2">
                  <label className="text-sm font-medium text-slate-700 mb-1 flex items-center gap-2">
                    <Key size={14} />
                    API Key
                    {getFieldStatus(apiKeyField)}
                  </label>
                  <div className="flex gap-2">
                    <div className="relative flex-1 min-w-0">
                      <input
                        type={showKeys[apiKeyField] ? 'text' : 'password'}
                        className="w-full px-3 py-2 pr-10 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-sm bg-white"
                        value={apiKeyValue}
                        onChange={(e) => updateConfig(apiKeyField, e.target.value)}
                        onBlur={(e) => e.target.value && saveImmediately(apiKeyField, e.target.value)}
                        placeholder={isConfigured ? '已配置，输入新密钥覆盖...' : 'sk-...'}
                      />
                      <button
                        type="button"
                        onClick={() => toggleShowKey(apiKeyField)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                        title={showKeys[apiKeyField] ? '隐藏' : '显示'}
                      >
                        {showKeys[apiKeyField] ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                    <span title="发送真实请求测试连通性">
                      <Button
                        variant="secondary"
                        onClick={() => testConnection(provider.id, true)}
                        disabled={testResults[provider.id] === 'testing'}
                        className="px-3 flex-shrink-0"
                      >
                        {testResults[provider.id] === 'testing' ? (
                          <RefreshCw size={16} className="animate-spin" />
                        ) : (
                          '测试'
                        )}
                      </Button>
                    </span>
                  </div>
                </div>

                {/* API URL */}
                <div>
                  <label className="text-sm font-medium text-slate-700 mb-1 flex items-center gap-2">
                    <Globe size={14} />
                    API 地址
                    {getFieldStatus(provider.api_url_field)}
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                    value={apiUrlValue}
                    onChange={(e) => updateConfig(provider.api_url_field, e.target.value)}
                    onBlur={(e) => saveImmediately(provider.api_url_field, e.target.value)}
                    placeholder={provider.default_api_url}
                  />
                </div>

                {/* Model */}
                <div>
                  <label className="text-sm font-medium text-slate-700 mb-1 flex items-center gap-2">
                    <Brain size={14} />
                    模型名称
                    {getFieldStatus(provider.model_field)}
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                    value={modelValue}
                    onChange={(e) => updateConfig(provider.model_field, e.target.value)}
                    onBlur={(e) => saveImmediately(provider.model_field, e.target.value)}
                    placeholder={provider.default_model}
                  />
                </div>
              </div>
            </Card>
          )
        })}

        {/* 参数配置 */}
        <Card className="p-6">
          <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Thermometer size={18} className="text-indigo-600" />
            生成参数
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 flex justify-between items-center">
                <span className="flex items-center gap-2">
                  生成 Temperature
                  {getFieldStatus('temperature_generation')}
                </span>
                <span className="text-indigo-600">{config.temperature_generation}</span>
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={config.temperature_generation}
                onChange={(e) => updateConfig('temperature_generation', parseFloat(e.target.value))}
                onMouseUp={(e) => saveImmediately('temperature_generation', parseFloat((e.target as HTMLInputElement).value))}
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
              />
              <div className="flex justify-between text-xs text-slate-400 mt-1">
                <span>精确</span>
                <span>创造性</span>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 flex justify-between items-center">
                <span className="flex items-center gap-2">
                  求解 Temperature
                  {getFieldStatus('temperature_solution')}
                </span>
                <span className="text-indigo-600">{config.temperature_solution}</span>
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={config.temperature_solution}
                onChange={(e) => updateConfig('temperature_solution', parseFloat(e.target.value))}
                onMouseUp={(e) => saveImmediately('temperature_solution', parseFloat((e.target as HTMLInputElement).value))}
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
              />
              <div className="flex justify-between text-xs text-slate-400 mt-1">
                <span>精确</span>
                <span>创造性</span>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 flex items-center gap-2">
                <Clock size={14} />
                超时时间 (分钟)
                {getFieldStatus('request_timeout_minutes')}
              </label>
              <input
                type="number"
                min="1"
                max="60"
                value={config.request_timeout_minutes}
                onChange={(e) => updateConfig('request_timeout_minutes', parseInt(e.target.value) || 5)}
                onBlur={(e) => saveImmediately('request_timeout_minutes', parseInt(e.target.value) || 5)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
        </Card>

        {/* 网络配置 */}
        <Card className="p-6">
          <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Globe size={18} className="text-indigo-600" />
            网络配置
          </h3>

          <div className="space-y-4">
            <label className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg cursor-pointer">
              <input
                type="checkbox"
                checked={config.proxy_enabled}
                onChange={(e) => {
                  updateConfig('proxy_enabled', e.target.checked, false)
                  saveImmediately('proxy_enabled', e.target.checked)
                }}
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <div className="flex items-center gap-2">
                <div className="font-medium text-slate-700">启用代理</div>
                {getFieldStatus('proxy_enabled')}
              </div>
            </label>

            {config.proxy_enabled && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-slate-700 mb-1 flex items-center gap-2">
                    HTTP 代理地址
                    {getFieldStatus('http_proxy')}
                  </label>
                  <input
                    type="text"
                    placeholder="http://127.0.0.1:7890"
                    value={config.http_proxy}
                    onChange={(e) => updateConfig('http_proxy', e.target.value)}
                    onBlur={(e) => saveImmediately('http_proxy', e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700 mb-1 flex items-center gap-2">
                    HTTPS 代理地址
                    {getFieldStatus('https_proxy')}
                  </label>
                  <input
                    type="text"
                    placeholder="http://127.0.0.1:7890"
                    value={config.https_proxy}
                    onChange={(e) => updateConfig('https_proxy', e.target.value)}
                    onBlur={(e) => saveImmediately('https_proxy', e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>
            )}

            <label className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg cursor-pointer">
              <input
                type="checkbox"
                checked={config.verify_ssl}
                onChange={(e) => {
                  updateConfig('verify_ssl', e.target.checked, false)
                  saveImmediately('verify_ssl', e.target.checked)
                }}
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <div className="flex items-center gap-2">
                <Shield size={16} className="text-slate-500" />
                <div>
                  <div className="font-medium text-slate-700 flex items-center gap-2">
                    SSL证书验证
                    {getFieldStatus('verify_ssl')}
                  </div>
                  <div className="text-xs text-slate-400">验证HTTPS证书（建议开启）</div>
                </div>
              </div>
            </label>
          </div>
        </Card>

        {/* 说明 */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <h4 className="font-semibold text-slate-700 mb-2">📋 配置说明</h4>
          <ul className="text-sm text-slate-600 space-y-1">
            <li>• <strong>DeepSeek</strong>：推荐用于数据生成和代码求解，推理能力强</li>
            <li>• <strong>OpenAI 兼容</strong>：支持任何兼容 OpenAI API 格式的服务</li>
            <li>• <strong>硅基流动</strong>：专用于 OCR 图片识别，自动使用，无需手动选择</li>
            <li>• 用户在任务创建界面选择使用哪个 LLM（DeepSeek 或 OpenAI 兼容）</li>
            <li>• 并发控制请前往「并发管理」页面配置</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
