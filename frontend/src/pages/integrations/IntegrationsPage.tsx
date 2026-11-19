import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Boxes,
  Plus,
  CheckCircle2,
  AlertCircle,
  Trash2,
  Activity,
  ExternalLink,
  Shield,
  Layers,
  Server,
  Globe,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { Modal } from '@/components/common/Modal'
import { Drawer } from '@/components/common/Drawer'
import { EmptyState } from '@/components/common/EmptyState'
import { TableSkeleton } from '@/components/common/LoadingSkeleton'
import { integrationsApi } from '@/api/integrations'
import { useIntegrations } from '@/context/IntegrationContext'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import { ZohoBooksOrganizations } from '@/components/integrations/ZohoBooksOrganizations'
import type { Integration, ZohoDataCenter, ConnectionHealthStatus } from '@/types/integration'

const ZOHO_DATA_CENTERS = [
  { value: 'in', label: 'India (.in) — accounts.zoho.in' },
  { value: 'us', label: 'United States (.com) — accounts.zoho.com' },
  { value: 'eu', label: 'European Union (.eu) — accounts.zoho.eu' },
  { value: 'au', label: 'Australia (.com.au) — accounts.zoho.com.au' },
  { value: 'ca', label: 'Canada (.ca) — accounts.zoho.ca' },
  { value: 'jp', label: 'Japan (.jp) — accounts.zoho.jp' },
  { value: 'cn', label: 'China (.com.cn) — accounts.zoho.com.cn' },
]

const defaultConnectionName = (product: 'crm' | 'books') => (
  product === 'books' ? 'My Zoho Books' : 'My Zoho CRM'
)

