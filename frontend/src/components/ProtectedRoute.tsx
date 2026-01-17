import { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

interface ProtectedRouteProps {
  children: ReactNode
  requireAdmin?: boolean
}

/**
 * Route guard component that handles authentication and authorization
 * - Redirects unauthenticated users to login
 * - Redirects non-admin users away from admin-only routes
 * - Preserves intended destination for post-login redirect
 */
export default function ProtectedRoute({ children, requireAdmin = false }: ProtectedRouteProps) {
  const { isAuthenticated, isAdmin } = useAuthStore()
  const location = useLocation()

  if (!isAuthenticated) {
    // Save the attempted URL for redirecting after login
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (requireAdmin && !isAdmin) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}
