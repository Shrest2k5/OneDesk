import { apiClient } from './client'
import type { SyncHistory, SyncRequest } from '@/types/sync'

export const syncApi = {
  triggerSync: async (integrationId: string, request: SyncRequest): Promise<SyncHistory> => {
    const response = await apiClient.post<SyncHistory>(`/integrations/${integrationId}/sync`, request)
    return response.data
  },

  getSyncHistory: async (integrationId: string, limit: number = 50): Promise<SyncHistory[]> => {
    const response = await apiClient.get<SyncHistory[]>(`/integrations/${integrationId}/sync-history`, {
      params: { limit },
    })
    return response.data
  },
}

