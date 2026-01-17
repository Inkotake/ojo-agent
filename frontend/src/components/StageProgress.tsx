import { Check, Circle, Loader2 } from 'lucide-react'

// 模块阶段定义
const STAGES = [
  { key: 'fetch', label: '拉取' },
  { key: 'gen', label: '生成' },
  { key: 'upload', label: '上传' },
  { key: 'solve', label: '验证' },
]

// 阶段状态映射（与后端 pipeline.py 的 stage 名称对应）
const STAGE_STATUS_MAP: Record<string, number> = {
  'pending': 0,
  'processing': 0,  // 通用处理中状态
  'fetch': 1,
  'fetching': 1,
  'retrying_fetch': 1,
  'gen': 2,
  'generating': 2,
  'generation': 2,
  'retrying_gen': 2,
  'upload': 3,
  'uploading': 3,
  'retrying_upload': 3,
  'solve': 4,
  'solving': 4,
  'retrying_solve': 4,
  'completed': 5,
  'failed': -1,
  'failed_fetch': -1,
  'failed_gen': -1,
  'failed_upload': -1,
  'failed_solve': -1,
  'cancelled': -2,
}

// 详细状态文本
const STAGE_DETAIL_TEXT: Record<string, string> = {
  'pending': '等待开始',
  'processing': '处理中',
  'fetch': '正在拉取题面',
  'fetching': '正在拉取题面',
  'retrying_fetch': '重试拉取中...',
  'gen': '正在生成数据',
  'generation': '正在生成数据',
  'generating': '调用LLM生成中',
  'retrying_gen': '重试生成中...',
  'upload': '正在上传题目',
  'uploading': '上传数据中',
  'retrying_upload': '重试上传中...',
  'solve': '正在验证',
  'solving': '提交代码验证中',
  'retrying_solve': '重试验证中...',
  'completed': '已完成',
  'failed': '处理失败',
  'failed_fetch': '拉取失败',
  'failed_gen': '生成失败',
  'failed_upload': '上传失败',
  'failed_solve': '验证失败',
  'cancelled': '已取消',
  'running': '执行中',
  'llm_calling': '调用大模型中',
  'llm_waiting': '等待LLM响应',
  'compiling': '编译中',
  'judging': '评测中',
}

interface StageProgressProps {
  stage: string
  status: number  // 任务整体状态
  className?: string
}

export default function StageProgress({ stage, status, className = '' }: StageProgressProps) {
  const currentStageIndex = STAGE_STATUS_MAP[stage?.toLowerCase()] ?? 0
  const isFailed = status === -1
  const isCancelled = status === -2
  const isCompleted = status === 4
  
  return (
    <div className={`flex items-center gap-0.5 ${className}`}>
      {STAGES.map((s, index) => {
        const stageNum = index + 1
        let stageStatus: 'pending' | 'active' | 'completed' | 'failed' = 'pending'
        
        if (isCompleted) {
          stageStatus = 'completed'
        } else if (isFailed || isCancelled) {
          if (stageNum < currentStageIndex) {
            stageStatus = 'completed'
          } else if (stageNum === currentStageIndex) {
            stageStatus = 'failed'
          }
        } else {
          if (stageNum < currentStageIndex) {
            stageStatus = 'completed'
          } else if (stageNum === currentStageIndex) {
            stageStatus = 'active'
          }
        }
        
        return (
          <div key={s.key} className="flex items-center">
            {/* 节点 */}
            <div className="flex flex-col items-center">
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium transition-all ${
                  stageStatus === 'completed'
                    ? 'bg-green-500 text-white'
                    : stageStatus === 'active'
                    ? 'bg-indigo-500 text-white ring-2 ring-indigo-200'
                    : stageStatus === 'failed'
                    ? 'bg-red-500 text-white'
                    : 'bg-slate-200 text-slate-400'
                }`}
                title={s.label}
              >
                {stageStatus === 'completed' ? (
                  <Check size={12} strokeWidth={3} />
                ) : stageStatus === 'active' ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : stageStatus === 'failed' ? (
                  <span className="text-[10px]">!</span>
                ) : (
                  <Circle size={8} />
                )}
              </div>
              <span className={`text-[9px] mt-0.5 ${
                stageStatus === 'active' ? 'text-indigo-600 font-medium' : 
                stageStatus === 'completed' ? 'text-green-600' :
                stageStatus === 'failed' ? 'text-red-500' :
                'text-slate-400'
              }`}>
                {s.label}
              </span>
            </div>
            
            {/* 连接线 */}
            {index < STAGES.length - 1 && (
              <div
                className={`w-4 h-0.5 mx-0.5 -mt-3 ${
                  stageNum < currentStageIndex || isCompleted
                    ? 'bg-green-400'
                    : 'bg-slate-200'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

// 详细状态显示组件
interface StageDetailProps {
  stage: string
  status: number
  errorMessage?: string
  className?: string
}

export function StageDetail({ stage, status, errorMessage, className = '' }: StageDetailProps) {
  const isActive = status === 1 || status === 2
  const isFailed = status === -1
  const isCompleted = status === 4
  
  const detailText = STAGE_DETAIL_TEXT[stage?.toLowerCase()] || stage || '处理中'
  
  // 状态图标和颜色
  let statusIcon = null
  let textColor = 'text-slate-500'
  
  if (isCompleted) {
    statusIcon = <Check size={12} className="text-green-500" />
    textColor = 'text-green-600'
  } else if (isFailed) {
    textColor = 'text-red-500'
  } else if (isActive) {
    statusIcon = <Loader2 size={12} className="animate-spin text-indigo-500" />
    textColor = 'text-indigo-600'
  }
  
  return (
    <div className={`flex flex-col ${className}`}>
      <div className={`flex items-center gap-1 text-xs ${textColor}`}>
        {statusIcon}
        <span className="font-medium">{isCompleted ? '完成' : isFailed ? '失败' : detailText}</span>
      </div>
      {errorMessage && isFailed && (
        <p className="text-[10px] text-red-400 truncate max-w-[140px] mt-0.5" title={errorMessage}>
          {errorMessage}
        </p>
      )}
    </div>
  )
}
