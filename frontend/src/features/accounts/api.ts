import { apiRequest } from '../../shared/api'
import { authenticatedRequest } from './auth'

export type Membership = {
  id: string
  organization: { id: string; name: string; slug: string }
  roles: Array<{ id: string; name: string }>
  is_org_admin: boolean
  scope_type: string
}

export type UserProfile = {
  id: string
  email: string
  is_active: boolean
  created_at: string
  updated_at: string
  memberships: Membership[]
}

type MessageResponse = { message: string }

export function requestRegistration(email: string) {
  return apiRequest<MessageResponse>('/api/v1/auth/register/', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export function getProfile() {
  return authenticatedRequest<UserProfile>('/api/v1/auth/me/')
}

export function requestPasswordChange() {
  return authenticatedRequest<MessageResponse>('/api/v1/auth/change-password-request/', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function requestEmailChange(newEmail: string) {
  return authenticatedRequest<MessageResponse>('/api/v1/auth/change-email-request/', {
    method: 'POST',
    body: JSON.stringify({ new_email: newEmail }),
  })
}