export interface User {
  id: string
  name: string
  email: string
  created_at: string
  updated_at: string
}

export interface UserRegisterInput {
  name: string
  email: string
  password: string
}

export interface UserLoginInput {
  email: string
  password: string
}

export interface AuthTokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export type AuthErrorCode = 'USER_NOT_FOUND' | 'INVALID_CREDENTIALS' | string

export interface AuthError {
  code?: AuthErrorCode
  message: string
}

