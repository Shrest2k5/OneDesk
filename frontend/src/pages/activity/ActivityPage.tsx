import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { History, RefreshCw, Filter, Search, CheckCircle2, AlertCircle, Clock, Calendar, Database } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { TableSkeleton } from '@/components/common/LoadingSkeleton'
import { EmptyState } from '@/components/common/EmptyState'
import { Drawer } from '@/components/common/Drawer'
import { syncApi } from '@/api/sync'
import { useIntegrations } from '@/context/IntegrationContext'
import { formatDate, formatDuration, formatRelativeTime } from '@/lib/utils'
import type { SyncHistory, SyncStatus } from '@/types/sync'

export const ActivityPage: React.FC = () => {
  const { integrations, activeIntegrationId, hasActiveConnection } = useIntegrations()

  const [selectedIntegrationId, setSelectedIntegrationId] = useState<string>(
    activeIntegrationId || integrations[0]?.id || ''
  )
  const [filterResource, setFilterResource] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedJob, setSelectedJob] = useState<SyncHistory | null>(null)

  const {
    data: history = [],
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['sync-history', selectedIntegrationId],
    queryFn: () => syncApi.getSyncHistory(selectedIntegrationId, 100),
    enabled: !!selectedIntegrationId,
    staleTime: 15000,
  })

  // Filtered jobs
  const filteredJobs = history.filter((job) => {
    if (filterResource !== 'all' && job.resource_type !== filterResource) return false
    if (filterStatus !== 'all' && job.status !== filterStatus) return false
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      const matchesResource = job.resource_type.toLowerCase().includes(q)
      const matchesError = job.error_message && job.error_message.toLowerCase().includes(q)
      if (!matchesResource && !matchesError) return false
    }
    return true
  })

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Integration Activity & Sync Logs</h2>
          <p className="text-xs text-slate-500 mt-1">
            Real-time audit log of synchronization runs, record counts, and failure diagnostics.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          isLoading={isFetching}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Refresh Logs
        </Button>
      </div>

      <Card noPadding>
        {/* Filters Toolbar */}
        <div className="p-4 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3 bg-white">
          <div className="flex flex-wrap items-center gap-3 flex-1">
            {/* Search */}
            <div className="relative w-full sm:w-64">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by resource or error..."
                className="w-full bg-slate-50 border border-slate-200/80 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Target Integration Filter */}
            {integrations.length > 1 && (
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-slate-500 font-medium">ERP:</span>
                <select
                  value={selectedIntegrationId}
                  onChange={(e) => setSelectedIntegrationId(e.target.value)}
                  className="bg-slate-50 border border-slate-200/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {integrations.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.connection_name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Resource Filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-500 font-medium">Module:</span>
              <select
                value={filterResource}
                onChange={(e) => setFilterResource(e.target.value)}
                className="bg-slate-50 border border-slate-200/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 capitalize"
              >
                <option value="all">All Modules</option>
                <option value="contacts">Contacts</option>
                <option value="leads">Leads</option>
                <option value="deals">Deals</option>
                <option value="accounts">Accounts</option>
              </select>
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-500 font-medium">Status:</span>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="bg-slate-50 border border-slate-200/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 capitalize"
              >
                <option value="all">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
                <option value="in_progress">In Progress</option>
              </select>
            </div>
          </div>

          <div className="text-xs text-slate-500 font-medium">
            <span>{filteredJobs.length} audit entries</span>
          </div>
        </div>

        {/* Content Table / Skeletons / Empty */}
        {!hasActiveConnection ? (
          <div className="p-8">
            <EmptyState
              icon={History}
              title="No ERP Systems Connected"
              description="Connect an ERP system to generate and inspect synchronization audit logs."
              actionLabel="Go to Integrations"
              onAction={() => (window.location.href = '/integrations')}
            />
          </div>
        ) : isLoading ? (
          <TableSkeleton rows={8} columns={6} />
        ) : filteredJobs.length === 0 ? (
          <div className="p-8">
            <EmptyState
              icon={History}
              title="No Audit Records Found"
              description={
                searchQuery || filterResource !== 'all' || filterStatus !== 'all'
                  ? 'No synchronization history matches your active filters.'
                  : 'No synchronizations have been performed yet.'
              }
              actionLabel={
                searchQuery || filterResource !== 'all' || filterStatus !== 'all' ? 'Reset Filters' : 'Go to Sync Center'
              }
              onAction={
                searchQuery || filterResource !== 'all' || filterStatus !== 'all'
                  ? () => {
                      setFilterResource('all')
                      setFilterStatus('all')
                      setSearchQuery('')
                    }
                  : () => (window.location.href = '/sync')
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs divide-y divide-slate-100">
              <thead className="bg-slate-50/70 text-slate-500 font-medium">
                <tr>
                  <th className="py-3 px-4">Job ID</th>
                  <th className="py-3 px-4">Resource</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Records Processed</th>
                  <th className="py-3 px-4">Duration</th>
                  <th className="py-3 px-4">Execution Time</th>
                  <th className="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredJobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => setSelectedJob(job)}
                    className="hover:bg-slate-50/70 cursor-pointer transition-colors group"
                  >
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-500">
                      {job.id.substring(0, 8)}...
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900 capitalize">
                      {job.resource_type}
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant={job.status}>{job.status}</Badge>
                    </td>
                    <td className="py-3 px-4 font-mono font-medium text-slate-900">
                      {job.records_processed}
                    </td>
                    <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                      {formatDuration(job.started_at, job.completed_at)}
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      {formatRelativeTime(job.started_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Button variant="ghost" size="sm" className="text-indigo-600 group-hover:text-indigo-700">
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Detail Drawer */}
      {selectedJob && (
        <Drawer
          isOpen={!!selectedJob}
          onClose={() => setSelectedJob(null)}
          title={`Sync Job Details: ${selectedJob.resource_type.toUpperCase()}`}
          subtitle={`Audit ID: ${selectedJob.id}`}
        >
          <div className="space-y-6 pt-2 text-xs">
            <div className="divide-y divide-slate-100 border border-slate-200/80 rounded-xl bg-slate-50/50">
              <div className="py-3 px-4 flex justify-between items-center">
                <span className="text-slate-500 font-medium">Job Status</span>
                <Badge variant={selectedJob.status}>{selectedJob.status}</Badge>
              </div>
              <div className="py-3 px-4 flex justify-between">
                <span className="text-slate-500 font-medium">Resource Synchronized</span>
                <span className="font-semibold text-slate-900 capitalize">{selectedJob.resource_type}</span>
              </div>
              <div className="py-3 px-4 flex justify-between">
                <span className="text-slate-500 font-medium">Records Processed</span>
                <span className="font-mono font-bold text-slate-900">{selectedJob.records_processed}</span>
              </div>
              <div className="py-3 px-4 flex justify-between">
                <span className="text-slate-500 font-medium">Duration</span>
                <span className="font-mono text-slate-800">
                  {formatDuration(selectedJob.started_at, selectedJob.completed_at)}
                </span>
              </div>
              <div className="py-3 px-4 flex justify-between">
                <span className="text-slate-500 font-medium">Started At</span>
                <span className="text-slate-800">{formatDate(selectedJob.started_at)}</span>
              </div>
              <div className="py-3 px-4 flex justify-between">
                <span className="text-slate-500 font-medium">Completed At</span>
                <span className="text-slate-800">{formatDate(selectedJob.completed_at)}</span>
              </div>
            </div>

            {selectedJob.error_message && (
              <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 space-y-1.5">
                <div className="font-semibold text-xs flex items-center gap-1.5 text-rose-800">
                  <AlertCircle className="w-4 h-4 text-rose-600" />
                  <span>Captured Error Diagnostic</span>
                </div>
                <pre className="text-[11px] font-mono text-rose-700 whitespace-pre-wrap bg-white/60 p-2.5 rounded border border-rose-200/60 overflow-x-auto">
                  {selectedJob.error_message}
                </pre>
              </div>
            )}
          </div>
        </Drawer>
      )}
    </div>
  )
}

