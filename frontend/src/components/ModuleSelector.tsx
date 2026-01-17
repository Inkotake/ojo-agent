import { useState } from 'react'
import { Download, Cpu, UploadCloud } from 'lucide-react'
import Toggle from './ui/Toggle'

interface ModuleConfig {
  fetch: boolean
  gen: boolean
  upload: boolean  // 上传并验证（合并了原来的upload和solve）
  solve: boolean   // 保留兼容性，但UI上不再单独显示
}

interface ModuleSelectorProps {
  value: ModuleConfig
  onChange: (config: ModuleConfig) => void
  disabled?: boolean
}

interface PresetOption {
  name: string
  config: ModuleConfig
  description: string
}

const presets: PresetOption[] = [
  {
    name: '完整流程',
    config: { fetch: true, gen: true, upload: true, solve: true },
    description: '拉取 → 生成 → 上传并验证'
  },
  {
    name: '只生成数据',
    config: { fetch: true, gen: true, upload: false, solve: false },
    description: '拉取题面并生成测试数据（不上传）'
  },
  {
    name: '上传并验证',
    config: { fetch: false, gen: false, upload: true, solve: true },
    description: '上传已生成的数据并远程验证'
  },
]

export default function ModuleSelector({ value, onChange, disabled = false }: ModuleSelectorProps) {
  const [showPresets, setShowPresets] = useState(false)
  
  const handleToggle = (key: keyof ModuleConfig) => {
    let newConfig = { ...value, [key]: !value[key] }
    
    // 上传和求解合并：开启上传时同时开启求解
    if (key === 'upload') {
      newConfig.solve = newConfig.upload
    }
    
    onChange(newConfig)
  }
  
  const applyPreset = (preset: PresetOption) => {
    onChange(preset.config)
    setShowPresets(false)
  }
  
  const modules = [
    { key: 'fetch' as const, label: '拉取题面', icon: Download, color: 'text-blue-500' },
    { key: 'gen' as const, label: '生成数据', icon: Cpu, color: 'text-purple-500' },
    { key: 'upload' as const, label: '上传并验证', icon: UploadCloud, color: 'text-green-500' },
  ]
  
  return (
    <div className="space-y-3">
      {/* 预设选择 */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-700">功能模块</span>
        <button
          type="button"
          onClick={() => setShowPresets(!showPresets)}
          className="text-xs text-indigo-600 hover:text-indigo-800"
          disabled={disabled}
        >
          {showPresets ? '收起预设' : '快速预设 ▾'}
        </button>
      </div>
      
      {/* 预设列表 */}
      {showPresets && (
        <div className="grid grid-cols-2 gap-2 p-2 bg-slate-50 rounded-lg">
          {presets.map((preset) => (
            <button
              key={preset.name}
              type="button"
              onClick={() => applyPreset(preset)}
              disabled={disabled}
              className="p-2 text-left bg-white border border-slate-200 rounded hover:border-indigo-300 hover:bg-indigo-50 transition-colors disabled:opacity-50"
            >
              <div className="text-sm font-medium text-slate-800">{preset.name}</div>
              <div className="text-xs text-slate-500">{preset.description}</div>
            </button>
          ))}
        </div>
      )}
      
      {/* 模块开关 */}
      <div className="grid grid-cols-2 gap-3">
        {modules.map(({ key, label, icon: Icon, color }) => (
          <div
            key={key}
            className={`flex items-center justify-between p-3 bg-white border rounded-lg transition-colors ${
              value[key] ? 'border-indigo-200 bg-indigo-50/50' : 'border-slate-200'
            } ${disabled ? 'opacity-50' : ''}`}
          >
            <div className="flex items-center gap-2">
              <Icon size={16} className={value[key] ? color : 'text-slate-400'} />
              <span className={`text-sm ${value[key] ? 'text-slate-800 font-medium' : 'text-slate-500'}`}>
                {label}
              </span>
            </div>
            <Toggle
              checked={value[key]}
              onChange={() => handleToggle(key)}
              disabled={disabled}
            />
          </div>
        ))}
      </div>
      
      {/* 依赖提示 */}
      {value.upload && !value.gen && (
        <p className="text-xs text-amber-600 bg-amber-50 p-2 rounded">
          ⚠️ 上传模式：将使用已存在的测试数据并远程验证
        </p>
      )}
      
      {/* 显示 solve 状态（与 upload 联动） */}
      <div className="text-xs text-slate-500 px-1">
        当前配置：拉取={value.fetch ? '✓' : '✗'} | 生成={value.gen ? '✓' : '✗'} | 上传={value.upload ? '✓' : '✗'} | 远程验证={value.solve ? '✓' : '✗'}
      </div>
    </div>
  )
}

// 导出类型
export type { ModuleConfig }
