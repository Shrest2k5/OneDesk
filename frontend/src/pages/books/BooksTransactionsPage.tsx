import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, RefreshCw, BadgeDollarSign } from 'lucide-react'
import { integrationsApi } from '@/api/integrations'
import { useIntegrations } from '@/context/IntegrationContext'
import type { BooksTransaction } from '@/types/books'
import { Card } from '@/components/common/Card'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'

const money = (value: unknown, currency?: string | null) => `${currency || ''} ${Number(value || 0).toFixed(2)}`.trim()
const dateText = (value?: string | null) => value ? new Date(value).toLocaleDateString() : '—'

export function BooksTransactionsPage() {
  const { getIntegrationForProduct, isLoading: integrationsLoading } = useIntegrations()
  const booksIntegration = getIntegrationForProduct('books')
  const id = booksIntegration?.id
  const [start, setStart] = useState(''); const [end, setEnd] = useState(''); const [kind, setKind] = useState(''); const [search, setSearch] = useState(''); const [page, setPage] = useState(1)
  const queryClient = useQueryClient()
  const enabled = Boolean(!integrationsLoading && id && booksIntegration?.provider === 'zoho')
  const params = { page, page_size: 25, start_date: start || undefined, end_date: end || undefined, transaction_type: kind || undefined, search: search || undefined }
  const transactions = useQuery({ queryKey: ['books-transactions', id, params], queryFn: () => integrationsApi.listBooksTransactions(id!, params), enabled, refetchOnMount: 'always', refetchInterval: (query) => query.state.data?.sync.status === 'in_progress' ? 2000 : false })
  const stats = useQuery({ queryKey: ['books-transaction-stats', id, start, end], queryFn: () => integrationsApi.booksTransactionStats(id!, { start_date: start || undefined, end_date: end || undefined }), enabled, refetchOnMount: 'always' })
  const refresh = useMutation({ mutationFn: () => integrationsApi.refreshBooksTransactions(id!, { start_date: start || undefined, end_date: end || undefined }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['books-transactions'] }); queryClient.invalidateQueries({ queryKey: ['books-transaction-stats'] }) } })
  const syncStatus = transactions.data?.sync.status
  useEffect(() => {
    if (syncStatus === 'completed' || syncStatus === 'failed') refresh.reset()
  }, [syncStatus, refresh])
  const rows = transactions.data?.data || []
  const isSyncing = refresh.isPending || syncStatus === 'in_progress' || syncStatus === 'queued'
  return <div className="space-y-4">
    {refresh.isError && <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">Synchronization failed: {(refresh.error as Error).message}</div>}
    <div className="flex items-center justify-between"><div><h1 className="text-xl font-bold text-slate-900">Financial Transactions</h1><p className="text-xs text-slate-500">Zoho Books payments, receipts, refunds, and bank transactions</p>{syncStatus === 'in_progress' && <p className="mt-1 text-xs text-indigo-600">Synchronization in progress…</p>}{syncStatus === 'failed' && transactions.data?.sync.error && <p className="mt-1 text-xs text-red-600">Last synchronization failed: {transactions.data.sync.error}</p>}</div><button className="flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs text-white disabled:opacity-50" disabled={isSyncing || !enabled} onClick={() => refresh.mutate()}><RefreshCw className="h-4 w-4" />{isSyncing ? 'Synchronizing…' : 'Synchronize'}</button></div>
    {!enabled ? <Card><EmptyState icon={BadgeDollarSign} title="No Zoho Books Connection Selected" description="Select an active Zoho Books integration and organization first." /></Card> : <>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{[['All', stats.data?.total || 0], ['Customer payments', stats.data?.counts.customer_payments || 0], ['Vendor payments', stats.data?.counts.vendor_payments || 0], ['Bank transactions', stats.data?.counts.bank_transactions || 0]].map(([label, value]) => <Card key={String(label)}><div className="text-xs text-slate-500">{label}</div><div className="mt-1 text-xl font-bold">{value}</div></Card>)}</div>
      <Card noPadding><div className="flex flex-wrap gap-2 border-b border-slate-100 p-4"><input type="date" className="rounded-lg border p-2 text-xs" value={start} onChange={e => { setStart(e.target.value); setPage(1) }} /><input type="date" className="rounded-lg border p-2 text-xs" value={end} onChange={e => { setEnd(e.target.value); setPage(1) }} /><select className="rounded-lg border p-2 text-xs" value={kind} onChange={e => { setKind(e.target.value); setPage(1) }}><option value="">All categories</option><option value="customer_payments">Customer payments</option><option value="vendor_payments">Vendor payments</option><option value="sales_receipts">Sales receipts</option><option value="credit_note_refunds">Credit note refunds</option><option value="customer_payment_refunds">Customer payment refunds</option><option value="vendor_payment_refunds">Vendor payment refunds</option><option value="bank_transactions">Bank transactions</option></select><div className="relative min-w-[220px] flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><input className="w-full rounded-lg border bg-slate-50 py-2 pl-9 pr-3 text-xs" placeholder="Search number, customer, vendor, reference" value={search} onChange={e => { setSearch(e.target.value); setPage(1) }} /></div></div>{transactions.isLoading ? <div className="p-8 text-center text-sm text-slate-500">Loading transactions…</div> : transactions.error ? <div className="p-8 text-center text-sm text-red-600">Unable to load transactions.</div> : !rows.length ? <div className="p-8"><EmptyState icon={BadgeDollarSign} title="No transactions found" description="Synchronize the selected date range to retrieve financial transactions." actionLabel="Synchronize" onAction={() => refresh.mutate()} /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-slate-50 text-[11px] uppercase text-slate-500"><tr><th className="p-4">Date</th><th className="p-4">Number / ID</th><th className="p-4">Party</th><th className="p-4">Category</th><th className="p-4">Mode</th><th className="p-4">Amount</th><th className="p-4">Status</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row: BooksTransaction) => <tr key={`${row.transaction_type}-${row.id}`}><td className="p-4">{dateText(row.transaction_date)}</td><td className="p-4 font-semibold">{row.number || '—'}<div className="font-mono text-[10px] text-slate-400">{row.transaction_id}</div></td><td className="p-4">{row.customer_name || row.vendor_name || '—'}</td><td className="p-4">{row.transaction_type.replaceAll('_', ' ')}</td><td className="p-4">{row.payment_mode || '—'}</td><td className="p-4">{money(row.amount, row.currency_code)}</td><td className="p-4">{row.status || '—'}</td></tr>)}</tbody></table></div>}<div className="px-2"><Pagination pagination={transactions.data?.pagination} onPageChange={setPage} isLoading={transactions.isFetching} /></div>{transactions.data?.sync.last_successful_sync && <div className="px-4 pb-3 text-[11px] text-slate-500">Last successful synchronization: {dateText(transactions.data.sync.last_successful_sync)}</div>}</Card>
    </>}
  </div>
}
