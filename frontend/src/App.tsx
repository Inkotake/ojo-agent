import { lazy, Suspense } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import ErrorBoundary from './components/ErrorBoundary'
import { ToastProvider } from './components/ui/Toast'
import { ConfirmProvider } from './components/ui/ConfirmDialog'

// Lazy load pages for better performance (code splitting)
const Dashboard = lazy(() => import('./pages/Dashboard'))
const TasksPage = lazy(() => import('./pages/TasksPage'))
const AdaptersPage = lazy(() => import('./pages/AdaptersPage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))
const UsagePage = lazy(() => import('./pages/UsagePage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))

// Admin-only pages
const TrainingPage = lazy(() => import('./pages/TrainingPage'))
const LLMConfigPage = lazy(() => import('./pages/LLMConfigPage'))
const WashToolPage = lazy(() => import('./pages/WashToolPage'))
const ConcurrencyPage = lazy(() => import('./pages/ConcurrencyPage'))

// Project Info page (public to all authenticated users)
const ProjectInfoPage = lazy(() => import('./pages/ProjectInfoPage'))

// Loading fallback component
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-slate-500">加载中...</p>
      </div>
    </div>
  )
}

// Create QueryClient with optimized cache strategy
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 1000,        // 5秒内数据不会过期
      gcTime: 10 * 60 * 1000,     // 10分钟后清理缓存（原 cacheTime）
      refetchOnMount: true,
      refetchOnReconnect: true,   // 网络重连时刷新
    },
    mutations: {
      retry: 0,                   // mutation 不重试
    },
  },
})

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <ConfirmProvider>
            <Router>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                {/* Public routes */}
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
                
                {/* Protected routes */}
                <Route path="/" element={<Layout />}>
                  <Route index element={<Navigate to="/dashboard" replace />} />
                  <Route path="dashboard" element={
                    <ProtectedRoute>
                      <Dashboard />
                    </ProtectedRoute>
                  } />
                  <Route path="tasks" element={
                    <ProtectedRoute>
                      <TasksPage />
                    </ProtectedRoute>
                  } />
                  <Route path="adapters" element={
                    <ProtectedRoute>
                      <AdaptersPage />
                    </ProtectedRoute>
                  } />
                  <Route path="admin" element={
                    <ProtectedRoute requireAdmin>
                      <AdminPage />
                    </ProtectedRoute>
                  } />
                  <Route path="usage" element={
                    <ProtectedRoute>
                      <UsagePage />
                    </ProtectedRoute>
                  } />
                  <Route path="settings" element={
                    <ProtectedRoute>
                      <SettingsPage />
                    </ProtectedRoute>
                  } />
                  <Route path="project-info" element={
                    <ProtectedRoute>
                      <ProjectInfoPage />
                    </ProtectedRoute>
                  } />
                  
                  {/* Admin-only routes */}
                  <Route path="training" element={
                    <ProtectedRoute requireAdmin>
                      <TrainingPage />
                    </ProtectedRoute>
                  } />
                  <Route path="llm-config" element={
                    <ProtectedRoute requireAdmin>
                      <LLMConfigPage />
                    </ProtectedRoute>
                  } />
                  <Route path="wash" element={
                    <ProtectedRoute requireAdmin>
                      <WashToolPage />
                    </ProtectedRoute>
                  } />
                  <Route path="concurrency" element={
                    <ProtectedRoute requireAdmin>
                      <ConcurrencyPage />
                    </ProtectedRoute>
                  } />
                </Route>
              </Routes>
            </Suspense>
            </Router>
          </ConfirmProvider>
        </ToastProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App
