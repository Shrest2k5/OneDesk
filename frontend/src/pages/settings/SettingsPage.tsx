import React from 'react'
import { User, Shield, Key, Database, RefreshCw, LogOut, CheckCircle2, Server } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { useAuth } from '@/context/AuthContext'
import { useIntegrations } from '@/context/IntegrationContext'
import { formatDate } from '@/lib/utils'

export const SettingsPage: React.FC = () => {
  const { user, logout } = useAuth()
  const { integrations, activeIntegration } = useIntegrations()

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Title */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">System Settings & Profile</h2>
        <p className="text-xs text-slate-500 mt-1">
          Review your tenant identity, integration security configuration, and active session details.
        </p>
      </div>

      {/* User Profile Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-slate-900 text-white flex items-center justify-center font-bold text-sm">
              {user?.name?.[0]?.toUpperCase() || 'U'}
            </div>
            <div>
              <CardTitle>User Profile & Tenant Identity</CardTitle>
              <CardDescription>Authenticated user credentials and tenant workspace ID.</CardDescription>
            </div>
          </div>
        </CardHeader>

        <div className="divide-y divide-slate-100 border border-slate-200/80 rounded-xl bg-slate-50/50 text-xs">
          <div className="py-3 px-4 flex justify-between">
            <span className="text-slate-500 font-medium">Full Name</span>
            <span className="font-semibold text-slate-900">{user?.name}</span>
          </div>
          <div className="py-3 px-4 flex justify-between">
            <span className="text-slate-500 font-medium">Email Address</span>
            <span className="font-mono text-slate-800">{user?.email}</span>
          </div>
          <div className="py-3 px-4 flex justify-between">
            <span className="text-slate-500 font-medium">Tenant ID (UUID)</span>
            <span className="font-mono text-[11px] text-slate-600">{user?.id}</span>
          </div>
          <div className="py-3 px-4 flex justify-between">
            <span className="text-slate-500 font-medium">Account Created</span>
            <span className="text-slate-800">{formatDate(user?.created_at)}</span>
          </div>
        </div>
      </Card>

      {/* Security & Cryptography Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-700 flex items-center justify-center">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <CardTitle>Security & Credential Protection</CardTitle>
              <CardDescription>
                Overview of cryptographic safeguards enforced by OneDesk for ERP tokens.
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <div className="space-y-3 text-xs">
          <div className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/60 flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-slate-900">Fernet AES-256 Symmetric Encryption at Rest</div>
              <div className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                OAuth access tokens and refresh tokens are encrypted before being written to PostgreSQL. Ciphertexts are
                decrypted transparently only in-memory during API calls. Plaintext credentials are never saved.
              </div>
            </div>
          </div>

          <div className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/60 flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-slate-900">OAuth State Replay Protection</div>
              <div className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                Cryptographic JWT state tokens contain single-use security nonces tracked by the server to prevent
                replay attacks during authorization redirect callbacks.
              </div>
            </div>
          </div>

          <div className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/60 flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-slate-900">Strict Multi-Tenant Isolation</div>
              <div className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                Every integration query, CRM resource retrieval, and sync operation is bound to your validated JWT user
                identity, completely preventing cross-tenant data leakage.
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Active Session & Logout */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Active Session</CardTitle>
            <CardDescription>Manage your current authenticated session.</CardDescription>
          </div>
        </CardHeader>

        <div className="flex items-center justify-between">
          <div className="text-xs text-slate-600">
            Sign out of your current browser session. You will be redirected to the sign in page.
          </div>
          <Button variant="danger" size="sm" onClick={logout} leftIcon={<LogOut className="w-3.5 h-3.5" />}>
            Sign Out
          </Button>
        </div>
      </Card>
    </div>
  )
}

