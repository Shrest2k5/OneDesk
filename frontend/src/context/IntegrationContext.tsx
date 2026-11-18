import React, { createContext, useContext, useState, useEffect } from 'react'
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
}

const IntegrationContext = createContext<IntegrationContextType | undefined>(undefined)

export const IntegrationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth()
  const [activeIntegrationId, setActiveIntegrationId] = useState<string | null>(null)

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
    const selectedStillExists = activeIntegrationId && integrations.some((integration) => integration.id === activeIntegrationId)
    if (integrations.length > 0 && !selectedStillExists) {
      const active = integrations.find((i) => i.status === 'active' && i.product === 'crm')
        || integrations.find((i) => i.status === 'active')
        || integrations[0]
      setActiveIntegrationId(active.id)
    } else if (integrations.length === 0) {
      setActiveIntegrationId(null)
    }
  }, [integrations, activeIntegrationId])

  const activeIntegration = integrations.find((i) => i.id === activeIntegrationId) || null
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

