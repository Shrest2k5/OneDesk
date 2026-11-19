import React, { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BadgeDollarSign, RefreshCw, Search, Users } from 'lucide-react'
import { integrationsApi } from '@/api/integrations'
import { useIntegrations } from '@/context/IntegrationContext'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { TableSkeleton } from '@/components/common/LoadingSkeleton'
import { formatDate } from '@/lib/utils'
import type { BooksInvoice, BooksInvoiceStats } from '@/types/books'

const money = (value: string | number | null | undefined, currency?: string | null) => {
  if (value === null || value === undefined || value === '') return '—'
  return `${currency || ''} ${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`.trim()
}

const InvoiceStatus: React.FC<{ status?: string | null }> = ({ status }) => {
  const value = status || 'unknown'
  const variant = value === 'paid' ? 'active' : value === 'overdue' ? 'failed' : value === 'draft' ? 'pending' : value === 'sent' ? 'primary' : 'neutral'
  return <Badge variant={variant}>{value.replace('_', ' ')}</Badge>
}

export const BooksInvoicesPage: React.FC = () => {
  const { activeIntegrationId, activeIntegration } = useIntegrations()
  const isBooks = activeIntegration?.provider === 'zoho' && activeIntegration.product === 'books' && activeIntegration.status === 'active'
  const [page, setPage] = useState(1); const [search, setSearch] = useState(''); const [invoiceStatus, setInvoiceStatus] = useState(''); const [customerId, setCustomerId] = useState(''); const [sortBy, setSortBy] = useState('invoice_date')
  const queryClient = useQueryClient()
  const organization = useQuery({ queryKey: ['books-selected-organization', activeIntegrationId], queryFn: () => integrationsApi.selectedBooksOrganization(activeIntegrationId!), enabled: Boolean(activeIntegrationId && isBooks) })
  const stats = useQuery({ queryKey: ['books-invoice-stats', activeIntegrationId], queryFn: () => integrationsApi.booksInvoiceStats(activeIntegrationId!), enabled: Boolean(activeIntegrationId && isBooks) })
  const invoices = useQuery({ queryKey: ['books-invoices', activeIntegrationId, page, search, invoiceStatus, customerId, sortBy], queryFn: () => integrationsApi.listBooksInvoices(activeIntegrationId!, { page, per_page: 25, search: search || undefined, invoice_status: invoiceStatus || undefined, customer_id: customerId || undefined, sort_by: sortBy, sort_order: 'desc' }), enabled: Boolean(activeIntegrationId && isBooks) })
  const refresh = useMutation({ mutationFn: () => integrationsApi.refreshBooksInvoices(activeIntegrationId!), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['books-invoices'] }); queryClient.invalidateQueries({ queryKey: ['books-invoice-stats'] }) } })
  useEffect(() => setPage(1), [activeIntegrationId, search, invoiceStatus, customerId, sortBy])
  const response = invoices.data as { data: BooksInvoice[]; pagination: any; sync: { last_successful_sync?: string | null } } | undefined
  const summary = stats.data as BooksInvoiceStats | undefined
  return <div className="space-y-6">
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"><div><h2 className="text-xl font-bold text-slate-900">Zoho Books Sales Invoices</h2><p className="text-sm text-slate-500">Sales invoices from the selected Books organization.</p>{isBooks && <p className="text-xs text-indigo-600 mt-1">{organization.data?.name || 'No organization selected'} · {activeIntegration?.connection_name}</p>}</div><Button variant="primary" size="sm" onClick={() => refresh.mutate()} isLoading={refresh.isPending} leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Synchronize</Button></div>
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">{[['Total', summary?.total], ['Paid', summary?.paid], ['Outstanding', summary?.outstanding], ['Overdue', summary?.overdue], ['Outstanding amount', summary?.total_outstanding]].map(([label, value]) => <Card key={label as string} noPadding className="p-4"><div className="text-xs uppercase tracking-wider text-slate-500">{label}</div><div className="mt-2 text-xl font-bold text-slate-900">{value ?? '—'}</div></Card>)}</div>
    {!isBooks ? <Card><EmptyState icon={BadgeDollarSign} title="No Zoho Books Connection Selected" description="Select or connect a Zoho Books integration and select an organization first." actionLabel="Go to Integrations" onAction={() => (window.location.href = '/integrations')} /></Card> : <Card noPadding><div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row gap-3"><div className="relative flex-1"><Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" /><input className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs" placeholder="Search invoice number or customer" value={search} onChange={e => setSearch(e.target.value)} /></div><input className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs" placeholder="Customer ID" value={customerId} onChange={e => setCustomerId(e.target.value)} /><select className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs" value={invoiceStatus} onChange={e => setInvoiceStatus(e.target.value)}><option value="">All statuses</option><option value="draft">Draft</option><option value="sent">Sent</option><option value="paid">Paid</option><option value="partially_paid">Partially paid</option><option value="overdue">Overdue</option></select><select className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs" value={sortBy} onChange={e => setSortBy(e.target.value)}><option value="invoice_date">Invoice date</option><option value="total">Total amount</option></select></div>{invoices.isLoading ? <TableSkeleton rows={8} columns={7} /> : invoices.error ? <div className="p-8"><EmptyState icon={BadgeDollarSign} title="Unable to load invoices" description={(invoices.error as Error).message} actionLabel="Retry" onAction={() => invoices.refetch()} /></div> : !response?.data.length ? <div className="p-8"><EmptyState icon={BadgeDollarSign} title="No invoices found" description="Synchronize your selected organization to retrieve sales invoices." actionLabel="Synchronize" onAction={() => refresh.mutate()} /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-slate-50 text-[11px] uppercase text-slate-500"><tr><th className="p-4">Invoice</th><th className="p-4">Customer</th><th className="p-4">Invoice date</th><th className="p-4">Due date</th><th className="p-4">Total</th><th className="p-4">Paid</th><th className="p-4">Balance</th><th className="p-4">Status</th></tr></thead><tbody className="divide-y divide-slate-100">{response.data.map(invoice => <tr key={invoice.id}><td className="p-4 font-semibold text-slate-900">{invoice.invoice_number || '—'}<div className="text-[10px] text-slate-400 font-mono">{invoice.invoice_id}</div></td><td className="p-4">{invoice.customer_name || '—'}</td><td className="p-4">{formatDate(invoice.invoice_date)}</td><td className="p-4">{formatDate(invoice.due_date)}</td><td className="p-4">{money(invoice.total, invoice.currency_code)}</td><td className="p-4">{money(invoice.amount_paid, invoice.currency_code)}</td><td className="p-4">{money(invoice.balance_due, invoice.currency_code)}</td><td className="p-4"><InvoiceStatus status={invoice.status} /></td></tr>)}</tbody></table></div>}<div className="px-2"><Pagination pagination={response?.pagination} onPageChange={setPage} isLoading={invoices.isFetching} /></div>{response?.sync.last_successful_sync && <div className="px-4 pb-3 text-[11px] text-slate-500">Last successful synchronization: {formatDate(response.sync.last_successful_sync)}</div>}</Card>}
  </div>
}
