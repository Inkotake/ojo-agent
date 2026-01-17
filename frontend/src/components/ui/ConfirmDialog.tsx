import { useState, createContext, useContext, useCallback, ReactNode } from 'react'
import { AlertTriangle, Trash2, X } from 'lucide-react'
import Button from './Button'

interface ConfirmOptions {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'warning' | 'info'
}

interface ConfirmContextType {
  confirm: (options: ConfirmOptions) => Promise<boolean>
}

const ConfirmContext = createContext<ConfirmContextType | null>(null)

export function useConfirm() {
  const context = useContext(ConfirmContext)
  if (!context) {
    throw new Error('useConfirm must be used within ConfirmProvider')
  }
  return context.confirm
}

interface ConfirmProviderProps {
  children: ReactNode
}

export function ConfirmProvider({ children }: ConfirmProviderProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [options, setOptions] = useState<ConfirmOptions | null>(null)
  const [resolver, setResolver] = useState<((value: boolean) => void) | null>(null)

  const confirm = useCallback((opts: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      setOptions(opts)
      setResolver(() => resolve)
      setIsOpen(true)
    })
  }, [])

  const handleConfirm = () => {
    setIsOpen(false)
    resolver?.(true)
  }

  const handleCancel = () => {
    setIsOpen(false)
    resolver?.(false)
  }

  const getIcon = () => {
    switch (options?.variant) {
      case 'danger':
        return <Trash2 className="w-6 h-6 text-red-500" />
      case 'warning':
        return <AlertTriangle className="w-6 h-6 text-amber-500" />
      default:
        return <AlertTriangle className="w-6 h-6 text-indigo-500" />
    }
  }

  const getIconBg = () => {
    switch (options?.variant) {
      case 'danger':
        return 'bg-red-100'
      case 'warning':
        return 'bg-amber-100'
      default:
        return 'bg-indigo-100'
    }
  }

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      
      {isOpen && options && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
            onClick={handleCancel}
          />
          
          {/* Dialog */}
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 animate-in zoom-in-95 fade-in duration-200">
            {/* Close button */}
            <button
              onClick={handleCancel}
              className="absolute top-4 right-4 p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <X size={18} />
            </button>
            
            <div className="p-6">
              {/* Icon */}
              <div className={`w-12 h-12 ${getIconBg()} rounded-full flex items-center justify-center mx-auto mb-4`}>
                {getIcon()}
              </div>
              
              {/* Title */}
              <h3 className="text-lg font-bold text-slate-800 text-center mb-2">
                {options.title || '确认操作'}
              </h3>
              
              {/* Message */}
              <p className="text-slate-500 text-center text-sm mb-6">
                {options.message}
              </p>
              
              {/* Actions */}
              <div className="flex gap-3">
                <Button
                  variant="secondary"
                  onClick={handleCancel}
                  className="flex-1"
                >
                  {options.cancelText || '取消'}
                </Button>
                <Button
                  variant={options.variant === 'danger' ? 'danger' : 'primary'}
                  onClick={handleConfirm}
                  className="flex-1"
                >
                  {options.confirmText || '确认'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}

export default ConfirmProvider
