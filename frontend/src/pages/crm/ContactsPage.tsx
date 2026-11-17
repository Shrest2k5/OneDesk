import React, { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Users, Search, RefreshCw, Mail, Phone, Building, Code, Database, CheckCircle2 } from 'lucide-react'
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
import type { ZohoContact } from '@/types/crm'
import { QuickSyncModal } from '@/components/sync/QuickSyncModal'

export const ContactsPage: React.FC = () => {
  const { activeIntegrationId, activeIntegration, hasActiveConnection } = useIntegrations()
  const isZohoSelected = activeIntegration?.provider === 'zoho' && activeIntegration.status === 'active'
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedContact, setSelectedContact] = useState<ZohoContact | null>(null)
  const [activeTab, setActiveTab] = useState<'details' | 'raw'>('details')
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false)

  const {
    data: response,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['contacts', activeIntegrationId, page, perPage],
    queryFn: () =>
      crmApi.listContacts({
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
    setSelectedContact(null)
  }, [activeIntegrationId])

  const contacts = response?.data || []
  const pagination = response?.pagination
  const recordsOnPage = pagination?.count ?? contacts.length

  // Client-side quick filter on current page
  const filteredContacts = contacts.filter((c) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    const fullName = `${c.first_name || ''} ${c.last_name || ''}`.toLowerCase()
    return (
      fullName.includes(q) ||
      (c.email && c.email.toLowerCase().includes(q)) ||
      (c.phone && c.phone.includes(q)) ||
      (c.account_name && c.account_name.toLowerCase().includes(q))
    )
  })

  return (
    <div className="space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
              <Users className="h-4 w-4" />
            </span>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Contacts</h2>
          </div>
          <p className="text-sm text-slate-500">
            Browse and manage contact records from the selected Zoho CRM organization.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {isZohoSelected && activeIntegration && (
            <Badge variant="active" className="bg-white">
              <Database className="h-3 w-3" />
              {activeIntegration.connection_name}
            </Badge>
          )}
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
            Sync Contacts
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Card noPadding className="p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Records loaded</span>
            <Users className="h-4 w-4 text-indigo-600" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-slate-900">{recordsOnPage}</div>
          <p className="mt-1 text-[11px] text-slate-500">Returned on the current page</p>
        </Card>
        <Card noPadding className="p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Filtered view</span>
            <Search className="h-4 w-4 text-slate-500" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-slate-900">{filteredContacts.length}</div>
          <p className="mt-1 text-[11px] text-slate-500">Matching the current search</p>
        </Card>
        <Card noPadding className="p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Connection</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-2 text-lg font-bold tracking-tight text-slate-900">
            {isZohoSelected ? 'Live' : 'Not selected'}
          </div>
          <p className="mt-1 text-[11px] text-slate-500">Zoho CRM data source</p>
        </Card>
      </div>

      {/* Main Table Card */}
      <Card noPadding>
        {/* Search & Filter Toolbar */}
        <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/40">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search contacts by name, email, account..."
              className="w-full bg-slate-50 border border-slate-200/80 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            {isFetching && <span className="text-[11px] text-indigo-600 animate-pulse">Syncing live records...</span>}
            <span className="font-medium text-slate-700">
              {filteredContacts.length} of {recordsOnPage} displayed
            </span>
          </div>
        </div>

        {/* Content Table / Skeletons / Empty */}
        {!isZohoSelected ? (
          <div className="p-8">
            <EmptyState
              icon={Users}
              title="No Zoho CRM Connection Selected"
              description="Select an active Zoho CRM integration or connect one in the Integrations section to view contacts."
              actionLabel="Go to Integrations"
              onAction={() => (window.location.href = '/integrations')}
            />
          </div>
        ) : isLoading ? (
          <TableSkeleton rows={8} columns={5} />
        ) : error ? (
          <div className="p-8">
            <EmptyState
              icon={Users}
              title="Unable to Retrieve Contacts"
              description={(error as Error).message || 'An error occurred while fetching contacts from Zoho.'}
              actionLabel="Retry"
              onAction={() => refetch()}
            />
          </div>
        ) : filteredContacts.length === 0 ? (
          <div className="p-8">
            <EmptyState
              icon={Users}
              title={searchQuery ? 'No Matching Contacts Found' : 'No Contacts Available in Zoho CRM'}
              description={
                searchQuery
                  ? `No records on current page matched "${searchQuery}".`
                  : 'Your connected Zoho CRM account has no contacts or requires initial synchronization.'
              }
              actionLabel={searchQuery ? 'Clear Search' : 'Sync Now'}
              onAction={searchQuery ? () => setSearchQuery('') : () => setIsSyncModalOpen(true)}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-xs divide-y divide-slate-100">
              <thead className="bg-slate-50/70 text-[11px] uppercase tracking-wider text-slate-500 font-semibold">
                <tr>
                  <th className="py-3 px-4">Contact Name</th>
                  <th className="py-3 px-4">Email</th>
                  <th className="py-3 px-4">Phone</th>
                  <th className="py-3 px-4">Account / Company</th>
                  <th className="py-3 px-4">Owner</th>
                  <th className="py-3 px-4">Modified</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredContacts.map((contact) => (
                  <tr
                    key={contact.id}
                    onClick={() => {
                      setSelectedContact(contact)
                      setActiveTab('details')
                    }}
                    className="hover:bg-slate-50/80 cursor-pointer transition-colors group"
                  >
                    <td className="py-3.5 px-4 font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-full bg-indigo-50 text-indigo-700 flex items-center justify-center font-bold text-[11px] shrink-0">
                          {contact.first_name?.[0]?.toUpperCase() || contact.last_name?.[0]?.toUpperCase() || 'C'}
                        </div>
                        <span>
                          {contact.first_name ? `${contact.first_name} ${contact.last_name || ''}` : contact.last_name || '—'}
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {contact.email ? (
                        <div className="flex items-center gap-1.5">
                          <Mail className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{contact.email}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 font-mono text-[11px]">
                      {contact.phone ? (
                        <div className="flex items-center gap-1.5">
                          <Phone className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{contact.phone}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {contact.account_name ? (
                        <div className="flex items-center gap-1.5">
                          <Building className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{contact.account_name}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">{contact.owner || '—'}</td>
                    <td className="py-3.5 px-4 text-slate-400 text-[11px]">{formatDate(contact.modified_time)}</td>
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

        {/* Pagination Bar */}
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

      {/* Record Detail Drawer */}
      {selectedContact && (
        <Drawer
          isOpen={!!selectedContact}
          onClose={() => setSelectedContact(null)}
          title={`${selectedContact.first_name || ''} ${selectedContact.last_name || ''}`.trim() || 'Contact'}
          subtitle={`Zoho Record ID: ${selectedContact.id}`}
        >
          {/* Tab Controls */}
          <div className="flex border-b border-slate-200">
            <button
              onClick={() => setActiveTab('details')}
              className={`py-2 px-4 text-xs font-semibold border-b-2 transition-all ${
                activeTab === 'details'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Contact Overview
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
                  <span className="text-slate-500 font-medium">First Name</span>
                  <span className="text-slate-900 font-semibold">{selectedContact.first_name || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Last Name</span>
                  <span className="text-slate-900 font-semibold">{selectedContact.last_name || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Email Address</span>
                  <span className="text-slate-900 font-mono">{selectedContact.email || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Phone Number</span>
                  <span className="text-slate-900 font-mono">{selectedContact.phone || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Mobile Number</span>
                  <span className="text-slate-900 font-mono">{selectedContact.mobile || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Account Name</span>
                  <span className="text-slate-900 font-semibold">{selectedContact.account_name || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Owner</span>
                  <span className="text-slate-900 font-semibold">{selectedContact.owner || '—'}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Record Created</span>
                  <span className="text-slate-800">{formatDate(selectedContact.created_time)}</span>
                </div>
                <div className="py-3 px-4 flex justify-between">
                  <span className="text-slate-500 font-medium">Last Modified</span>
                  <span className="text-slate-800">{formatDate(selectedContact.modified_time)}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="pt-2">
              <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 text-[11px] font-mono overflow-x-auto max-h-[500px]">
                {JSON.stringify(selectedContact.raw_data || selectedContact, null, 2)}
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
          defaultResourceType="contacts"
        />
      )}
    </div>
  )
}

