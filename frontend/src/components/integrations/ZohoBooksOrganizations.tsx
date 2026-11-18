import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, RefreshCw, Building2 } from 'lucide-react'
import { integrationsApi } from '@/api/integrations'
import type { Integration } from '@/types/integration'
import { Button } from '@/components/common/Button'
import { EmptyState } from '@/components/common/EmptyState'
import { TableSkeleton } from '@/components/common/LoadingSkeleton'

interface Props {
  integration: Integration
}

export const ZohoBooksOrganizations: React.FC<Props> = ({ integration }) => {
  const queryClient = useQueryClient()
  const organizationsQuery = useQuery({
    queryKey: ['books-organizations', integration.id],
    queryFn: () => integrationsApi.listBooksOrganizations(integration.id),
  })

  const refreshMutation = useMutation({
    mutationFn: () => integrationsApi.refreshBooksOrganizations(integration.id),
    onSuccess: (data) => queryClient.setQueryData(['books-organizations', integration.id], data),
  })

  const selectMutation = useMutation({
    mutationFn: (organizationId: string) => integrationsApi.selectBooksOrganization(integration.id, organizationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books-organizations', integration.id] })
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
    },
  })

  if (organizationsQuery.isLoading) return <TableSkeleton rows={4} columns={3} />
  if (organizationsQuery.isError) {
    return <p className="p-4 text-xs text-rose-600">Unable to load Zoho Books organizations. Try refreshing.</p>
  }

  const organizations = organizationsQuery.data || []
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">Organizations available to this Zoho Books connection.</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refreshMutation.mutate()}
          isLoading={refreshMutation.isPending}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Refresh
        </Button>
      </div>
      {organizations.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No Books Organizations Found"
          description="Refresh this connection to retrieve organizations accessible through Zoho Books."
          actionLabel="Refresh Organizations"
          onAction={() => refreshMutation.mutate()}
        />
      ) : (
        <div className="space-y-2">
          {organizations.map((organization) => (
            <div key={organization.external_organization_id} className="flex items-center justify-between rounded-lg border border-slate-200 p-3">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  {organization.name}
                  {organization.selected && <CheckCircle2 className="h-4 w-4 text-emerald-600" />}
                </div>
                <div className="mt-1 text-[11px] text-slate-500">
                  {organization.currency_code || 'Currency unavailable'}{organization.currency_symbol ? ` (${organization.currency_symbol})` : ''}
                  {' · '}{organization.time_zone || 'Time zone unavailable'}
                </div>
              </div>
              <Button
                variant={organization.selected ? 'outline' : 'primary'}
                size="sm"
                disabled={organization.selected || !organization.is_org_active}
                isLoading={selectMutation.isPending && selectMutation.variables === organization.external_organization_id}
                onClick={() => selectMutation.mutate(organization.external_organization_id)}
              >
                {organization.selected ? 'Selected' : 'Select'}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
