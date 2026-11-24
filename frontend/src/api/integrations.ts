import { apiClient } from './client'
import type {
  ConnectionHealthStatus,
  Integration,
  ZohoConnectRequest,
  ZohoConnectResponse,
  OdooConnectRequest,
  OdooConnectResponse,
  BooksOrganization,
} from '@/types/integration'
import type { BooksContactStats, BooksContactsResponse, BooksInvoiceStats, BooksTransactionsResponse, BooksTransactionStats, BooksPurchasesResponse } from '@/types/books'
import type {
  OdooContactStats,
  OdooContactsResponse,
  OdooInvoice,
  OdooBill,
  OdooCreditNote,
  OdooPayment,
  OdooTransaction,
  OdooInvoiceStats,
  OdooBillStats,
  OdooCreditNoteStats,
  OdooPaymentStats,
  OdooTransactionStats,
  OdooFinancialResponse,
} from '@/types/odoo'

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

  initiateZohoBooksConnect: async (data: ZohoConnectRequest): Promise<ZohoConnectResponse> => {
    const response = await apiClient.post<ZohoConnectResponse>('/integrations/zoho/books/connect', data)
    return response.data
  },

  connectOdoo: async (data: OdooConnectRequest): Promise<OdooConnectResponse> => {
    const response = await apiClient.post<OdooConnectResponse>('/integrations/odoo/connect', data)
    return response.data
  },

  listOdooContacts: async (integrationId: string, params: { page: number; per_page: number; kind?: string; search?: string; include_archived?: boolean }): Promise<OdooContactsResponse> => {
    const response = await apiClient.get<OdooContactsResponse>(`/integrations/odoo/${integrationId}/contacts`, { params })
    return response.data
  },

  odooContactStats: async (integrationId: string): Promise<OdooContactStats> => {
    const response = await apiClient.get<OdooContactStats>(`/integrations/odoo/${integrationId}/contacts/stats`)
    return response.data
  },

  refreshOdooContacts: async (integrationId: string, per_page = 200): Promise<Record<string, unknown>> => {
    const response = await apiClient.post<Record<string, unknown>>(`/integrations/odoo/${integrationId}/contacts/refresh`, undefined, { params: { async_mode: true, per_page } })
    return response.data
  },

  // Odoo Financial Resources
  listOdooInvoices: async (integrationId: string, params: Record<string, string | number | boolean | undefined>): Promise<OdooFinancialResponse<OdooInvoice>> => {
    const response = await apiClient.get<OdooFinancialResponse<OdooInvoice>>(`/integrations/odoo/${integrationId}/invoices`, { params })
    return response.data
  },

  odooInvoiceStats: async (integrationId: string): Promise<OdooInvoiceStats> => {
    const response = await apiClient.get<OdooInvoiceStats>(`/integrations/odoo/${integrationId}/invoices/stats`)
    return response.data
  },

  refreshOdooInvoices: async (integrationId: string, per_page = 200): Promise<Record<string, unknown>> => {
    const response = await apiClient.post<Record<string, unknown>>(`/integrations/odoo/${integrationId}/invoices/refresh`, undefined, { params: { async_mode: true, per_page } })
    return response.data
  },

  listOdooBills: async (integrationId: string, params: Record<string, string | number | boolean | undefined>): Promise<OdooFinancialResponse<OdooBill>> => {
    const response = await apiClient.get<OdooFinancialResponse<OdooBill>>(`/integrations/odoo/${integrationId}/bills`, { params })
    return response.data
  },

  odooBillStats: async (integrationId: string): Promise<OdooBillStats> => {
    const response = await apiClient.get<OdooBillStats>(`/integrations/odoo/${integrationId}/bills/stats`)
    return response.data
  },

  refreshOdooBills: async (integrationId: string, per_page = 200): Promise<Record<string, unknown>> => {
    const response = await apiClient.post<Record<string, unknown>>(`/integrations/odoo/${integrationId}/bills/refresh`, undefined, { params: { async_mode: true, per_page } })
    return response.data
  },

  listOdooCreditNotes: async (integrationId: string, params: Record<string, string | number | boolean | undefined>): Promise<OdooFinancialResponse<OdooCreditNote>> => {
    const response = await apiClient.get<OdooFinancialResponse<OdooCreditNote>>(`/integrations/odoo/${integrationId}/credit-notes`, { params })
    return response.data
  },

  odooCreditNoteStats: async (integrationId: string): Promise<OdooCreditNoteStats> => {
    const response = await apiClient.get<OdooCreditNoteStats>(`/integrations/odoo/${integrationId}/credit-notes/stats`)
    return response.data
  },

  refreshOdooCreditNotes: async (integrationId: string, per_page = 200): Promise<Record<string, unknown>> => {
    const response = await apiClient.post<Record<string, unknown>>(`/integrations/odoo/${integrationId}/credit-notes/refresh`, undefined, { params: { async_mode: true, per_page } })
    return response.data
  },

  listOdooPayments: async (integrationId: string, params: Record<string, string | number | boolean | undefined>): Promise<OdooFinancialResponse<OdooPayment>> => {
    const response = await apiClient.get<OdooFinancialResponse<OdooPayment>>(`/integrations/odoo/${integrationId}/payments`, { params })
    return response.data
  },

  odooPaymentStats: async (integrationId: string): Promise<OdooPaymentStats> => {
    const response = await apiClient.get<OdooPaymentStats>(`/integrations/odoo/${integrationId}/payments/stats`)
    return response.data
  },

  refreshOdooPayments: async (integrationId: string, per_page = 200): Promise<Record<string, unknown>> => {
    const response = await apiClient.post<Record<string, unknown>>(`/integrations/odoo/${integrationId}/payments/refresh`, undefined, { params: { async_mode: true, per_page } })
    return response.data
  },

  listOdooTransactions: async (integrationId: string, params: Record<string, string | number | boolean | undefined>): Promise<OdooFinancialResponse<OdooTransaction>> => {
    const response = await apiClient.get<OdooFinancialResponse<OdooTransaction>>(`/integrations/odoo/${integrationId}/transactions`, { params })
    return response.data
  },

  odooTransactionStats: async (integrationId: string): Promise<OdooTransactionStats> => {
    const response = await apiClient.get<OdooTransactionStats>(`/integrations/odoo/${integrationId}/transactions/stats`)
    return response.data
  },

  refreshOdooTransactions: async (integrationId: string, per_page = 200): Promise<Record<string, unknown>> => {
    const response = await apiClient.post<Record<string, unknown>>(`/integrations/odoo/${integrationId}/transactions/refresh`, undefined, { params: { async_mode: true, per_page } })
    return response.data
  },

  listBooksOrganizations: async (integrationId: string): Promise<BooksOrganization[]> => {
    const response = await apiClient.get<BooksOrganization[]>(`/integrations/zoho/books/${integrationId}/organizations`)
    return response.data
  },

  refreshBooksOrganizations: async (integrationId: string): Promise<BooksOrganization[]> => {
    const response = await apiClient.post<BooksOrganization[]>(`/integrations/zoho/books/${integrationId}/organizations/refresh`)
    return response.data
  },

  selectBooksOrganization: async (integrationId: string, organizationId: string): Promise<BooksOrganization> => {
    const response = await apiClient.put<BooksOrganization>(
      `/integrations/zoho/books/${integrationId}/organizations/${encodeURIComponent(organizationId)}/select`,
    )
    return response.data
  },

  selectedBooksOrganization: async (integrationId: string): Promise<BooksOrganization | null> => {
    const response = await apiClient.get<BooksOrganization | null>(`/integrations/zoho/books/${integrationId}/organizations/selected`)
    return response.data
  },

  listBooksContacts: async (integrationId: string, params: { page: number; per_page: number; contact_type?: string; search?: string }): Promise<BooksContactsResponse> => {
    const response = await apiClient.get<BooksContactsResponse>(`/integrations/zoho/books/${integrationId}/contacts`, { params })
    return response.data
  },

  booksContactStats: async (integrationId: string): Promise<BooksContactStats> => {
    const response = await apiClient.get<BooksContactStats>(`/integrations/zoho/books/${integrationId}/contacts/stats`)
    return response.data
  },

  refreshBooksContacts: async (integrationId: string): Promise<Record<string, unknown>> => {
    const response = await apiClient.post<Record<string, unknown>>(`/integrations/zoho/books/${integrationId}/contacts/refresh`)
    return response.data
  },

  listBooksInvoices: async (integrationId: string, params: Record<string, string | number | undefined>) => {
    const response = await apiClient.get(`/integrations/zoho/books/${integrationId}/invoices`, { params })
    return response.data
  },

  booksInvoiceStats: async (integrationId: string): Promise<BooksInvoiceStats> => {
    const response = await apiClient.get<BooksInvoiceStats>(`/integrations/zoho/books/${integrationId}/invoices/stats`)
    return response.data
  },

  refreshBooksInvoices: async (integrationId: string): Promise<Record<string, unknown>> => {
    const response = await apiClient.post<Record<string, unknown>>(`/integrations/zoho/books/${integrationId}/invoices/refresh`)
    return response.data
  },
  listBooksTransactions: async (integrationId: string, params: Record<string, string | number | undefined>): Promise<BooksTransactionsResponse> => (await apiClient.get<BooksTransactionsResponse>(`/integrations/zoho/books/${integrationId}/transactions`, { params })).data,
  booksTransactionStats: async (integrationId: string, params?: Record<string, string | undefined>): Promise<BooksTransactionStats> => (await apiClient.get<BooksTransactionStats>(`/integrations/zoho/books/${integrationId}/transactions/stats`, { params })).data,
  refreshBooksTransactions: async (integrationId: string, params?: Record<string, string | undefined>): Promise<Record<string, unknown>> => (await apiClient.post<Record<string, unknown>>(`/integrations/zoho/books/${integrationId}/transactions/refresh`, undefined, { params: { ...params, async_mode: 'true' } })).data,
  listBooksPurchases: async (integrationId: string, resource: string, params: Record<string, string | number | undefined>): Promise<BooksPurchasesResponse> => (await apiClient.get<BooksPurchasesResponse>(`/integrations/zoho/books/${integrationId}/purchases/${resource}`, { params })).data,
  refreshBooksPurchases: async (integrationId: string, params?: Record<string, string | undefined>): Promise<Record<string, unknown>> => (await apiClient.post<Record<string, unknown>>(`/integrations/zoho/books/${integrationId}/purchases/refresh`, undefined, { params: { ...params, async_mode: 'true' } })).data,
}

