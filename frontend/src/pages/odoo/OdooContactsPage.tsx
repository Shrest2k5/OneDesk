import React, { useEffect, useState } from 'react'
import { Building2, Mail, Phone, RefreshCw, Search, Users } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { integrationsApi } from '@/api/integrations'
import { useIntegrations } from '@/context/IntegrationContext'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { TableSkeleton } from '@/components/common/LoadingSkeleton'
import { formatDate } from '@/lib/utils'

export const OdooContactsPage: React.FC = () => {
  const { getIntegrationForProduct, isLoading: integrationsLoading } = useIntegrations()
  const integration = getIntegrationForProduct('erp')
  const integrationId = integration?.provider === 'odoo' ? integration.id : null
  const [page, setPage] = useState(1)
  const [kind, setKind] = useState('')
  const [search, setSearch] = useState('')
  const [includeArchived, setIncludeArchived] = useState(true)
  const queryClient = useQueryClient()
  const ready = Boolean(!integrationsLoading && integrationId)
  const contacts = useQuery({
    queryKey: ['odoo-contacts', integrationId, page, kind, search, includeArchived],
    queryFn: () => integrationsApi.listOdooContacts(integrationId!, { page, per_page: 25, kind: kind || undefined, search: search || undefined, include_archived: includeArchived }),
    enabled: ready,
  })
  const stats = useQuery({
    queryKey: ['odoo-contact-stats', integrationId],
    queryFn: () => integrationsApi.odooContactStats(integrationId!),
    enabled: ready,
  })
  const refresh = useMutation({
    mutationFn: () => integrationsApi.refreshOdooContacts(integrationId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['odoo-contacts'] })
      queryClient.invalidateQueries({ queryKey: ['odoo-contact-stats'] })
    },
  })
  useEffect(() => { setPage(1) }, [integrationId, kind, search, includeArchived])
  const response = contacts.data

  if (!integrationId) {
    return <Card><EmptyState icon={Users} title="No Odoo connection selected" description="Connect an external Odoo ERP instance before viewing partners." actionLabel="Go to Integrations" onAction={() => { window.location.href = '/integrations' }} /></Card>
  }

  return <div className="space-y-6">
    {refresh.isError && <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">Synchronization failed: {(refresh.error as Error).message}</div>}
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div><h2 className="text-xl font-bold text-slate-900">Odoo Partners</h2><p className="text-sm text-slate-500">Contacts, customers and vendors from the connected external Odoo instance.</p><p className="text-xs text-indigo-600 mt-1">{integration?.connection_name} · {response?.sync.status || 'never synced'}</p></div>
      <Button variant="primary" size="sm" onClick={() => refresh.mutate()} isLoading={refresh.isPending} leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Synchronize</Button>
    </div>
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {([['Total', stats.data?.total], ['Customers', stats.data?.customers], ['Vendors', stats.data?.vendors], ['Companies', stats.data?.companies]] as const).map(([label, value]) => <Card key={label} noPadding className="p-4"><div className="text-xs uppercase tracking-wider text-slate-500">{label}</div><div className="mt-2 text-2xl font-bold text-slate-900">{value ?? '—'}</div></Card>)}
    </div>
    <Card noPadding>
      <div className="p-4 border-b border-slate-100 flex flex-col lg:flex-row gap-3">
        <div className="relative flex-1"><Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" /><input className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs" placeholder="Search name, email or phone" value={search} onChange={e => setSearch(e.target.value)} /></div>
        <select className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs" value={kind} onChange={e => setKind(e.target.value)}><option value="">All partners</option><option value="customer">Customers</option><option value="vendor">Vendors</option></select>
        <label className="flex items-center gap-2 text-xs text-slate-600 px-2"><input type="checkbox" checked={includeArchived} onChange={e => setIncludeArchived(e.target.checked)} /> Include archived</label>
      </div>
      {contacts.isLoading ? <TableSkeleton rows={8} columns={6} /> : contacts.error ? <div className="p-8"><EmptyState icon={Users} title="Unable to load Odoo partners" description={(contacts.error as Error).message} actionLabel="Retry" onAction={() => contacts.refetch()} /></div> : !response?.data.length ? <div className="p-8"><EmptyState icon={Users} title="No Odoo partners found" description="Synchronize the connected Odoo instance to retrieve partners." actionLabel="Synchronize" onAction={() => refresh.mutate()} /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-slate-50 text-[11px] uppercase text-slate-500"><tr><th className="p-4">Name</th><th className="p-4">Company / Parent</th><th className="p-4">Classification</th><th className="p-4">Email</th><th className="p-4">Phone</th><th className="p-4">Status</th></tr></thead><tbody className="divide-y divide-slate-100">{response.data.map(partner => <tr key={partner.id}><td className="p-4 font-semibold text-slate-900">{partner.name || '—'}<div className="text-[10px] text-slate-400 font-mono">#{partner.partner_id}{partner.is_company ? ' · Company' : ' · Contact'}</div></td><td className="p-4">{partner.parent ? <span className="flex items-center gap-1"><Building2 className="w-3 h-3" />{partner.parent.name}</span> : '—'}</td><td className="p-4">{partner.classifications.length ? partner.classifications.join(', ') : 'Contact'}</td><td className="p-4">{partner.email ? <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{partner.email}</span> : '—'}</td><td className="p-4">{partner.phone || partner.mobile ? <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{partner.phone || partner.mobile}</span> : '—'}</td><td className="p-4">{partner.active ? 'Active' : 'Archived'}</td></tr>)}</tbody></table></div>}
      <div className="px-2"><Pagination pagination={response?.pagination} onPageChange={setPage} isLoading={contacts.isFetching} /></div>
      {response?.sync.last_successful_sync && <div className="px-4 pb-3 text-[11px] text-slate-500">Last successful synchronization: {formatDate(response.sync.last_successful_sync)}</div>}
    </Card>
  </div>
}
