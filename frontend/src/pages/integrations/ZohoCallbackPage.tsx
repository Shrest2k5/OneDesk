import React, { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, AlertCircle, Loader2, ArrowRight, ShieldCheck, Layers } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Card } from '@/components/common/Card'
import { useAuth } from '@/context/AuthContext'
import { useIntegrations } from '@/context/IntegrationContext'
import type { Integration } from '@/types/integration'

export const ZohoCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth()
  const { refetchIntegrations, setActiveIntegrationId } = useIntegrations()

  const callbackStatus = searchParams.get('status')
  const integrationId = searchParams.get('integration_id')

  const [isLoading, setIsLoading] = useState(true)
  const [integration, setIntegration] = useState<Integration | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (callbackStatus === 'error') {
      setIsLoading(false)
      setErrorMessage('Zoho authorization was canceled or could not be completed. No connection was created.')
      return
    }

    if (callbackStatus !== 'success' || !integrationId) {
      setIsLoading(false)
      setErrorMessage('This OAuth callback is incomplete or has expired. Please start the connection again.')
      return
    }

    if (isAuthLoading) return

    if (!isAuthenticated) {
      setIsLoading(false)
      setErrorMessage('Your OneDesk session has expired. Please sign in and check Integrations for the connection status.')
      return
    }

    let cancelled = false
    const refreshIntegrationState = async () => {
      try {
        // The backend has already exchanged the code and persisted encrypted tokens.
        // Refresh the normal authenticated source of truth; no OAuth parameters are
        // ever sent from React to the API.
        await queryClient.invalidateQueries({ queryKey: ['integrations'] })
        const result = await refetchIntegrations()
        const integrations = Array.isArray((result as { data?: unknown }).data)
          ? ((result as { data: Integration[] }).data)
          : []
        const connectedIntegration = integrations.find((item) => item.id === integrationId) || null
        if (!cancelled) {
          setIntegration(connectedIntegration)
          setActiveIntegrationId(integrationId)
        }
      } catch {
        // The OAuth operation succeeded server-side. Keep the success state even
        // if a transient integration-list refresh fails; the Integrations page can
        // retry through its existing query when the user navigates there.
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void refreshIntegrationState()
    return () => {
      cancelled = true
    }
  }, [callbackStatus, integrationId, isAuthenticated, isAuthLoading, queryClient, refetchIntegrations, setActiveIntegrationId])

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center mb-6">
        <div className="inline-flex w-12 h-12 rounded-xl bg-indigo-600 items-center justify-center text-white shadow-md shadow-indigo-200 mb-4">
          <Layers className="w-6 h-6" />
        </div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Zoho OAuth Authorization</h2>
        <p className="text-xs text-slate-500 mt-1">OneDesk Unified ERP Integration Handshake</p>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-lg">
        <Card className="p-8 text-center shadow-lg">
          {isLoading && (
            <div className="py-12 space-y-4">
              <Loader2 className="w-10 h-10 text-indigo-600 animate-spin mx-auto" />
              <div className="font-semibold text-slate-900 text-sm">Completing Secure Handshake...</div>
              <p className="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
                Exchanging authorization code with Zoho Accounts, verifying CSRF state token, and storing encrypted
                credentials in PostgreSQL.
              </p>
            </div>
          )}

          {!isLoading && !errorMessage && (
            <div className="space-y-6">
              <div className="w-14 h-14 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto shadow-sm">
                <CheckCircle2 className="w-8 h-8" />
              </div>

              <div>
                <h3 className="text-lg font-bold text-slate-900">Zoho CRM connected successfully!</h3>
                <p className="text-xs text-slate-500 mt-1">
                  {integration ? (
                    <>Connection established for <span className="font-semibold text-slate-800">{integration.connection_name}</span>.</>
                  ) : (
                    <>Your connection is ready. It will appear in Integrations shortly.</>
                  )}
                </p>
              </div>

              <div className="p-3 bg-indigo-50/70 border border-indigo-200/60 rounded-lg flex items-center gap-2 text-[11px] text-indigo-900 text-left">
                <ShieldCheck className="w-4 h-4 text-indigo-600 shrink-0" />
                <span>Your Zoho credentials remain encrypted and are never sent to this page.</span>
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                <Button variant="outline" size="md" onClick={() => navigate('/integrations')} className="w-full sm:w-auto">
                  View Integrations
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  onClick={() => navigate('/crm/contacts')}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                  className="w-full sm:w-auto"
                >
                  Explore CRM Contacts
                </Button>
              </div>
            </div>
          )}

          {!isLoading && errorMessage && (
            <div className="space-y-6">
              <div className="w-14 h-14 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center mx-auto shadow-sm">
                <AlertCircle className="w-8 h-8" />
              </div>

              <div>
                <h3 className="text-lg font-bold text-slate-900">Connection Failed</h3>
                <p className="text-xs text-rose-600 mt-1 max-w-sm mx-auto">{errorMessage}</p>
              </div>

              <div className="flex items-center justify-center gap-3 pt-4">
                <Button variant="primary" size="md" onClick={() => navigate('/integrations')}>
                  Return to Integrations
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

