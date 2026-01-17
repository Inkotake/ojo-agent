import { ReactNode } from 'react'
import { Inbox } from 'lucide-react'

interface Column<T> {
  key: string
  header: string
  className?: string
  render?: (item: T, index: number) => ReactNode
}

interface TableProps<T> {
  columns: Column<T>[]
  data: T[]
  keyExtractor: (item: T, index: number) => string
  emptyMessage?: string
  emptyIcon?: ReactNode
  loading?: boolean
  className?: string
}

/**
 * Reusable Table component with consistent styling and empty state
 */
export default function Table<T>({
  columns,
  data,
  keyExtractor,
  emptyMessage = '暂无数据',
  emptyIcon,
  loading = false,
  className = '',
}: TableProps<T>) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden ${className}`}>
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 border-b border-slate-100">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-6 py-3 font-medium text-slate-500 ${col.className || ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {loading ? (
            // Loading skeleton
            Array.from({ length: 3 }).map((_, i) => (
              <tr key={`skeleton-${i}`}>
                {columns.map((col) => (
                  <td key={col.key} className="px-6 py-4">
                    <div className="h-4 bg-slate-100 rounded animate-pulse" />
                  </td>
                ))}
              </tr>
            ))
          ) : data.length === 0 ? (
            // Empty state
            <tr>
              <td colSpan={columns.length} className="px-6 py-12 text-center">
                <div className="flex flex-col items-center gap-3 text-slate-400">
                  {emptyIcon || <Inbox size={40} strokeWidth={1.5} />}
                  <p className="text-sm">{emptyMessage}</p>
                </div>
              </td>
            </tr>
          ) : (
            // Data rows
            data.map((item, index) => (
              <tr
                key={keyExtractor(item, index)}
                className="hover:bg-slate-50/50 transition-colors"
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`px-6 py-4 ${col.className || ''}`}
                  >
                    {col.render
                      ? col.render(item, index)
                      : (item as Record<string, unknown>)[col.key] as ReactNode}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

// Export column type for external use
export type { Column, TableProps }
