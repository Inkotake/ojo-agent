import { useState } from 'react'
import { X, FileText, Wand2, Loader2, Check, AlertCircle } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import apiClient from '../api/client'
import Button from './ui/Button'
import Input from './ui/Input'
import { useToast } from './ui/Toast'

interface PasteProblemDialogProps {
  isOpen: boolean
  onClose: () => void
  onCreated: (problemId: string) => void
}

interface ProblemFormData {
  customId: string
  title: string
  description: string
  inputFormat: string
  outputFormat: string
  samples: string
  constraints: string
  timeLimit: string
  memoryLimit: string
}

export default function PasteProblemDialog({ isOpen, onClose, onCreated }: PasteProblemDialogProps) {
  const toast = useToast()
  
  const [mode, setMode] = useState<'paste' | 'form'>('paste')
  const [rawText, setRawText] = useState('')
  const [formData, setFormData] = useState<ProblemFormData>({
    customId: '',
    title: '',
    description: '',
    inputFormat: '',
    outputFormat: '',
    samples: '',
    constraints: '',
    timeLimit: '1000',
    memoryLimit: '256'
  })
  
  // 解析粘贴的题面
  const parseMutation = useMutation({
    mutationFn: async (text: string) => {
      // 简单的本地解析逻辑
      const parsed: Partial<ProblemFormData> = {}
      
      // 尝试提取标题 (第一行或者带#的行)
      const lines = text.split('\n')
      const titleLine = lines.find(l => l.trim().startsWith('#') || (lines.indexOf(l) === 0 && l.trim()))
      if (titleLine) {
        parsed.title = titleLine.replace(/^#+\s*/, '').trim()
      }
      
      // 尝试提取各部分
      const sections = text.split(/(?=##?\s*(?:题目描述|问题描述|Description|输入格式|Input|输出格式|Output|样例|Sample|数据范围|Constraints))/i)
      
      for (const section of sections) {
        const lower = section.toLowerCase()
        if (lower.includes('题目描述') || lower.includes('description') || lower.includes('问题描述')) {
          parsed.description = section.replace(/^##?\s*[^\n]+\n/, '').trim()
        } else if (lower.includes('输入格式') || lower.includes('input format')) {
          parsed.inputFormat = section.replace(/^##?\s*[^\n]+\n/, '').trim()
        } else if (lower.includes('输出格式') || lower.includes('output format')) {
          parsed.outputFormat = section.replace(/^##?\s*[^\n]+\n/, '').trim()
        } else if (lower.includes('样例') || lower.includes('sample')) {
          parsed.samples = section.replace(/^##?\s*[^\n]+\n/, '').trim()
        } else if (lower.includes('数据范围') || lower.includes('constraint')) {
          parsed.constraints = section.replace(/^##?\s*[^\n]+\n/, '').trim()
        }
      }
      
      // 如果没有找到结构化内容，整体作为描述
      if (!parsed.description && !parsed.inputFormat) {
        parsed.description = text
      }
      
      return parsed
    },
    onSuccess: (parsed) => {
      setFormData(prev => ({
        ...prev,
        ...parsed
      }))
      setMode('form')
      toast.success('题面解析完成，请检查并补充信息')
    }
  })
  
  // 创建题目
  const createMutation = useMutation({
    mutationFn: async (data: ProblemFormData) => {
      const response = await apiClient.post('/api/problems/create-manual', {
        custom_id: data.customId || `manual_${Date.now()}`,
        title: data.title,
        description: data.description,
        input_format: data.inputFormat,
        output_format: data.outputFormat,
        samples: data.samples,
        constraints: data.constraints,
        time_limit: parseInt(data.timeLimit) || 1000,
        memory_limit: parseInt(data.memoryLimit) || 256
      })
      return response.data
    },
    onSuccess: (data) => {
      toast.success('题目创建成功')
      onCreated(data.problem_id || formData.customId)
      handleClose()
    },
    onError: (error: Error) => {
      toast.error(`创建失败: ${error.message}`)
    }
  })
  
  const handleParse = () => {
    if (!rawText.trim()) {
      toast.error('请粘贴题面内容')
      return
    }
    parseMutation.mutate(rawText)
  }
  
  const handleCreate = () => {
    if (!formData.title.trim()) {
      toast.error('请输入题目标题')
      return
    }
    if (!formData.description.trim()) {
      toast.error('请输入题目描述')
      return
    }
    createMutation.mutate(formData)
  }
  
  const handleClose = () => {
    setMode('paste')
    setRawText('')
    setFormData({
      customId: '',
      title: '',
      description: '',
      inputFormat: '',
      outputFormat: '',
      samples: '',
      constraints: '',
      timeLimit: '1000',
      memoryLimit: '256'
    })
    onClose()
  }
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col animate-in fade-in zoom-in duration-200">
        {/* 头部 */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <FileText size={20} className="text-indigo-600" />
            <h3 className="text-lg font-bold text-slate-800">粘贴题面创建任务</h3>
          </div>
          <button onClick={handleClose} className="p-2 hover:bg-slate-100 rounded-lg transition-colors">
            <X size={20} className="text-slate-500" />
          </button>
        </div>
        
        {/* 内容 */}
        <div className="flex-1 overflow-y-auto p-6">
          {mode === 'paste' ? (
            <div className="space-y-4">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
                <AlertCircle size={18} className="text-amber-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-amber-800">
                  <p className="font-medium">提示</p>
                  <p>直接粘贴题面内容（支持Markdown格式），系统将自动解析题目结构。</p>
                </div>
              </div>
              
              <textarea
                className="w-full h-80 p-4 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
                placeholder={`# 题目标题

## 题目描述
这是一道简单的题目...

## 输入格式
第一行输入一个整数 n...

## 输出格式
输出一行...

## 样例输入
5

## 样例输出
10

## 数据范围
1 ≤ n ≤ 10^6`}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
              />
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-start gap-2">
                <Check size={18} className="text-green-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-green-800">
                  <p className="font-medium">解析完成</p>
                  <p>请检查以下信息，可根据需要手动修改。</p>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="自定义ID"
                  placeholder="可选，如 manual_001"
                  value={formData.customId}
                  onChange={(e) => setFormData(prev => ({ ...prev, customId: e.target.value }))}
                />
                <Input
                  label="题目标题"
                  placeholder="题目标题"
                  value={formData.title}
                  onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">题目描述</label>
                <textarea
                  className="w-full h-32 p-3 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">输入格式</label>
                  <textarea
                    className="w-full h-20 p-3 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                    value={formData.inputFormat}
                    onChange={(e) => setFormData(prev => ({ ...prev, inputFormat: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">输出格式</label>
                  <textarea
                    className="w-full h-20 p-3 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                    value={formData.outputFormat}
                    onChange={(e) => setFormData(prev => ({ ...prev, outputFormat: e.target.value }))}
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">样例</label>
                <textarea
                  className="w-full h-24 p-3 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
                  placeholder="输入:&#10;5&#10;输出:&#10;10"
                  value={formData.samples}
                  onChange={(e) => setFormData(prev => ({ ...prev, samples: e.target.value }))}
                />
              </div>
              
              <div className="grid grid-cols-3 gap-4">
                <Input
                  label="时间限制 (ms)"
                  type="number"
                  value={formData.timeLimit}
                  onChange={(e) => setFormData(prev => ({ ...prev, timeLimit: e.target.value }))}
                />
                <Input
                  label="内存限制 (MB)"
                  type="number"
                  value={formData.memoryLimit}
                  onChange={(e) => setFormData(prev => ({ ...prev, memoryLimit: e.target.value }))}
                />
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">数据范围</label>
                  <input
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                    placeholder="1 ≤ n ≤ 10^6"
                    value={formData.constraints}
                    onChange={(e) => setFormData(prev => ({ ...prev, constraints: e.target.value }))}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* 底部 */}
        <div className="flex justify-between p-4 border-t border-slate-200">
          <div>
            {mode === 'form' && (
              <Button variant="ghost" onClick={() => setMode('paste')}>
                返回编辑
              </Button>
            )}
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={handleClose}>
              取消
            </Button>
            {mode === 'paste' ? (
              <Button onClick={handleParse} disabled={parseMutation.isPending || !rawText.trim()}>
                {parseMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
                解析题面
              </Button>
            ) : (
              <Button onClick={handleCreate} disabled={createMutation.isPending}>
                {createMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                创建并添加
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
