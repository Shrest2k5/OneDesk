import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  RefreshCw,
  Play,
  CheckCircle2,
  AlertCircle,
  Clock,
  Database,
  ArrowRight,
  Layers,
  ShieldCheck,
  Check,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { EmptyState } from '@/components/common/EmptyState'
import { TableSkeleton } from '@/components/common/LoadingSkeleton'
import { syncApi } from '@/api/sync'
import { useIntegrations } from '@/context/IntegrationContext'
import { formatDate, formatDuration, formatRelativeTime } from '@/lib/utils'
import type { SyncResourceType, SyncHistory } from '@/types/sync'

export const SyncCenterPage: React.FC = () => {
  const queryClient = useQueryClient()
  const { integrations, activeIntegrationId, hasActiveConnection } = useIntegrations()

  const [selectedIntegrationId, setSelectedIntegrationId] = useState<string>(
    activeIntegrationId || integrations[0]?.id || ''
  )
  const [resourceType, setResourceType] = useState<SyncResourceType>('contacts')
  const [incremental, setIncremental] = useState<boolean>(true)
  const [asyncMode, setAsyncMode] = useState<boolean>(false)
  const [lastSyncResult, setLastSyncResult] = useState<SyncHistory | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)

  // Fetch sync history for the selected integration
  const {
    data: history = [],
    isLoading: isHistoryLoading,
    isFetching: isHistoryFetching,
    refetch: refetchHistory,
  } = useQuery({
    queryKey: ['sync-history', selectedIntegrationId],
    queryFn: () => syncApi.getSyncHistory(selectedIntegrationId, 50),
    enabled: !!selectedIntegrationId,
    refetchInterval: (query) => {
      // If there are in_progress jobs, poll every 3 seconds
      const hasInProgress = query.state.data?.some((h) => h.status === 'in_progress')
      return hasInProgress ? 3000 : false
    },
  })

  // Trigger sync mutation
  const syncMutation = useMutation({
    mutationFn: () =>
      syncApi.triggerSync(selectedIntegrationId, {
        resource_type: resourceType,
        incremental,
        async_mode: asyncMode,
      }),
    onSuccess: (data) => {
      setLastSyncResult(data)
      setSyncError(null)
      queryClient.invalidateQueries({ queryKey: ['sync-history'] })
      queryClient.invalidateQueries({ queryKey: [resourceType] })
    },
    onError: (err: any) => {
      setSyncError(err.message || 'Synchronization failed.')
      setLastSyncResult(null)
    },
  })

  const handleTriggerSync = () => {
    setLastSyncResult(null)
    setSyncError(null)
    syncMutation.mutate()
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">Synchronization Center</h2>
        <p className="text-xs text-slate-500 mt-1">
          Control on-demand delta and full synchronizations between external ERP systems and OneDesk.
        </p>
      </div>

      {!hasActiveConnection ? (
        <Card className="p-8">
          <EmptyState
            icon={RefreshCw}
            title="No Active ERP System Connected"
            description="You must connect a Zoho CRM account before triggering data synchronization."
            actionLabel="Connect Zoho CRM"
            onAction={() => (window.location.href = '/integrations')}
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Sync Configuration Panel */}
          <div className="lg:col-span-1 space-y-6">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Launch Synchronization</CardTitle>
                  <CardDescription>Configure target ERP resource and sync strategy.</CardDescription>
                </div>
              </CardHeader>

              <div className="space-y-4">
                {/* Target ERP Connection */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">ERP Instance</label>
                  <select
                    value={selectedIntegrationId}
                    onChange={(e) => setSelectedIntegrationId(e.target.value)}
                    disabled={syncMutation.isPending}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    {integrations.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.connection_name} ({i.provider.toUpperCase()} - {i.status})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Resource Selector */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">ERP Resource</label>
                  <div className="grid grid-cols-2 gap-2">
                    {(['contacts', 'leads', 'deals', 'accounts'] as SyncResourceType[]).map((res) => (
                      <button
                        key={res}
                        type="button"
                        onClick={() => setResourceType(res)}
                        disabled={syncMutation.isPending}
                        className={`py-2 px-3 text-xs font-medium rounded-lg border text-left capitalize transition-all ${
                          resourceType === res
                            ? 'border-indigo-600 bg-indigo-50/70 text-indigo-700 font-semibold shadow-2xs'
                            : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        {res}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Strategy Options */}
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 space-y-3">
                  <div>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={incremental}
                        onChange={(e) => setIncremental(e.target.checked)}
                        disabled={syncMutation.isPending}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 w-3.5 h-3.5"
                      />
                      <span className="text-xs text-slate-800 font-semibold">Incremental Delta Sync</span>
                    </label>
                    <p className="text-[11px] text-slate-500 pl-5.5 mt-0.5 leading-normal">
                      Uses <span className="font-mono text-slate-600">If-Modified-Since</span> headers to pull only updated
                      or newly created records since the last successful sync.
                    </p>
                  </div>

                  <div className="pt-2 border-t border-slate-200/60">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={asyncMode}
                        onChange={(e) => setAsyncMode(e.target.checked)}
                        disabled={syncMutation.isPending}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 w-3.5 h-3.5"
                      />
                      <span className="text-xs text-slate-800 font-semibold">Asynchronous Mode (Celery)</span>
                    </label>
                    <p className="text-[11px] text-slate-500 pl-5.5 mt-0.5 leading-normal">
                      Dispatches the task to the Celery worker queue, allowing background processing without blocking the
                      request.
                    </p>
                  </div>
                </div>

                {/* Launch Button */}
                <Button
                  variant="primary"
                  size="md"
                  onClick={handleTriggerSync}
                  isLoading={syncMutation.isPending}
                  disabled={!selectedIntegrationId}
                  className="w-full"
                  leftIcon={<Play className="w-4 h-4 fill-current" />}
                >
                  {syncMutation.isPending ? 'Executing Sync...' : 'Execute Synchronization'}
                </Button>
              </div>
            </Card>

            {/* Execution Result Feedback Card */}
            {lastSyncResult && (
              <Card className="border-emerald-200 bg-emerald-50/50">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                  <div className="space-y-1 text-xs">
                    <div className="font-bold text-emerald-950">
                      {lastSyncResult.status === 'completed'
                        ? 'Sync Completed Successfully'
                        : 'Job Dispatched to Background Worker'}
                    </div>
                    <div className="text-emerald-800 text-[11px]">
                      Records processed:{' '}
                      <span className="font-bold text-emerald-900">{lastSyncResult.records_processed}</span>
                    </div>
                    <div className="text-emerald-700 text-[11px]">
                      Execution time: {formatDuration(lastSyncResult.started_at, lastSyncResult.completed_at)}
                    </div>
                    <div className="pt-2">
                      <Link
                        to={`/crm/${lastSyncResult.resource_type}`}
                        className="inline-flex items-center gap-1 font-semibold text-emerald-800 hover:text-emerald-900 hover:underline"
                      >
                        <span>View {lastSyncResult.resource_type} table</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>
                </div>
              </Card>
            )}

            {syncError && (
              <Card className="border-rose-200 bg-rose-50/50">
                <div className="flex items-start gap-3 text-xs">
                  <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-bold text-rose-950">Synchronization Failed</div>
                    <div className="text-rose-800 text-[11px] mt-0.5">{syncError}</div>
                  </div>
                </div>
              </Card>
            )}
          </div>

          {/* Right Column (2 Cols): Integration Sync History Table */}
          <div className="lg:col-span-2">
            <Card noPadding>
              <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <CardTitle>Sync Execution History</CardTitle>
                  <CardDescription>
                    Historical log of synchronization runs for the selected ERP connection.
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchHistory()}
                  isLoading={isHistoryFetching}
                  leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
                >
                  Refresh History
                </Button>
              </div>

              {isHistoryLoading ? (
                <TableSkeleton rows={6} columns={5} />
              ) : history.length === 0 ? (
                <div className="p-8">
                  <EmptyState
                    icon={Clock}
                    title="No Sync History for this Connection"
                    description="Trigger a synchronization job using the panel on the left to see audit records here."
                  />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs divide-y divide-slate-100">
                    <thead className="bg-slate-50/70 text-slate-500 font-medium">
                      <tr>
                        <th className="py-3 px-4">Resource</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Records Processed</th>
                        <th className="py-3 px-4">Duration</th>
                        <th className="py-3 px-4">Started At</th>
                        <th className="py-3 px-4">Error / Notes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                      {history.map((job) => (
                        <tr key={job.id} className="hover:bg-slate-50/60 transition-colors">
                          <td className="py-3.5 px-4 font-semibold text-slate-900 capitalize flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
                            <span>{job.resource_type}</span>
                          </td>
                          <td className="py-3.5 px-4">
                            <Badge variant={job.status}>{job.status}</Badge>
                          </td>
                          <td className="py-3.5 px-4 font-mono font-medium text-slate-900">
                            {job.records_processed}
                          </td>
                          <td className="py-3.5 px-4 text-slate-500 font-mono text-[11px]">
                            {formatDuration(job.started_at, job.completed_at)}
                          </td>
                          <td className="py-3.5 px-4 text-slate-500">{formatRelativeTime(job.started_at)}</td>
                          <td className="py-3.5 px-4 text-slate-500 max-w-xs truncate">
                            {job.error_message ? (
                              <span className="text-rose-600 font-medium" title={job.error_message}>
                                {job.error_message}
                              </span>
                            ) : (
                              <span className="text-slate-400">Clean execution</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

