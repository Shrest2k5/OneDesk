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
import type { OdooContactStats, OdooContactsResponse } from '@/types/odoo'

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

