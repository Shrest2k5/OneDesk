import React from 'react'
import { cn } from '@/lib/utils'

export type BadgeVariant =
  | 'active'
  | 'completed'
  | 'in_progress'
  | 'pending'
  | 'failed'
  | 'revoked'
  | 'expired'
  | 'error'
  | 'neutral'
  | 'primary'

interface BadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  className?: string
  dot?: boolean
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  children,
  className,
  dot = true,
}) => {
  const styles: Record<BadgeVariant, { bg: string; dot: string }> = {
    active: {
      bg: 'bg-emerald-50 text-emerald-700 border-emerald-200/80',
      dot: 'bg-emerald-500',
    },
    completed: {
      bg: 'bg-emerald-50 text-emerald-700 border-emerald-200/80',
      dot: 'bg-emerald-500',
    },
    in_progress: {
      bg: 'bg-sky-50 text-sky-700 border-sky-200/80 animate-pulse',
      dot: 'bg-sky-500',
    },
    pending: {
      bg: 'bg-amber-50 text-amber-700 border-amber-200/80',
      dot: 'bg-amber-500',
    },
    failed: {
      bg: 'bg-rose-50 text-rose-700 border-rose-200/80',
      dot: 'bg-rose-500',
    },
    revoked: {
      bg: 'bg-rose-50 text-rose-700 border-rose-200/80',
      dot: 'bg-rose-500',
    },
    expired: {
      bg: 'bg-amber-50 text-amber-700 border-amber-200/80',
      dot: 'bg-amber-500',
    },
    error: {
      bg: 'bg-rose-50 text-rose-700 border-rose-200/80',
      dot: 'bg-rose-500',
    },
    neutral: {
      bg: 'bg-slate-100 text-slate-700 border-slate-200/80',
      dot: 'bg-slate-400',
    },
    primary: {
      bg: 'bg-indigo-50 text-indigo-700 border-indigo-200/80',
      dot: 'bg-indigo-500',
    },
  }

  const current = styles[variant] || styles.neutral

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border capitalize tracking-tight',
        current.bg,
        className
      )}
    >
      {dot && <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', current.dot)} />}
      <span>{children}</span>
    </span>
  )
}

