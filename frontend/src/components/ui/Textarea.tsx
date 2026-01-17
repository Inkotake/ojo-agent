import { forwardRef, TextareaHTMLAttributes } from 'react'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
  helperText?: string
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, helperText, className = '', ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block text-sm font-medium text-slate-700 mb-1">
            {label}
            {props.required && <span className="text-red-500 ml-1">*</span>}
          </label>
        )}
        <textarea
          ref={ref}
          className={`
            w-full p-3 
            bg-slate-100 
            border border-slate-200 
            rounded-lg 
            text-sm text-slate-800 font-mono
            placeholder:text-slate-400
            focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent focus:bg-white
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-all resize-y
            ${error ? 'border-red-300 focus:ring-red-500' : ''}
            ${className}
          `.trim().replace(/\s+/g, ' ')}
          {...props}
        />
        {helperText && !error && (
          <p className="text-xs text-slate-500 mt-1">{helperText}</p>
        )}
        {error && (
          <p className="text-xs text-red-500 mt-1">{error}</p>
        )}
      </div>
    )
  }
)

Textarea.displayName = 'Textarea'

export default Textarea
