import { useState, useEffect, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { X, Search, Plus, Loader2, Tag, ChevronDown, ChevronRight } from 'lucide-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import Button from './ui/Button'
import { useToast } from './ui/Toast'

interface Problem {
  id: string
  title?: string
  url: string
  source: string
}

interface TagInfo {
  id: number
  name: string
  rank: number
  classification: string
  classification_id?: number
}

interface TagClassification {
  id: number
  name: string
  tags: TagInfo[]
}

interface TagGroup {
  id: number
  name: string
  classifications: TagClassification[]
}

interface BatchAddDialogProps {
  isOpen: boolean
  onClose: () => void
  onAdd: (problemUrls: string[]) => void
}

export default function BatchAddDialog({ isOpen, onClose, onAdd }: BatchAddDialogProps) {
  const toast = useToast()
  
  const [fetchedProblems, setFetchedProblems] = useState<Problem[]>([])
  const [selectedProblems, setSelectedProblems] = useState<Set<string>>(new Set())
  
  // 标签相关状态
  const [tagSearch, setTagSearch] = useState('')
  const [selectedTag, setSelectedTag] = useState<TagInfo | null>(null)
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set())
  const [expandedClassifications, setExpandedClassifications] = useState<Set<number>>(new Set())
  
  // 获取所有标签
  const { data: tagsData, isLoading: tagsLoading } = useQuery({
    queryKey: ['aicoders-tags'],
    queryFn: async () => {
      const response = await apiClient.get('/api/problems/tags')
      return response.data as { groups: TagGroup[], total_tags: number }
    },
    enabled: isOpen,
    staleTime: 5 * 60 * 1000  // 5分钟缓存
  })
  
  // 过滤标签
  const filteredGroups = useMemo(() => {
    if (!tagsData?.groups) return []
    if (!tagSearch.trim()) return tagsData.groups
    
    const search = tagSearch.toLowerCase()
    return tagsData.groups.map(group => ({
      ...group,
      classifications: group.classifications.map(cls => ({
        ...cls,
        tags: cls.tags.filter(tag => 
          tag.name.toLowerCase().includes(search)
        )
      })).filter(cls => cls.tags.length > 0)
    })).filter(group => group.classifications.length > 0)
  }, [tagsData?.groups, tagSearch])
  
  // 按标签获取题目
  const fetchByTagMutation = useMutation({
    mutationFn: async (tag: TagInfo) => {
      const response = await apiClient.get('/api/problems/by-tag-aicoders', {
        params: { tag_id: tag.id, tag_name: tag.name, limit: 200 }
      })
      return response.data.problems as Problem[]
    },
    onSuccess: (problems) => {
      setFetchedProblems(problems)
      setSelectedProblems(new Set<string>())  // 默认不选
      toast.success(`获取到 ${problems.length} 道题目`)
    },
    onError: (error: Error) => {
      toast.error(`获取失败: ${error.message}`)
    }
  })
  
  const handleSelectTag = (tag: TagInfo) => {
    setSelectedTag(tag)
    fetchByTagMutation.mutate(tag)
  }
  
  const toggleGroup = (groupId: number) => {
    const next = new Set(expandedGroups)
    if (next.has(groupId)) next.delete(groupId)
    else next.add(groupId)
    setExpandedGroups(next)
  }
  
  const toggleClassification = (classId: number) => {
    const next = new Set(expandedClassifications)
    if (next.has(classId)) next.delete(classId)
    else next.add(classId)
    setExpandedClassifications(next)
  }
  
  const handleToggleSelect = (id: string) => {
    setSelectedProblems(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }
  
  // 搜索时自动展开所有分组
  useEffect(() => {
    if (tagSearch.trim() && tagsData?.groups) {
      setExpandedGroups(new Set(tagsData.groups.map(g => g.id)))
      const allClassIds = tagsData.groups.flatMap(g => g.classifications.map(c => c.id))
      setExpandedClassifications(new Set(allClassIds))
    }
  }, [tagSearch, tagsData?.groups])
  
  // 防止滚动穿透：弹窗打开时禁用body滚动
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])
  
  const handleSelectAll = () => {
    setSelectedProblems(new Set(fetchedProblems.map(p => p.id)))
  }
  
  const handleAdd = () => {
    if (selectedProblems.size === 0) {
      toast.error('请选择至少一道题目')
      return
    }
    
    // 根据选中的ID获取对应的URL
    const urlsToAdd = fetchedProblems
      .filter(p => selectedProblems.has(p.id))
      .map(p => p.url)
    
    onAdd(urlsToAdd)
    toast.success(`已添加 ${urlsToAdd.length} 道题目`)
    handleClose()
  }
  
  const handleClose = () => {
    setFetchedProblems([])
    setSelectedProblems(new Set())
    setTagSearch('')
    setSelectedTag(null)
    onClose()
  }
  
  if (!isOpen) return null
  
  return createPortal(
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onWheel={(e) => e.stopPropagation()}
      onTouchMove={(e) => e.stopPropagation()}
    >
      <div 
        className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col animate-in fade-in zoom-in duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <h3 className="text-lg font-bold text-slate-800">
            批量添加题目
            {selectedTag && (
              <span className="ml-2 text-sm font-normal text-indigo-600">
                - 标签: {selectedTag.name}
              </span>
            )}
          </h3>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X size={20} className="text-slate-500" />
          </button>
        </div>
        
        {/* 标签模式 - 左右分栏 */}
        {(
          <div className="flex-1 flex overflow-hidden">
            {/* 左侧：标签选择 */}
            <div className="w-1/2 border-r border-slate-100 flex flex-col">
              {/* 搜索框 */}
              <div className="p-3 border-b border-slate-100">
                <div className="relative">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    placeholder="搜索标签..."
                    value={tagSearch}
                    onChange={(e) => setTagSearch(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                {tagsData && (
                  <div className="mt-2 text-xs text-slate-500">
                    共 {tagsData.total_tags} 个标签
                  </div>
                )}
              </div>
              
              {/* 标签列表 */}
              <div className="flex-1 overflow-y-auto p-2">
                {tagsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 size={24} className="animate-spin text-indigo-500" />
                    <span className="ml-2 text-slate-500">加载标签中...</span>
                  </div>
                ) : filteredGroups.length === 0 ? (
                  <div className="text-center py-8 text-slate-400">
                    {tagSearch ? '未找到匹配的标签' : '暂无标签数据'}
                  </div>
                ) : (
                  <div className="space-y-1">
                    {filteredGroups.map(group => (
                      <div key={group.id} className="rounded-lg overflow-hidden">
                        {/* 分组标题 */}
                        <button
                          onClick={() => toggleGroup(group.id)}
                          className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-700 bg-slate-50 hover:bg-slate-100 transition-colors"
                        >
                          {expandedGroups.has(group.id) ? (
                            <ChevronDown size={14} />
                          ) : (
                            <ChevronRight size={14} />
                          )}
                          {group.name}
                          <span className="ml-auto text-xs text-slate-400">
                            {group.classifications.reduce((sum, c) => sum + c.tags.length, 0)}
                          </span>
                        </button>
                        
                        {/* 分类列表 */}
                        {expandedGroups.has(group.id) && (
                          <div className="pl-4">
                            {group.classifications.map(cls => (
                              <div key={cls.id}>
                                {/* 分类标题 */}
                                <button
                                  onClick={() => toggleClassification(cls.id)}
                                  className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-600 hover:bg-slate-50 transition-colors"
                                >
                                  {expandedClassifications.has(cls.id) ? (
                                    <ChevronDown size={12} />
                                  ) : (
                                    <ChevronRight size={12} />
                                  )}
                                  {cls.name}
                                  <span className="ml-auto text-slate-400">{cls.tags.length}</span>
                                </button>
                                
                                {/* 标签按钮 */}
                                {expandedClassifications.has(cls.id) && (
                                  <div className="flex flex-wrap gap-1 px-2 py-1 pb-2">
                                    {cls.tags.map(tag => (
                                      <button
                                        key={tag.id}
                                        onClick={() => handleSelectTag(tag)}
                                        disabled={fetchByTagMutation.isPending}
                                        className={`px-2 py-1 text-xs rounded-full transition-colors ${
                                          selectedTag?.id === tag.id
                                            ? 'bg-indigo-500 text-white'
                                            : 'bg-slate-100 text-slate-600 hover:bg-indigo-100 hover:text-indigo-700'
                                        }`}
                                      >
                                        {tag.name}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            
            {/* 右侧：题目列表 */}
            <div className="w-1/2 flex flex-col">
              {fetchByTagMutation.isPending ? (
                <div className="flex-1 flex items-center justify-center">
                  <Loader2 size={24} className="animate-spin text-indigo-500" />
                  <span className="ml-2 text-slate-500">获取题目中...</span>
                </div>
              ) : fetchedProblems.length === 0 ? (
                <div className="flex-1 flex items-center justify-center text-slate-400">
                  <div className="text-center">
                    <Tag size={40} className="mx-auto mb-2 opacity-50" />
                    <p>请从左侧选择一个标签</p>
                  </div>
                </div>
              ) : (
                <>
                  {/* 题目统计 */}
                  <div className="flex items-center justify-between px-4 py-2 bg-slate-50 border-b border-slate-100">
                    <span className="text-sm text-slate-600">
                      已选择 {selectedProblems.size} / {fetchedProblems.length}
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setSelectedProblems(new Set())}
                        className="text-sm text-slate-500 hover:text-slate-700"
                        disabled={selectedProblems.size === 0}
                      >
                        清空
                      </button>
                      <button
                        onClick={handleSelectAll}
                        className="text-sm text-indigo-600 hover:text-indigo-800"
                      >
                        全选
                      </button>
                    </div>
                  </div>
                  
                  {/* 题目列表 */}
                  <div className="flex-1 overflow-y-auto p-2">
                    <div className="grid grid-cols-1 gap-1">
                      {fetchedProblems.map((problem) => (
                        <div
                          key={problem.id}
                          onClick={() => handleToggleSelect(problem.id)}
                          className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
                            selectedProblems.has(problem.id)
                              ? 'bg-indigo-50 border border-indigo-200'
                              : 'bg-slate-50 border border-transparent hover:bg-slate-100'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedProblems.has(problem.id)}
                            readOnly
                            className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 pointer-events-none"
                          />
                          <span className="text-sm text-slate-700 truncate flex-1">
                            <span className="font-mono text-indigo-600 mr-2">#{problem.id}</span>
                            {problem.title || '(无标题)'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
        
                
        {/* 底部按钮 */}
        <div className="flex justify-end gap-3 p-4 border-t border-slate-200">
          <Button variant="secondary" onClick={handleClose}>
            取消
          </Button>
          <Button
            onClick={handleAdd}
            disabled={selectedProblems.size === 0}
          >
            <Plus size={16} />
            添加到任务 ({selectedProblems.size})
          </Button>
        </div>
      </div>
    </div>,
    document.body
  )
}
