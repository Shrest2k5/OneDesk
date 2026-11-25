import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateString?: string | null): string {
  if (!dateString) return '—'
  try {
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return dateString
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  } catch {
    return dateString
  }
}

export function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return '—'
  try {
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return dateString
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSecs = Math.floor(diffMs / 1000)
    const diffMins = Math.floor(diffSecs / 60)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffSecs < 60) return 'just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return formatDate(dateString)
  } catch {
    return dateString
  }
}

export function formatCurrency(amount?: number | null, currency: string = 'USD'): string {
  if (amount === null || amount === undefined) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function formatDuration(startedAt?: string | null, completedAt?: string | null): string {
  if (!startedAt) return '—'
  if (!completedAt) return 'In progress...'
  try {
    const start = new Date(startedAt).getTime()
    const end = new Date(completedAt).getTime()
    const diffMs = Math.max(0, end - start)
    const secs = (diffMs / 1000).toFixed(1)
    if (diffMs < 1000) return `${diffMs}ms`
    if (diffMs < 60000) return `${secs}s`
    const mins = Math.floor(diffMs / 60000)
    const remSecs = Math.round((diffMs % 60000) / 1000)
    return `${mins}m ${remSecs}s`
  } catch {
    return '—'
  }
}

