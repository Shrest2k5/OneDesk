import axios, { AxiosError } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

// Request interceptor: attach bearer token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('onedesk_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

export interface ApiError extends Error {
  status?: number
  code?: string
  raw?: any
}

// Response interceptor: handle 401 unauthorized & normalize error messages
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<any>) => {
    if (error.response?.status === 401) {
      // Avoid redirecting if we are already attempting to login/register
      const isAuthRoute = error.config?.url?.includes('/auth/login') || error.config?.url?.includes('/auth/register')
      if (!isAuthRoute) {
        localStorage.removeItem('onedesk_token')
        window.dispatchEvent(new Event('onedesk-logout'))
      }
    }

    const errorPayload = error.response?.data
    let message = 'An unexpected error occurred. Please try again.'
    let code: string | undefined = undefined

    if (typeof errorPayload === 'string') {
      message = errorPayload
    } else if (errorPayload && typeof errorPayload === 'object') {
      // 1. Extract error code if present
      if (typeof errorPayload.code === 'string') {
        code = errorPayload.code
      } else if (errorPayload.detail && typeof errorPayload.detail === 'object' && !Array.isArray(errorPayload.detail)) {
        if (typeof errorPayload.detail.code === 'string') {
          code = errorPayload.detail.code
        }
      }

      // 2. Extract human-readable error message
      if (typeof errorPayload.detail === 'string') {
        message = errorPayload.detail
      } else if (Array.isArray(errorPayload.detail)) {
        // Pydantic validation errors
        message = errorPayload.detail.map((err: any) => `${err.loc?.join('.') || 'field'}: ${err.msg}`).join(', ')
      } else if (errorPayload.detail && typeof errorPayload.detail === 'object') {
        message = errorPayload.detail.message || errorPayload.detail.msg || errorPayload.detail.detail || message
      } else if (errorPayload.message) {
        message = errorPayload.message
      }
    } else if (error.message) {
      message = error.message
    }

    const enhancedError = new Error(message) as ApiError
    enhancedError.status = error.response?.status
    enhancedError.code = code
    enhancedError.raw = errorPayload

    return Promise.reject(enhancedError)
  }
)

