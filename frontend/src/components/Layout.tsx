import { useState, useEffect } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Terminal, Settings, LogOut, Code, Globe, BarChart3, Server, ChevronRight, Bell, Menu, X, BookOpen, Brain, Eraser, Gauge, Info } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useNotificationStore } from '../stores/notificationStore'
import apiClient from '../api/client'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, isAdmin, logout } = useAuthStore()
  const { fetchUnreadCount, hasUnread } = useNotificationStore()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  
  // 启用键盘快捷键
  useKeyboardShortcuts()
  
  // 登录后获取未读通知数，并定时刷新
  useEffect(() => {
    fetchUnreadCount()
    // 每5分钟自动检查
    const interval = setInterval(fetchUnreadCount, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [fetchUnreadCount])
  
  const handleLogout = async () => {
    try {
      // Call backend logout API to log activity
      await apiClient.post('/api/auth/logout')
    } catch (e) {
      // Ignore errors - continue with local logout
    }
    logout()
    navigate('/login')
  }
  
  const navigation = [
    { id: 'dashboard', label: '仪表盘', href: '/dashboard', icon: LayoutDashboard, section: '主要' },
    { id: 'tasks', label: '任务中心', href: '/tasks', icon: Code, section: '主要' },
    { id: 'usage', label: 'API 用量', href: '/usage', icon: BarChart3, section: '主要' },
    { id: 'admin', label: '管理面板', href: '/admin', icon: Server, section: '系统', adminOnly: true },
    { id: 'adapters', label: '适配器', href: '/adapters', icon: Globe, section: '系统' },
    { id: 'project-info', label: '项目信息', href: '/project-info', icon: Info, section: '系统', showBadge: true },
    { id: 'settings', label: '设置', href: '/settings', icon: Settings, section: '系统' },
    // 管理员工具
    { id: 'training', label: '题单管理', href: '/training', icon: BookOpen, section: '管理员工具', adminOnly: true },
    { id: 'llm-config', label: 'LLM配置', href: '/llm-config', icon: Brain, section: '管理员工具', adminOnly: true },
    { id: 'wash', label: '文本清洗', href: '/wash', icon: Eraser, section: '管理员工具', adminOnly: true },
    { id: 'concurrency', label: '并发管理', href: '/concurrency', icon: Gauge, section: '管理员工具', adminOnly: true },
  ]
  
  const NavItem = ({ item }: { item: any }) => {
    const Icon = item.icon
    const isActive = location.pathname === item.href
    // 显示小红点：仅当 showBadge 为 true 且有未读更新时
    const showNotificationBadge = item.showBadge && hasUnread()
    
    if (item.adminOnly && !isAdmin) {
      return null
    }
    
    return (
      <Link
        to={item.href}
        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${
          isActive 
            ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-200' 
            : 'text-slate-500 hover:bg-slate-100 hover:text-indigo-600'
        }`}
      >
        <div className="relative">
          <Icon size={20} className={`${isActive ? 'text-white' : 'text-slate-400 group-hover:text-indigo-600'}`} />
          {/* 小红点 - 未读更新提示 */}
          {showNotificationBadge && !isActive && (
            <span className="absolute -top-1 -right-1 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
            </span>
          )}
        </div>
        <span className="font-medium flex-1">{item.label}</span>
        {/* 未读数量徽章 */}
        {showNotificationBadge && !isActive && (
          <span className="px-1.5 py-0.5 text-xs font-medium bg-red-500 text-white rounded-full min-w-[18px] text-center">
            新
          </span>
        )}
        {isActive && <ChevronRight size={16} className="ml-auto opacity-50" />}
      </Link>
    )
  }
  
  const groupedNav = navigation.reduce((acc, item) => {
    if (!acc[item.section]) {
      acc[item.section] = []
    }
    acc[item.section].push(item)
    return acc
  }, {} as Record<string, any[]>)
  
  // 点击导航后关闭移动端菜单
  const handleNavClick = () => {
    setMobileMenuOpen(false)
  }
  
  return (
    <div className="min-h-screen bg-slate-50 flex overflow-hidden font-sans text-slate-900">
      
      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}
      
      {/* Sidebar - Desktop fixed, Mobile slide-out */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-100 flex flex-col
        transform transition-transform duration-300 ease-in-out
        lg:translate-x-0
        ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Mobile close button */}
        <button
          onClick={() => setMobileMenuOpen(false)}
          className="lg:hidden absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-600"
          aria-label="关闭菜单"
        >
          <X size={20} />
        </button>
        <div className="p-6 flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-200">
            <Terminal className="text-white w-6 h-6" />
          </div>
          <div>
            <h1 className="font-bold text-lg text-slate-800 leading-tight">OJ 助手</h1>
            <p className="text-xs text-slate-400 font-medium tracking-wide">v9.0</p>
          </div>
        </div>
        
        <nav className="flex-1 px-4 space-y-2 mt-4 overflow-y-auto">
          {Object.entries(groupedNav).map(([section, items]) => (
            <div key={section}>
              <p className="px-4 text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 mt-6 first:mt-0">
                {section}
              </p>
              {items.map(item => (
                <div key={item.id} onClick={handleNavClick}>
                  <NavItem item={item} />
                </div>
              ))}
            </div>
          ))}
        </nav>
        
        <div className="p-4 border-t border-slate-100">
          <div className="flex items-center gap-3 px-2 mb-4">
            <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-bold">
              {isAdmin ? 'AD' : 'US'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-slate-700 truncate">{user?.username || '访客'}</p>
              <p className="text-xs text-slate-500 capitalize">{user?.role || 'user'}</p>
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 p-2 rounded-lg text-slate-500 hover:text-red-600 hover:bg-red-50 transition-colors text-sm font-medium"
          >
            <LogOut size={16} /> 退出登录
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 lg:ml-64 flex flex-col h-screen overflow-hidden">
        <header className="h-16 bg-white border-b border-slate-100 flex items-center justify-between px-4 lg:px-8">
          <div className="flex items-center gap-4">
            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-2 -ml-2 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors"
              aria-label="打开菜单"
            >
              <Menu size={24} />
            </button>
            <h2 className="text-lg font-bold text-slate-700 capitalize">
              {location.pathname.replace('/', '').replace('-', ' ') || 'Dashboard'}
            </h2>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-green-50 text-green-700 rounded-full text-xs font-medium border border-green-100">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              系统运行正常
            </div>
            {/* 🔔 通知按钮 - 点击跳转到项目信息页 */}
            <button 
              onClick={() => navigate('/project-info')}
              className="p-2 text-slate-400 hover:text-indigo-600 transition-colors relative group"
              title="项目更新"
            >
              <Bell size={20} />
              {/* 小红点 - 有未读时显示 */}
              {hasUnread() && (
                <span className="absolute top-1.5 right-1.5 flex h-2.5 w-2.5">
                  {/* 呼吸动画效果 */}
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500 border border-white"></span>
                </span>
              )}
            </button>
          </div>
        </header>
        
        <div className="flex-1 overflow-y-auto p-4 lg:p-8">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  )
}
