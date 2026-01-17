import { Globe, Code2, Zap, Leaf, Droplets, FileQuestion, type LucideIcon } from 'lucide-react'

// ==================== 平台配置 ====================

/** OJ 平台配置 */
export interface OJPlatformConfig {
  name: string        // 完整名称
  shortName: string   // 简称（用于显示）
  color: string       // 文字颜色
  bgColor: string     // 背景颜色
  icon: LucideIcon    // 图标组件
  adapter: string     // 后端适配器名称
}

export const OJ_PLATFORMS: Record<string, OJPlatformConfig> = {
  aicoders: {
    name: 'Aicoders',
    shortName: 'AI',
    color: 'text-indigo-600',
    bgColor: 'bg-indigo-100',
    icon: Code2,
    adapter: 'aicoders'
  },
  shsoj: { 
    name: 'SHSOJ', 
    shortName: 'SHS',
    color: 'text-blue-600', 
    bgColor: 'bg-blue-100',
    icon: Code2,
    adapter: 'shsoj'
  },
  codeforces: { 
    name: 'Codeforces', 
    shortName: 'CF',
    color: 'text-orange-600', 
    bgColor: 'bg-orange-100',
    icon: Zap,
    adapter: 'codeforces'
  },
  atcoder: { 
    name: 'AtCoder', 
    shortName: 'AC',
    color: 'text-gray-700', 
    bgColor: 'bg-gray-100',
    icon: Globe,
    adapter: 'atcoder'
  },
  luogu: { 
    name: '洛谷', 
    shortName: '洛谷',
    color: 'text-green-600', 
    bgColor: 'bg-green-100',
    icon: Leaf,
    adapter: 'luogu'
  },
  hydrooj: { 
    name: 'HydroOJ', 
    shortName: 'Hydro',
    color: 'text-purple-600', 
    bgColor: 'bg-purple-100',
    icon: Droplets,
    adapter: 'hydrooj'
  },
  unknown: { 
    name: '未知', 
    shortName: '?',
    color: 'text-slate-500', 
    bgColor: 'bg-slate-100',
    icon: FileQuestion,
    adapter: 'auto'
  },
}

// ==================== 识别函数 ====================

/** 根据 problem_id 或 URL 识别来源 OJ */
export function identifyOJ(input: string): string {
  if (!input) return 'unknown'
  
  const lowerInput = input.toLowerCase()
  
  // URL 匹配
  if (lowerInput.includes('aicoders.cn')) return 'aicoders'
  if (lowerInput.includes('shsoj') || lowerInput.includes('shsbnu')) return 'shsoj'
  if (lowerInput.includes('codeforces.com')) return 'codeforces'
  if (lowerInput.includes('atcoder.jp')) return 'atcoder'
  if (lowerInput.includes('luogu.com')) return 'luogu'
  if (lowerInput.includes('hydro')) return 'hydrooj'
  
  // 洛谷题号格式：P1234, B1234, T1234, U1234 等
  if (/^[PBTU]\d+$/i.test(input)) return 'luogu'
  
  // Codeforces 题号格式：1234A, 1234B 等
  if (/^\d+[A-Z]$/i.test(input)) return 'codeforces'
  
  // 纯数字默认为SHSOJ
  if (/^\d+$/.test(input)) return 'shsoj'
  
  return 'unknown'
}

// ==================== ID 格式化 ====================

/** 平台 ID 显示配置 */
const OJ_ID_CONFIG: Record<string, { tag: string; position: 'prefix' | 'suffix' | 'none' }> = {
  aicoders: { tag: 'AIC', position: 'suffix' },
  shsoj: { tag: 'SHS', position: 'suffix' },
  codeforces: { tag: 'CF', position: 'prefix' },
  atcoder: { tag: '', position: 'none' },
  luogu: { tag: '', position: 'none' },
  hydrooj: { tag: 'HY', position: 'suffix' },
  unknown: { tag: '', position: 'none' }
}

// 从 URL 或 ID 提取短题目 ID
export function extractShortId(input: string): string {
  if (!input) return ''
  
  // Aicoders / SHSOJ: https://oj.aicoders.cn/problem/1154 -> 1154
  let match = input.match(/\/problem\/(\d+)/)
  if (match) return match[1]
  
  // Codeforces: https://codeforces.com/problemset/problem/1234/A -> 1234A
  match = input.match(/codeforces\.com\/(?:problemset\/)?problem\/(\d+)\/([A-Z]\d?)/)
  if (match) return `${match[1]}${match[2]}`
  
  // AtCoder: https://atcoder.jp/contests/abc123/tasks/abc123_a -> abc123_a
  match = input.match(/atcoder\.jp\/contests\/[^/]+\/tasks\/([^/?]+)/)
  if (match) return match[1]
  
  // Luogu: https://www.luogu.com.cn/problem/P1001 -> P1001
  match = input.match(/luogu\.com[^/]*\/problem\/([A-Z]?\d+)/)
  if (match) return match[1]
  
  // 已经是短 ID (纯数字或 P+数字)
  if (/^[A-Z]?\d+[A-Z]?\d?$/.test(input)) return input
  
  // 截取最后部分
  const parts = input.split('/')
  const lastPart = parts[parts.length - 1]
  if (lastPart && lastPart.length < 20) return lastPart
  
  return input.slice(0, 10) + '...'
}

// 格式化显示 ID
export function formatDisplayId(input: string, ojType?: string): string {
  const oj = ojType || identifyOJ(input)
  const shortId = extractShortId(input)
  const config = OJ_ID_CONFIG[oj] || OJ_ID_CONFIG.unknown
  
  if (config.position === 'prefix' && config.tag) {
    return `${config.tag}-${shortId}`
  } else if (config.position === 'suffix' && config.tag) {
    return `${shortId}-${config.tag}`
  }
  return shortId || input.slice(0, 15)
}

// ==================== 组件 ====================

interface OJIconProps {
  oj: string | null | undefined
  size?: 'sm' | 'md' | 'lg'
  showName?: boolean
  className?: string
}

/** OJ 平台图标组件 */
export default function OJIcon({ oj, size = 'md', showName = false, className = '' }: OJIconProps) {
  const platform = OJ_PLATFORMS[oj?.toLowerCase() || 'unknown'] || OJ_PLATFORMS.unknown
  const Icon = platform.icon
  
  const sizeClasses = {
    sm: 'w-5 h-5 text-xs',
    md: 'w-6 h-6 text-sm',
    lg: 'w-8 h-8 text-base',
  }
  
  const iconSizes = {
    sm: 12,
    md: 14,
    lg: 18,
  }
  
  if (showName) {
    return (
      <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded ${platform.bgColor} ${className}`}>
        <Icon size={iconSizes[size]} className={platform.color} />
        <span className={`font-medium ${platform.color} ${size === 'sm' ? 'text-xs' : 'text-sm'}`}>
          {platform.shortName}
        </span>
      </div>
    )
  }
  
  return (
    <div 
      className={`inline-flex items-center justify-center rounded ${platform.bgColor} ${sizeClasses[size]} ${className}`}
      title={platform.name}
    >
      <Icon size={iconSizes[size]} className={platform.color} />
    </div>
  )
}
