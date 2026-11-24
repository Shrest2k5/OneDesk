import React, { useEffect, useState } from 'react'
import { ArrowLeftRight, ChevronDown, ChevronRight, FileSpreadsheet, Layers, RefreshCw, Search } from 'lucide-react'
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
import type { OdooTransaction } from '@/types/odoo'

const money = (value: string | number | null | undefined, currency?: string | null) => {
  if (value === null || value === undefined || value === '') return '—'
  return `${currency || ''} ${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`.trim()
}

export const OdooTransactionsPage: React.FC = () => {
  const { getIntegrationForProduct, isLoading: integrationsLoading } = useIntegrations()
  const integration = getIntegrationForProduct('erp')
  const integrationId = integration?.provider === 'odoo' ? integration.id : null
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [txTypeFilter, setTxTypeFilter] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [sortBy, setSortBy] = useState('date')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const queryClient = useQueryClient()
  const ready = Boolean(!integrationsLoading && integrationId)

  const transactions = useQuery({
    queryKey: ['odoo-transactions', integrationId, page, search, txTypeFilter, startDate, endDate, sortBy],
    queryFn: () =>
      integrationsApi.listOdooTransactions(integrationId!, {
        page,
        per_page: 25,
        search: search || undefined,
        transaction_type: txTypeFilter || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        sort_by: sortBy,
        sort_order: 'desc',
      }),
    enabled: ready,
  })

  const stats = useQuery({
    queryKey: ['odoo-transaction-stats', integrationId],
    queryFn: () => integrationsApi.odooTransactionStats(integrationId!),
    enabled: ready,
  })

  const refresh = useMutation({
    mutationFn: () => integrationsApi.refreshOdooTransactions(integrationId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['odoo-transactions'] })
      queryClient.invalidateQueries({ queryKey: ['odoo-transaction-stats'] })
    },
  })

  useEffect(() => {
    setPage(1)
  }, [integrationId, search, txTypeFilter, startDate, endDate, sortBy])

  const response = transactions.data
  const summary = stats.data

  if (!integrationId) {
    return (
      <Card>
        <EmptyState
          icon={ArrowLeftRight}
          title="No Odoo connection selected"
          description="Connect an external Odoo ERP instance to view accounting transactions."
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
          <h2 className="text-xl font-bold text-slate-900">Odoo Accounting Transactions</h2>
          <p className="text-sm text-slate-500">
            Journal entries (account.move: entry) and bank statement lines.
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
          ['Total Transactions', summary?.total],
          ['Journal Entries', summary?.journal_entries],
          ['Bank Transactions', summary?.bank_transactions],
          ['Total Volume', summary?.total_amount ? `$${summary.total_amount}` : '—'],
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
              placeholder="Search entry number, reference or partner"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs"
            value={txTypeFilter}
            onChange={(e) => setTxTypeFilter(e.target.value)}
          >
            <option value="">All Transaction Types</option>
            <option value="journal_entry">Journal Entries (account.move)</option>
            <option value="bank_transaction">Bank Statement Lines</option>
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
            <option value="date">Date</option>
            <option value="amount">Amount</option>
          </select>
        </div>

        {transactions.isLoading ? (
          <TableSkeleton rows={8} columns={7} />
        ) : transactions.error ? (
          <div className="p-8">
            <EmptyState
              icon={ArrowLeftRight}
              title="Unable to load transactions"
              description={(transactions.error as Error).message}
              actionLabel="Retry"
              onAction={() => transactions.refetch()}
            />
          </div>
        ) : !response?.data?.length ? (
          <div className="p-8">
            <EmptyState
              icon={ArrowLeftRight}
              title="No transactions found"
              description="Synchronize the connected Odoo instance to extract journal entries."
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
                  <th className="p-4">Transaction / Entry</th>
                  <th className="p-4">Type</th>
                  <th className="p-4">Journal</th>
                  <th className="p-4">Partner</th>
                  <th className="p-4">Date</th>
                  <th className="p-4 text-right">Debit / Total</th>
                  <th className="p-4">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {response.data.map((tx: OdooTransaction) => {
                  const isExpanded = expandedId === tx.id
                  const isJournal = tx.transaction_type === 'journal_entry'
                  const displayNum = tx.entry_number || tx.number || 'Entry'
                  return (
                    <React.Fragment key={tx.id}>
                      <tr
                        className={`hover:bg-slate-50/60 cursor-pointer transition-colors ${
                          isExpanded ? 'bg-indigo-50/20' : ''
                        }`}
                        onClick={() => setExpandedId(isExpanded ? null : tx.id)}
                      >
                        <td className="p-4 text-slate-400">
                          {tx.lines?.length ? (
                            isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-indigo-600" />
                            ) : (
                              <ChevronRight className="w-4 h-4" />
                            )
                          ) : null}
                        </td>
                        <td className="p-4 font-semibold text-slate-900">
                          {displayNum}
                          <div className="text-[10px] text-slate-400 font-mono">
                            ID: {tx.entry_id} {tx.reference ? `· Ref: ${tx.reference}` : ''}
                          </div>
                        </td>
                        <td className="p-4">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold ${
                              isJournal
                                ? 'bg-indigo-50 text-indigo-700 border border-indigo-200/60'
                                : 'bg-teal-50 text-teal-700 border border-teal-200/60'
                            }`}
                          >
                            {isJournal ? 'Journal Entry' : 'Bank Statement Line'}
                          </span>
                        </td>
                        <td className="p-4 text-slate-600">
                          {tx.journal?.name || '—'}
                        </td>
                        <td className="p-4 text-slate-700">
                          {tx.partner?.name || '—'}
                        </td>
                        <td className="p-4 text-slate-600">{formatDate(tx.date)}</td>
                        <td className="p-4 text-right font-bold text-slate-900">
                          {money(tx.total_amount || tx.amount, tx.currency)}
                        </td>
                        <td className="p-4">
                          <Badge variant={tx.status === 'posted' ? 'active' : 'pending'}>
                            {tx.status === 'posted' ? 'Posted' : tx.status}
                          </Badge>
                        </td>
                      </tr>

                      {/* Journal Lines Breakdown */}
                      {isExpanded && tx.lines && tx.lines.length > 0 && (
                        <tr className="bg-slate-50/80 border-b border-indigo-100">
                          <td colSpan={8} className="p-4 pl-12">
                            <div className="rounded-lg bg-white border border-slate-200 overflow-hidden shadow-sm">
                              <div className="bg-slate-100/70 px-4 py-2 text-[11px] font-semibold text-slate-600 flex items-center gap-1.5">
                                <FileSpreadsheet className="w-3.5 h-3.5 text-indigo-600" />
                                <span>Double-Entry Move Lines ({tx.lines.length})</span>
                              </div>
                              <table className="w-full text-xs text-left">
                                <thead className="border-b border-slate-100 text-[10px] uppercase text-slate-400 bg-slate-50/40">
                                  <tr>
                                    <th className="px-4 py-2">Account / Label</th>
                                    <th className="px-4 py-2">Partner</th>
                                    <th className="px-4 py-2 text-right">Debit</th>
                                    <th className="px-4 py-2 text-right">Credit</th>
                                    <th className="px-4 py-2 text-right">Balance</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                  {tx.lines.map((line, idx) => (
                                    <tr key={line.id || idx}>
                                      <td className="px-4 py-2.5">
                                        <div className="font-medium text-slate-900">
                                          {line.account_name || 'Account'}
                                        </div>
                                        {line.name && (
                                          <div className="text-[10px] text-slate-400">{line.name}</div>
                                        )}
                                      </td>
                                      <td className="px-4 py-2.5 text-slate-600">
                                        {line.partner_name || '—'}
                                      </td>
                                      <td className="px-4 py-2.5 text-right font-mono text-slate-700">
                                        {line.debit > 0 ? money(line.debit, tx.currency) : '—'}
                                      </td>
                                      <td className="px-4 py-2.5 text-right font-mono text-slate-700">
                                        {line.credit > 0 ? money(line.credit, tx.currency) : '—'}
                                      </td>
                                      <td className="px-4 py-2.5 text-right font-semibold text-slate-900 font-mono">
                                        {money(line.balance, tx.currency)}
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
          <Pagination pagination={response?.pagination} onPageChange={setPage} isLoading={transactions.isFetching} />
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