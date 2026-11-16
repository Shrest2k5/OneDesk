import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from './Button'
import type { PaginationInfo } from '@/types/crm'

interface PaginationProps {
  pagination?: PaginationInfo
  onPageChange: (newPage: number) => void
  onPerPageChange?: (newPerPage: number) => void
  isLoading?: boolean
}

export const Pagination: React.FC<PaginationProps> = ({
  pagination,
  onPageChange,
  onPerPageChange,
  isLoading = false,
}) => {
  if (!pagination) return null

  const { page, per_page, count, more_records } = pagination

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 py-3 px-4 border-t border-slate-100 bg-white">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <span>
          Showing <span className="font-medium text-slate-900">{count}</span> records on page{' '}
          <span className="font-medium text-slate-900">{page}</span>
        </span>
        {onPerPageChange && (
          <div className="flex items-center gap-1.5 ml-4 border-l border-slate-200 pl-4">
            <span>Per page:</span>
            <select
              value={per_page}
              onChange={(e) => onPerPageChange(Number(e.target.value))}
              disabled={isLoading}
              className="bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={page <= 1 || isLoading}
          onClick={() => onPageChange(page - 1)}
          leftIcon={<ChevronLeft className="w-3.5 h-3.5" />}
        >
          Previous
        </Button>
        <span className="px-3 py-1 text-xs font-semibold text-slate-700 bg-slate-100 rounded-md border border-slate-200/60">
          Page {page}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={!more_records || isLoading}
          onClick={() => onPageChange(page + 1)}
          rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
        >
          Next
        </Button>
      </div>
    </div>
  )
}

