import React, { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Target, Search, RefreshCw, Mail, Phone, Building, Calendar, Code } from 'lucide-react'
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
import type { ZohoLead } from '@/types/crm'
import { QuickSyncModal } from '@/components/sync/QuickSyncModal'

export const LeadsPage: React.FC = () => {
  const { activeIntegrationId, activeIntegration, hasActiveConnection } = useIntegrations()
  const isZohoSelected = activeIntegration?.provider === 'zoho' && activeIntegration.status === 'active'
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedLead, setSelectedLead] = useState<ZohoLead | null>(null)
  const [activeTab, setActiveTab] = useState<'details' | 'raw'>('details')
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false)

  const {
    data: response,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['leads', activeIntegrationId, page, perPage],
    queryFn: () =>
      crmApi.listLeads({
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
    setSelectedLead(null)
  }, [activeIntegrationId])

  const leads = response?.data || []
  const pagination = response?.pagination

  const filteredLeads = leads.filter((l) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    const fullName = `${l.first_name || ''} ${l.last_name || ''}`.toLowerCase()
    return (
      fullName.includes(q) ||
      (l.company && l.company.toLowerCase().includes(q)) ||
      (l.email && l.email.toLowerCase().includes(q)) ||
      (l.phone && l.phone.includes(q)) ||
      (l.lead_status && l.lead_status.toLowerCase().includes(q))
    )
  })

  return (
    <div className="space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Zoho CRM Leads</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Normalized sales prospects and leads retrieved from your Zoho CRM instance.
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
            Sync Leads
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
              placeholder="Search leads by name, company, status..."
              className="w-full bg-slate-50 border border-slate-200/80 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            {isFetching && <span className="text-[11px] text-indigo-600 animate-pulse">Syncing live records...</span>}
            <span className="font-medium text-slate-700">{filteredLeads.length} displayed</span>
          </div>
        </div>

        {/* Content Table / Skeletons / Empty */}
        {!isZohoSelected ? (
          <div className="p-8">
            <EmptyState
              icon={Target}
              title="No Zoho CRM Connection Selected"
              description="Select an active Zoho CRM integration or connect one in the Integrations section to view leads."
              actionLabel="Go to Integrations"
              onAction={() => (window.location.href = '/integrations')}
            />
          </div>
        ) : isLoading ? (
          <TableSkeleton rows={8} columns={5} />
        ) : error ? (
          <div className="p-8">
            <EmptyState
              icon={Target}
              title="Unable to Retrieve Leads"
              description={(error as Error).message || 'An error occurred while fetching leads from Zoho.'}
              actionLabel="Retry"
              onAction={() => refetch()}
            />
          </div>
        ) : filteredLeads.length === 0 ? (
          <div className="p-8">
            <EmptyState
              icon={Target}
              title={searchQuery ? 'No Matching Leads Found' : 'No Leads Available in Zoho CRM'}
              description={
                searchQuery
                  ? `No records on current page matched "${searchQuery}".`
                  : 'Your connected Zoho CRM account has no leads or requires synchronization.'
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
                  <th className="py-3 px-4">Lead Name</th>
                  <th className="py-3 px-4">Company</th>
                  <th className="py-3 px-4">Email</th>
                  <th className="py-3 px-4">Phone</th>
                  <th className="py-3 px-4">Lead Source</th>
                  <th className="py-3 px-4">Lead Status</th>
                  <th className="py-3 px-4">Owner</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredLeads.map((lead) => (
                  <tr
                    key={lead.id}
                    onClick={() => {
                      setSelectedLead(lead)
                      setActiveTab('details')
                    }}
                    className="hover:bg-slate-50/80 cursor-pointer transition-colors group"
                  >
                    <td className="py-3.5 px-4 font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-full bg-amber-50 text-amber-700 flex items-center justify-center font-bold text-[11px] shrink-0">
                          {lead.first_name?.[0]?.toUpperCase() || lead.last_name?.[0]?.toUpperCase() || 'L'}
                        </div>
                        <span>{lead.first_name ? `${lead.first_name} ${lead.last_name || ''}` : lead.last_name || '—'}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {lead.company ? (
                        <div className="flex items-center gap-1.5">
                          <Building className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{lead.company}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {lead.email ? (
                        <div className="flex items-center gap-1.5">
                          <Mail className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{lead.email}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 font-mono text-[11px]">
                      {lead.phone ? (
                        <div className="flex items-center gap-1.5">
                          <Phone className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{lead.phone}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">{lead.lead_source || '—'}</td>
                    <td className="py-3.5 px-4">
                      {lead.lead_status ? (
                        <Badge variant="neutral">{lead.lead_status}</Badge>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">{lead.owner || '—'}</td>
                    <td className="py-3.5 px-4 text-slate-400 text-[11px]">{formatDate(lead.created_time)}</td>
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
      {selectedLead && (
        <Drawer
          isOpen={!!selectedLead}
          onClose={() => setSelectedLead(null)}
          title={`${selectedLead.first_name || ''} ${selectedLead.last_name || ''}`.trim() || 'Lead'}
          subtitle={`Lead ID: ${selectedLead.id}`}
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
              Lead Information
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
                  <span className="text-slate-500 font-medium">Full Name</span>
                  <span className="text-slate-900 font-semibold">
                    {selectedLead.first_name ? `${selectedLead.first_name} ${selectedLead.last_name || ''}` : selectedLead.last_name || '—'}
                  </span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Company</span>
                  <span className="text-slate-900 font-semibold">{selectedLead.company || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Lead Status</span>
                  {selectedLead.lead_status ? (
                    <Badge variant="neutral">{selectedLead.lead_status}</Badge>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Lead Source</span>
                  <span className="text-slate-900 font-medium">{selectedLead.lead_source || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Email</span>
                  <span className="text-slate-900 font-mono">{selectedLead.email || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Phone</span>
                  <span className="text-slate-900 font-mono">{selectedLead.phone || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Owner</span>
                  <span className="text-slate-900 font-semibold">{selectedLead.owner || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Record Created</span>
                  <span className="text-slate-800">{formatDate(selectedLead.created_time)}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Last Modified</span>
                  <span className="text-slate-800">{formatDate(selectedLead.modified_time)}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="pt-2">
              <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 text-[11px] font-mono overflow-x-auto max-h-[500px]">
                {JSON.stringify(selectedLead.raw_data || selectedLead, null, 2)}
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
          defaultResourceType="leads"
        />
      )}
    </div>
  )
}

