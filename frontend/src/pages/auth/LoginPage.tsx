import React, { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Eye, EyeOff, Layers, Lock, Mail, AlertCircle, ArrowRight, UserPlus } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { useAuth } from '@/context/AuthContext'
import type { ApiError } from '@/api/client'

export const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()

  // Form states
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Validation & Error states
  const [emailError, setEmailError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)
  const [isUserNotFound, setIsUserNotFound] = useState(false)

  const from = location.state?.from?.pathname || '/'

  // Reset errors when user edits input
  const handleEmailChange = (val: string) => {
    setEmail(val)
    if (emailError) setEmailError(null)
    if (authError) setAuthError(null)
    if (isUserNotFound) setIsUserNotFound(false)
  }

  const handlePasswordChange = (val: string) => {
    setPassword(val)
    if (passwordError) setPasswordError(null)
    if (authError) setAuthError(null)
  }

  // Validate fields before making network request
  const validateForm = (): boolean => {
    let isValid = true
    const trimmedEmail = email.trim()

    if (!trimmedEmail) {
      setEmailError('Email address is required.')
      isValid = false
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      if (!emailRegex.test(trimmedEmail)) {
        setEmailError('Please enter a valid email address.')
        isValid = false
      }
    }

    if (!password) {
      setPasswordError('Password is required.')
      isValid = false
    }

    return isValid
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Clear stale errors
    setEmailError(null)
    setPasswordError(null)
    setAuthError(null)
    setIsUserNotFound(false)

    // Scenario D: Validate input and prevent unnecessary API requests
    if (!validateForm()) {
      return
    }

    // Prevent duplicate submission while loading
    if (isSubmitting) return

    setIsSubmitting(true)

    try {
      // Scenario C: Authenticate normally and redirect
      await login({ email: email.trim(), password })
      navigate(from, { replace: true })
    } catch (err: any) {
      const apiErr = err as ApiError
      const errorCode = apiErr.code || apiErr.raw?.code || apiErr.raw?.detail?.code

      // Scenario A: Email does not exist (USER_NOT_FOUND)
      if (errorCode === 'USER_NOT_FOUND') {
        setIsUserNotFound(true)
      } else {
        // Scenario B: Email exists but password is incorrect or general error
        setIsUserNotFound(false)
        setAuthError(apiErr.message || 'Incorrect email or password. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleGoToRegister = () => {
    navigate('/register', {
      state: { email: email.trim() },
    })
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        {/* Brand Icon */}
        <div className="inline-flex w-12 h-12 rounded-xl bg-indigo-600 items-center justify-center text-white shadow-md shadow-indigo-200 mb-4">
          <Layers className="w-6 h-6" />
        </div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Sign in to OneDesk</h2>
        <p className="text-xs text-slate-500 mt-1.5">Unified ERP Integration & Management Platform</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200/80 rounded-2xl sm:px-10">
          
          {/* Scenario A: User Not Found Prominent Signup Card */}
          {isUserNotFound && (
            <div className="mb-5 p-4 rounded-xl bg-amber-50/90 border border-amber-200/90 text-slate-800 text-xs">
              <div className="flex items-start gap-3">
                <div className="p-1.5 bg-amber-100 rounded-lg text-amber-700 shrink-0 mt-0.5">
                  <UserPlus className="w-4 h-4" />
                </div>
                <div className="flex-1">
                  <h4 className="font-semibold text-slate-900 mb-1">No account found</h4>
                  <p className="text-slate-600 leading-relaxed mb-3">
                    No account found with this email address. Please create an account to continue.
                  </p>
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    onClick={handleGoToRegister}
                    rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                    className="shadow-sm"
                  >
                    Create Account
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Scenario B: Generic Authentication Error Banner */}
          {authError && !isUserNotFound && (
            <div className="mb-5 p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Authentication failed: </span>
                <span>{authError}</span>
              </div>
            </div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit} noValidate>
            {/* Email Field */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Email address</label>
              <div className="relative rounded-lg shadow-2xs">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => handleEmailChange(e.target.value)}
                  placeholder="name@company.com"
                  disabled={isSubmitting}
                  className={`block w-full pl-9 pr-3 py-2 text-xs border rounded-lg focus:outline-none focus:ring-2 focus:border-transparent text-slate-900 placeholder-slate-400 transition-colors ${
                    emailError
                      ? 'border-rose-300 focus:ring-rose-500'
                      : isUserNotFound
                      ? 'border-amber-300 focus:ring-amber-500'
                      : 'border-slate-300 focus:ring-indigo-500'
                  }`}
                />
              </div>
              {emailError && (
                <p className="mt-1.5 text-[11px] text-rose-600 font-medium flex items-center gap-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  {emailError}
                </p>
              )}
            </div>

            {/* Password Field */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Password</label>
              <div className="relative rounded-lg shadow-2xs">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => handlePasswordChange(e.target.value)}
                  placeholder="••••••••"
                  disabled={isSubmitting}
                  className={`block w-full pl-9 pr-10 py-2 text-xs border rounded-lg focus:outline-none focus:ring-2 focus:border-transparent text-slate-900 placeholder-slate-400 transition-colors ${
                    passwordError ? 'border-rose-300 focus:ring-rose-500' : 'border-slate-300 focus:ring-indigo-500'
                  }`}
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {passwordError && (
                <p className="mt-1.5 text-[11px] text-rose-600 font-medium flex items-center gap-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  {passwordError}
                </p>
              )}
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={isSubmitting}
                disabled={isSubmitting}
                className="w-full"
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Sign In
              </Button>
            </div>
          </form>

          {/* Registration Link */}
          <div className="mt-6 text-center border-t border-slate-100 pt-5">
            <p className="text-xs text-slate-500">
              Don't have an account?{' '}
              <Link
                to="/register"
                state={{ email: email.trim() || undefined }}
                className="font-semibold text-indigo-600 hover:text-indigo-500 hover:underline"
              >
                Register tenant
              </Link>
            </p>
          </div>
        </div>

        {/* Security Footer */}
        <div className="mt-6 text-center text-[11px] text-slate-400">
          Protected by Fernet AES-256 encryption at rest & multi-tenant isolation.
        </div>
      </div>
    </div>
  )
}

