import React, { useEffect, useState } from 'react'
import { Receipt, ChevronDown, ChevronRight, Layers, RefreshCw, Search } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { integrationsApi } from '@/api/integrations'
import { useIntegrations } from '@/context/IntegrationContext'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { EmptyState } from '@/components/common/EmptyState'
import { Pagination } from '@/components/common/Pagination'
import { TableSkeleton } from '@/components/common/LoadingSkeleton'
import { formatDate } from '@/lib/utils'
import type { OdooCreditNote } from '@/types/odoo'

const money = (value: string | number | null | undefined, currency?: string | null) => {
  if (value === null || value === undefined || value === '') return '—'
  return `${currency || ''} ${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`.trim()
}

const StateBadge: React.FC<{ state?: string | null }> = ({ state }) => {
  const s = (state || 'draft').toLowerCase()
  const variant = s === 'posted' ? 'active' : s === 'cancel' ? 'failed' : 'pending'
  return <Badge variant={variant}>{s === 'posted' ? 'Posted' : s === 'cancel' ? 'Cancelled' : 'Draft'}</Badge>
}

export const OdooCreditNotesPage: React.FC = () => {
  const { getIntegrationForProduct, isLoading: integrationsLoading } = useIntegrations()
  const integration = getIntegrationForProduct('erp')
  const integrationId = integration?.provider === 'odoo' ? integration.id : null
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [kindFilter, setKindFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState('date')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const queryClient = useQueryClient()
  const ready = Boolean(!integrationsLoading && integrationId)

  const creditNotes = useQuery({
    queryKey: ['odoo-credit-notes', integrationId, page, search, kindFilter, statusFilter, sortBy],
    queryFn: () =>
      integrationsApi.listOdooCreditNotes(integrationId!, {
        page,
        per_page: 25,
        search: search || undefined,
        kind: kindFilter || undefined,
        status: statusFilter || undefined,
        sort_by: sortBy,
        sort_order: 'desc',
      }),
    enabled: ready,
  })

  const stats = useQuery({
    queryKey: ['odoo-credit-note-stats', integrationId],
    queryFn: () => integrationsApi.odooCreditNoteStats(integrationId!),
    enabled: ready,
  })

  const refresh = useMutation({
    mutationFn: () => integrationsApi.refreshOdooCreditNotes(integrationId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['odoo-credit-notes'] })
      queryClient.invalidateQueries({ queryKey: ['odoo-credit-note-stats'] })
    },
  })

  useEffect(() => {
    setPage(1)
  }, [integrationId, search, kindFilter, statusFilter, sortBy])

  const response = creditNotes.data
  const summary = stats.data

  if (!integrationId) {
    return (
      <Card>
        <EmptyState
          icon={Receipt}
          title="No Odoo connection selected"
          description="Connect an external Odoo ERP instance to view credit notes and refunds."
          actionLabel="Go to Integrations"
          onAction={() => {
            window.location.href = '/integrations'
          }}
        />
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {refresh.isError && (
        <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700">
          Synchronization failed: {(refresh.error as Error).message}
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Odoo Credit Notes & Refunds</h2>
          <p className="text-sm text-slate-500">
            Customer credit notes (out_refund) and vendor refunds (in_refund).
          </p>
          <p className="text-xs text-indigo-600 mt-1">
            {integration?.connection_name} · {response?.sync?.status || 'never synced'}
          </p>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => refresh.mutate()}
          isLoading={refresh.isPending}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Synchronize
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          ['Total Credit Notes', summary?.total],
          ['Customer Credit Notes', summary?.customer_credit_notes],
          ['Vendor Refunds', summary?.vendor_credit_notes],
          ['Total Refund Amount', summary?.total_amount ? `$${summary.total_amount}` : '—'],
        ].map(([label, value]) => (
          <Card key={label as string} noPadding className="p-4">
            <div className="text-xs uppercase tracking-wider text-slate-500">{label}</div>
            <div className="mt-2 text-xl font-bold text-slate-900">{value ?? '—'}</div>
          </Card>
        ))}
      </div>

      {/* Filters and Table */}
      <Card noPadding>
        <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs"
              placeholder="Search credit note number, reference or partner"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs"
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
          >
            <option value="">All Document Types</option>
            <option value="customer">Customer Credit Notes (out_refund)</option>
            <option value="vendor">Vendor Refunds (in_refund)</option>
          </select>
          <select
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All States</option>
            <option value="posted">Posted</option>
            <option value="draft">Draft</option>
            <option value="cancel">Cancelled</option>
          </select>
          <select
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="date">Date</option>
            <option value="total">Total Amount</option>
          </select>
        </div>

        {creditNotes.isLoading ? (
          <TableSkeleton rows={8} columns={7} />
        ) : creditNotes.error ? (
          <div className="p-8">
            <EmptyState
              icon={Receipt}
              title="Unable to load credit notes"
              description={(creditNotes.error as Error).message}
              actionLabel="Retry"
              onAction={() => creditNotes.refetch()}
            />
          </div>
        ) : !response?.data?.length ? (
          <div className="p-8">
            <EmptyState
              icon={Receipt}
              title="No credit notes found"
              description="Synchronize the connected Odoo instance to extract credit notes and refunds."
              actionLabel="Synchronize"
              onAction={() => refresh.mutate()}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[950px] text-left text-xs">
              <thead className="bg-slate-50 text-[11px] uppercase text-slate-500">
                <tr>
                  <th className="p-4 w-10"></th>
                  <th className="p-4">Credit Note</th>
                  <th className="p-4">Type</th>
                  <th className="p-4">Partner</th>
                  <th className="p-4">Date</th>
                  <th className="p-4 text-right">Subtotal</th>
                  <th className="p-4 text-right">Total Amount</th>
                  <th className="p-4">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {response.data.map((cn: OdooCreditNote) => {
                  const isExpanded = expandedId === cn.id
                  const isCust = cn.credit_note_type === 'customer'
                  return (
                    <React.Fragment key={cn.id}>
                      <tr
                        className={`hover:bg-slate-50/60 cursor-pointer transition-colors ${
                          isExpanded ? 'bg-indigo-50/20' : ''
                        }`}
                        onClick={() => setExpandedId(isExpanded ? null : cn.id)}
                      >
                        <td className="p-4 text-slate-400">
                          {cn.line_items?.length ? (
                            isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-indigo-600" />
                            ) : (
                              <ChevronRight className="w-4 h-4" />
                            )
                          ) : null}
                        </td>
                        <td className="p-4 font-semibold text-slate-900">
                          {cn.credit_note_number || 'Draft'}
                          <div className="text-[10px] text-slate-400 font-mono">
                            ID: {cn.credit_note_id} {cn.reference_number ? `· Ref: ${cn.reference_number}` : ''}
                          </div>
                        </td>
                        <td className="p-4">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold ${
                              isCust
                                ? 'bg-purple-50 text-purple-700 border border-purple-200/60'
                                : 'bg-amber-50 text-amber-700 border border-amber-200/60'
                            }`}
                          >
                            {isCust ? 'Customer Credit' : 'Vendor Refund'}
                          </span>
                        </td>
                        <td className="p-4 text-slate-700">
                          {cn.partner_name || '—'}
                          {cn.partner_id && (
                            <div className="text-[10px] text-slate-400">Partner #{cn.partner_id}</div>
                          )}
                        </td>
                        <td className="p-4 text-slate-600">{formatDate(cn.date)}</td>
                        <td className="p-4 text-right font-medium text-slate-700">
                          {money(cn.subtotal, cn.currency)}
                        </td>
                        <td className="p-4 text-right font-bold text-slate-900">
                          {money(cn.total, cn.currency)}
                        </td>
                        <td className="p-4">
                          <StateBadge state={cn.status} />
                        </td>
                      </tr>

                      {/* Line Items Expansion */}
                      {isExpanded && cn.line_items && cn.line_items.length > 0 && (
                        <tr className="bg-slate-50/80 border-b border-indigo-100">
                          <td colSpan={8} className="p-4 pl-12">
                            <div className="rounded-lg bg-white border border-slate-200 overflow-hidden shadow-sm">
                              <div className="bg-slate-100/70 px-4 py-2 text-[11px] font-semibold text-slate-600 flex items-center gap-1.5">
                                <Layers className="w-3.5 h-3.5 text-indigo-600" />
                                <span>Credit Note Line Items ({cn.line_items.length})</span>
                              </div>
                              <table className="w-full text-xs text-left">
                                <thead className="border-b border-slate-100 text-[10px] uppercase text-slate-400 bg-slate-50/40">
                                  <tr>
                                    <th className="px-4 py-2">Product / Description</th>
                                    <th className="px-4 py-2 text-right">Quantity</th>
                                    <th className="px-4 py-2 text-right">Unit Price</th>
                                    <th className="px-4 py-2 text-right">Subtotal</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                  {cn.line_items.map((line, idx) => (
                                    <tr key={line.id || idx}>
                                      <td className="px-4 py-2.5">
                                        <div className="font-medium text-slate-900">
                                          {line.product_name || line.name || 'Item'}
                                        </div>
                                        {line.product_id && (
                                          <div className="text-[10px] text-slate-400 font-mono">
                                            Product #{line.product_id}
                                          </div>
                                        )}
                                      </td>
                                      <td className="px-4 py-2.5 text-right font-mono text-slate-700">
                                        {line.quantity}
                                      </td>
                                      <td className="px-4 py-2.5 text-right font-mono text-slate-700">
                                        {money(line.price_unit, cn.currency)}
                                      </td>
                                      <td className="px-4 py-2.5 text-right font-semibold text-slate-900 font-mono">
                                        {money(line.price_subtotal, cn.currency)}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="px-2">
          <Pagination pagination={response?.pagination} onPageChange={setPage} isLoading={creditNotes.isFetching} />
        </div>
        {response?.sync?.last_successful_sync && (
          <div className="px-4 pb-3 text-[11px] text-slate-500">
            Last successful synchronization: {formatDate(response.sync.last_successful_sync)}
          </div>
        )}
      </Card>
    </div>
  )
}