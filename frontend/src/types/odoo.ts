export interface OdooPartner {
  id: string
  partner_id: string
  name?: string | null
  display_name?: string | null
  active: boolean
  is_company: boolean
  company_type?: string | null
  contact_type?: string | null
  parent?: { id: number | string; name: string } | null
  commercial_partner?: { id: number | string; name: string } | null
  email?: string | null
  phone?: string | null
  mobile?: string | null
  street?: string | null
  street2?: string | null
  city?: string | null
  zip?: string | null
  state?: { id: number | string; name: string } | null
  country?: { id: number | string; name: string } | null
  customer_rank: number
  supplier_rank: number
  classifications: string[]
  created_at?: string | null
  updated_at?: string | null
  raw_data?: Record<string, unknown>
}

export interface OdooContactsResponse {
  data: OdooPartner[]
  pagination: { page: number; per_page: number; count: number; total: number; more_records: boolean }
  sync: { status: string; error?: string | null; last_successful_sync?: string | null }
}

export interface OdooContactStats {
  total: number
  customers: number
  vendors: number
  companies: number
  archived: number
}
