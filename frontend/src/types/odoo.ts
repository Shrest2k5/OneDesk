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

export interface OdooLineItem {
  id: string
  product_id?: string | null
  product_name?: string | null
  name?: string | null
  quantity: number
  price_unit: number
  discount: number
  price_subtotal: number
  price_total: number
  taxes?: Array<{ id: number; name: string }> | null
  account_id?: string | null
}

export interface OdooInvoice {
  id: string
  invoice_id: string
  invoice_number?: string | null
  reference_number?: string | null
  customer_id?: string | null
  customer_name?: string | null
  status: string
  payment_state: string
  invoice_date?: string | null
  due_date?: string | null
  currency?: string | null
  currency_id?: number | null
  subtotal: number
  tax_amount: number
  total: number
  balance_due: number
  amount_paid: number
  line_items: OdooLineItem[]
  line_item_count: number
  created_at?: string | null
  updated_at?: string | null
}

export interface OdooBill {
  id: string
  bill_id: string
  bill_number?: string | null
  reference_number?: string | null
  vendor_id?: string | null
  vendor_name?: string | null
  status: string
  payment_state: string
  bill_date?: string | null
  due_date?: string | null
  currency?: string | null
  currency_id?: number | null
  subtotal: number
  tax_amount: number
  total: number
  balance_due: number
  amount_paid: number
  line_items: OdooLineItem[]
  line_item_count: number
  created_at?: string | null
  updated_at?: string | null
}

export interface OdooCreditNote {
  id: string
  credit_note_id: string
  credit_note_number?: string | null
  credit_note_type: 'customer' | 'vendor'
  reference_number?: string | null
  partner_id?: string | null
  partner_name?: string | null
  status: string
  payment_state: string
  date?: string | null
  currency?: string | null
  currency_id?: number | null
  subtotal: number
  tax_amount: number
  total: number
  balance_due: number
  amount_paid: number
  line_items: OdooLineItem[]
  line_item_count: number
  created_at?: string | null
  updated_at?: string | null
}

export interface OdooPayment {
  id: string
  payment_id: string
  payment_number?: string | null
  payment_reference?: string | null
  payment_type: 'inbound' | 'outbound'
  partner_type?: string | null
  partner_id?: string | null
  partner_name?: string | null
  amount: number
  currency?: string | null
  currency_id?: number | null
  payment_date?: string | null
  status: string
  is_reconciled: boolean
  reconciled_invoice_ids: number[]
  reconciled_bill_ids: number[]
  journal?: { id: number; name: string } | null
  created_at?: string | null
  updated_at?: string | null
}

export interface OdooTransactionJournalLine {
  id: string
  account_id?: string | null
  account_name?: string | null
  name?: string | null
  partner_id?: string | null
  partner_name?: string | null
  debit: number
  credit: number
  balance: number
}

export interface OdooTransaction {
  id: string
  entry_id: string
  entry_number?: string | null
  number?: string | null
  transaction_type: 'journal_entry' | 'bank_transaction'
  reference?: string | null
  date?: string | null
  journal?: { id: number; name: string } | null
  partner?: { id: number; name: string } | null
  status: string
  currency?: string | null
  currency_id?: number | null
  total_amount: number
  amount?: number
  lines: OdooTransactionJournalLine[]
  line_count: number
  created_at?: string | null
  updated_at?: string | null
}

export interface OdooInvoiceStats {
  total: number
  draft: number
  posted: number
  cancelled: number
  paid: number
  not_paid: number
  partial: number
  in_payment: number
  total_amount: string
  total_outstanding: string
  total_paid: string
}

export interface OdooBillStats {
  total: number
  draft: number
  posted: number
  cancelled: number
  paid: number
  not_paid: number
  partial: number
  in_payment: number
  total_amount: string
  total_outstanding: string
  total_paid: string
}

export interface OdooCreditNoteStats {
  total: number
  customer_credit_notes: number
  vendor_credit_notes: number
  total_amount: string
}

export interface OdooPaymentStats {
  total: number
  customer_payments: number
  vendor_payments: number
  total_inbound: string
  total_outbound: string
  reconciled: number
}

export interface OdooTransactionStats {
  total: number
  journal_entries: number
  bank_transactions: number
  total_amount: string
}

export interface OdooFinancialResponse<T> {
  data: T[]
  pagination: { page: number; per_page: number; count: number; total: number; more_records: boolean }
  sync: { status: string; error?: string | null; last_successful_sync?: string | null }
}
