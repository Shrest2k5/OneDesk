import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Boxes,
  Users,
  Target,
  BadgeDollarSign,
  Building2,
  RefreshCw,
  History,
  Settings,
  LogOut,
  Layers,
  WalletCards,
  ChevronRight,
  FileText,
  Receipt,
  ArrowLeftRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'

interface NavItem {
  name: string
  to: string
  icon: React.ElementType
}

const coreNav: NavItem[] = [
  { name: 'Dashboard', to: '/', icon: LayoutDashboard },
  { name: 'Integrations', to: '/integrations', icon: Boxes },
]

const crmNav: NavItem[] = [
  { name: 'Contacts', to: '/crm/contacts', icon: Users },
  { name: 'Leads', to: '/crm/leads', icon: Target },
  { name: 'Deals', to: '/crm/deals', icon: BadgeDollarSign },
  { name: 'Accounts', to: '/crm/accounts', icon: Building2 },
]

const booksNav: NavItem[] = [{ name: 'Contacts', to: '/books/contacts', icon: WalletCards }, { name: 'Sales Invoices', to: '/books/invoices', icon: BadgeDollarSign }, { name: 'Purchases', to: '/books/purchases', icon: FileText }, { name: 'Financial Transactions', to: '/books/transactions', icon: WalletCards }]
const odooNav: NavItem[] = [
  { name: 'Partners', to: '/odoo/contacts', icon: Users },
  { name: 'Customer Invoices', to: '/odoo/invoices', icon: BadgeDollarSign },
  { name: 'Vendor Bills', to: '/odoo/bills', icon: FileText },
  { name: 'Credit Notes', to: '/odoo/credit-notes', icon: Receipt },
  { name: 'Payments', to: '/odoo/payments', icon: WalletCards },
  { name: 'Transactions', to: '/odoo/transactions', icon: ArrowLeftRight },
]

const opsNav: NavItem[] = [
  { name: 'Sync Center', to: '/sync', icon: RefreshCw },
  { name: 'Activity History', to: '/activity', icon: History },
]

export const Sidebar: React.FC = () => {
  const { user, logout } = useAuth()

  return (
    <aside className="w-64 border-r border-slate-200/80 bg-white flex flex-col shrink-0 h-screen sticky top-0 select-none">
      {/* Brand Header */}
      <div className="h-16 px-5 border-b border-slate-100 flex items-center justify-between">
        <NavLink to="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-sm shadow-indigo-300 group-hover:bg-indigo-700 transition-colors">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-sm tracking-tight text-slate-900 leading-none">OneDesk</div>
            <div className="text-[10px] text-slate-400 font-medium tracking-wider uppercase mt-1">Unified ERP</div>
          </div>
        </NavLink>
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/60">
          v0.1.0
        </span>
      </div>

      {/* Navigation Sections */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {/* Core Nav */}
        <div>
          <div className="px-2.5 text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-2">Platform</div>
          <nav className="space-y-0.5">
            {coreNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium transition-colors group',
                    isActive
                      ? 'bg-indigo-50/70 text-indigo-700 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  )
                }
              >
                <div className="flex items-center gap-2.5">
                  <item.icon className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
                  <span>{item.name}</span>
                </div>
              </NavLink>
            ))}
          </nav>
        </div>

        <div>
          <div className="px-2.5 text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-2 flex items-center justify-between"><span>Odoo Workspace</span><span className="text-[9px] bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded font-mono font-medium">JSON-2</span></div>
          <nav className="space-y-0.5">
            {odooNav.map((item) => <NavLink key={item.to} to={item.to} className={({ isActive }) => cn('flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-medium transition-colors', isActive ? 'bg-indigo-50/70 text-indigo-700 font-semibold' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50')}><item.icon className="w-4 h-4 text-slate-400" /><span>{item.name}</span></NavLink>)}
          </nav>
        </div>

        {/* CRM Workspace */}
        <div>
          <div className="px-2.5 text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-2 flex items-center justify-between">
            <span>CRM Workspace</span>
            <span className="text-[9px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-mono font-medium">Zoho</span>
          </div>
          <nav className="space-y-0.5">
            {crmNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium transition-colors group',
                    isActive
                      ? 'bg-indigo-50/70 text-indigo-700 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  )
                }
              >
                <div className="flex items-center gap-2.5">
                  <item.icon className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
                  <span>{item.name}</span>
                </div>
                <ChevronRight className="w-3 h-3 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity" />
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Sync & Operations */}
        <div>
          <div className="px-2.5 text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-2 flex items-center justify-between">
            <span>Books Workspace</span><span className="text-[9px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-mono font-medium">Zoho</span>
          </div>
          <nav className="space-y-0.5">
            {booksNav.map((item) => <NavLink key={item.to} to={item.to} className={({ isActive }) => cn('flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-medium transition-colors', isActive ? 'bg-indigo-50/70 text-indigo-700 font-semibold' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50')}><item.icon className="w-4 h-4 text-slate-400" /><span>{item.name}</span></NavLink>)}
          </nav>
        </div>

        {/* Sync & Operations */}
        <div>
          <div className="px-2.5 text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-2">Operations</div>
          <nav className="space-y-0.5">
            {opsNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium transition-colors group',
                    isActive
                      ? 'bg-indigo-50/70 text-indigo-700 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  )
                }
              >
                <div className="flex items-center gap-2.5">
                  <item.icon className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
                  <span>{item.name}</span>
                </div>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* System Settings */}
        <div>
          <div className="px-2.5 text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-2">System</div>
          <nav className="space-y-0.5">
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                cn(
                  'flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium transition-colors group',
                  isActive
                    ? 'bg-indigo-50/70 text-indigo-700 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                )
              }
            >
              <div className="flex items-center gap-2.5">
                <Settings className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
                <span>Settings & Profile</span>
              </div>
            </NavLink>
          </nav>
        </div>
      </div>

      {/* User Footer */}
      <div className="p-3 border-t border-slate-100 bg-slate-50/40">
        <div className="flex items-center justify-between gap-2 p-2 rounded-lg bg-white border border-slate-200/60 shadow-2xs">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center text-xs font-bold shrink-0">
              {user?.name?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-slate-900 truncate">{user?.name || 'User'}</div>
              <div className="text-[11px] text-slate-400 truncate">{user?.email || 'user@onedesk.io'}</div>
            </div>
          </div>
          <button
            onClick={logout}
            title="Sign out"
            className="p-1.5 text-slate-400 hover:text-rose-600 rounded-md hover:bg-rose-50 transition-colors shrink-0"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}

