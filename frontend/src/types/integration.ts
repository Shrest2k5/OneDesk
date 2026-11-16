export type IntegrationStatus = 'active' | 'expired' | 'revoked' | 'error'

export interface Integration {
  id: string
  provider: string
  connection_name: string
  external_account_id?: string | null
  status: IntegrationStatus
  api_domain?: string | null
  token_expires_at?: string | null
  created_at: string
  updated_at: string
}

export type ZohoDataCenter = 'us' | 'eu' | 'in' | 'cn' | 'au' | 'ca' | 'jp'

export interface ZohoConnectRequest {
  connection_name: string
  data_center?: ZohoDataCenter
}

export interface ZohoConnectResponse {
  authorization_url: string
  state: string
  data_center: string
}

export interface ConnectionHealthStatus {
  status: 'connected' | 'error' | 'revoked'
  provider: string
  connection_name: string
  api_domain?: string
  organization_name?: string
  token_status?: string
  error?: string
}

