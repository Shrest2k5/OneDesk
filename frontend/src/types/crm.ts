export interface PaginationInfo {
  page: number
  per_page: number
  count: number
  more_records: boolean
}

export interface ZohoContact {
  id: string
  first_name?: string | null
  last_name: string
  email?: string | null
  phone?: string | null
  account_name?: string | null
  created_time?: string | null
  modified_time?: string | null
  raw_data?: Record<string, any> | null
}

export interface ZohoLead {
  id: string
  first_name?: string | null
  last_name: string
  company?: string | null
  email?: string | null
  phone?: string | null
  lead_status?: string | null
  created_time?: string | null
  modified_time?: string | null
  raw_data?: Record<string, any> | null
}

export interface ZohoDeal {
  id: string
  deal_name: string
  amount?: number | null
  stage?: string | null
  closing_date?: string | null
  account_name?: string | null
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
  billing_city?: string | null
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

