// ============================================
// Common Types for OJO Frontend
// ============================================

// Task related types
export interface Task {
  id: string
  task_id: string
  problem_id: string
  title?: string
  oj?: string              // OJ platform name (display)
  oj_platform?: string     // OJ platform identifier
  status: TaskStatus
  progress: number
  stage: string
  created_at: string
  updated_at?: string
}

export type TaskStatus = 
  | -2  // cancelled
  | -1  // failed
  | 0   // pending
  | 1   // judging
  | 2   // compiling
  | 3   // compile error
  | 4   // accepted
  | 5   // wrong answer
  | 6   // fetching
  | 7   // generating
  | 8   // uploading

// User related types
export interface User {
  id: number
  username: string
  role: 'user' | 'admin'
  email?: string
  status: 'active' | 'inactive'
  last_login?: string
}

// Adapter related types
export interface Adapter {
  name: string
  display_name: string
  capabilities: AdapterCapability[]
  version: string
  status: 'online' | 'offline' | 'ready' | 'unknown'
  config_schema: ConfigSchema
  config_values: Record<string, unknown>
  has_config: boolean
}

export type AdapterCapability = 
  | 'fetch_problem' 
  | 'FETCH_PROBLEM'
  | 'upload_data' 
  | 'UPLOAD_DATA'
  | 'submit_solution'
  | 'SUBMIT_SOLUTION'

export interface ConfigSchema {
  [key: string]: ConfigField
}

export interface ConfigField {
  type: 'text' | 'password' | 'number' | 'boolean'
  label: string
  default?: string
  required?: boolean
  tooltip?: string
}

// API Response types
export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  total: number
  page: number
  limit: number
}

// System stats
export interface SystemStats {
  total: number
  success: number
  failed: number
  running: number
  pending: number
}

// WebSocket message types
export interface WSMessage {
  type: WSMessageType
  timestamp?: string
  task_id?: string
  problem_id?: string
  progress?: number
  stage?: string
  data?: unknown
}

export type WSMessageType = 
  | 'task.progress'
  | 'task.completed'
  | 'task.failed'
  | 'task.started'
  | 'system.status'
