import React, { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Database, Plus, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { useIntegrations } from '@/context/IntegrationContext'
import { QuickSyncModal } from '@/components/sync/QuickSyncModal'

export const Header: React.FC = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const { integrations, activeIntegration, activeIntegrationId, setActiveIntegrationId, hasActiveConnection } =
    useIntegrations()
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false)

  // Map pathname to friendly header title
  const getPageTitle = (path: string) => {
    if (path === '/') return 'Dashboard Overview'
    if (path.startsWith('/integrations')) return 'Integration Management'
    if (path === '/crm/contacts') return 'CRM Contacts'
    if (path === '/crm/leads') return 'CRM Leads'
    if (path === '/crm/deals') return 'CRM Deals Pipeline'
    if (path === '/crm/accounts') return 'CRM Accounts & Companies'
    if (path === '/sync') return 'Synchronization Center'
    if (path === '/activity') return 'Activity & Sync History'
    if (path === '/settings') return 'Settings & Profile'
    return 'OneDesk Platform'
  }

  return (
    <header className="h-16 border-b border-slate-200/80 bg-white/95 backdrop-blur-xs px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Route Title & Breadcrumb */}
      <div className="flex items-center gap-3">
        <h1 className="text-base font-semibold text-slate-900 tracking-tight m-0">
          {getPageTitle(location.pathname)}
        </h1>
      </div>

      {/* Right controls: Active Integration Selector + Actions */}
      <div className="flex items-center gap-3">
        {/* Active Integration Scope Dropdown */}
        {integrations.length > 0 ? (
          <div className="flex items-center gap-2 bg-slate-50 border border-slate-200/80 rounded-lg px-2.5 py-1.5 shadow-2xs">
            <Database className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
            <select
              value={activeIntegrationId || ''}
              onChange={(e) => setActiveIntegrationId(e.target.value || null)}
              className="bg-transparent text-xs font-medium text-slate-700 focus:outline-none cursor-pointer pr-1"
            >
              {integrations.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.connection_name} ({item.provider.toUpperCase()} - {item.status})
                </option>
              ))}
            </select>
            {activeIntegration?.status === 'active' ? (
              <span title="Active Connection" className="flex items-center">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
              </span>
            ) : (
              <span title={activeIntegration?.status} className="flex items-center">
                <AlertCircle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
              </span>
            )}
          </div>
        ) : (
          <Badge variant="neutral" dot={false}>
            No ERP Connected
          </Badge>
        )}

        {/* Quick Sync Button */}
        {hasActiveConnection && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsSyncModalOpen(true)}
            leftIcon={<RefreshCw className="w-3.5 h-3.5 text-indigo-600" />}
          >
            Sync Data
          </Button>
        )}

        {/* Connect ERP Quick Action */}
        <Button
          variant="primary"
          size="sm"
          onClick={() => navigate('/integrations')}
          leftIcon={<Plus className="w-3.5 h-3.5" />}
        >
          Connect ERP
        </Button>
      </div>

      {/* Quick Sync Modal */}
      {isSyncModalOpen && (
        <QuickSyncModal
          isOpen={isSyncModalOpen}
          onClose={() => setIsSyncModalOpen(false)}
          defaultIntegrationId={activeIntegrationId || undefined}
        />
      )}
    </header>
  )
}
