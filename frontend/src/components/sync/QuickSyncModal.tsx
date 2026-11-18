import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, CheckCircle2, AlertCircle, ArrowRight } from 'lucide-react'
import { Modal } from '@/components/common/Modal'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { syncApi } from '@/api/sync'
import { useIntegrations } from '@/context/IntegrationContext'
import type { SyncResourceType, SyncHistory } from '@/types/sync'

interface QuickSyncModalProps {
  isOpen: boolean
  onClose: () => void
  defaultIntegrationId?: string
  defaultResourceType?: SyncResourceType
}

export const QuickSyncModal: React.FC<QuickSyncModalProps> = ({
  isOpen,
  onClose,
  defaultIntegrationId,
  defaultResourceType = 'contacts',
}) => {
  const queryClient = useQueryClient()
  const { integrations, activeIntegrationId } = useIntegrations()

  const [selectedIntegrationId, setSelectedIntegrationId] = useState<string>(
    defaultIntegrationId || activeIntegrationId || integrations[0]?.id || ''
  )
  const [resourceType, setResourceType] = useState<SyncResourceType>(defaultResourceType)
  const [incremental, setIncremental] = useState<boolean>(true)
  const [asyncMode, setAsyncMode] = useState<boolean>(false)
  const [lastResult, setLastResult] = useState<SyncHistory | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const syncMutation = useMutation({
    mutationFn: () =>
      syncApi.triggerSync(selectedIntegrationId, {
        resource_type: resourceType,
        incremental,
        async_mode: asyncMode,
      }),
    onSuccess: (data) => {
      setLastResult(data)
      setErrorMessage(null)
      // Invalidate relevant caches
      queryClient.invalidateQueries({ queryKey: ['sync-history'] })
      queryClient.invalidateQueries({ queryKey: [resourceType] })
    },
    onError: (err: any) => {
      setErrorMessage(err.message || 'Synchronization failed.')
      setLastResult(null)
    },
  })

  const handleStartSync = () => {
    setLastResult(null)
    setErrorMessage(null)
    syncMutation.mutate()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Synchronize ERP Data"
      description="Pull the latest records from your connected ERP into OneDesk."
      maxWidth="md"
    >
      <div className="space-y-4 pt-1">
        {/* Integration Selection */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">Connected ERP Instance</label>
          <select
            value={selectedIntegrationId}
            onChange={(e) => setSelectedIntegrationId(e.target.value)}
            disabled={syncMutation.isPending}
            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {integrations.map((i) => (
              <option key={i.id} value={i.id}>
                {i.connection_name} ({i.provider.toUpperCase()} {i.product.toUpperCase()} - {i.status})
              </option>
            ))}
          </select>
        </div>

        {/* Resource Type */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">Resource Module</label>
          <div className="grid grid-cols-2 gap-2">
            {(['contacts', 'leads', 'deals', 'accounts'] as SyncResourceType[]).map((res) => (
              <button
                key={res}
                type="button"
                onClick={() => setResourceType(res)}
                disabled={syncMutation.isPending}
                className={`py-2 px-3 text-xs font-medium rounded-lg border text-left capitalize transition-all ${
                  resourceType === res
                    ? 'border-indigo-600 bg-indigo-50/60 text-indigo-700 font-semibold shadow-2xs'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                {res}
              </button>
            ))}
          </div>
        </div>

        {/* Sync Strategy Options */}
        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80 space-y-2.5">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={incremental}
              onChange={(e) => setIncremental(e.target.checked)}
              disabled={syncMutation.isPending}
              className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 w-3.5 h-3.5"
            />
            <span className="text-xs text-slate-700 font-medium">Incremental Delta Sync</span>
          </label>
          <p className="text-[11px] text-slate-500 pl-5 leading-normal">
            {incremental
              ? 'Pulls only records created or modified since the last completed sync timestamp.'
              : 'Pulls all available records across the entire module from the ERP.'}
          </p>

          <div className="border-t border-slate-200/60 pt-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={asyncMode}
                onChange={(e) => setAsyncMode(e.target.checked)}
                disabled={syncMutation.isPending}
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 w-3.5 h-3.5"
              />
              <span className="text-xs text-slate-700 font-medium">Run in Background (Celery Async Worker)</span>
            </label>
          </div>
        </div>

        {/* Results Banner */}
        {lastResult && (
          <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold">
                {lastResult.status === 'completed'
                  ? 'Synchronization Complete'
                  : 'Sync Dispatched to Background Worker'}
              </div>
              <div className="text-[11px] text-emerald-700 mt-0.5">
                Processed <span className="font-bold">{lastResult.records_processed}</span> {resourceType} records.
              </div>
            </div>
          </div>
        )}

        {/* Error Banner */}
        {errorMessage && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold">Synchronization Error</div>
              <div className="text-[11px] text-rose-700 mt-0.5">{errorMessage}</div>
            </div>
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
          <Button variant="outline" size="sm" onClick={onClose} disabled={syncMutation.isPending}>
            {lastResult ? 'Close' : 'Cancel'}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleStartSync}
            isLoading={syncMutation.isPending}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            {syncMutation.isPending ? 'Syncing...' : 'Start Sync'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

