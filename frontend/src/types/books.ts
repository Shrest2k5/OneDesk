export interface BooksContact {
  id: string
  contact_id: string
  contact_name?: string | null
  company_name?: string | null
  contact_type?: string | string[] | null
  contact_types: string[]
  email?: string | null
  phone?: string | null
  currency_code?: string | null
  currency_symbol?: string | null
  created_time?: string | null
  last_modified_time?: string | null
  raw_data?: Record<string, unknown>
}

export interface BooksContactsResponse {
  data: BooksContact[]
  pagination: { page: number; per_page: number; count: number; total: number; more_records: boolean }
  sync: { status: string; error?: string | null; last_successful_sync?: string | null }
}

export interface BooksContactStats { total: number; customers: number; vendors: number }

export interface BooksInvoice {
  id: string
  invoice_id: string
  invoice_number?: string | null
  reference_number?: string | null
  invoice_date?: string | null
  due_date?: string | null
  customer_id?: string | null
  customer_name?: string | null
  customer_email?: string | null
  status?: string | null
  currency_code?: string | null
  currency_symbol?: string | null
  subtotal?: string | number | null
  tax_amount?: string | number | null
  discount?: string | number | null
  total?: string | number | null
  balance_due?: string | number | null
  amount_paid?: string | number | null
  line_items?: unknown[]
  raw_data?: Record<string, unknown>
}

export interface BooksInvoiceStats {
  total: number; outstanding: number; draft: number; sent: number; overdue: number; paid: number; partially_paid: number
  total_amount: string; total_outstanding: string
}

export interface BooksTransaction {
  id: string; transaction_id: string; transaction_type: string; number?: string | null
  customer_name?: string | null; vendor_name?: string | null; transaction_date?: string | null
  payment_mode?: string | null; amount?: string | number | null; currency_code?: string | null
  status?: string | null; reference_number?: string | null
}
export interface BooksTransactionsResponse { data: BooksTransaction[]; pagination: { page: number; per_page: number; count: number; total: number; more_records: boolean }; sync: { status: string; error?: string | null; last_successful_sync?: string | null } }
export interface BooksTransactionStats { total: number; counts: Record<string, number>; amounts: Record<string, string> }
