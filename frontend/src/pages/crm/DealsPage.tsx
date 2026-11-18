import React, { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BadgeDollarSign, Search, RefreshCw, Calendar, Building, DollarSign, Code, TrendingUp } from 'lucide-react'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { TableSkeleton } from '@/components/common/LoadingSkeleton'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { Drawer } from '@/components/common/Drawer'
import { crmApi } from '@/api/crm'
import { useIntegrations } from '@/context/IntegrationContext'
import { formatDate, formatCurrency } from '@/lib/utils'
import type { ZohoDeal } from '@/types/crm'
import { QuickSyncModal } from '@/components/sync/QuickSyncModal'

export const DealsPage: React.FC = () => {
  const { activeIntegrationId, activeIntegration, hasActiveConnection } = useIntegrations()
  const isZohoSelected = activeIntegration?.provider === 'zoho' && activeIntegration.product === 'crm' && activeIntegration.status === 'active'
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDeal, setSelectedDeal] = useState<ZohoDeal | null>(null)
  const [activeTab, setActiveTab] = useState<'details' | 'raw'>('details')
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false)

  const {
    data: response,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['deals', activeIntegrationId, page, perPage],
    queryFn: () =>
      crmApi.listDeals({
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
    setSelectedDeal(null)
  }, [activeIntegrationId])

  const deals = response?.data || []
  const pagination = response?.pagination

  const filteredDeals = deals.filter((d) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      d.deal_name.toLowerCase().includes(q) ||
      (d.stage && d.stage.toLowerCase().includes(q)) ||
      (d.account_name && d.account_name.toLowerCase().includes(q))
    )
  })

  // Calculate total pipeline value on current page
  const pagePipelineValue = filteredDeals.reduce((sum, d) => sum + (d.amount || 0), 0)

  return (
    <div className="space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Zoho CRM Deals & Opportunities</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Active sales opportunities, revenue stages, and deal pipelines normalized from Zoho CRM.
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
            Sync Deals
          </Button>
        </div>
      </div>

      {/* Main Table Card */}
      <Card noPadding>
        {/* Search Toolbar & Page Summary */}
        <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search deals by name, stage, account..."
              className="w-full bg-slate-50 border border-slate-200/80 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex items-center gap-4 text-xs">
            {pagePipelineValue > 0 && (
              <div className="flex items-center gap-1.5 text-slate-700 font-semibold bg-emerald-50 px-2.5 py-1 rounded-md border border-emerald-200/70">
                <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
                <span>Page Value: {formatCurrency(pagePipelineValue)}</span>
              </div>
            )}
            <span className="font-medium text-slate-600">{filteredDeals.length} displayed</span>
          </div>
        </div>

        {/* Content Table / Skeletons / Empty */}
        {!isZohoSelected ? (
          <div className="p-8">
            <EmptyState
              icon={BadgeDollarSign}
              title="No Zoho CRM Connection Selected"
              description="Select an active Zoho CRM integration or connect one in the Integrations section to view deals."
              actionLabel="Go to Integrations"
              onAction={() => (window.location.href = '/integrations')}
            />
          </div>
        ) : isLoading ? (
          <TableSkeleton rows={8} columns={6} />
        ) : error ? (
          <div className="p-8">
            <EmptyState
              icon={BadgeDollarSign}
              title="Unable to Retrieve Deals"
              description={(error as Error).message || 'An error occurred while fetching deals from Zoho.'}
              actionLabel="Retry"
              onAction={() => refetch()}
            />
          </div>
        ) : filteredDeals.length === 0 ? (
          <div className="p-8">
            <EmptyState
              icon={BadgeDollarSign}
              title={searchQuery ? 'No Matching Deals Found' : 'No Deals Available in Zoho CRM'}
              description={
                searchQuery
                  ? `No records on current page matched "${searchQuery}".`
                  : 'Your connected Zoho CRM account has no deal records or requires synchronization.'
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
                  <th className="py-3 px-4">Deal Name</th>
                  <th className="py-3 px-4">Amount</th>
                  <th className="py-3 px-4">Currency</th>
                  <th className="py-3 px-4">Stage</th>
                  <th className="py-3 px-4">Expected Closing Date</th>
                  <th className="py-3 px-4">Account Name</th>
                  <th className="py-3 px-4">Owner</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredDeals.map((deal) => (
                  <tr
                    key={deal.id}
                    onClick={() => {
                      setSelectedDeal(deal)
                      setActiveTab('details')
                    }}
                    className="hover:bg-slate-50/80 cursor-pointer transition-colors group"
                  >
                    <td className="py-3.5 px-4 font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-full bg-emerald-50 text-emerald-700 flex items-center justify-center font-bold text-[11px] shrink-0">
                          $
                        </div>
                        <span>{deal.deal_name}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-semibold text-slate-900">
                      {deal.amount !== null && deal.amount !== undefined ? (
                        formatCurrency(deal.amount)
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">{deal.currency || '—'}</td>
                    <td className="py-3.5 px-4">
                      {deal.stage ? (
                        <Badge variant="primary">{deal.stage}</Badge>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {deal.closing_date ? (
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{deal.closing_date}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {deal.account_name ? (
                        <div className="flex items-center gap-1.5">
                          <Building className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{deal.account_name}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">{deal.owner || '—'}</td>
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
      {selectedDeal && (
        <Drawer
          isOpen={!!selectedDeal}
          onClose={() => setSelectedDeal(null)}
          title={selectedDeal.deal_name}
          subtitle={`Deal ID: ${selectedDeal.id}`}
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
              Deal Overview
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
                  <span className="text-slate-500 font-medium">Deal Name</span>
                  <span className="text-slate-900 font-semibold">{selectedDeal.deal_name}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Deal Amount</span>
                  <span className="text-emerald-700 font-bold">{formatCurrency(selectedDeal.amount)}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Currency</span>
                  <span className="text-slate-900 font-medium">{selectedDeal.currency || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Pipeline Stage</span>
                  {selectedDeal.stage ? <Badge variant="primary">{selectedDeal.stage}</Badge> : '—'}
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Closing Date</span>
                  <span className="text-slate-900 font-medium">{selectedDeal.closing_date || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Account Name</span>
                  <span className="text-slate-900 font-medium">{selectedDeal.account_name || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Probability</span>
                  <span className="text-slate-900 font-medium">{selectedDeal.probability ?? '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Owner</span>
                  <span className="text-slate-900 font-semibold">{selectedDeal.owner || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Created Time</span>
                  <span className="text-slate-800">{formatDate(selectedDeal.created_time)}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Last Modified</span>
                  <span className="text-slate-800">{formatDate(selectedDeal.modified_time)}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="pt-2">
              <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 text-[11px] font-mono overflow-x-auto max-h-[500px]">
                {JSON.stringify(selectedDeal.raw_data || selectedDeal, null, 2)}
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
          defaultResourceType="deals"
        />
      )}
    </div>
  )
}

