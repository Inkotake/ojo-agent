interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label?: string
  description?: string
  disabled?: boolean
}

export default function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false
}: ToggleProps) {
  return (
    <div className="flex items-center justify-between">
      {(label || description) && (
        <div>
          {label && (
            <p className="text-sm font-medium text-slate-700">{label}</p>
          )}
          {description && (
            <p className="text-xs text-slate-500">{description}</p>
          )}
        </div>
      )}
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={`
          relative w-10 h-6 rounded-full transition-colors
          ${checked ? 'bg-indigo-600' : 'bg-slate-200'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `.trim().replace(/\s+/g, ' ')}
      >
        <span
          className={`
            absolute top-1 w-4 h-4 bg-white rounded-full shadow-sm transition-all
            ${checked ? 'right-1' : 'left-1'}
          `.trim().replace(/\s+/g, ' ')}
        />
      </button>
    </div>
  )
}
