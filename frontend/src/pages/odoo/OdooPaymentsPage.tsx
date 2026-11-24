import React, { useEffect, useState } from 'react'
import { CheckCircle2, Clock, RefreshCw, Search, WalletCards } from 'lucide-react'
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
import type { OdooPayment } from '@/types/odoo'

const money = (value: string | number | null | undefined, currency?: string | null) => {
  if (value === null || value === undefined || value === '') return '—'
  return `${currency || ''} ${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`.trim()
}

export const OdooPaymentsPage: React.FC = () => {
  const { getIntegrationForProduct, isLoading: integrationsLoading } = useIntegrations()
  const integration = getIntegrationForProduct('erp')
  const integrationId = integration?.provider === 'odoo' ? integration.id : null
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [paymentTypeFilter, setPaymentTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [sortBy, setSortBy] = useState('payment_date')

  const queryClient = useQueryClient()
  const ready = Boolean(!integrationsLoading && integrationId)

  const payments = useQuery({
    queryKey: ['odoo-payments', integrationId, page, search, paymentTypeFilter, statusFilter, startDate, endDate, sortBy],
    queryFn: () =>
      integrationsApi.listOdooPayments(integrationId!, {
        page,
        per_page: 25,
        search: search || undefined,
        payment_type: paymentTypeFilter || undefined,
        status: statusFilter || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        sort_by: sortBy,
        sort_order: 'desc',
      }),
    enabled: ready,
  })

  const stats = useQuery({
    queryKey: ['odoo-payment-stats', integrationId],
    queryFn: () => integrationsApi.odooPaymentStats(integrationId!),
    enabled: ready,
  })

  const refresh = useMutation({
    mutationFn: () => integrationsApi.refreshOdooPayments(integrationId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['odoo-payments'] })
      queryClient.invalidateQueries({ queryKey: ['odoo-payment-stats'] })
    },
  })

  useEffect(() => {
    setPage(1)
  }, [integrationId, search, paymentTypeFilter, statusFilter, startDate, endDate, sortBy])

  const response = payments.data
  const summary = stats.data

  if (!integrationId) {
    return (
      <Card>
        <EmptyState
          icon={WalletCards}
          title="No Odoo connection selected"
          description="Connect an external Odoo ERP instance to view payments."
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
          <h2 className="text-xl font-bold text-slate-900">Odoo Payments</h2>
          <p className="text-sm text-slate-500">
            Customer collections (inbound) and vendor disbursements (outbound).
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
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[
          ['Total Payments', summary?.total],
          ['Customer Receipts', summary?.customer_payments],
          ['Vendor Payments', summary?.vendor_payments],
          ['Total Inbound', summary?.total_inbound ? `$${summary.total_inbound}` : '—'],
          ['Total Outbound', summary?.total_outbound ? `$${summary.total_outbound}` : '—'],
        ].map(([label, value]) => (
          <Card key={label as string} noPadding className="p-4">
            <div className="text-xs uppercase tracking-wider text-slate-500">{label}</div>
            <div className="mt-2 text-xl font-bold text-slate-900">{value ?? '—'}</div>
          </Card>
        ))}
      </div>

      {/* Filters and Table */}
      <Card noPadding>
        <div className="p-4 border-b border-slate-100 flex flex-col lg:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs"
              placeholder="Search payment number, memo or partner"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs"
            value={paymentTypeFilter}
            onChange={(e) => setPaymentTypeFilter(e.target.value)}
          >
            <option value="">All Flow Types</option>
            <option value="inbound">Inbound (Customer Payment)</option>
            <option value="outbound">Outbound (Vendor Payment)</option>
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
          <div className="flex items-center gap-1.5">
            <input
              type="date"
              className="border border-slate-200 rounded-lg px-2 py-1 text-xs"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
            <span className="text-slate-400 text-xs">to</span>
            <input
              type="date"
              className="border border-slate-200 rounded-lg px-2 py-1 text-xs"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
          <select
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="payment_date">Payment Date</option>
            <option value="amount">Amount</option>
          </select>
        </div>

        {payments.isLoading ? (
          <TableSkeleton rows={8} columns={7} />
        ) : payments.error ? (
          <div className="p-8">
            <EmptyState
              icon={WalletCards}
              title="Unable to load payments"
              description={(payments.error as Error).message}
              actionLabel="Retry"
              onAction={() => payments.refetch()}
            />
          </div>
        ) : !response?.data?.length ? (
          <div className="p-8">
            <EmptyState
              icon={WalletCards}
              title="No payments found"
              description="Synchronize the connected Odoo instance to extract payment records."
              actionLabel="Synchronize"
              onAction={() => refresh.mutate()}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[950px] text-left text-xs">
              <thead className="bg-slate-50 text-[11px] uppercase text-slate-500">
                <tr>
                  <th className="p-4">Payment</th>
                  <th className="p-4">Flow</th>
                  <th className="p-4">Partner</th>
                  <th className="p-4">Journal</th>
                  <th className="p-4">Payment Date</th>
                  <th className="p-4 text-right">Amount</th>
                  <th className="p-4">Reconciliation</th>
                  <th className="p-4">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {response.data.map((pmt: OdooPayment) => {
                  const isInbound = pmt.payment_type === 'inbound'
                  return (
                    <tr key={pmt.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="p-4 font-semibold text-slate-900">
                        {pmt.payment_number || 'Draft'}
                        <div className="text-[10px] text-slate-400 font-mono">
                          ID: {pmt.payment_id} {pmt.payment_reference ? `· Memo: ${pmt.payment_reference}` : ''}
                        </div>
                      </td>
                      <td className="p-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold ${
                            isInbound
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/60'
                              : 'bg-rose-50 text-rose-700 border border-rose-200/60'
                          }`}
                        >
                          {isInbound ? 'Customer Inbound' : 'Vendor Outbound'}
                        </span>
                      </td>
                      <td className="p-4 text-slate-700">
                        {pmt.partner_name || '—'}
                        {pmt.partner_id && (
                          <div className="text-[10px] text-slate-400">Partner #{pmt.partner_id}</div>
                        )}
                      </td>
                      <td className="p-4 text-slate-600">
                        {pmt.journal?.name || '—'}
                      </td>
                      <td className="p-4 text-slate-600">{formatDate(pmt.payment_date)}</td>
                      <td className="p-4 text-right font-bold text-slate-900">
                        {money(pmt.amount, pmt.currency)}
                      </td>
                      <td className="p-4">
                        {pmt.is_reconciled ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Reconciled
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400">
                            <Clock className="w-3.5 h-3.5" /> Unreconciled
                          </span>
                        )}
                        {(pmt.reconciled_invoice_ids?.length > 0 || pmt.reconciled_bill_ids?.length > 0) && (
                          <div className="text-[10px] text-indigo-600 mt-0.5">
                            {pmt.reconciled_invoice_ids?.length ? `${pmt.reconciled_invoice_ids.length} invoice(s)` : ''}
                            {pmt.reconciled_bill_ids?.length ? `${pmt.reconciled_bill_ids.length} bill(s)` : ''}
                          </div>
                        )}
                      </td>
                      <td className="p-4">
                        <Badge variant={pmt.status === 'posted' ? 'active' : 'pending'}>
                          {pmt.status === 'posted' ? 'Posted' : pmt.status}
                        </Badge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="px-2">
          <Pagination pagination={response?.pagination} onPageChange={setPage} isLoading={payments.isFetching} />
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