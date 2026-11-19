import React, { createContext, useCallback, useContext, useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { integrationsApi } from '@/api/integrations'
import type { Integration } from '@/types/integration'
import { useAuth } from './AuthContext'

interface IntegrationContextType {
  integrations: Integration[]
  activeIntegration: Integration | null
  activeIntegrationId: string | null
  setActiveIntegrationId: (id: string | null) => void
  isLoading: boolean
  hasActiveConnection: boolean
  refetchIntegrations: () => Promise<unknown>
  getIntegrationForProduct: (product: Integration['product']) => Integration | null
}

const IntegrationContext = createContext<IntegrationContextType | undefined>(undefined)
const ACTIVE_INTEGRATION_STORAGE_KEY = 'onedesk_active_integration_id'

export const IntegrationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth()
  const [activeIntegrationId, setActiveIntegrationIdState] = useState<string | null>(() => (
    localStorage.getItem(ACTIVE_INTEGRATION_STORAGE_KEY)
  ))

  const setActiveIntegrationId = useCallback((id: string | null) => {
    setActiveIntegrationIdState(id)
    if (id) {
      localStorage.setItem(ACTIVE_INTEGRATION_STORAGE_KEY, id)
    } else {
      localStorage.removeItem(ACTIVE_INTEGRATION_STORAGE_KEY)
    }
  }, [])

  const {
    data: integrations = [],
    isLoading,
    refetch: refetchIntegrations,
  } = useQuery({
    queryKey: ['integrations'],
    queryFn: integrationsApi.list,
    enabled: isAuthenticated,
    staleTime: 30000,
  })

  // Set default active integration if available and none selected
  useEffect(() => {
    if (isLoading) return
    const selectedStillExists = activeIntegrationId && integrations.some((integration) => integration.id === activeIntegrationId)
    if (integrations.length > 0 && !selectedStillExists) {
      const active = integrations.find((i) => i.status === 'active' && i.product === 'crm')
        || integrations.find((i) => i.status === 'active')
        || integrations[0]
      setActiveIntegrationId(active.id)
    } else if (integrations.length === 0) {
      setActiveIntegrationId(null)
    }
  }, [integrations, activeIntegrationId, isLoading, setActiveIntegrationId])

  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated) {
      setActiveIntegrationId(null)
    }
  }, [isAuthenticated, isAuthLoading, setActiveIntegrationId])

  const activeIntegration = integrations.find((i) => i.id === activeIntegrationId) || null
  const getIntegrationForProduct = useCallback((product: Integration['product']) => {
    // The backend integration list is authoritative. A persisted ID is only
    // accepted when it resolves to the requested product in that list.
    if (activeIntegration?.product === product && activeIntegration.status === 'active') {
      return activeIntegration
    }
    return integrations.find((integration) => (
      integration.product === product && integration.status === 'active'
    )) || null
  }, [activeIntegration, integrations])
  const hasActiveConnection = integrations.some((i) => i.status === 'active')

  return (
    <IntegrationContext.Provider
      value={{
        integrations,
        activeIntegration,
        activeIntegrationId,
        setActiveIntegrationId,
        isLoading,
        hasActiveConnection,
        refetchIntegrations,
        getIntegrationForProduct,
      }}
    >
      {children}
    </IntegrationContext.Provider>
  )
}

export const useIntegrations = (): IntegrationContextType => {
  const context = useContext(IntegrationContext)
  if (!context) {
    throw new Error('useIntegrations must be used within an IntegrationProvider')
  }
  return context
}