export const IntegrationsPage: React.FC = () => {
  const queryClient = useQueryClient()
  const { integrations, isLoading, refetchIntegrations } = useIntegrations()

  // Modal & Drawer States
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false)
  const [connectionProduct, setConnectionProduct] = useState<'crm' | 'books'>('crm')
  const [connectionName, setConnectionName] = useState('My Zoho CRM')
  const [selectedDc, setSelectedDc] = useState<ZohoDataCenter>('in')
  const [connectError, setConnectError] = useState<string | null>(null)

  const [inspectIntegration, setInspectIntegration] = useState<Integration | null>(null)
  const [booksOrganizationsIntegration, setBooksOrganizationsIntegration] = useState<Integration | null>(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  // Status check state
  const [healthStatusResult, setHealthStatusResult] = useState<{
    id: string
    data?: ConnectionHealthStatus
    loading: boolean
    error?: string
  } | null>(null)

  const openConnectDialog = (product: 'crm' | 'books' = 'crm') => {
    const previousDefault = defaultConnectionName(connectionProduct)
    setConnectError(null)
    setConnectionProduct(product)
    setConnectionName((currentName) => (
      !currentName.trim() || currentName === previousDefault
        ? defaultConnectionName(product)
        : currentName
    ))
    setIsConnectModalOpen(true)
  }

  // Connect mutation
  const connectMutation = useMutation({
    mutationFn: () => {
      const request = {
        connection_name: connectionName.trim(),
        data_center: selectedDc,
      }
      return connectionProduct === 'books'
        ? integrationsApi.initiateZohoBooksConnect(request)
        : integrationsApi.initiateZohoConnect(request)
    },
    onSuccess: (data) => {
      // Redirect to Zoho OAuth authorization screen
      window.location.href = data.authorization_url
    },
    onError: (err: any) => {
      setConnectError(err.message || 'Failed to initiate Zoho OAuth connection.')
    },
  })

  // Disconnect mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => integrationsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
      refetchIntegrations()
      setDeleteConfirmId(null)
      if (inspectIntegration) setInspectIntegration(null)
    },
  })

  // Check health status
  const handleCheckHealth = async (integration: Integration) => {
    setHealthStatusResult({ id: integration.id, loading: true })
    try {
      const result = await integrationsApi.checkStatus(integration.id)
      setHealthStatusResult({ id: integration.id, data: result, loading: false })
    } catch (err: any) {
      setHealthStatusResult({
        id: integration.id,
        loading: false,
        error: err.message || 'Health check failed.',
      })
    }
  }

  return (
    <div className="space-y-8">
      {/* Page Title & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">ERP Integrations</h2>
          <p className="text-xs text-slate-500 mt-1">
            Manage your connected ERP providers, check live API health, and authorize new connections.
          </p>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => openConnectDialog()}
          leftIcon={<Plus className="w-4 h-4" />}
        >
          Connect Zoho
        </Button>
      </div>

      {/* Active Connected ERP Instances Section */}
      <Card noPadding>
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Connected ERP Connections</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Authorized integrations under your account. Tokens are protected with Fernet AES encryption at rest.
            </p>
          </div>
          <span className="text-xs font-semibold px-2 py-0.5 bg-slate-100 rounded-full text-slate-700">
            {integrations.length} {integrations.length === 1 ? 'connection' : 'connections'}
          </span>
        </div>

        {isLoading ? (
          <TableSkeleton rows={3} columns={5} />
        ) : integrations.length === 0 ? (
          <div className="p-8">
            <EmptyState
              icon={Boxes}
              title="No ERP Accounts Connected"
              description="Authorize a Zoho CRM or Zoho Books account to connect it to OneDesk."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs divide-y divide-slate-100">
              <thead className="bg-slate-50/70 text-slate-500 font-medium">
                <tr>
                  <th className="py-3 px-4">Connection Name</th>
                  <th className="py-3 px-4">Provider</th>
                  <th className="py-3 px-4">Org / Account ID</th>
                  <th className="py-3 px-4">API Domain</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Connected At</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {integrations.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-slate-900">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-md bg-indigo-50 text-indigo-700 flex items-center justify-center font-bold text-[10px] uppercase shrink-0">
                          {item.product.substring(0, 2)}
                        </div>
                        <span>{item.connection_name}</span>
                      </div>
                    </td>
                        <td className="py-3.5 px-4 capitalize">{item.provider} {item.product}</td>
                    <td className="py-3.5 px-4 font-mono text-[11px] text-slate-500">
                      {item.external_account_id || '—'}
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 text-[11px]">{item.api_domain || 'Default'}</td>
                    <td className="py-3.5 px-4">
                      <Badge variant={item.status}>{item.status}</Badge>
                    </td>
                    <td className="py-3.5 px-4 text-slate-500">{formatDate(item.created_at)}</td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleCheckHealth(item)}
                          isLoading={healthStatusResult?.id === item.id && healthStatusResult.loading}
                          leftIcon={<Activity className="w-3.5 h-3.5 text-slate-400" />}
                          title="Check live remote connectivity"
                        >
                          Check Health
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setInspectIntegration(item)}
                        >
                          Details
                        </Button>
                        {item.product === 'books' && (
                          <Button variant="ghost" size="sm" onClick={() => setBooksOrganizationsIntegration(item)}>
                            Organizations
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteConfirmId(item.id)}
                          className="text-rose-600 hover:text-rose-700 hover:bg-rose-50 p-1.5"
                          title="Disconnect ERP"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Live Health Status Alert Result */}
      {healthStatusResult && !healthStatusResult.loading && (
        <div
          className={`p-4 rounded-xl border text-xs flex items-start gap-3 transition-all ${
            healthStatusResult.data?.status === 'connected'
              ? 'bg-emerald-50/80 border-emerald-200 text-emerald-900'
              : 'bg-rose-50/80 border-rose-200 text-rose-900'
          }`}
        >
          {healthStatusResult.data?.status === 'connected' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          )}
          <div className="flex-1">
            <div className="font-semibold text-sm">
              Remote Connection Check:{' '}
              {healthStatusResult.data?.status === 'connected' ? 'Healthy & Connected' : 'Health Check Failed'}
            </div>
            {healthStatusResult.data && (
              <div className="mt-1 space-y-0.5 text-xs">
                <div>
                  Organization:{' '}
                  <span className="font-semibold">{healthStatusResult.data.organization_name || 'Zoho CRM'}</span>
                </div>
                <div>
                  Provider Domain:{' '}
                  <span className="font-mono">{healthStatusResult.data.api_domain || 'Remote API'}</span>
                </div>
                <div>
                  Token Status: <Badge variant="active">{healthStatusResult.data.token_status || 'valid'}</Badge>
                </div>
              </div>
            )}
            {healthStatusResult.error && (
              <div className="mt-1 text-rose-700 font-medium">{healthStatusResult.error}</div>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setHealthStatusResult(null)}
            className="text-slate-400 hover:text-slate-700"
          >
            Dismiss
          </Button>
        </div>
      )}

      {/* ERP Marketplace / Available Providers */}
      <div>
        <div className="mb-4">
          <h3 className="text-base font-semibold text-slate-900 tracking-tight">ERP Integration Catalog</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Supported and upcoming enterprise platforms supported by OneDesk unified integration architecture.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Zoho CRM Card */}
          <Card className="flex flex-col justify-between border-indigo-200 bg-gradient-to-b from-white to-indigo-50/30">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold text-sm shadow-sm">
                  ZC
                </div>
                <Badge variant="active">Production Ready</Badge>
              </div>
              <h4 className="text-sm font-semibold text-slate-900">Zoho CRM v8</h4>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Official REST API v8 integration with automatic token refreshing, multi-datacenter support, and unified
                CRM data normalization.
              </p>
              <div className="mt-4 pt-4 border-t border-slate-100 space-y-1.5 text-[11px] text-slate-600">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Contacts, Leads, Deals, Accounts</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Incremental & On-demand sync</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  <span>US, EU, IN, AU, CA, JP, CN data centers</span>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100 text-center text-[11px] text-slate-500">
              Use the <span className="font-semibold text-slate-700">Connect Zoho</span> button above to choose CRM or Books.
            </div>
          </Card>

          {/* Zoho Books Card */}
          <Card className="flex flex-col justify-between border-emerald-200 bg-gradient-to-b from-white to-emerald-50/30">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center font-bold text-sm shadow-sm">
                  ZB
                </div>
                <Badge variant="active">OAuth Available</Badge>
              </div>
              <h4 className="text-sm font-semibold text-slate-900">Zoho Books</h4>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Secure, read-only authorization for your Zoho Books account. Organization selection and Books data are coming next.
              </p>
              <div className="mt-4 pt-4 border-t border-slate-100 space-y-1.5 text-[11px] text-slate-600">
                <div className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /><span>Read-only OAuth scopes</span></div>
                <div className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /><span>Multi-data-center support</span></div>
                <div className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /><span>Credentials encrypted at rest</span></div>
              </div>
            </div>
            <div className="mt-6 pt-4 border-t border-slate-100 text-center text-[11px] text-slate-500">
              Use the <span className="font-semibold text-slate-700">Connect Zoho</span> button above to choose CRM or Books.
            </div>
          </Card>

          {/* Odoo Card (Coming Soon) */}
          <Card className="flex flex-col justify-between opacity-80 bg-slate-50/50">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-xl bg-purple-700 text-white flex items-center justify-center font-bold text-sm">
                  OD
                </div>
                <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded bg-slate-200 text-slate-600">
                  Coming Soon
                </span>
              </div>
              <h4 className="text-sm font-semibold text-slate-900">Odoo ERP</h4>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Planned XML-RPC & JSON-RPC connectivity for Odoo Community and Enterprise editions, providing access to
                partners, sales, and products.
              </p>
              <div className="mt-4 pt-4 border-t border-slate-200/60 space-y-1.5 text-[11px] text-slate-500">
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                  <span>Odoo 16+ & 17+ support planned</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                  <span>Unified contact & partner pipeline</span>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-200/60">
              <Button variant="outline" size="sm" disabled className="w-full">
                Under Development
              </Button>
            </div>
          </Card>

          {/* SAP Card (Coming Soon) */}
          <Card className="flex flex-col justify-between opacity-80 bg-slate-50/50">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-xl bg-blue-900 text-white flex items-center justify-center font-bold text-sm">
                  SAP
                </div>
                <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded bg-slate-200 text-slate-600">
                  Coming Soon
                </span>
              </div>
              <h4 className="text-sm font-semibold text-slate-900">SAP S/4HANA</h4>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Planned SAP OData integration layer for Business Partner and Sales Order synchronization via SAP Cloud
                Platform API Management.
              </p>
              <div className="mt-4 pt-4 border-t border-slate-200/60 space-y-1.5 text-[11px] text-slate-500">
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                  <span>SAP S/4HANA Cloud & On-Premise</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                  <span>Enterprise Business Partner APIs</span>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-200/60">
              <Button variant="outline" size="sm" disabled className="w-full">
                Under Development
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* Connect Zoho Modal */}
      {isConnectModalOpen && (
        <Modal
          isOpen={isConnectModalOpen}
          onClose={() => setIsConnectModalOpen(false)}
          title={`Connect Zoho ${connectionProduct === 'books' ? 'Books' : 'CRM'} Account`}
          description="Initiate official OAuth 2.0 authorization with Zoho. You will be redirected to Zoho Accounts to grant permissions."
          maxWidth="md"
        >
          <div className="space-y-4 pt-2">
            {connectError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <span>{connectError}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Zoho Product</label>
              <select
                value={connectionProduct}
                onChange={(e) => {
                  const nextProduct = e.target.value as 'crm' | 'books'
                  const currentDefault = defaultConnectionName(connectionProduct)
                  setConnectionProduct(nextProduct)
                  setConnectionName((currentName) => (
                    !currentName.trim() || currentName === currentDefault
                      ? defaultConnectionName(nextProduct)
                      : currentName
                  ))
                }}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="crm">Zoho CRM</option>
                <option value="books">Zoho Books</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Connection Name</label>
              <input
                type="text"
                value={connectionName}
                onChange={(e) => setConnectionName(e.target.value)}
                placeholder={`e.g. Corporate Zoho ${connectionProduct === 'books' ? 'Books' : 'CRM'}`}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Zoho Data Center (Accounts Domain)
              </label>
              <select
                value={selectedDc}
                onChange={(e) => setSelectedDc(e.target.value as ZohoDataCenter)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {ZOHO_DATA_CENTERS.map((dc) => (
                  <option key={dc.value} value={dc.value}>
                    {dc.label}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-slate-500 mt-1">
                Select the region where your Zoho organization is hosted.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-600 space-y-1">
              <div className="font-semibold text-slate-900">OAuth Permissions Requested:</div>
              {connectionProduct === 'books' ? (
                <>
                  <div>&bull; ZohoBooks.settings.READ (Organization metadata)</div>
                  <div>&bull; ZohoBooks module READ scopes only</div>
                  <div className="text-slate-500 mt-1">No write, create, update, or delete permissions are requested.</div>
                </>
              ) : (
                <>
                  <div>&bull; ZohoCRM.modules.ALL (Contacts, Leads, Deals, Accounts)</div>
                  <div>&bull; ZohoCRM.settings.ALL (Organization metadata)</div>
                  <div>&bull; ZohoCRM.org.READ (Connection health and organization identity)</div>
                </>
              )}
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsConnectModalOpen(false)}
                disabled={connectMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => connectMutation.mutate()}
                isLoading={connectMutation.isPending}
                rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
              >
                Authorize with Zoho
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Disconnect Confirmation Modal */}
      {booksOrganizationsIntegration && (
        <Modal
          isOpen={!!booksOrganizationsIntegration}
          onClose={() => setBooksOrganizationsIntegration(null)}
          title={`Zoho Books Organizations — ${booksOrganizationsIntegration.connection_name}`}
          description="View and select the Zoho Books organization used for future Books data access."
          maxWidth="lg"
        >
          <ZohoBooksOrganizations integration={booksOrganizationsIntegration} />
        </Modal>
      )}

      {/* Disconnect Confirmation Modal */}
      {deleteConfirmId && (
        <Modal
          isOpen={!!deleteConfirmId}
          onClose={() => setDeleteConfirmId(null)}
          title="Disconnect ERP Integration"
          description="Are you sure you want to disconnect this ERP account? This will revoke access and delete associated sync history."
          maxWidth="sm"
        >
          <div className="pt-2 flex items-center justify-end gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeleteConfirmId(null)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => deleteMutation.mutate(deleteConfirmId)}
              isLoading={deleteMutation.isPending}
            >
              Disconnect
            </Button>
          </div>
        </Modal>
      )}

      {/* Details Drawer */}
      {inspectIntegration && (
        <Drawer
          isOpen={!!inspectIntegration}
          onClose={() => setInspectIntegration(null)}
          title={inspectIntegration.connection_name}
          subtitle={`Integration ID: ${inspectIntegration.id}`}
        >
          <div className="space-y-5 text-xs">
            <div>
              <h4 className="font-semibold text-slate-900 mb-2">Connection Metadata</h4>
              <div className="divide-y divide-slate-100 border border-slate-200/80 rounded-lg bg-slate-50/50">
                <div className="py-2.5 px-3 flex justify-between">
                  <span className="text-slate-500">Provider</span>
                  <span className="font-semibold uppercase">{inspectIntegration.provider}</span>
                </div>
                <div className="py-2.5 px-3 flex justify-between">
                  <span className="text-slate-500">Connection Name</span>
                  <span className="font-medium text-slate-900">{inspectIntegration.connection_name}</span>
                </div>
                <div className="py-2.5 px-3 flex justify-between">
                  <span className="text-slate-500">Organization ID</span>
                  <span className="font-mono text-slate-800">{inspectIntegration.external_account_id || '—'}</span>
                </div>
                <div className="py-2.5 px-3 flex justify-between">
                  <span className="text-slate-500">Status</span>
                  <Badge variant={inspectIntegration.status}>{inspectIntegration.status}</Badge>
                </div>
                <div className="py-2.5 px-3 flex justify-between">
                  <span className="text-slate-500">API Base Domain</span>
                  <span className="font-mono text-slate-800">{inspectIntegration.api_domain || 'Default'}</span>
                </div>
                <div className="py-2.5 px-3 flex justify-between">
                  <span className="text-slate-500">Access Token Expires At</span>
                  <span className="font-medium text-slate-800">
                    {formatDate(inspectIntegration.token_expires_at)}
                  </span>
                </div>
                <div className="py-2.5 px-3 flex justify-between">
                  <span className="text-slate-500">Connected Date</span>
                  <span className="text-slate-800">{formatDate(inspectIntegration.created_at)}</span>
                </div>
              </div>
            </div>

            <div className="p-3.5 rounded-lg bg-indigo-50/60 border border-indigo-200/60 flex items-start gap-2.5">
              <Shield className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
              <div className="text-[11px] text-indigo-900 leading-relaxed">
                OAuth access tokens and refresh tokens are encrypted at rest with Fernet symmetric AES encryption.
                Plaintext secrets are never exposed to API responses or logs.
              </div>
            </div>
          </div>
        </Drawer>
      )}
    </div>
  )
}

