import React, { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Mail, Phone, RefreshCw, Search, Users } from 'lucide-react'
import { integrationsApi } from '@/api/integrations'
import { useIntegrations } from '@/context/IntegrationContext'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { TableSkeleton } from '@/components/common/LoadingSkeleton'
import { formatDate } from '@/lib/utils'

export const BooksContactsPage: React.FC = () => {
  const { getIntegrationForProduct, isLoading: integrationsLoading } = useIntegrations()
  const activeIntegration = getIntegrationForProduct('books')
  const activeIntegrationId = activeIntegration?.id || null
  const isBooks = Boolean(activeIntegration?.provider === 'zoho')
  const [page, setPage] = useState(1); const [type, setType] = useState(''); const [search, setSearch] = useState('')
  const queryClient = useQueryClient()
  const booksReady = Boolean(!integrationsLoading && activeIntegrationId && isBooks)
  const contacts = useQuery({ queryKey: ['books-contacts', activeIntegrationId, page, type, search], queryFn: () => integrationsApi.listBooksContacts(activeIntegrationId!, { page, per_page: 25, contact_type: type || undefined, search: search || undefined }), enabled: booksReady, refetchOnMount: 'always' })
  const stats = useQuery({ queryKey: ['books-contact-stats', activeIntegrationId], queryFn: () => integrationsApi.booksContactStats(activeIntegrationId!), enabled: booksReady, refetchOnMount: 'always' })
  const organization = useQuery({ queryKey: ['books-selected-organization', activeIntegrationId], queryFn: () => integrationsApi.selectedBooksOrganization(activeIntegrationId!), enabled: booksReady, refetchOnMount: 'always' })
  const refresh = useMutation({ mutationFn: () => integrationsApi.refreshBooksContacts(activeIntegrationId!), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['books-contacts'] }); queryClient.invalidateQueries({ queryKey: ['books-contact-stats'] }) } })
  useEffect(() => { setPage(1) }, [activeIntegrationId, type, search])
  const response = contacts.data
  return <div className="space-y-6">
    {refresh.isError && <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">Synchronization failed: {(refresh.error as Error).message}</div>}
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"><div><h2 className="text-xl font-bold text-slate-900">Zoho Books Contacts</h2><p className="text-sm text-slate-500">Customers and vendors from the selected Books organization.</p>{isBooks && <p className="text-xs text-indigo-600 mt-1">{organization.data?.name || 'No organization selected'} · {activeIntegration?.connection_name}</p>}</div><Button variant="primary" size="sm" onClick={() => refresh.mutate()} isLoading={refresh.isPending} leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Synchronize</Button></div>
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">{[['Total contacts', stats.data?.total], ['Customers', stats.data?.customers], ['Vendors', stats.data?.vendors]].map(([label, value]) => <Card key={label as string} noPadding className="p-4"><div className="text-xs uppercase tracking-wider text-slate-500">{label}</div><div className="mt-2 text-2xl font-bold text-slate-900">{value ?? '—'}</div></Card>)}</div>
    {!isBooks ? <Card><EmptyState icon={Users} title="No Zoho Books Connection Selected" description="Select or connect a Zoho Books integration and select an organization first." actionLabel="Go to Integrations" onAction={() => (window.location.href = '/integrations')} /></Card> : <Card noPadding><div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row gap-3"><div className="relative flex-1"><Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" /><input className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs" placeholder="Search name, company, or email" value={search} onChange={e => setSearch(e.target.value)} /></div><select className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs" value={type} onChange={e => setType(e.target.value)}><option value="">All types</option><option value="customer">Customers</option><option value="vendor">Vendors</option></select></div>{contacts.isLoading ? <TableSkeleton rows={8} columns={5} /> : contacts.error ? <div className="p-8"><EmptyState icon={Users} title="Unable to load Books contacts" description={(contacts.error as Error).message} actionLabel="Retry" onAction={() => contacts.refetch()} /></div> : !response?.data.length ? <div className="p-8"><EmptyState icon={Users} title="No Books contacts found" description="Synchronize your selected organization to retrieve contacts." actionLabel="Synchronize" onAction={() => refresh.mutate()} /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="bg-slate-50 text-[11px] uppercase text-slate-500"><tr><th className="p-4">Name</th><th className="p-4">Company</th><th className="p-4">Type</th><th className="p-4">Email</th><th className="p-4">Phone</th><th className="p-4">Currency</th></tr></thead><tbody className="divide-y divide-slate-100">{response.data.map(c => <tr key={c.id}><td className="p-4 font-semibold text-slate-900">{c.contact_name || '—'}<div className="text-[10px] text-slate-400 font-mono">{c.contact_id}</div></td><td className="p-4">{c.company_name ? <span className="flex items-center gap-1"><Building2 className="w-3 h-3" />{c.company_name}</span> : '—'}</td><td className="p-4">{c.contact_types.join(', ') || '—'}</td><td className="p-4">{c.email ? <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{c.email}</span> : '—'}</td><td className="p-4">{c.phone ? <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{c.phone}</span> : '—'}</td><td className="p-4">{c.currency_code || c.currency_symbol || '—'}</td></tr>)}</tbody></table></div>}<div className="px-2"><Pagination pagination={response?.pagination} onPageChange={setPage} isLoading={contacts.isFetching} /></div>{response?.sync.last_successful_sync && <div className="px-4 pb-3 text-[11px] text-slate-500">Last successful synchronization: {formatDate(response.sync.last_successful_sync)}</div>}</Card>}
  </div>
}
