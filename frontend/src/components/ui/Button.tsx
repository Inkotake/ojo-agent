import { LucideIcon } from 'lucide-react'

interface ButtonProps {
  children: React.ReactNode
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success'
  onClick?: () => void
  className?: string
  disabled?: boolean
  icon?: LucideIcon
  type?: 'button' | 'submit' | 'reset'
}

export default function Button({
  children,
  variant = 'primary',
  onClick,
  className = '',
  disabled = false,
  icon: Icon,
  type = 'button'
}: ButtonProps) {
  const baseStyle = 'inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2'
  
  const variants = {
    primary: 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-md shadow-indigo-200 disabled:opacity-50 disabled:cursor-not-allowed',
    secondary: 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:border-slate-300 shadow-sm',
    danger: 'bg-red-50 text-red-600 hover:bg-red-100 border border-transparent',
    ghost: 'bg-transparent text-slate-600 hover:bg-slate-100',
    success: 'bg-green-600 text-white hover:bg-green-700 shadow-md shadow-green-200'
  }

  return (
    <button
      type={type}
      onClick={onClick}
      className={`${baseStyle} ${variants[variant]} ${className}`}
      disabled={disabled}
    >
      {Icon && <Icon size={16} />}
      {children}
    </button>
  )
}

