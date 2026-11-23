export type IntegrationStatus = 'active' | 'expired' | 'revoked' | 'error'

export interface Integration {
  id: string
  provider: string
  product: 'crm' | 'books' | string
  connection_name: string
  external_account_id?: string | null
  external_database?: string | null
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
  integration_id?: string
}

export interface ZohoConnectResponse {
  authorization_url: string
  state: string
  data_center: string
}

export interface OdooConnectRequest {
  connection_name: string
  instance_url: string
  api_key: string
  database?: string
  integration_id?: string
}

export interface OdooConnectResponse {
  id: string
  provider: 'odoo'
  product: string
  connection_name: string
  api_domain?: string | null
  external_database?: string | null
  status: IntegrationStatus
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

export interface BooksOrganization {
  id: string
  external_organization_id: string
  name: string
  email?: string | null
  currency_code?: string | null
  currency_symbol?: string | null
  time_zone?: string | null
  is_default_org: boolean
  is_org_active: boolean
  fetched_at: string
  selected: boolean
}

