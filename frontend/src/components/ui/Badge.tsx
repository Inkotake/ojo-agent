import { Clock, Activity, Server, XCircle, CheckCircle2, DownloadCloud, Cpu, UploadCloud } from 'lucide-react'

interface BadgeProps {
  status: number
}

// Status Codes mapping from backend
const STATUS_MAP: Record<number, { text: string; color: string; icon: any }> = {
  [-3]: { text: '待提交', color: 'bg-slate-100 text-slate-500', icon: Clock },  // 本地待提交
  [-2]: { text: '已取消', color: 'bg-orange-100 text-orange-600', icon: XCircle },
  [-1]: { text: '失败', color: 'bg-red-100 text-red-600', icon: XCircle },
  0: { text: '队列中', color: 'bg-gray-100 text-gray-600', icon: Clock },  // 已提交，等待后端处理
  1: { text: '处理中', color: 'bg-blue-100 text-blue-600', icon: Activity },
  2: { text: '编译中', color: 'bg-yellow-100 text-yellow-600', icon: Server },
  3: { text: '编译错误', color: 'bg-red-100 text-red-600', icon: XCircle },
  4: { text: '完成', color: 'bg-green-100 text-green-600', icon: CheckCircle2 },
  5: { text: '答案错误', color: 'bg-red-100 text-red-600', icon: XCircle },
  6: { text: '获取中', color: 'bg-purple-100 text-purple-600', icon: DownloadCloud },
  7: { text: '生成中', color: 'bg-indigo-100 text-indigo-600', icon: Cpu },
  8: { text: '上传中', color: 'bg-cyan-100 text-cyan-600', icon: UploadCloud },
}

export default function Badge({ status }: BadgeProps) {
  const config = STATUS_MAP[status] || STATUS_MAP[0]
  const Icon = config.icon

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.color}`}>
      <Icon size={12} />
      {config.text}
    </span>
  )
}

