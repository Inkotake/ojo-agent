import { useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

interface ShortcutConfig {
  key: string
  ctrl?: boolean
  alt?: boolean
  shift?: boolean
  action: () => void
  description: string
}

/**
 * 键盘快捷键 Hook
 * 提供全局键盘导航支持
 */
export function useKeyboardShortcuts() {
  const navigate = useNavigate()

  // 定义快捷键
  const shortcuts: ShortcutConfig[] = [
    { key: 'd', alt: true, action: () => navigate('/dashboard'), description: '打开仪表盘' },
    { key: 't', alt: true, action: () => navigate('/tasks'), description: '打开任务中心' },
    { key: 'a', alt: true, action: () => navigate('/adapters'), description: '打开适配器' },
    { key: 's', alt: true, action: () => navigate('/settings'), description: '打开设置' },
    { key: '/', ctrl: true, action: () => focusSearch(), description: '聚焦搜索框' },
  ]

  const focusSearch = useCallback(() => {
    const searchInput = document.querySelector<HTMLInputElement>('[data-search-input]')
    if (searchInput) {
      searchInput.focus()
    }
  }, [])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // 忽略在输入框中的按键（除非是 Escape）
      const target = event.target as HTMLElement
      const isInputField = target.tagName === 'INPUT' || 
                          target.tagName === 'TEXTAREA' || 
                          target.isContentEditable

      if (isInputField && event.key !== 'Escape') {
        return
      }

      // 查找匹配的快捷键
      for (const shortcut of shortcuts) {
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase()
        const ctrlMatch = shortcut.ctrl ? (event.ctrlKey || event.metaKey) : !event.ctrlKey && !event.metaKey
        const altMatch = shortcut.alt ? event.altKey : !event.altKey
        const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey

        if (keyMatch && ctrlMatch && altMatch && shiftMatch) {
          event.preventDefault()
          shortcut.action()
          return
        }
      }

      // Escape 键关闭模态框
      if (event.key === 'Escape') {
        const modal = document.querySelector('[data-modal]')
        const closeButton = modal?.querySelector<HTMLButtonElement>('[data-modal-close]')
        if (closeButton) {
          closeButton.click()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigate, shortcuts])

  return { shortcuts }
}

/**
 * 获取快捷键描述（用于显示帮助）
 */
export function getShortcutLabel(shortcut: ShortcutConfig): string {
  const parts: string[] = []
  if (shortcut.ctrl) parts.push('Ctrl')
  if (shortcut.alt) parts.push('Alt')
  if (shortcut.shift) parts.push('Shift')
  parts.push(shortcut.key.toUpperCase())
  return parts.join(' + ')
}

export default useKeyboardShortcuts
