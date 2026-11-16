import React, { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Building2, Search, RefreshCw, Globe, Phone, MapPin, Briefcase, Code, ExternalLink } from 'lucide-react'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { TableSkeleton } from '@/components/common/LoadingSkeleton'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { Drawer } from '@/components/common/Drawer'
import { crmApi } from '@/api/crm'
import { useIntegrations } from '@/context/IntegrationContext'
import { formatDate } from '@/lib/utils'
import type { ZohoAccount } from '@/types/crm'
import { QuickSyncModal } from '@/components/sync/QuickSyncModal'

export const AccountsPage: React.FC = () => {
  const { activeIntegrationId, activeIntegration, hasActiveConnection } = useIntegrations()
  const isZohoSelected = activeIntegration?.provider === 'zoho' && activeIntegration.status === 'active'
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedAccount, setSelectedAccount] = useState<ZohoAccount | null>(null)
  const [activeTab, setActiveTab] = useState<'details' | 'raw'>('details')
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false)

  const {
    data: response,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['accounts', activeIntegrationId, page, perPage],
    queryFn: () =>
      crmApi.listAccounts({
        integration_id: activeIntegrationId || undefined,
        page,
        per_page: perPage,
      }),
    enabled: Boolean(activeIntegrationId) && hasActiveConnection && isZohoSelected,
    staleTime: 60000,
  })

  useEffect(() => {
    setPage(1)
    setSearchQuery('')
    setSelectedAccount(null)
  }, [activeIntegrationId])

  const accounts = response?.data || []
  const pagination = response?.pagination

  const filteredAccounts = accounts.filter((a) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      a.account_name.toLowerCase().includes(q) ||
      (a.industry && a.industry.toLowerCase().includes(q)) ||
      (a.billing_city && a.billing_city.toLowerCase().includes(q)) ||
      (a.website && a.website.toLowerCase().includes(q))
    )
  })

  return (
    <div className="space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Zoho CRM Accounts & Companies</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Enterprise company profiles, industry categorization, and contact domains mapped from Zoho CRM.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            isLoading={isFetching}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsSyncModalOpen(true)}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Sync Accounts
          </Button>
        </div>
      </div>

      {/* Main Table Card */}
      <Card noPadding>
        {/* Search Toolbar */}
        <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search companies by name, industry, city..."
              className="w-full bg-slate-50 border border-slate-200/80 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            {isFetching && <span className="text-[11px] text-indigo-600 animate-pulse">Syncing live records...</span>}
            <span className="font-medium text-slate-700">{filteredAccounts.length} displayed</span>
          </div>
        </div>

        {/* Content Table / Skeletons / Empty */}
        {!isZohoSelected ? (
          <div className="p-8">
            <EmptyState
              icon={Building2}
              title="No Zoho CRM Connection Selected"
              description="Select an active Zoho CRM integration or connect one in the Integrations section to view account profiles."
              actionLabel="Go to Integrations"
              onAction={() => (window.location.href = '/integrations')}
            />
          </div>
        ) : isLoading ? (
          <TableSkeleton rows={8} columns={5} />
        ) : error ? (
          <div className="p-8">
            <EmptyState
              icon={Building2}
              title="Unable to Retrieve Accounts"
              description={(error as Error).message || 'An error occurred while fetching accounts from Zoho.'}
              actionLabel="Retry"
              onAction={() => refetch()}
            />
          </div>
        ) : filteredAccounts.length === 0 ? (
          <div className="p-8">
            <EmptyState
              icon={Building2}
              title={searchQuery ? 'No Matching Accounts Found' : 'No Accounts Available in Zoho CRM'}
              description={
                searchQuery
                  ? `No records on current page matched "${searchQuery}".`
                  : 'Your connected Zoho CRM organization has no account records or requires initial synchronization.'
              }
              actionLabel={searchQuery ? 'Clear Search' : 'Sync Now'}
              onAction={searchQuery ? () => setSearchQuery('') : () => setIsSyncModalOpen(true)}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs divide-y divide-slate-100">
              <thead className="bg-slate-50/70 text-slate-500 font-medium">
                <tr>
                  <th className="py-3 px-4">Account / Company Name</th>
                  <th className="py-3 px-4">Industry</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Website</th>
                  <th className="py-3 px-4">Phone</th>
                  <th className="py-3 px-4">Billing City</th>
                  <th className="py-3 px-4">Country</th>
                  <th className="py-3 px-4">Owner</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredAccounts.map((account) => (
                  <tr
                    key={account.id}
                    onClick={() => {
                      setSelectedAccount(account)
                      setActiveTab('details')
                    }}
                    className="hover:bg-slate-50/80 cursor-pointer transition-colors group"
                  >
                    <td className="py-3.5 px-4 font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-full bg-sky-50 text-sky-700 flex items-center justify-center font-bold text-[11px] shrink-0">
                          {account.account_name[0]?.toUpperCase() || 'A'}
                        </div>
                        <span>{account.account_name}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">{account.account_type || '—'}</td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {account.industry ? (
                        <div className="flex items-center gap-1.5">
                          <Briefcase className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{account.industry}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {account.website ? (
                        <a
                          href={account.website.startsWith('http') ? account.website : `https://${account.website}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 hover:underline"
                        >
                          <Globe className="w-3 h-3" />
                          <span>{account.website.replace(/^https?:\/\//, '')}</span>
                        </a>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 font-mono text-[11px]">
                      {account.phone ? (
                        <div className="flex items-center gap-1.5">
                          <Phone className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{account.phone}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {account.billing_city ? (
                        <div className="flex items-center gap-1.5">
                          <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{account.billing_city}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">{account.billing_country || '—'}</td>
                    <td className="py-3.5 px-4 text-slate-600">{account.owner || '—'}</td>
                    <td className="py-3.5 px-4 text-right">
                      <Button variant="ghost" size="sm" className="text-indigo-600 group-hover:text-indigo-700">
                        View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <Pagination
          pagination={pagination}
          onPageChange={(newPage) => setPage(newPage)}
          onPerPageChange={(newPerPage) => {
            setPerPage(newPerPage)
            setPage(1)
          }}
          isLoading={isFetching}
        />
      </Card>

      {/* Detail Drawer */}
      {selectedAccount && (
        <Drawer
          isOpen={!!selectedAccount}
          onClose={() => setSelectedAccount(null)}
          title={selectedAccount.account_name}
          subtitle={`Account ID: ${selectedAccount.id}`}
        >
          <div className="flex border-b border-slate-200">
            <button
              onClick={() => setActiveTab('details')}
              className={`py-2 px-4 text-xs font-semibold border-b-2 transition-all ${
                activeTab === 'details'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Account Overview
            </button>
            <button
              onClick={() => setActiveTab('raw')}
              className={`py-2 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 ${
                activeTab === 'raw'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Code className="w-3.5 h-3.5" />
              <span>Raw Zoho API Payload</span>
            </button>
          </div>

          {activeTab === 'details' ? (
            <div className="space-y-6 pt-2">
              <div className="divide-y divide-slate-100 border border-slate-200/80 rounded-xl bg-slate-50/50 text-xs">
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Account Name</span>
                  <span className="text-slate-900 font-semibold">{selectedAccount.account_name}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Industry</span>
                  <span className="text-slate-900 font-medium">{selectedAccount.industry || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Account Type</span>
                  <span className="text-slate-900 font-medium">{selectedAccount.account_type || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Billing City</span>
                  <span className="text-slate-900 font-medium">{selectedAccount.billing_city || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Billing Country</span>
                  <span className="text-slate-900 font-medium">{selectedAccount.billing_country || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Website</span>
                  <span className="text-slate-900 font-mono">{selectedAccount.website || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Phone</span>
                  <span className="text-slate-900 font-mono">{selectedAccount.phone || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Owner</span>
                  <span className="text-slate-900 font-semibold">{selectedAccount.owner || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Created Time</span>
                  <span className="text-slate-800">{formatDate(selectedAccount.created_time)}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Last Modified</span>
                  <span className="text-slate-800">{formatDate(selectedAccount.modified_time)}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="pt-2">
              <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 text-[11px] font-mono overflow-x-auto max-h-[500px]">
                {JSON.stringify(selectedAccount.raw_data || selectedAccount, null, 2)}
              </pre>
            </div>
          )}
        </Drawer>
      )}

      {/* Quick Sync Modal */}
      {isSyncModalOpen && (
        <QuickSyncModal
          isOpen={isSyncModalOpen}
          onClose={() => setIsSyncModalOpen(false)}
          defaultIntegrationId={activeIntegrationId || undefined}
          defaultResourceType="accounts"
        />
      )}
    </div>
  )
}

