import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import Card from '../components/ui/Card'

export default function UsagePage() {
  // Fetch real usage stats from backend
  const { data: usageData } = useQuery({
    queryKey: ['usage-stats'],
    queryFn: async () => {
      const response = await apiClient.get('/api/stats/usage')
      return response.data
    },
    refetchInterval: 10000,
  })
  
  const tokenTrend = usageData?.trend || [0, 0, 0, 0, 0, 0, 0]
  const modelDist = usageData?.model_distribution || {}
  
  // Calculate percentages
  const total = Object.values(modelDist).reduce((sum: number, val: any) => sum + (val || 0), 0) || 1
  const modelDistribution = [
    { name: 'DeepSeek', pct: Math.round((modelDist.deepseek || 0) / total * 100), color: 'bg-green-500' },
    { name: 'Gemini', pct: Math.round((modelDist.gemini || 0) / total * 100), color: 'bg-purple-500' },
    { name: '其他', pct: Math.round((modelDist.other || 0) / total * 100), color: 'bg-blue-500' },
  ]

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <h2 className="text-2xl font-bold text-slate-800">API 使用统计</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="col-span-2 p-6">
          <h3 className="font-bold text-slate-800 mb-6">Token 消耗趋势</h3>
          <div className="h-64 flex items-end justify-between gap-2">
            {tokenTrend.map((h: number, i: number) => (
              <div key={i} className="w-full bg-indigo-50 rounded-t-lg relative group">
                <div
                  className="absolute bottom-0 left-0 right-0 bg-indigo-500 rounded-t-lg transition-all"
                  style={{ height: `${h}%` }}
                ></div>
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-4 text-xs text-slate-500">
            <span>周一</span>
            <span>周二</span>
            <span>周三</span>
            <span>周四</span>
            <span>周五</span>
            <span>周六</span>
            <span>周日</span>
          </div>
        </Card>
        
        <Card className="p-6">
          <h3 className="font-bold text-slate-800 mb-6">模型分布</h3>
          <div className="space-y-4">
            {modelDistribution.map(model => (
              <div key={model.name}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600">{model.name}</span>
                  <span className="font-bold text-slate-800">{model.pct}%</span>
                </div>
                <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${model.color}`}
                    style={{ width: `${model.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

