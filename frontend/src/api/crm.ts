import { apiClient } from './client'
import type {
  CrmQueryParams,
  PaginatedResponse,
  ZohoAccount,
  ZohoContact,
  ZohoDeal,
  ZohoLead,
} from '@/types/crm'

export const crmApi = {
  // Contacts
  listContacts: async (params?: CrmQueryParams): Promise<PaginatedResponse<ZohoContact>> => {
    const response = await apiClient.get<PaginatedResponse<ZohoContact>>('/zoho/contacts', {
      params,
    })
    return response.data
  },

  getContact: async (id: string, integrationId?: string): Promise<ZohoContact> => {
    const response = await apiClient.get<ZohoContact>(`/zoho/contacts/${id}`, {
      params: integrationId ? { integration_id: integrationId } : undefined,
    })
    return response.data
  },

  // Leads
  listLeads: async (params?: CrmQueryParams): Promise<PaginatedResponse<ZohoLead>> => {
    const response = await apiClient.get<PaginatedResponse<ZohoLead>>('/zoho/leads', {
      params,
    })
    return response.data
  },

  getLead: async (id: string, integrationId?: string): Promise<ZohoLead> => {
    const response = await apiClient.get<ZohoLead>(`/zoho/leads/${id}`, {
      params: integrationId ? { integration_id: integrationId } : undefined,
    })
    return response.data
  },

  // Deals
  listDeals: async (params?: CrmQueryParams): Promise<PaginatedResponse<ZohoDeal>> => {
    const response = await apiClient.get<PaginatedResponse<ZohoDeal>>('/zoho/deals', {
      params,
    })
    return response.data
  },

  getDeal: async (id: string, integrationId?: string): Promise<ZohoDeal> => {
    const response = await apiClient.get<ZohoDeal>(`/zoho/deals/${id}`, {
      params: integrationId ? { integration_id: integrationId } : undefined,
    })
    return response.data
  },

  // Accounts
  listAccounts: async (params?: CrmQueryParams): Promise<PaginatedResponse<ZohoAccount>> => {
    const response = await apiClient.get<PaginatedResponse<ZohoAccount>>('/zoho/accounts', {
      params,
    })
    return response.data
  },

  getAccount: async (id: string, integrationId?: string): Promise<ZohoAccount> => {
    const response = await apiClient.get<ZohoAccount>(`/zoho/accounts/${id}`, {
      params: integrationId ? { integration_id: integrationId } : undefined,
    })
    return response.data
  },
}

