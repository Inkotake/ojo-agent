import { useState, useCallback } from 'react'
import apiClient from '../api/client'

interface DownloadState {
  loading: boolean
  error: string | null
}

/**
 * Hook for downloading workspace files
 * Extracts common download logic from Dashboard and TasksPage
 */
export function useDownload() {
  const [state, setState] = useState<DownloadState>({
    loading: false,
    error: null,
  })

  const downloadWorkspace = useCallback(async (taskId: string) => {
    setState({ loading: true, error: null })
    
    try {
      // 使用特殊的配置：增加超时时间，禁用重试（blob下载不应该重试）
      const response = await apiClient.get(`/api/workspace/download/${taskId}`, {
        responseType: 'blob',
        timeout: 600000, // 10分钟超时（大文件下载需要更长时间）
        // @ts-expect-error - 添加标记以防止重试
        __skipRetry: true,
        // 确保不对响应进行转换
        transformResponse: [(data) => data]
      })
      
      console.log('Download response:', {
        status: response.status,
        contentType: response.headers['content-type'],
        contentLength: response.headers['content-length'],
        dataType: typeof response.data,
        dataSize: response.data?.size
      })
      
      // 验证响应数据
      if (!response.data) {
        throw new Error('响应数据为空')
      }
      
      // 确保数据是 Blob 类型
      let blob: Blob
      if (response.data instanceof Blob) {
        blob = response.data
      } else {
        // 如果不是 Blob，尝试转换
        blob = new Blob([response.data], { type: 'application/zip' })
      }
      
      if (blob.size === 0) {
        throw new Error('下载的文件为空')
      }
      
      console.log('Blob created:', { size: blob.size, type: blob.type })
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `workspace_${taskId}.zip`)
      document.body.appendChild(link)
      link.click()
      
      // 延迟移除，确保下载开始
      setTimeout(() => {
        link.remove()
        window.URL.revokeObjectURL(url)
      }, 100)
      
      setState({ loading: false, error: null })
      return true
    } catch (error: any) {
      console.error('下载失败:', error)
      console.error('Error details:', {
        message: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        code: error.code,
        responseData: error.response?.data
      })
      
      let errorMessage = '下载失败，请重试'
      
      if (error.response?.status === 404) {
        errorMessage = '工作区不存在或没有可下载的文件'
      } else if (error.response?.status === 403) {
        errorMessage = '无权访问此任务'
      } else if (error.code === 'ECONNABORTED') {
        errorMessage = '下载超时，请重试'
      } else if (error.message) {
        errorMessage = error.message
      }
      
      setState({ loading: false, error: errorMessage })
      return false
    }
  }, [])

  return {
    downloadWorkspace,
    downloading: state.loading,
    downloadError: state.error,
  }
}

export default useDownload
