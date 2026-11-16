import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Boxes,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Users,
  Target,
  BadgeDollarSign,
  Building2,
  ArrowRight,
  Database,
  ExternalLink,
  ShieldCheck,
  Plus,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { EmptyState } from '@/components/common/EmptyState'
import { Skeleton } from '@/components/common/LoadingSkeleton'
import { useIntegrations } from '@/context/IntegrationContext'
import { syncApi } from '@/api/sync'
import { formatDate, formatDuration, formatRelativeTime } from '@/lib/utils'
import { QuickSyncModal } from '@/components/sync/QuickSyncModal'

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate()
  const { integrations, activeIntegration, activeIntegrationId, isLoading: isIntegrationsLoading } = useIntegrations()
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false)

  // Fetch recent sync history for active integration if available
  const { data: syncHistory = [], isLoading: isHistoryLoading } = useQuery({
    queryKey: ['sync-history', activeIntegrationId],
    queryFn: () => syncApi.getSyncHistory(activeIntegrationId!, 10),
    enabled: !!activeIntegrationId,
    staleTime: 15000,
  })

  const activeIntegrationsCount = integrations.filter((i) => i.status === 'active').length
  const recentSyncsCount = syncHistory.length
  const failedSyncsCount = syncHistory.filter((s) => s.status === 'failed').length

  return (
    <div className="space-y-6">
      {/* Welcome Banner / Overview */}
      <div className="bg-gradient-to-r from-slate-900 to-indigo-950 rounded-2xl p-6 sm:p-8 text-white shadow-md relative overflow-hidden">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/10 text-indigo-200 text-xs font-medium mb-3 backdrop-blur-xs">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
            <span>Fernet AES-256 Protected Integration Layer</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white mb-2">ERP Integration Ecosystem</h2>
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed mb-6">
            OneDesk connects and synchronizes your enterprise data across external ERP systems with continuous token
            lifecycle management and multi-tenant isolation.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate('/integrations')}
              leftIcon={<Plus className="w-3.5 h-3.5" />}
              className="bg-indigo-500 hover:bg-indigo-600 shadow-none border border-indigo-400/30"
            >
              Connect New ERP
            </Button>
            {activeIntegrationId && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsSyncModalOpen(true)}
                leftIcon={<RefreshCw className="w-3.5 h-3.5 text-slate-200" />}
                className="bg-white/10 hover:bg-white/20 text-white border-white/20"
              >
                Trigger Sync
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Stat Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Connected ERPs */}
        <Card noPadding className="p-4">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Connected ERPs</span>
            <Boxes className="w-4 h-4 text-indigo-600" />
          </div>
          {isIntegrationsLoading ? (
            <Skeleton className="h-8 w-16" />
          ) : (
            <div className="text-2xl font-bold text-slate-900 tracking-tight">{integrations.length}</div>
          )}
          <div className="text-[11px] text-slate-500 mt-1">
            {activeIntegrationsCount} active, {integrations.length - activeIntegrationsCount} inactive
          </div>
        </Card>

        {/* Ecosystem Health */}
        <Card noPadding className="p-4">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Connection Health</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          {isIntegrationsLoading ? (
            <Skeleton className="h-8 w-24" />
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-slate-900 tracking-tight">
                {activeIntegrationsCount > 0 ? 'Operational' : 'Idle'}
              </span>
            </div>
          )}
          <div className="text-[11px] text-slate-500 mt-1">
            {activeIntegrationsCount > 0 ? 'Zoho CRM v8 API Online' : 'No active connections'}
          </div>
        </Card>

        {/* Sync Operations */}
        <Card noPadding className="p-4">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Sync Activity</span>
            <RefreshCw className="w-4 h-4 text-sky-500" />
          </div>
          {isHistoryLoading ? (
            <Skeleton className="h-8 w-16" />
          ) : (
            <div className="text-2xl font-bold text-slate-900 tracking-tight">{recentSyncsCount}</div>
          )}
          <div className="text-[11px] text-slate-500 mt-1">
            {failedSyncsCount > 0 ? (
              <span className="text-rose-600 font-medium">{failedSyncsCount} failed operations</span>
            ) : (
              'All recent jobs completed'
            )}
          </div>
        </Card>

        {/* Supported Modules */}
        <Card noPadding className="p-4">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">CRM Modules</span>
            <Database className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 tracking-tight">4 Modules</div>
          <div className="text-[11px] text-slate-500 mt-1">Contacts, Leads, Deals, Accounts</div>
        </Card>
      </div>

      {/* Main Grid: CRM Workspace Quick Links & Recent Sync Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 Cols): Quick CRM Workspaces */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Zoho CRM Workspace Modules</CardTitle>
                <CardDescription>
                  Explore normalized CRM data retrieved on-demand from your authorized Zoho tenant.
                </CardDescription>
              </div>
              <Link to="/crm/contacts" className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1">
                <span>View all</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </CardHeader>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Contacts Card */}
              <Link
                to="/crm/contacts"
                className="group p-4 rounded-xl border border-slate-200/80 bg-slate-50/50 hover:bg-white hover:border-indigo-300 hover:shadow-xs transition-all"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                    <Users className="w-4 h-4" />
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-300 group-hover:text-indigo-600 transition-colors" />
                </div>
                <div className="text-sm font-semibold text-slate-900 group-hover:text-indigo-600">Contacts</div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Browse normalized customer and client profiles with email, phone, and company mappings.
                </p>
              </Link>

              {/* Leads Card */}
              <Link
                to="/crm/leads"
                className="group p-4 rounded-xl border border-slate-200/80 bg-slate-50/50 hover:bg-white hover:border-indigo-300 hover:shadow-xs transition-all"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="w-9 h-9 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center group-hover:bg-amber-600 group-hover:text-white transition-colors">
                    <Target className="w-4 h-4" />
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-300 group-hover:text-amber-600 transition-colors" />
                </div>
                <div className="text-sm font-semibold text-slate-900 group-hover:text-amber-600">Leads</div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Track incoming business opportunities, lead statuses, and prospective client outreach.
                </p>
              </Link>

              {/* Deals Card */}
              <Link
                to="/crm/deals"
                className="group p-4 rounded-xl border border-slate-200/80 bg-slate-50/50 hover:bg-white hover:border-indigo-300 hover:shadow-xs transition-all"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center group-hover:bg-emerald-600 group-hover:text-white transition-colors">
                    <BadgeDollarSign className="w-4 h-4" />
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-300 group-hover:text-emerald-600 transition-colors" />
                </div>
                <div className="text-sm font-semibold text-slate-900 group-hover:text-emerald-600">Deals</div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Monitor deal pipelines, revenue amounts, stages, and anticipated closing schedules.
                </p>
              </Link>

              {/* Accounts Card */}
              <Link
                to="/crm/accounts"
                className="group p-4 rounded-xl border border-slate-200/80 bg-slate-50/50 hover:bg-white hover:border-indigo-300 hover:shadow-xs transition-all"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="w-9 h-9 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center group-hover:bg-sky-600 group-hover:text-white transition-colors">
                    <Building2 className="w-4 h-4" />
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-300 group-hover:text-sky-600 transition-colors" />
                </div>
                <div className="text-sm font-semibold text-slate-900 group-hover:text-sky-600">Accounts</div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Inspect enterprise organizations, industry verticals, billing locations, and corporate profiles.
                </p>
              </Link>
            </div>
          </Card>

          {/* Connected ERP List Preview */}
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Connected ERP Instances</CardTitle>
                <CardDescription>Active multi-datacenter connections authorized under your account.</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => navigate('/integrations')}>
                Manage
              </Button>
            </CardHeader>

            {integrations.length === 0 ? (
              <EmptyState
                icon={Boxes}
                title="No ERP Systems Connected"
                description="Connect your Zoho CRM account to start retrieving contacts, leads, deals, and accounts."
                actionLabel="Connect Zoho CRM"
                onAction={() => navigate('/integrations')}
              />
            ) : (
              <div className="divide-y divide-slate-100">
                {integrations.map((item) => (
                  <div key={item.id} className="py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-700 flex items-center justify-center font-bold text-xs uppercase">
                        {item.provider.substring(0, 2)}
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-slate-900">{item.connection_name}</div>
                        <div className="text-[11px] text-slate-400">
                          Domain: {item.api_domain || 'Default DC'} &bull; Connected {formatRelativeTime(item.created_at)}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={item.status}>{item.status}</Badge>
                      <Button variant="ghost" size="sm" onClick={() => navigate('/integrations')}>
                        Details
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right Column (1 Col): Recent Sync Runs */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Recent Sync Activity</CardTitle>
                <CardDescription>Audit logs of latest synchronization runs.</CardDescription>
              </div>
              <Link to="/activity" className="text-xs font-semibold text-indigo-600 hover:text-indigo-700">
                View all
              </Link>
            </CardHeader>

            {isHistoryLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : syncHistory.length === 0 ? (
              <div className="text-center py-8">
                <RefreshCw className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <div className="text-xs font-semibold text-slate-700">No sync history yet</div>
                <p className="text-[11px] text-slate-400 mt-0.5 mb-4">Run your first data synchronization.</p>
                {activeIntegrationId && (
                  <Button variant="outline" size="sm" onClick={() => setIsSyncModalOpen(true)}>
                    Start Sync
                  </Button>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {syncHistory.slice(0, 5).map((log) => (
                  <div key={log.id} className="p-3 rounded-lg border border-slate-100 bg-slate-50/60 text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-900 capitalize">{log.resource_type}</span>
                      <Badge variant={log.status}>{log.status}</Badge>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span>{log.records_processed} records</span>
                      <span>{formatDuration(log.started_at, log.completed_at)}</span>
                    </div>
                    {log.error_message && (
                      <div className="text-[10px] text-rose-600 bg-rose-50 p-1.5 rounded truncate">
                        {log.error_message}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Quick System Architecture Card */}
          <Card className="bg-slate-900 text-white border-slate-800">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Integration Roadmap</h4>
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between p-2 rounded bg-slate-800/80">
                <span className="font-medium">Zoho CRM v8</span>
                <Badge variant="active">Active</Badge>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-slate-800/40 text-slate-400">
                <span>Odoo ERP</span>
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Coming Soon</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-slate-800/40 text-slate-400">
                <span>SAP S/4HANA</span>
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Coming Soon</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Quick Sync Modal */}
      {isSyncModalOpen && (
        <QuickSyncModal
          isOpen={isSyncModalOpen}
          onClose={() => setIsSyncModalOpen(false)}
          defaultIntegrationId={activeIntegrationId || undefined}
        />
      )}
    </div>
  )
}

