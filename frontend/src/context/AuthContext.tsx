import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { authApi } from '@/api/auth'
import type { User, UserLoginInput, UserRegisterInput } from '@/types/auth'

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (data: UserLoginInput) => Promise<void>
  register: (data: UserRegisterInput) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('onedesk_token'))
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  const logout = useCallback(() => {
    localStorage.removeItem('onedesk_token')
    setToken(null)
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    try {
      const userData = await authApi.getMe()
      setUser(userData)
    } catch {
      logout()
    }
  }, [logout])

  useEffect(() => {
    const handleLogoutEvent = () => logout()
    window.addEventListener('onedesk-logout', handleLogoutEvent)
    return () => window.removeEventListener('onedesk-logout', handleLogoutEvent)
  }, [logout])

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('onedesk_token')
      if (storedToken) {
        try {
          const userData = await authApi.getMe()
          setUser(userData)
          setToken(storedToken)
        } catch {
          logout()
        }
      }
      setIsLoading(false)
    }

    initAuth()
  }, [logout])

  const login = async (data: UserLoginInput) => {
    const response = await authApi.login(data)
    localStorage.setItem('onedesk_token', response.access_token)
    setToken(response.access_token)
    const userData = await authApi.getMe()
    setUser(userData)
  }

  const register = async (data: UserRegisterInput) => {
    await authApi.register(data)
    // Auto-login after successful registration
    await login({ email: data.email, password: data.password })
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

