import { apiClient } from './client'
import type { AuthTokenResponse, User, UserLoginInput, UserRegisterInput } from '@/types/auth'

export const authApi = {
  register: async (data: UserRegisterInput): Promise<User> => {
    const response = await apiClient.post<User>('/auth/register', data)
    return response.data
  },

  login: async (data: UserLoginInput): Promise<AuthTokenResponse> => {
    const response = await apiClient.post<AuthTokenResponse>('/auth/login', data)
    return response.data
  },

  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/me')
    return response.data
  },
}

