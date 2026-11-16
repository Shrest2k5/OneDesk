import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Eye, EyeOff, Layers, Lock, Mail, User, AlertCircle, ArrowRight, Sparkles } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { useAuth } from '@/context/AuthContext'

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { register } = useAuth()

  // Read email passed from login redirect state (Scenario A)
  const stateEmail = (location.state as { email?: string } | null)?.email || ''

  const [name, setName] = useState('')
  const [email, setEmail] = useState(stateEmail)
  const [password, setPassword] = useState('') // Password is NEVER prepopulated or transferred
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nameError, setNameError] = useState<string | null>(null)
  const [emailError, setEmailError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Sync if location state changes
  useEffect(() => {
    if (stateEmail && !email) {
      setEmail(stateEmail)
    }
  }, [stateEmail])

  const handleNameChange = (val: string) => {
    setName(val)
    if (nameError) setNameError(null)
    if (error) setError(null)
  }

  const handleEmailChange = (val: string) => {
    setEmail(val)
    if (emailError) setEmailError(null)
    if (error) setError(null)
  }

  const handlePasswordChange = (val: string) => {
    setPassword(val)
    if (passwordError) setPasswordError(null)
    if (error) setError(null)
  }

  const validateForm = (): boolean => {
    let isValid = true
    const trimmedName = name.trim()
    const trimmedEmail = email.trim()

    if (!trimmedName) {
      setNameError('Full name is required.')
      isValid = false
    }

    if (!trimmedEmail) {
      setEmailError('Work email is required.')
      isValid = false
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      if (!emailRegex.test(trimmedEmail)) {
        setEmailError('Please enter a valid work email.')
        isValid = false
      }
    }

    if (!password) {
      setPasswordError('Password is required.')
      isValid = false
    } else if (password.length < 8) {
      setPasswordError('Password must be at least 8 characters long.')
      isValid = false
    }

    return isValid
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setNameError(null)
    setEmailError(null)
    setPasswordError(null)

    if (!validateForm()) {
      return
    }

    if (isSubmitting) return

    setIsSubmitting(true)

    try {
      await register({
        name: name.trim(),
        email: email.trim(),
        password,
      })
      navigate('/', { replace: true })
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please try a different email.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex w-12 h-12 rounded-xl bg-indigo-600 items-center justify-center text-white shadow-md shadow-indigo-200 mb-4">
          <Layers className="w-6 h-6" />
        </div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Create your OneDesk Account</h2>
        <p className="text-xs text-slate-500 mt-1.5">Register a multi-tenant ERP integration workspace</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200/80 rounded-2xl sm:px-10">
          
          {/* Subtle prefill indicator when redirected from login */}
          {stateEmail && (
            <div className="mb-5 p-3 rounded-xl bg-indigo-50/70 border border-indigo-100/90 text-indigo-900 text-xs flex items-start gap-2.5">
              <Sparkles className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Email prefilled: </span>
                <span className="text-indigo-800">
                  We've carried over <span className="font-mono font-medium">{stateEmail}</span> from your sign-in attempt.
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="mb-5 p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit} noValidate>
            {/* Full Name */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Full Name</label>
              <div className="relative rounded-lg shadow-2xs">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <User className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  placeholder="Jane Doe"
                  disabled={isSubmitting}
                  className={`block w-full pl-9 pr-3 py-2 text-xs border rounded-lg focus:outline-none focus:ring-2 focus:border-transparent text-slate-900 placeholder-slate-400 transition-colors ${
                    nameError ? 'border-rose-300 focus:ring-rose-500' : 'border-slate-300 focus:ring-indigo-500'
                  }`}
                />
              </div>
              {nameError && (
                <p className="mt-1.5 text-[11px] text-rose-600 font-medium flex items-center gap-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  {nameError}
                </p>
              )}
            </div>

            {/* Email Address */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Work Email</label>
              <div className="relative rounded-lg shadow-2xs">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => handleEmailChange(e.target.value)}
                  placeholder="jane@company.com"
                  disabled={isSubmitting}
                  className={`block w-full pl-9 pr-3 py-2 text-xs border rounded-lg focus:outline-none focus:ring-2 focus:border-transparent text-slate-900 placeholder-slate-400 transition-colors ${
                    emailError ? 'border-rose-300 focus:ring-rose-500' : 'border-slate-300 focus:ring-indigo-500'
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

            {/* Password */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Password (min 8 chars)</label>
              <div className="relative rounded-lg shadow-2xs">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => handlePasswordChange(e.target.value)}
                  placeholder="At least 8 characters"
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
                Create Account
              </Button>
            </div>
          </form>

          {/* Login Link */}
          <div className="mt-6 text-center border-t border-slate-100 pt-5">
            <p className="text-xs text-slate-500">
              Already have an account?{' '}
              <Link to="/login" className="font-semibold text-indigo-600 hover:text-indigo-500 hover:underline">
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

