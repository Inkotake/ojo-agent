import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios'

// Use relative path since frontend and API are on the same server
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

// Configuration
const DEFAULT_TIMEOUT = 30000
const MAX_RETRIES = 2
const RETRY_DELAY = 1000

// Retryable status codes
const RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504]

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Get auth token from zustand persisted storage
 */
function getAuthToken(): string | null {
  try {
    const authStorage = localStorage.getItem('auth-storage')
    if (!authStorage) return null
    const authData = JSON.parse(authStorage)
    return authData?.state?.token || null
  } catch {
    return null
  }
}

// Request interceptor: auto-add Authorization header
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAuthToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

/**
 * Delay helper for retry
 */
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * Check if error is retryable
 */
function isRetryable(error: AxiosError): boolean {
  // Network errors are retryable
  if (!error.response) return true
  // Check status code
  return RETRYABLE_STATUS_CODES.includes(error.response.status)
}

// Response interceptor: handle errors with retry logic
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const config = error.config
    
    // Handle 401 unauthorized error - no retry
    if (error.response?.status === 401) {
      localStorage.removeItem('auth-storage')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }
    
    // Retry logic for retryable errors (skip if marked to skip retry)
    // @ts-expect-error - checking custom skip retry flag
    if (config && isRetryable(error) && !config.__skipRetry) {
      // @ts-expect-error - adding custom retry count
      const retryCount = config.__retryCount || 0
      
      if (retryCount < MAX_RETRIES) {
        // @ts-expect-error - adding custom retry count
        config.__retryCount = retryCount + 1
        
        console.warn(`API request failed, retrying (${retryCount + 1}/${MAX_RETRIES})...`)
        await delay(RETRY_DELAY * (retryCount + 1)) // Exponential backoff
        
        return apiClient(config)
      }
    }
    
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export default apiClient

