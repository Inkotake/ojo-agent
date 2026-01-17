import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { 
  Eraser, Eye, AlertTriangle, CheckCircle, 
  Loader2, FileText
} from 'lucide-react'
import apiClient from '../api/client'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { useToast } from '../components/ui/Toast'

interface WashResult {
  problem_id: string
  field: string
  original: string
  cleaned: string
  changes: number
}

const defaultFields = [
  { key: 'description', label: '题目描述', checked: true },
  { key: 'input', label: '输入格式', checked: true },
  { key: 'output', label: '输出格式', checked: true },
  { key: 'hint', label: '提示', checked: true },
]

export default function WashToolPage() {
  const toast = useToast()
  
  const [problemIds, setProblemIds] = useState('')
  const [selectedFields, setSelectedFields] = useState<string[]>(
    defaultFields.filter(f => f.checked).map(f => f.key)
  )
  const [customWords, setCustomWords] = useState('')
  const [previewResults, setPreviewResults] = useState<WashResult[]>([])
  const [showPreview, setShowPreview] = useState(false)
  
  // 获取默认敏感词
  const { data: defaultWordsData } = useQuery({
    queryKey: ['sensitive-words'],
    queryFn: async () => {
      const response = await apiClient.get('/api/wash/sensitive-words')
      return response.data
    }
  })
  
  const defaultWords: string[] = defaultWordsData?.words || []
  
  // 预览清洗
  const previewMutation = useMutation({
    mutationFn: async () => {
      const ids = problemIds.split(/[\n,]/).map(s => s.trim()).filter(s => s)
      const words = customWords 
        ? customWords.split(/[\n,]/).map(s => s.trim()).filter(s => s)
        : undefined
      
      const response = await apiClient.post('/api/wash/preview', {
        problem_ids: ids,
        fields: selectedFields,
        sensitive_words: words
      })
      return response.data
    },
    onSuccess: (data) => {
      setPreviewResults(data.results || [])
      setShowPreview(true)
      if (data.total_changes > 0) {
        toast.success(`发现 ${data.total_changes} 处需要清洗`)
      } else {
        toast.info('未发现需要清洗的内容')
      }
    },
    onError: (error: Error) => {
      toast.error(`预览失败: ${error.message}`)
    }
  })
  
  // 执行清洗
  const executeMutation = useMutation({
    mutationFn: async () => {
      const ids = problemIds.split(/[\n,]/).map(s => s.trim()).filter(s => s)
      const words = customWords 
        ? customWords.split(/[\n,]/).map(s => s.trim()).filter(s => s)
        : undefined
      
      const response = await apiClient.post('/api/wash/execute', {
        problem_ids: ids,
        fields: selectedFields,
        sensitive_words: words,
        dry_run: false
      })
      return response.data
    },
    onSuccess: () => {
      toast.success('清洗任务已开始执行')
      setShowPreview(false)
      setPreviewResults([])
    },
    onError: (error: Error) => {
      toast.error(`执行失败: ${error.message}`)
    }
  })
  
  const toggleField = (field: string) => {
    setSelectedFields(prev => 
      prev.includes(field) 
        ? prev.filter(f => f !== field)
        : [...prev, field]
    )
  }
  
  const getParsedIds = () => {
    return problemIds.split(/[\n,]/).map(s => s.trim()).filter(s => s)
  }
  
  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* 头部 */}
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">文本清洗工具</h2>
          <p className="text-slate-500">批量清洗SHSOJ题目中的敏感信息</p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧配置 */}
        <div className="lg:col-span-1 space-y-4">
          {/* 题目ID输入 */}
          <Card className="p-4">
            <h3 className="font-bold text-slate-700 mb-3 flex items-center gap-2">
              <FileText size={16} />
              题目ID
            </h3>
            <textarea
              className="w-full h-32 p-3 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
              placeholder="每行输入一个题目ID&#10;1001&#10;1002&#10;1003"
              value={problemIds}
              onChange={(e) => setProblemIds(e.target.value)}
            />
            <p className="text-xs text-slate-400 mt-2">
              已输入 {getParsedIds().length} 个题目
            </p>
          </Card>
          
          {/* 字段选择 */}
          <Card className="p-4">
            <h3 className="font-bold text-slate-700 mb-3">清洗字段</h3>
            <div className="space-y-2">
              {defaultFields.map(field => (
                <label key={field.key} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedFields.includes(field.key)}
                    onChange={() => toggleField(field.key)}
                    className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-sm text-slate-700">{field.label}</span>
                </label>
              ))}
            </div>
          </Card>
          
          {/* 敏感词配置 */}
          <Card className="p-4">
            <h3 className="font-bold text-slate-700 mb-3">敏感词</h3>
            <div className="mb-3">
              <div className="flex flex-wrap gap-1">
                {defaultWords.slice(0, 10).map(word => (
                  <span key={word} className="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded">
                    {word}
                  </span>
                ))}
                {defaultWords.length > 10 && (
                  <span className="px-2 py-0.5 text-slate-400 text-xs">
                    +{defaultWords.length - 10} 更多
                  </span>
                )}
              </div>
            </div>
            <textarea
              className="w-full h-20 p-2 border border-slate-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
              placeholder="自定义敏感词（可选）&#10;每行一个"
              value={customWords}
              onChange={(e) => setCustomWords(e.target.value)}
            />
          </Card>
          
          {/* 操作按钮 */}
          <div className="flex gap-2">
            <Button 
              className="flex-1"
              variant="secondary"
              onClick={() => previewMutation.mutate()}
              disabled={previewMutation.isPending || getParsedIds().length === 0}
            >
              {previewMutation.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Eye size={16} />
              )}
              预览
            </Button>
            <Button 
              className="flex-1"
              onClick={() => executeMutation.mutate()}
              disabled={executeMutation.isPending || getParsedIds().length === 0}
            >
              {executeMutation.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Eraser size={16} />
              )}
              执行清洗
            </Button>
          </div>
        </div>
        
        {/* 右侧预览结果 */}
        <div className="lg:col-span-2">
          <Card className="p-4 h-full">
            <h3 className="font-bold text-slate-700 mb-4 flex items-center gap-2">
              <Eye size={16} />
              预览结果
            </h3>
            
            {!showPreview ? (
              <div className="flex flex-col items-center justify-center h-64 text-slate-400">
                <Eraser size={48} className="mb-3 opacity-30" />
                <p>点击"预览"查看清洗效果</p>
              </div>
            ) : previewResults.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-green-600">
                <CheckCircle size={48} className="mb-3" />
                <p className="font-medium">未发现需要清洗的内容</p>
                <p className="text-sm text-slate-400 mt-1">所选题目中没有匹配的敏感词</p>
              </div>
            ) : (
              <div className="space-y-4 max-h-[600px] overflow-y-auto">
                {previewResults.map((result, index) => (
                  <div key={index} className="border border-slate-200 rounded-lg overflow-hidden">
                    <div className="bg-slate-50 px-4 py-2 flex items-center justify-between">
                      <span className="font-mono text-sm text-slate-700">
                        题目 {result.problem_id} - {result.field}
                      </span>
                      <span className="text-xs text-amber-600 bg-amber-100 px-2 py-0.5 rounded">
                        {result.changes} 处修改
                      </span>
                    </div>
                    <div className="grid grid-cols-2 divide-x divide-slate-200">
                      <div className="p-3">
                        <div className="text-xs text-slate-400 mb-1">原文</div>
                        <div className="text-sm text-slate-600 whitespace-pre-wrap break-words">
                          {result.original}
                        </div>
                      </div>
                      <div className="p-3 bg-green-50/50">
                        <div className="text-xs text-green-600 mb-1">清洗后</div>
                        <div className="text-sm text-slate-600 whitespace-pre-wrap break-words">
                          {result.cleaned}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
      
      {/* 警告提示 */}
      <Card className="p-4 border-amber-200 bg-amber-50">
        <div className="flex items-start gap-3">
          <AlertTriangle size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-amber-800">注意事项</h4>
            <ul className="text-sm text-amber-700 mt-1 space-y-1">
              <li>• 清洗操作将直接修改OJ平台上的题目内容，请谨慎操作</li>
              <li>• 建议先使用"预览"功能确认清洗效果</li>
              <li>• 批量清洗会有速率限制，处理大量题目需要一定时间</li>
              <li>• 此功能仅管理员可用</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  )
}
