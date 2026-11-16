import { apiClient } from './client'
import type {
  ConnectionHealthStatus,
  Integration,
  ZohoConnectRequest,
  ZohoConnectResponse,
} from '@/types/integration'

export const integrationsApi = {
  list: async (): Promise<Integration[]> => {
    const response = await apiClient.get<Integration[]>('/integrations')
    return response.data
  },

  get: async (id: string): Promise<Integration> => {
    const response = await apiClient.get<Integration>(`/integrations/${id}`)
    return response.data
  },

  checkStatus: async (id: string): Promise<ConnectionHealthStatus> => {
    const response = await apiClient.get<ConnectionHealthStatus>(`/integrations/${id}/status`)
    return response.data
  },

  delete: async (id: string): Promise<{ status: string; message: string }> => {
    const response = await apiClient.delete<{ status: string; message: string }>(`/integrations/${id}`)
    return response.data
  },

  // Zoho specific
  initiateZohoConnect: async (data: ZohoConnectRequest): Promise<ZohoConnectResponse> => {
    const response = await apiClient.post<ZohoConnectResponse>('/integrations/zoho/connect', data)
    return response.data
  },
}

