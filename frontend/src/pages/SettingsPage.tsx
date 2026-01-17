import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Save, Settings as SettingsIcon, Info, Globe, Lock } from 'lucide-react'
import { Link } from 'react-router-dom'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Toggle from '../components/ui/Toggle'
import { useToast } from '../components/ui/Toast'
import apiClient from '../api/client'

export default function SettingsPage() {
  const toast = useToast()
  
  // Password change state
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  
  const [configs, setConfigs] = useState({
    autoDownload: false,
    keepCache: true,
    // NOTE: LLM Provider 选择已移至任务创建界面（TasksPage）
    // NOTE: 并发控制已移至并发管理页面（ConcurrencyPage）
  })

  // Fetch config from backend
  const { data: configData, isLoading } = useQuery({
    queryKey: ['user-config'],
    queryFn: async () => {
      const response = await apiClient.get('/api/config')
      return response.data.config
    },
  })

  // Sync backend config to local state
  useEffect(() => {
    if (configData) {
      setConfigs(prev => ({
        ...prev,
        ...configData,
      }))
    }
  }, [configData])

  const [isSaving, setIsSaving] = useState(false)
  
  // Change password mutation
  const changePasswordMutation = useMutation({
    mutationFn: async (data: { old_password: string; new_password: string }) => {
      await apiClient.post('/api/auth/change-password', data)
    },
    onSuccess: () => {
      toast.success('密码修改成功')
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '密码修改失败')
    }
  })

  const handleChangePassword = () => {
    if (!oldPassword || !newPassword || !confirmPassword) {
      toast.error('请填写所有密码字段')
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error('两次输入的新密码不一致')
      return
    }
    if (newPassword.length < 6) {
      toast.error('新密码长度至少6个字符')
      return
    }
    changePasswordMutation.mutate({ old_password: oldPassword, new_password: newPassword })
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      // Save config items
      for (const [key, value] of Object.entries(configs)) {
        await apiClient.post('/api/config', { scope: 'user', key, value })
      }
      toast.success('设置已保存！更改将在下一个任务中生效。')
    } catch (error) {
      toast.error('保存失败，请重试')
      console.error('Save config error:', error)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">用户设置</h2>
          <p className="text-slate-500">配置应用偏好和系统选项</p>
        </div>
        <Button icon={Save} onClick={handleSave} disabled={isLoading || isSaving}>
          {isSaving ? '保存中...' : '保存设置'}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 偏好设置 */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-2 mb-4">
            <SettingsIcon className="text-indigo-600" size={20} />
            <h3 className="font-bold text-slate-800">偏好设置</h3>
          </div>
          
          <div className="space-y-4">
            <Toggle
              label="自动下载工作区"
              description="任务完成后自动下载代码和数据"
              checked={configs.autoDownload}
              onChange={(checked) => setConfigs({ ...configs, autoDownload: checked })}
            />
            
            <Toggle
              label="保留本地缓存"
              description="在 workspace/ 目录中保留最近的任务"
              checked={configs.keepCache}
              onChange={(checked) => setConfigs({ ...configs, keepCache: checked })}
            />
            
            <div className="bg-blue-50 p-4 rounded-lg border border-blue-100">
              <div className="flex items-start gap-3">
                <Info className="text-blue-600 mt-0.5" size={18} />
                <div>
                  <h4 className="text-sm font-bold text-blue-800 mb-1">LLM 配置已迁移</h4>
                  <p className="text-xs text-blue-600 mb-3">
                    LLM 提供商选择现在在<strong>任务创建界面</strong>进行，每个任务可以选择不同的 LLM。
                    并发控制已移至<strong>并发管理</strong>页面统一配置。
                  </p>
                  <div className="flex gap-2">
                    <Link 
                      to="/tasks"
                      className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:text-blue-800"
                    >
                      前往任务页面 →
                    </Link>
                    <Link 
                      to="/concurrency"
                      className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:text-blue-800"
                    >
                      前往并发管理 →
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* 适配器配置提示 */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-2 mb-4">
            <Globe className="text-indigo-600" size={20} />
            <h3 className="font-bold text-slate-800">OJ 平台配置</h3>
          </div>
          
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-100">
            <div className="flex items-start gap-3">
              <Info className="text-blue-600 mt-0.5" size={18} />
              <div>
                <h4 className="text-sm font-bold text-blue-800 mb-1">适配器配置已迁移</h4>
                <p className="text-xs text-blue-600 mb-3">
                  OJ 平台的认证信息（Cookie、Token 等）现在在适配器页面中配置。
                  每个适配器都有自己的配置表单。
                </p>
                <Link 
                  to="/adapters"
                  className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:text-blue-800"
                >
                  前往适配器页面配置 →
                </Link>
              </div>
            </div>
          </div>
          
          <div className="mt-4 p-4 bg-slate-50 rounded-lg">
            <h4 className="text-sm font-bold text-slate-700 mb-2">支持的适配器</h4>
            <div className="space-y-2 text-xs text-slate-600">
              <div className="flex justify-between">
                <span>SHSOJ</span>
                <span className="text-slate-400">用户名/密码认证</span>
              </div>
              <div className="flex justify-between">
                <span>HydroOJ</span>
                <span className="text-slate-400">Cookie 认证</span>
              </div>
              <div className="flex justify-between">
                <span>Codeforces</span>
                <span className="text-slate-400">无需认证（公开API）</span>
              </div>
              <div className="flex justify-between">
                <span>洛谷</span>
                <span className="text-slate-400">无需认证</span>
              </div>
            </div>
          </div>
        </Card>
        
        {/* 密码修改 */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-2 mb-4">
            <Lock className="text-indigo-600" size={20} />
            <h3 className="font-bold text-slate-800">修改密码</h3>
          </div>
          
          <div className="space-y-4">
            <Input
              label="当前密码"
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              placeholder="输入当前密码"
            />
            
            <Input
              label="新密码"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="至少6个字符"
            />
            
            <Input
              label="确认新密码"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="再次输入新密码"
            />
            
            <Button 
              onClick={handleChangePassword} 
              disabled={changePasswordMutation.isPending}
              className="w-full"
            >
              {changePasswordMutation.isPending ? '修改中...' : '修改密码'}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  )
}

