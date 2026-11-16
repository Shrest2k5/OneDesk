export interface PaginationInfo {
  page: number
  per_page: number
  count: number
  more_records: boolean
}

export interface ZohoContact {
  id: string
  first_name?: string | null
  last_name?: string | null
  email?: string | null
  phone?: string | null
  mobile?: string | null
  account_name?: string | null
  owner?: string | null
  created_time?: string | null
  modified_time?: string | null
  raw_data?: Record<string, any> | null
}

export interface ZohoLead {
  id: string
  first_name?: string | null
  last_name?: string | null
  company?: string | null
  email?: string | null
  phone?: string | null
  lead_source?: string | null
  lead_status?: string | null
  owner?: string | null
  created_time?: string | null
  modified_time?: string | null
  raw_data?: Record<string, any> | null
}

export interface ZohoDeal {
  id: string
  deal_name: string
  amount?: number | null
  currency?: string | null
  stage?: string | null
  closing_date?: string | null
  probability?: number | null
  account_name?: string | null
  owner?: string | null
  created_time?: string | null
  modified_time?: string | null
  raw_data?: Record<string, any> | null
}

export interface ZohoAccount {
  id: string
  account_name: string
  phone?: string | null
  website?: string | null
  industry?: string | null
  account_type?: string | null
  billing_city?: string | null
  billing_country?: string | null
  owner?: string | null
  created_time?: string | null
  modified_time?: string | null
  raw_data?: Record<string, any> | null
}

export interface PaginatedResponse<T> {
  data: T[]
  pagination: PaginationInfo
}

export interface CrmQueryParams {
  integration_id?: string
  page?: number
  per_page?: number
  fields?: string
  modified_since?: string
}

