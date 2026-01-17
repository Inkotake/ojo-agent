import { create } from 'zustand'

export interface Task {
  id: string
  problemId: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  stage: string
  enableGeneration: boolean
  enableUpload: boolean
  enableSolve: boolean
  createdAt: string
  updatedAt: string
}

interface TaskStore {
  tasks: Task[]
  addTask: (task: Task) => void
  updateTask: (id: string, updates: Partial<Task>) => void
  removeTask: (id: string) => void
  clearTasks: () => void
}

export const useTaskStore = create<TaskStore>((set) => ({
  tasks: [],
  
  addTask: (task) => set((state) => ({
    tasks: [...state.tasks, task]
  })),
  
  updateTask: (id, updates) => set((state) => ({
    tasks: state.tasks.map(t => 
      t.id === id ? { ...t, ...updates } : t
    )
  })),
  
  removeTask: (id) => set((state) => ({
    tasks: state.tasks.filter(t => t.id !== id)
  })),
  
  clearTasks: () => set({ tasks: [] })
}))

