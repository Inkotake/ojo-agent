interface ProgressBarProps {
  value: number
  max?: number
  color?: string
}

export default function ProgressBar({ value, max = 100, color = 'bg-indigo-600' }: ProgressBarProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100))
  
  return (
    <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
      <div
        className={`h-full transition-all duration-500 ease-out ${color}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  )
}

