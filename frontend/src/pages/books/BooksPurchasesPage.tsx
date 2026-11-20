import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, RefreshCw, Search } from 'lucide-react'
import { integrationsApi } from '@/api/integrations'
import { useIntegrations } from '@/context/IntegrationContext'
import { Card } from '@/components/common/Card'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { Badge } from '@/components/common/Badge'
import type { BooksPurchase } from '@/types/books'
import type { ApiError } from '@/api/client'

const money = (value: unknown, currency?: string | null) => `${currency || ''} ${Number(value || 0).toFixed(2)}`.trim()
const dateText = (value?: string | null) => value ? new Date(value).toLocaleDateString() : '—'
const tabs = [{ key: 'bills', label: 'Bills' }, { key: 'vendor-credits', label: 'Vendor Credits' }, { key: 'vendor-payments', label: 'Vendor Payments' }]

export function BooksPurchasesPage() {
  const { getIntegrationForProduct, isLoading: integrationsLoading } = useIntegrations()
  const integration = getIntegrationForProduct('books'); const id = integration?.id
  const [tab, setTab] = useState('bills'); const [start, setStart] = useState(''); const [end, setEnd] = useState(''); const [search, setSearch] = useState(''); const [status, setStatus] = useState(''); const [page, setPage] = useState(1)
  const enabled = Boolean(!integrationsLoading && id && integration?.provider === 'zoho')
  const params = { page, page_size: 25, start_date: start || undefined, end_date: end || undefined, search: search || undefined, record_status: status || undefined }
  const query = useQuery({ queryKey: ['books-purchases', id, tab, params], queryFn: () => integrationsApi.listBooksPurchases(id!, tab, params), enabled, refetchOnMount: 'always', refetchInterval: q => q.state.data?.sync.status === 'in_progress' ? 2000 : false })
  const client = useQueryClient()
  const refresh = useMutation({ mutationFn: () => integrationsApi.refreshBooksPurchases(id!, { start_date: start || undefined, end_date: end || undefined }), onSuccess: () => client.invalidateQueries({ queryKey: ['books-purchases'] }) })
  const syncStatus = query.data?.sync.status; const syncing = refresh.isPending || syncStatus === 'in_progress' || syncStatus === 'queued'; const rows = query.data?.data || []
  const syncError = query.data?.sync.error || ((refresh.error as ApiError | null)?.message)
  const authorizationRequired = Boolean(syncError && /authorization failed|not authorized|permission/i.test(syncError))
  useEffect(() => { setPage(1) }, [tab, start, end, search, status])
  return <div className="space-y-4">
    <div className="flex items-center justify-between"><div><h1 className="text-xl font-bold text-slate-900">Purchases</h1><p className="text-xs text-slate-500">Zoho Books bills, vendor credits, and vendor payments</p>{syncStatus === 'in_progress' && <p className="mt-1 text-xs text-indigo-600">Synchronization in progress…</p>}{syncStatus === 'failed' && <p className="mt-1 text-xs text-red-600">Last synchronization failed: {query.data?.sync.error}</p>}</div><button className="flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs text-white disabled:opacity-50" disabled={syncing || !enabled} onClick={() => refresh.mutate()}><RefreshCw className="h-4 w-4" />{syncing ? 'Synchronizing…' : 'Synchronize'}</button></div>
    {refresh.isError && <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">Synchronization failed: {(refresh.error as Error).message}</div>}
    {authorizationRequired && <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">Zoho Books authorization needs to be updated. Reauthorize this existing Books integration from Integrations, or ask your Zoho Books administrator to grant access to Vendor Credits and Vendor Payments.</div>}
    {!enabled ? <Card><EmptyState icon={FileText} title="No Zoho Books Connection Selected" description="Select an active Zoho Books integration and organization first." /></Card> : <Card noPadding><div className="flex gap-1 border-b border-slate-100 p-3">{tabs.map(item => <button key={item.key} onClick={() => setTab(item.key)} className={`rounded-lg px-3 py-2 text-xs font-semibold ${tab === item.key ? 'bg-indigo-50 text-indigo-700' : 'text-slate-500 hover:bg-slate-50'}`}>{item.label}</button>)}</div><div className="flex flex-wrap gap-2 border-b border-slate-100 p-4"><input type="date" className="rounded-lg border p-2 text-xs" value={start} onChange={e => setStart(e.target.value)} /><input type="date" className="rounded-lg border p-2 text-xs" value={end} onChange={e => setEnd(e.target.value)} /><select className="rounded-lg border p-2 text-xs" value={status} onChange={e => setStatus(e.target.value)}><option value="">All statuses</option><option value="open">Open</option><option value="paid">Paid</option><option value="overdue">Overdue</option><option value="closed">Closed</option></select><div className="relative min-w-[220px] flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><input className="w-full rounded-lg border bg-slate-50 py-2 pl-9 pr-3 text-xs" placeholder="Search number, vendor, reference" value={search} onChange={e => setSearch(e.target.value)} /></div></div>{query.isLoading ? <div className="p-8 text-center text-sm text-slate-500">Loading purchases…</div> : query.isError ? <div className="p-8 text-center text-sm text-red-600">Unable to load purchases.</div> : !rows.length ? <div className="p-8"><EmptyState icon={FileText} title={`No ${tabs.find(x => x.key === tab)?.label.toLowerCase()} found`} description="Synchronize Zoho Books to retrieve purchase records." actionLabel="Synchronize" onAction={() => refresh.mutate()} /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-slate-50 text-[11px] uppercase text-slate-500"><tr><th className="p-4">Date</th><th className="p-4">Number / ID</th><th className="p-4">Vendor</th><th className="p-4">Due date</th><th className="p-4">Total</th><th className="p-4">Balance</th><th className="p-4">Status</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row: BooksPurchase) => <tr key={row.id}><td className="p-4">{dateText(row.date || row.transaction_date)}</td><td className="p-4 font-semibold">{row.number || row.payment_number || '—'}<div className="font-mono text-[10px] text-slate-400">{row.id}</div></td><td className="p-4">{row.vendor_name || '—'}</td><td className="p-4">{dateText(row.due_date)}</td><td className="p-4">{money(row.total ?? row.amount, row.currency_code)}</td><td className="p-4">{money(row.balance, row.currency_code)}</td><td className="p-4">{row.status ? <Badge variant={row.status === 'paid' ? 'completed' : row.status === 'overdue' ? 'failed' : 'neutral'}>{row.status}</Badge> : '—'}</td></tr>)}</tbody></table></div>}<div className="px-2"><Pagination pagination={query.data?.pagination} onPageChange={setPage} isLoading={query.isFetching} /></div></Card>}
  </div>
}
