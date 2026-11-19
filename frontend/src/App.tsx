import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/context/AuthContext'
import { IntegrationProvider } from '@/context/IntegrationContext'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppLayout } from '@/components/layout/AppLayout'

// Pages
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { DashboardPage } from '@/pages/dashboard/DashboardPage'
import { IntegrationsPage } from '@/pages/integrations/IntegrationsPage'
import { ZohoCallbackPage } from '@/pages/integrations/ZohoCallbackPage'
import { ContactsPage } from '@/pages/crm/ContactsPage'
import { BooksContactsPage } from '@/pages/books/BooksContactsPage'
import { BooksInvoicesPage } from '@/pages/books/BooksInvoicesPage'
import { BooksTransactionsPage } from '@/pages/books/BooksTransactionsPage'
import { LeadsPage } from '@/pages/crm/LeadsPage'
import { DealsPage } from '@/pages/crm/DealsPage'
import { AccountsPage } from '@/pages/crm/AccountsPage'
import { SyncCenterPage } from '@/pages/sync/SyncCenterPage'
import { ActivityPage } from '@/pages/activity/ActivityPage'
import { SettingsPage } from '@/pages/settings/SettingsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000,
    },
  },
})

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <IntegrationProvider>
          <BrowserRouter>
            <Routes>
            {/* Public Auth Routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* OAuth Callback Handshake */}
            <Route path="/integrations/zoho/callback" element={<ZohoCallbackPage />} />
            <Route path="/integrations/zoho/books/callback" element={<ZohoCallbackPage />} />

            {/* Protected SaaS Application Routes */}
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/integrations" element={<IntegrationsPage />} />
                <Route path="/crm/contacts" element={<ContactsPage />} />
                <Route path="/crm/leads" element={<LeadsPage />} />
                <Route path="/crm/deals" element={<DealsPage />} />
                <Route path="/crm/accounts" element={<AccountsPage />} />
                <Route path="/books/contacts" element={<BooksContactsPage />} />
                <Route path="/books/invoices" element={<BooksInvoicesPage />} />
                <Route path="/books/transactions" element={<BooksTransactionsPage />} />
                <Route path="/sync" element={<SyncCenterPage />} />
                <Route path="/activity" element={<ActivityPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>
            </Route>

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </IntegrationProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
