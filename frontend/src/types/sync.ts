export type SyncStatus = 'pending' | 'in_progress' | 'completed' | 'failed'

export type SyncResourceType = 'contacts' | 'leads' | 'deals' | 'accounts'

export interface SyncRequest {
  resource_type: SyncResourceType
  incremental?: boolean
  async_mode?: boolean
}

export interface SyncHistory {
  id: string
  integration_id: string
  resource_type: string
  status: SyncStatus
  records_processed: number
  started_at: string
  completed_at?: string | null
  error_message?: string | null
}

